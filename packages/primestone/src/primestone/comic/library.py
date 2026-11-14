"""Comic Library : import par lots, validation, rendu des pages, rapport de lot.

Pipeline (une étape durable par document puis par page, voir ADR-0004) :

    import (synchrone : empreinte SHA-256, stockage, déduplication)
      → library.validate   (format, intégrité, nombre de pages, pages attendues)
      → library.render_page (une par page)   (WebP, profil de rendu versionné)
      → document COMPLETE uniquement si TOUTES les pages sont rendues

Reprise après panne : stockage adressé par contenu, étapes idempotentes
(clés `library.validate:<sha>` et `library.render:<sha>:p<n>:<profil>`), pages uniques
par (document, numéro), verrou sur le document lors de la mise à jour de son statut.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from primestone.comic.formats import (
    DocumentFormat,
    Limits,
    RejectedDocumentError,
    detect_file_format,
    inspect_document,
    render_page,
)
from primestone.jobs import PostgresJobQueue
from primestone.provenance import missing_pages
from primestone.storage import ObjectStore

VALIDATE_STEP = "library.validate"
RENDER_STEP = "library.render_page"
IMPORT_RUN_KIND = "library.import"


class ImportOutcome(StrEnum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    VALIDATED = "VALIDATED"
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"  # pages manquantes par rapport au nombre attendu
    REJECTED = "REJECTED"  # fichier invalide
    FAILED = "FAILED"  # au moins une page illisible


@dataclass(frozen=True)
class ImportSource:
    """Fichier à importer, déjà présent sur le disque local (téléversement ou dossier)."""

    path: Path
    filename: str
    title: str | None = None
    series_title: str | None = None
    issue_number: str | None = None
    language: str | None = None
    expected_page_count: int | None = None


@dataclass(frozen=True)
class ImportItemResult:
    filename: str
    outcome: ImportOutcome
    document_id: UUID | None
    error: str | None = None


@dataclass(frozen=True)
class ImportResult:
    run_id: UUID
    items: list[ImportItemResult]


@dataclass(frozen=True)
class RenderProfile:
    max_dimension: int = 2400
    webp_quality: int = 85

    @property
    def name(self) -> str:
        return f"webp-d{self.max_dimension}-q{self.webp_quality}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def original_key(sha: str, fmt: DocumentFormat) -> str:
    return f"originals/{sha[:2]}/{sha}.{fmt.value.lower()}"


def render_key(sha: str, profile: RenderProfile, page_number: int) -> str:
    return f"renders/{sha[:2]}/{sha}/{profile.name}/{page_number:04d}.webp"


class LibraryService:
    def __init__(
        self,
        engine: Engine,
        store: ObjectStore,
        queue: PostgresJobQueue,
        *,
        limits: Limits | None = None,
        profile: RenderProfile | None = None,
    ) -> None:
        self._engine = engine
        self._store = store
        self._queue = queue
        self.limits = limits or Limits()
        self.profile = profile or RenderProfile()

    # --- Import (synchrone) ---------------------------------------------------------------

    def start_import(
        self, sources: Sequence[ImportSource], *, label: str | None = None
    ) -> ImportResult:
        run_id = self._queue.create_run(
            IMPORT_RUN_KIND, {"files": len(sources), "label": label, "profile": self.profile.name}
        )
        items = [self._import_one(run_id, source) for source in sources]
        self._queue.refresh_run(run_id)  # lot sans nouvelle étape : terminé immédiatement
        return ImportResult(run_id=run_id, items=items)

    def _import_one(self, run_id: UUID, source: ImportSource) -> ImportItemResult:
        try:
            size = source.path.stat().st_size
            if size == 0:
                raise RejectedDocumentError("fichier vide")
            if size > self.limits.max_file_bytes:
                raise RejectedDocumentError(f"fichier trop volumineux ({size} octets)")
            fmt = detect_file_format(source.path)
        except RejectedDocumentError as exc:
            return self._record_rejection(run_id, source.filename, str(exc))

        sha = sha256_file(source.path)
        key = original_key(sha, fmt)
        if not self._store.exists(key):
            self._store.put_file(key, source.path, content_type=_content_type(fmt))

        with self._engine.begin() as conn:
            # Sérialise les imports concurrents d'un même fichier.
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:sha))"), {"sha": sha})
            existing = conn.execute(
                text("SELECT id FROM document WHERE sha256 = :sha"), {"sha": sha}
            ).scalar_one_or_none()
            if existing is not None:
                document_id: UUID = existing
                outcome = ImportOutcome.DUPLICATE
            else:
                comic_id = conn.execute(
                    text(
                        """
                        INSERT INTO comic (title, series_title, issue_number, language,
                                           expected_page_count)
                        VALUES (:title, :series, :issue, :lang, :expected)
                        RETURNING id
                        """
                    ),
                    {
                        "title": source.title or Path(source.filename).stem,
                        "series": source.series_title,
                        "issue": source.issue_number,
                        "lang": source.language,
                        "expected": source.expected_page_count,
                    },
                ).scalar_one()
                document_id = conn.execute(
                    text(
                        """
                        INSERT INTO document (comic_id, sha256, format, byte_size, storage_key,
                                              original_filename)
                        VALUES (:comic, :sha, :fmt, :size, :key, :name)
                        RETURNING id
                        """
                    ),
                    {
                        "comic": comic_id,
                        "sha": sha,
                        "fmt": fmt.value,
                        "size": size,
                        "key": key,
                        "name": source.filename,
                    },
                ).scalar_one()
                outcome = ImportOutcome.NEW
            conn.execute(
                text(
                    "INSERT INTO import_item (run_id, document_id, original_filename, outcome) "
                    "VALUES (:run, :doc, :name, :outcome)"
                ),
                {"run": run_id, "doc": document_id, "name": source.filename, "outcome": outcome},
            )
        # Idempotent : un doublon dont la validation existe déjà ne crée rien de nouveau,
        # un doublon resté inachevé (import interrompu) est relancé.
        self._queue.enqueue(
            run_id,
            VALIDATE_STEP,
            {"document_id": str(document_id)},
            idempotency_key=f"{VALIDATE_STEP}:{sha}",
        )
        return ImportItemResult(source.filename, outcome, document_id)

    def _record_rejection(self, run_id: UUID, filename: str, error: str) -> ImportItemResult:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO import_item (run_id, original_filename, outcome, error) "
                    "VALUES (:run, :name, 'REJECTED', :error)"
                ),
                {"run": run_id, "name": filename, "error": error},
            )
        return ImportItemResult(filename, ImportOutcome.REJECTED, None, error)

    # --- Étape : validation -----------------------------------------------------------------

    def validate_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = UUID(payload["document_id"])
        doc = self._document(document_id)
        if doc["status"] != DocumentStatus.UPLOADED:
            if doc["page_count"]:
                self._enqueue_renders(document_id, doc["sha256"], doc["page_count"])
            return {"skipped": doc["status"]}

        try:
            with self._store.local_copy(doc["storage_key"]) as path:
                info = inspect_document(path, self.limits)
        except RejectedDocumentError as exc:
            self._set_document_status(document_id, DocumentStatus.REJECTED, str(exc))
            return {"rejected": str(exc)}

        expected = doc["expected_page_count"]
        status, error = DocumentStatus.VALIDATED, None
        if expected is not None and info.page_count != expected:
            status = DocumentStatus.INCOMPLETE
            error = f"{info.page_count} page(s) présente(s), {expected} attendue(s)"

        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE document SET format = :fmt, page_count = :n, status = :status, "
                    "error = :error, updated_at = now() WHERE id = :id"
                ),
                {
                    "id": document_id,
                    "fmt": info.format.value,
                    "n": info.page_count,
                    "status": status.value,
                    "error": error,
                },
            )
            conn.execute(
                text(
                    "INSERT INTO page (document_id, number) "
                    "SELECT :id, n FROM generate_series(1, :count) AS n "
                    "ON CONFLICT (document_id, number) DO NOTHING"
                ),
                {"id": document_id, "count": info.page_count},
            )
        self._enqueue_renders(document_id, doc["sha256"], info.page_count)
        return {"format": info.format.value, "page_count": info.page_count, "status": status}

    def _enqueue_renders(self, document_id: UUID, sha: str, page_count: int) -> None:
        run_id = self._current_run(document_id)
        for number in range(1, page_count + 1):
            self._queue.enqueue(
                run_id,
                RENDER_STEP,
                {"document_id": str(document_id), "page": number},
                idempotency_key=f"library.render:{sha}:p{number}:{self.profile.name}",
            )

    def _current_run(self, document_id: UUID) -> UUID:
        with self._engine.connect() as conn:
            run_id: UUID = conn.execute(
                text(
                    "SELECT run_id FROM pipeline_step WHERE name = :step "
                    "AND payload->>'document_id' = :doc ORDER BY created_at LIMIT 1"
                ),
                {"step": VALIDATE_STEP, "doc": str(document_id)},
            ).scalar_one()
        return run_id

    # --- Étape : rendu d'une page -----------------------------------------------------------

    def render_document_page(self, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = UUID(payload["document_id"])
        number = int(payload["page"])
        doc = self._document(document_id)
        if doc["status"] == DocumentStatus.REJECTED:
            return {"skipped": "REJECTED"}

        key = render_key(doc["sha256"], self.profile, number)
        try:
            with self._store.local_copy(doc["storage_key"]) as path:
                rendered = render_page(
                    path,
                    DocumentFormat(doc["format"]),
                    number,
                    max_dimension=self.profile.max_dimension,
                    quality=self.profile.webp_quality,
                    limits=self.limits,
                )
        except RejectedDocumentError as exc:
            self._mark_page_failed(document_id, number, str(exc))
            return {"page": number, "failed": str(exc)}

        self._store.put_bytes(key, rendered.data, content_type="image/webp")
        with self._engine.begin() as conn:
            conn.execute(
                text("SELECT id FROM document WHERE id = :id FOR UPDATE"), {"id": document_id}
            )
            conn.execute(
                text(
                    """
                    UPDATE page SET status = 'RENDERED', render_key = :key,
                           render_profile = :profile, render_sha256 = :sha,
                           width = :w, height = :h, byte_size = :size,
                           error = NULL, rendered_at = now(), updated_at = now()
                     WHERE document_id = :doc AND number = :n
                    """
                ),
                {
                    "doc": document_id,
                    "n": number,
                    "key": key,
                    "profile": self.profile.name,
                    "sha": hashlib.sha256(rendered.data).hexdigest(),
                    "w": rendered.width,
                    "h": rendered.height,
                    "size": len(rendered.data),
                },
            )
            rendered_pages = set(
                conn.execute(
                    text(
                        "SELECT number FROM page WHERE document_id = :doc AND status = 'RENDERED'"
                    ),
                    {"doc": document_id},
                ).scalars()
            )
            status = conn.execute(
                text("SELECT status FROM document WHERE id = :id"), {"id": document_id}
            ).scalar_one()
            # Règle de complétude : aucune page manquante (voir primestone.provenance).
            if status == DocumentStatus.VALIDATED and not missing_pages(
                doc["page_count"], rendered_pages
            ):
                conn.execute(
                    text(
                        "UPDATE document SET status = 'COMPLETE', updated_at = now() WHERE id = :id"
                    ),
                    {"id": document_id},
                )
        return {"page": number, "width": rendered.width, "height": rendered.height}

    def _mark_page_failed(self, document_id: UUID, number: int, error: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("SELECT id FROM document WHERE id = :id FOR UPDATE"), {"id": document_id}
            )
            conn.execute(
                text(
                    "UPDATE page SET status = 'FAILED', error = :error, updated_at = now() "
                    "WHERE document_id = :doc AND number = :n"
                ),
                {"doc": document_id, "n": number, "error": error},
            )
            conn.execute(
                text(
                    "UPDATE document SET status = 'FAILED', error = :error, updated_at = now() "
                    "WHERE id = :id AND status IN ('VALIDATED', 'INCOMPLETE')"
                ),
                {"id": document_id, "error": f"page {number} : {error}"},
            )

    # --- Lecture ----------------------------------------------------------------------------

    def _document(self, document_id: UUID) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        """
                        SELECT d.id, d.sha256, d.format, d.storage_key, d.status, d.page_count,
                               c.expected_page_count
                          FROM document d JOIN comic c ON c.id = d.comic_id
                         WHERE d.id = :id
                        """
                    ),
                    {"id": document_id},
                )
                .mappings()
                .one()
            )
        return dict(row)

    def _set_document_status(self, document_id: UUID, status: DocumentStatus, error: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE document SET status = :status, error = :error, updated_at = now() "
                    "WHERE id = :id"
                ),
                {"id": document_id, "status": status.value, "error": error},
            )

    def batch_report(self, run_id: UUID) -> dict[str, Any] | None:
        """Rapport d'un lot : statut, durée, volumes, et détail par fichier."""
        with self._engine.connect() as conn:
            run = (
                conn.execute(
                    text(
                        """
                        SELECT id, kind, status, params, created_at, finished_at,
                               EXTRACT(EPOCH FROM (COALESCE(finished_at, now()) - created_at))
                                 AS duration_seconds
                          FROM pipeline_run WHERE id = :id
                        """
                    ),
                    {"id": run_id},
                )
                .mappings()
                .one_or_none()
            )
            if run is None or run["kind"] != IMPORT_RUN_KIND:
                return None
            items = (
                conn.execute(
                    text(
                        """
                        SELECT i.original_filename AS filename, i.outcome, i.error AS import_error,
                               d.id AS document_id, d.status, d.format, d.page_count,
                               d.byte_size, d.error,
                               count(p.id) FILTER (WHERE p.status = 'RENDERED') AS pages_rendered,
                               count(p.id) FILTER (WHERE p.status = 'FAILED') AS pages_failed,
                               COALESCE(sum(p.byte_size), 0) AS rendered_bytes
                          FROM import_item i
                          LEFT JOIN document d ON d.id = i.document_id
                          LEFT JOIN page p ON p.document_id = d.id
                         WHERE i.run_id = :id
                         GROUP BY i.id, d.id
                         ORDER BY i.created_at, i.original_filename
                        """
                    ),
                    {"id": run_id},
                )
                .mappings()
                .all()
            )
            steps: dict[str, int] = {
                row[0]: int(row[1])
                for row in conn.execute(
                    text(
                        "SELECT status, count(*) FROM pipeline_step WHERE run_id = :id "
                        "GROUP BY status"
                    ),
                    {"id": run_id},
                )
            }

        detail = [
            {
                "filename": i["filename"],
                "outcome": i["outcome"],
                "document_id": str(i["document_id"]) if i["document_id"] else None,
                "status": i["status"],
                "format": i["format"],
                "page_count": i["page_count"],
                "pages_rendered": int(i["pages_rendered"]),
                "pages_failed": int(i["pages_failed"]),
                "error": i["import_error"] or i["error"],
            }
            for i in items
        ]
        by_status: dict[str, int] = {}
        for i in items:
            key = i["status"] or "REJECTED"
            by_status[key] = by_status.get(key, 0) + 1
        return {
            "run_id": str(run["id"]),
            "status": run["status"],
            "created_at": run["created_at"].isoformat(),
            "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None,
            "duration_seconds": round(float(run["duration_seconds"]), 3),
            "render_profile": run["params"].get("profile"),
            "totals": {
                "files": len(items),
                "new": sum(1 for i in items if i["outcome"] == "NEW"),
                "duplicates": sum(1 for i in items if i["outcome"] == "DUPLICATE"),
                "rejected_at_import": sum(1 for i in items if i["outcome"] == "REJECTED"),
                "documents_by_status": by_status,
                "pages_total": sum(i["page_count"] or 0 for i in items),
                "pages_rendered": sum(int(i["pages_rendered"]) for i in items),
                "pages_failed": sum(int(i["pages_failed"]) for i in items),
                "original_bytes": sum(int(i["byte_size"] or 0) for i in items),
                "rendered_bytes": sum(int(i["rendered_bytes"]) for i in items),
                "steps_by_status": steps,
            },
            "items": detail,
        }


def _content_type(fmt: DocumentFormat) -> str:
    return "application/pdf" if fmt is DocumentFormat.PDF else "application/vnd.comicbook+zip"
