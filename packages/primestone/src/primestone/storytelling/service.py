"""Scripts : 13 étapes (retour possible à toute étape), versions, notation, adaptation FR/EN,
validation finale. Rien n'est effacé ; chaque action est journalisée."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from primestone.db.schema import SCRIPT_STEPS
from primestone.editorial.factcheck import Corpus, check_text
from primestone.forensic import ForensicService
from primestone.storytelling.analysis import score, work_citations

PASS_MARK = 70  # note minimale pour la validation finale (en plus de l'absence de veto)
MAX_SCRIPT_CHARS = 400_000


class ScriptError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _page_lines(page: Any) -> list[str]:
    """Lignes d'une page dans l'ordre de LECTURE (haut → bas) : le flux PDF peut regrouper les
    titres à part (constaté sur de vrais scripts). Le texte de chaque ligne vient du flux (mots
    intacts) ; seule sa position (boîte de son premier caractère) sert à les ordonner."""
    textpage = page.get_textpage()
    count = textpage.count_chars()
    stream = textpage.get_text_range(0, count)
    if len(stream) != count:  # alignement texte / caractères impossible : ordre du flux
        return [line for line in stream.splitlines() if line.strip()]
    positioned: list[tuple[float, float, int, str]] = []
    start = 0
    for n, line in enumerate(stream.split("\r\n")):
        if line.strip():
            offset = len(line) - len(line.lstrip())
            left, _bottom, _right, top = textpage.get_charbox(start + offset)
            positioned.append((round(top), left, n, line.strip()))
        start += len(line) + 2
    return [line for *_, line in sorted(positioned, key=lambda p: (-p[0], p[2]))]


def read_script_file(path: Path) -> str:
    """Texte d'un script : .txt / .md, ou PDF (extraction locale, gratuite, ordre de lecture)."""
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium

        from primestone.comic.formats import PDFIUM_LOCK  # PDFium n'est pas thread-safe

        with PDFIUM_LOCK:
            pdf = pdfium.PdfDocument(path)
            try:
                return "\n".join(line for i in range(len(pdf)) for line in _page_lines(pdf[i]))
            finally:
                pdf.close()
    return path.read_text(encoding="utf-8")


class StorytellingService:
    def __init__(self, engine: Engine, forensic: ForensicService) -> None:
        self._engine = engine
        self._forensic = forensic

    @staticmethod
    def _log(
        conn: Connection,
        script_id: UUID,
        action: str,
        author: str,
        detail: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        conn.execute(
            text(
                "INSERT INTO script_event (script_id, action, detail, author, reason) "
                "VALUES (:s, :a, CAST(:d AS jsonb), :author, :r)"
            ),
            {"s": script_id, "a": action, "d": _json(detail or {}), "author": author, "r": reason},
        )

    def _row(self, conn: Connection, script_id: UUID, *, lock: bool = False) -> Any:
        query = "SELECT * FROM script WHERE id = :s"
        row = conn.execute(
            text(query + " FOR UPDATE" if lock else query), {"s": script_id}
        ).one_or_none()
        if row is None:
            raise LookupError("script introuvable")
        return row

    def create(
        self,
        *,
        title: str,
        language: str,
        content: str,
        author: str,
        document_ids: Sequence[UUID] = (),
        origin: str = "HUMAN",
        adapted_from: UUID | None = None,
    ) -> UUID:
        if language not in ("fr", "en"):
            raise ScriptError("langue attendue : fr ou en")
        if not title.strip() or not author.strip():
            raise ScriptError("titre et auteur obligatoires")
        with self._engine.begin() as conn:
            if document_ids:
                known = conn.execute(
                    text("SELECT count(*) FROM document WHERE id = ANY(:ids)"),
                    {"ids": list(document_ids)},
                ).scalar_one()
                if known != len(set(document_ids)):
                    raise ScriptError("document inconnu")
            script_id: UUID = conn.execute(
                text(
                    "INSERT INTO script (title, language, document_ids, adapted_from, author) "
                    "VALUES (:t, :l, CAST(:d AS jsonb), :a, :author) RETURNING id"
                ),
                {
                    "t": title.strip(),
                    "l": language,
                    "d": _json([str(d) for d in dict.fromkeys(document_ids)]),
                    "a": adapted_from,
                    "author": author,
                },
            ).scalar_one()
            self._log(conn, script_id, "CREATED", author, {"language": language})
        if content.strip():
            self.add_version(script_id, content, author=author, origin=origin)
        return script_id

    def add_version(
        self, script_id: UUID, content: str, *, author: str, origin: str = "HUMAN"
    ) -> dict[str, Any]:
        if not content.strip():
            raise ScriptError("version vide")
        if len(content) > MAX_SCRIPT_CHARS:
            raise ScriptError("script trop long")
        with self._engine.begin() as conn:
            row = self._row(conn, script_id, lock=True)
            if row.status == "VALIDATED":
                raise ScriptError("script validé : créer une adaptation ou un nouveau script")
            number = conn.execute(
                text(
                    "SELECT COALESCE(max(number), 0) + 1 FROM script_version WHERE script_id = :s"
                ),
                {"s": script_id},
            ).scalar_one()
            version_id: UUID = conn.execute(
                text(
                    "INSERT INTO script_version (script_id, number, step, content, origin, author) "
                    "VALUES (:s, :n, :step, :c, :o, :a) RETURNING id"
                ),
                {
                    "s": script_id,
                    "n": number,
                    "step": row.step,
                    "c": content,
                    "o": origin,
                    "a": author,
                },
            ).scalar_one()
            conn.execute(
                text("UPDATE script SET updated_at = now() WHERE id = :s"), {"s": script_id}
            )
            self._log(
                conn, script_id, "VERSION_ADDED", author, {"number": number, "step": row.step}
            )
        return {"id": str(version_id), "number": number}

    def move(self, script_id: UUID, step: str, *, author: str, reason: str | None = None) -> None:
        """Toute étape est accessible (retour en arrière compris), sauf la validation finale,
        qui passe par `validate`."""
        if step not in SCRIPT_STEPS:
            raise ScriptError(f"étape inconnue : {step}")
        if step == "FINAL_VALIDATION":
            raise ScriptError("la validation finale passe par « validate »")
        with self._engine.begin() as conn:
            row = self._row(conn, script_id, lock=True)
            if row.status == "VALIDATED":
                raise ScriptError("script déjà validé")
            conn.execute(
                text("UPDATE script SET step = :st, updated_at = now() WHERE id = :s"),
                {"st": step, "s": script_id},
            )
            self._log(conn, script_id, "STEP", author, {"from": row.step, "to": step}, reason)

    def _corpus(self, document_ids: Sequence[UUID]) -> Corpus:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT d.id, c.title, d.page_count FROM document d "
                    "JOIN comic c ON c.id = d.comic_id WHERE d.id = ANY(:ids)"
                ),
                {"ids": list(document_ids)},
            ).all()
        return Corpus(
            titles={r[0]: r[1] for r in rows},
            page_counts={r[0]: r[2] or 0 for r in rows},
            rows=self._forensic.text_rows(document_ids) if document_ids else [],
            claims=self._forensic.observations(document_ids, kind="CLAIM", limit=10_000)
            if document_ids
            else [],
        )

    def evaluate(self, script_id: UUID, *, version: int | None = None) -> dict[str, Any]:
        """Fact Checker + références d'œuvres + pré-notation ; enregistre la note."""
        with self._engine.connect() as conn:
            row = self._row(conn, script_id)
            v = conn.execute(
                text(
                    "SELECT id, number, content FROM script_version WHERE script_id = :s "
                    "AND (CAST(:n AS integer) IS NULL OR number = :n) "
                    "ORDER BY number DESC LIMIT 1"
                ),
                {"s": script_id, "n": version},
            ).one_or_none()
            library_titles = [r[0] for r in conn.execute(text("SELECT title FROM comic")).all()]
        if v is None:
            raise ScriptError("aucune version à évaluer")
        documents = [UUID(d) for d in row.document_ids]
        report = check_text(v.content, self._corpus(documents))
        result = score(v.content, report, work_citations(v.content, library_titles))
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO script_score (version_id, method, criteria, total, factual_veto, "
                    "analysis) VALUES (:v, :m, CAST(:c AS jsonb), :t, :veto, CAST(:a AS jsonb))"
                ),
                {
                    "v": v.id,
                    "m": result["method"],
                    "c": _json(result["criteria"]),
                    "t": result["total"],
                    "veto": result["factual_veto"],
                    "a": _json(result["analysis"]),
                },
            )
            self._log(
                conn,
                script_id,
                "SCORED",
                "editorial_critic",
                {"version": v.number, "total": result["total"], "veto": result["factual_veto"]},
            )
        return {**result, "version": v.number}

    def validate(self, script_id: UUID, *, author: str) -> None:
        """Validation finale humaine : dernière version notée, aucun veto, note ≥ PASS_MARK."""
        with self._engine.begin() as conn:
            row = self._row(conn, script_id, lock=True)
            last = conn.execute(
                text(
                    """
                    SELECT v.number, s.total, s.factual_veto
                      FROM script_version v
                      LEFT JOIN LATERAL (SELECT total, factual_veto FROM script_score
                                          WHERE version_id = v.id
                                          ORDER BY created_at DESC LIMIT 1) s ON true
                     WHERE v.script_id = :s ORDER BY v.number DESC LIMIT 1
                    """
                ),
                {"s": script_id},
            ).one_or_none()
            if row.status == "VALIDATED":
                raise ScriptError("script déjà validé")
            if last is None or last.total is None:
                raise ScriptError("la dernière version doit être évaluée avant validation")
            if last.factual_veto:
                raise ScriptError("veto factuel : erreur factuelle majeure, validation impossible")
            if last.total < PASS_MARK:
                raise ScriptError(f"note {last.total}/100 inférieure au seuil {PASS_MARK}")
            conn.execute(
                text(
                    "UPDATE script SET status = 'VALIDATED', step = 'FINAL_VALIDATION', "
                    "updated_at = now() WHERE id = :s"
                ),
                {"s": script_id},
            )
            self._log(
                conn, script_id, "VALIDATED", author, {"version": last.number, "total": last.total}
            )

    def adapt(self, script_id: UUID, *, content: str, title: str | None, author: str) -> UUID:
        """Version dans l'autre langue : un script à part entière (ses propres angles, hooks,
        références), relié à l'original, qui suit tout le processus."""
        with self._engine.connect() as conn:
            row = self._row(conn, script_id)
        target = "en" if row.language == "fr" else "fr"
        new_id = self.create(
            title=title or f"{row.title} ({target.upper()})",
            language=target,
            content=content,
            author=author,
            document_ids=[UUID(d) for d in row.document_ids],
            adapted_from=script_id,
        )
        with self._engine.begin() as conn:
            conn.execute(text("UPDATE script SET step = 'ADAPTATION' WHERE id = :s"), {"s": new_id})
            self._log(
                conn, script_id, "ADAPTED", author, {"adaptation": str(new_id), "language": target}
            )
        return new_id

    def scripts(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                {**dict(r), "id": str(r["id"])}
                for r in conn.execute(
                    text(
                        """
                        SELECT s.id, s.title, s.language, s.step, s.status, s.updated_at,
                               (SELECT max(number) FROM script_version v
                                 WHERE v.script_id = s.id) AS versions,
                               (SELECT sc.total FROM script_score sc
                                  JOIN script_version v ON v.id = sc.version_id
                                 WHERE v.script_id = s.id
                                 ORDER BY v.number DESC, sc.created_at DESC LIMIT 1) AS last_total
                          FROM script s ORDER BY s.updated_at DESC
                        """
                    )
                ).mappings()
            ]

    def script(self, script_id: UUID) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = self._row(conn, script_id)
            versions = [
                {**dict(r), "id": str(r["id"])}
                for r in conn.execute(
                    text(
                        "SELECT id, number, step, origin, author, created_at, content "
                        "FROM script_version WHERE script_id = :s ORDER BY number"
                    ),
                    {"s": script_id},
                ).mappings()
            ]
            scores = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT v.number AS version, sc.method, sc.criteria, sc.total, "
                        "sc.factual_veto, sc.analysis, sc.created_at FROM script_score sc "
                        "JOIN script_version v ON v.id = sc.version_id WHERE v.script_id = :s "
                        "ORDER BY sc.created_at"
                    ),
                    {"s": script_id},
                ).mappings()
            ]
            events = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT action, detail, author, reason, created_at FROM script_event "
                        "WHERE script_id = :s ORDER BY created_at, id"
                    ),
                    {"s": script_id},
                ).mappings()
            ]
            adaptations = [
                str(r[0])
                for r in conn.execute(
                    text("SELECT id FROM script WHERE adapted_from = :s"), {"s": script_id}
                ).all()
            ]
        data = dict(row._mapping)
        return {
            **data,
            "id": str(data["id"]),
            "adapted_from": str(data["adapted_from"]) if data["adapted_from"] else None,
            "steps": list(SCRIPT_STEPS),
            "pass_mark": PASS_MARK,
            "versions": versions,
            "scores": scores,
            "events": events,
            "adaptations": adaptations,
        }
