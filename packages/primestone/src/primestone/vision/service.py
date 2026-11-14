"""Service Comic Vision : estimation, lancement sous budget, analyse de page, lecture.

Supervision (autonomie L5 supervisée) : toute analyse par un fournisseur payant est
précédée d'une estimation, refusée si elle dépasse le budget fourni, et le budget est
revérifié avant CHAQUE appel à partir des coûts réellement enregistrés en base (valable
pour plusieurs workers). Une analyse identique n'est jamais payée deux fois
(`analysis_key` unique).
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import Engine, text

from primestone.jobs import PermanentError, PostgresJobQueue
from primestone.provenance import BoundingBox
from primestone.storage import ObjectStore
from primestone.vision.assign import assign_texts
from primestone.vision.models import Panel, ReadingDirection, TextKind, TextRegion
from primestone.vision.panels import DETECTOR_VERSION, detect_panels
from primestone.vision.providers import (
    PageContext,
    PageVisionProvider,
    VisionProviderError,
)

ANALYZE_STEP = "vision.analyze_page"
HUMAN_PROVIDER = "human"
RUN_KIND = "vision.analyze"
ESTIMATE_PANELS_PER_PAGE = 6


@dataclass(frozen=True)
class HumanText:
    text: str
    kind: TextKind
    panel_index: int | None = None
    speaker: str | None = None
    language: str | None = None
    bbox: BoundingBox | None = None


class _HumanProvider:
    name = HUMAN_PROVIDER
    prompt_version = "manual"

    def __init__(self, author: str) -> None:
        self.model = f"human:{author}"

    def estimate_cost(self, context: PageContext) -> Decimal:
        return Decimal("0")

    async def analyze(self, context: PageContext) -> Any:  # pragma: no cover - jamais appelé
        raise NotImplementedError


class VisionBudgetError(ValueError):
    def __init__(self, estimate: VisionEstimate, reason: str | None = None) -> None:
        super().__init__(
            reason
            or f"coût estimé {estimate.estimated_cost_usd} USD > budget {estimate.budget_usd} USD"
        )
        self.estimate = estimate


@dataclass(frozen=True)
class VisionEstimate:
    provider: str
    model: str
    pages: int
    already_analyzed: int
    to_analyze: int
    estimated_cost_usd: Decimal
    budget_usd: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "pages": self.pages,
            "already_analyzed": self.already_analyzed,
            "to_analyze": self.to_analyze,
            "estimated_cost_usd": str(self.estimated_cost_usd),
            "budget_usd": str(self.budget_usd),
        }


ProviderFactory = Callable[[str], PageVisionProvider]


class VisionService:
    def __init__(
        self,
        engine: Engine,
        store: ObjectStore,
        queue: PostgresJobQueue,
        provider_factory: ProviderFactory,
        *,
        zero_cost: bool = True,
    ) -> None:
        self.zero_cost = zero_cost
        self._engine = engine
        self._store = store
        self._queue = queue
        self._factory = provider_factory
        self._providers: dict[str, PageVisionProvider] = {}

    def provider(self, name: str) -> PageVisionProvider:
        if name not in self._providers:
            self._providers[name] = self._factory(name)
        return self._providers[name]

    @staticmethod
    def analysis_key(
        render_sha: str, provider: PageVisionProvider, direction: ReadingDirection
    ) -> str:
        return ":".join(
            [
                render_sha,
                DETECTOR_VERSION,
                provider.name,
                provider.model,
                provider.prompt_version,
                direction.value,
            ]
        )

    def _rendered_pages(self, document_ids: Sequence[UUID]) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                        SELECT p.id, p.number, p.document_id, p.render_key, p.render_sha256,
                               p.width, p.height
                          FROM page p
                         WHERE p.document_id = ANY(:ids) AND p.status = 'RENDERED'
                         ORDER BY p.document_id, p.number
                        """
                    ),
                    {"ids": list(document_ids)},
                )
                .mappings()
                .all()
            )
            # Une analyse vaut pour tout rendu identique, quel que soit le document d'origine.
            existing = set(
                conn.execute(
                    text(
                        "SELECT a.analysis_key FROM page_analysis a "
                        "WHERE a.render_sha256 IN (SELECT render_sha256 FROM page "
                        "WHERE document_id = ANY(:ids) AND status = 'RENDERED')"
                    ),
                    {"ids": list(document_ids)},
                ).scalars()
            )
        return [{**dict(r), "_existing": existing} for r in rows]

    def estimate(
        self,
        document_ids: Sequence[UUID],
        provider_name: str,
        budget_usd: Decimal,
        direction: ReadingDirection = ReadingDirection.LTR,
    ) -> tuple[VisionEstimate, list[dict[str, Any]]]:
        provider = self.provider(provider_name)
        pages = self._rendered_pages(document_ids)
        todo = [
            p
            for p in pages
            if self.analysis_key(p["render_sha256"], provider, direction) not in p["_existing"]
        ]
        placeholder = [
            Panel(index=i, bbox=BoundingBox(x=0, y=0, width=1, height=1))
            for i in range(1, ESTIMATE_PANELS_PER_PAGE + 1)
        ]
        cost = sum(
            (
                provider.estimate_cost(
                    PageContext(b"", p["width"], p["height"], placeholder, direction)
                )
                for p in todo
            ),
            Decimal("0"),
        )
        estimate = VisionEstimate(
            provider=provider.name,
            model=provider.model,
            pages=len(pages),
            already_analyzed=len(pages) - len(todo),
            to_analyze=len(todo),
            estimated_cost_usd=cost.quantize(Decimal("0.0001")),
            budget_usd=budget_usd,
        )
        return estimate, todo

    def start(
        self,
        document_ids: Sequence[UUID],
        provider_name: str,
        budget_usd: Decimal,
        *,
        direction: ReadingDirection = ReadingDirection.LTR,
        language_hint: str | None = None,
    ) -> tuple[UUID, VisionEstimate]:
        estimate, todo = self.estimate(document_ids, provider_name, budget_usd, direction)
        if self.zero_cost and estimate.estimated_cost_usd > 0:
            raise VisionBudgetError(estimate, "mode zéro coût : toute dépense est refusée")
        if estimate.estimated_cost_usd > budget_usd:
            raise VisionBudgetError(estimate)
        provider = self.provider(provider_name)
        run_id = self._queue.create_run(
            RUN_KIND,
            {
                **estimate.as_dict(),
                "direction": direction.value,
                "language_hint": language_hint,
                "document_ids": [str(d) for d in document_ids],
            },
        )
        for page in todo:
            key = self.analysis_key(page["render_sha256"], provider, direction)
            self._queue.enqueue(
                run_id,
                ANALYZE_STEP,
                {
                    "page_id": str(page["id"]),
                    "run_id": str(run_id),
                    "provider": provider_name,
                    "direction": direction.value,
                    "language_hint": language_hint,
                },
                idempotency_key=f"vision:{key}",
            )
        self._queue.refresh_run(run_id)
        return run_id, estimate

    # --- Étape : analyse d'une page --------------------------------------------------------

    async def analyze_page(self, payload: dict[str, Any]) -> dict[str, Any]:
        page_id = UUID(payload["page_id"])
        run_id = UUID(payload["run_id"])
        direction = ReadingDirection(payload["direction"])
        provider = self.provider(payload["provider"])
        page = self._page(page_id)
        key = self.analysis_key(page["render_sha256"], provider, direction)
        if self._analysis_exists(key):
            return {"skipped": "déjà analysée"}

        with self._store.open(page["render_key"]) as fh:
            image_bytes = fh.read()
        image = Image.open(io.BytesIO(image_bytes))
        panels = await asyncio.to_thread(detect_panels, image, direction=direction)
        context = PageContext(
            image_webp=image_bytes,
            width=image.width,
            height=image.height,
            panels=panels,
            direction=direction,
            language_hint=payload.get("language_hint"),
        )

        budget, spent = self._budget(run_id)
        planned = provider.estimate_cost(context)
        if self.zero_cost and planned > 0:
            raise PermanentError("mode zéro coût : appel payant refusé")
        if spent + planned > budget:
            raise PermanentError(f"budget épuisé : {spent} + {planned} > {budget} USD")

        try:
            result = await provider.analyze(context)
        except VisionProviderError as exc:
            if not exc.permanent:
                raise
            self._record(
                page_id,
                run_id,
                page["render_sha256"],
                key,
                provider,
                direction,
                panels,
                [],
                None,
                str(exc),
            )
            raise PermanentError(str(exc)) from exc

        texts = assign_texts(panels, result.texts, direction)
        self._record(
            page_id,
            run_id,
            page["render_sha256"],
            key,
            provider,
            direction,
            panels,
            texts,
            result,
            None,
        )
        return {"panels": len(panels), "texts": len(texts), "cost_usd": str(result.cost_usd)}

    def _page(self, page_id: UUID) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text("SELECT id, render_key, render_sha256, status FROM page WHERE id = :id"),
                    {"id": page_id},
                )
                .mappings()
                .one()
            )
        if row["status"] != "RENDERED":
            raise PermanentError("page non rendue")
        return dict(row)

    def _analysis_exists(self, key: str) -> bool:
        with self._engine.connect() as conn:
            return (
                conn.execute(
                    text("SELECT 1 FROM page_analysis WHERE analysis_key = :k"), {"k": key}
                ).scalar_one_or_none()
                is not None
            )

    def _budget(self, run_id: UUID) -> tuple[Decimal, Decimal]:
        with self._engine.connect() as conn:
            budget = conn.execute(
                text("SELECT params->>'budget_usd' FROM pipeline_run WHERE id = :id"),
                {"id": run_id},
            ).scalar_one()
            spent = conn.execute(
                text("SELECT COALESCE(sum(cost_usd), 0) FROM page_analysis WHERE run_id = :id"),
                {"id": run_id},
            ).scalar_one()
        return Decimal(budget), Decimal(spent)

    def _record(
        self,
        page_id: UUID,
        run_id: UUID | None,
        render_sha: str,
        key: str,
        provider: PageVisionProvider,
        direction: ReadingDirection,
        panels: list[Panel],
        texts: list[TextRegion],
        result: Any,
        error: str | None,
    ) -> None:
        with self._engine.begin() as conn:
            analysis_id = conn.execute(
                text(
                    """
                    INSERT INTO page_analysis (page_id, run_id, render_sha256, analysis_key,
                           status, detector, provider, model, prompt_version, reading_direction,
                           cost_usd, input_tokens, output_tokens, latency_ms, error)
                    VALUES (:page, :run, :render_sha, :key, :status, :detector, :provider,
                            :model, :prompt, :direction, :cost, :tin, :tout, :latency, :error)
                    ON CONFLICT (analysis_key) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "page": page_id,
                    "run": run_id,
                    "render_sha": render_sha,
                    "key": key,
                    "status": "FAILED" if error else "SUCCEEDED",
                    "detector": DETECTOR_VERSION,
                    "provider": provider.name,
                    "model": result.model if result else provider.model,
                    "prompt": provider.prompt_version,
                    "direction": direction.value,
                    "cost": result.cost_usd if result else Decimal("0"),
                    "tin": result.input_tokens if result else 0,
                    "tout": result.output_tokens if result else 0,
                    "latency": result.latency_ms if result else None,
                    "error": error,
                },
            ).scalar_one_or_none()
            if analysis_id is None:
                return  # un autre worker l'a enregistrée entre-temps
            for p in panels:
                conn.execute(
                    text(
                        'INSERT INTO panel (analysis_id, "index", x, y, width, height) '
                        "VALUES (:a, :i, :x, :y, :w, :h)"
                    ),
                    {
                        "a": analysis_id,
                        "i": p.index,
                        "x": p.bbox.x,
                        "y": p.bbox.y,
                        "w": p.bbox.width,
                        "h": p.bbox.height,
                    },
                )
            for t in texts:
                conn.execute(
                    text(
                        """
                        INSERT INTO text_region (analysis_id, "order", panel_index, kind, text,
                               language, confidence, speaker, speaker_confidence,
                               x, y, width, height)
                        VALUES (:a, :o, :panel, :kind, :text, :lang, :conf, :speaker, :sconf,
                                :x, :y, :w, :h)
                        """
                    ),
                    {
                        "a": analysis_id,
                        "o": t.order,
                        "panel": t.panel_index,
                        "kind": t.kind.value,
                        "text": t.text,
                        "lang": t.language,
                        "conf": t.confidence,
                        "speaker": t.speaker,
                        "sconf": t.speaker_confidence,
                        "x": t.bbox.x,
                        "y": t.bbox.y,
                        "w": t.bbox.width,
                        "h": t.bbox.height,
                    },
                )

    # --- Transcription humaine (gratuite, source la plus fiable) ---------------------------

    def save_human_transcription(
        self,
        document_id: UUID,
        number: int,
        entries: Sequence[HumanText],
        *,
        author: str,
        direction: ReadingDirection = ReadingDirection.LTR,
    ) -> UUID:
        """Enregistre une transcription saisie ou corrigée par un humain.

        Nouvelle analyse (fournisseur « human », coût nul) qui devient la version servie ;
        les analyses précédentes sont conservées (ajout seul). Les cases reprennent celles de
        la dernière analyse, ou sont détectées si la page n'a jamais été analysée."""
        with self._engine.connect() as conn:
            page = (
                conn.execute(
                    text(
                        "SELECT id, render_key, render_sha256, status FROM page "
                        "WHERE document_id = :doc AND number = :n"
                    ),
                    {"doc": document_id, "n": number},
                )
                .mappings()
                .one_or_none()
            )
        if page is None or page["status"] != "RENDERED":
            raise LookupError("page introuvable ou non rendue")

        previous = self.latest_analysis(document_id, number)
        if previous is not None:
            panels = [
                Panel(index=p["index"], bbox=BoundingBox(**p["bbox"])) for p in previous["panels"]
            ]
        else:
            with self._store.open(page["render_key"]) as fh:
                image = Image.open(io.BytesIO(fh.read()))
                panels = detect_panels(image, direction=direction)
        by_index = {p.index: p.bbox for p in panels}
        full_page = BoundingBox(x=0, y=0, width=1, height=1)
        regions = []
        for entry in entries:
            if entry.panel_index is not None and entry.panel_index not in by_index:
                raise ValueError(f"case {entry.panel_index} inexistante sur cette page")
            regions.append(
                TextRegion(
                    text=entry.text,
                    kind=entry.kind,
                    bbox=entry.bbox
                    or (by_index[entry.panel_index] if entry.panel_index else full_page),
                    language=entry.language,
                    confidence=1.0,
                    speaker=entry.speaker,
                    speaker_confidence=1.0 if entry.speaker else None,
                )
            )
        texts = assign_texts(panels, regions, direction)
        # Une case choisie donne au texte la boîte de cette case : le rattachement
        # géométrique la retrouve sans cas particulier.
        analysis_id = uuid4()
        key = f"{page['render_sha256']}:human:{analysis_id}"
        self._record(
            page["id"],
            None,
            page["render_sha256"],
            key,
            _HumanProvider(author),
            direction,
            panels,
            texts,
            None,
            None,
        )
        with self._engine.connect() as conn:
            saved: UUID = conn.execute(
                text("SELECT id FROM page_analysis WHERE analysis_key = :k"), {"k": key}
            ).scalar_one()
        return saved

    # --- Lecture ----------------------------------------------------------------------------

    def page_panels(
        self,
        document_id: UUID,
        number: int,
        direction: ReadingDirection = ReadingDirection.LTR,
    ) -> list[dict[str, Any]] | None:
        """Cases de la page : celles de la dernière analyse, sinon détectées à la volée
        (local, gratuit, rien n'est enregistré). None si la page n'est pas rendue."""
        latest = self.latest_analysis(document_id, number)
        if latest is not None:
            panels: list[dict[str, Any]] = latest["panels"]
            return panels
        with self._engine.connect() as conn:
            key = conn.execute(
                text(
                    "SELECT render_key FROM page WHERE document_id = :doc AND number = :n "
                    "AND status = 'RENDERED'"
                ),
                {"doc": document_id, "n": number},
            ).scalar_one_or_none()
        if key is None:
            return None
        with self._store.open(key) as fh:
            image = Image.open(io.BytesIO(fh.read()))
            detected = detect_panels(image, direction=direction)
        return [{"index": p.index, "bbox": p.bbox.model_dump()} for p in detected]

    def latest_analysis(self, document_id: UUID, number: int) -> dict[str, Any] | None:
        """Dernière analyse réussie d'une page, avec cases et textes dans l'ordre de lecture."""
        with self._engine.connect() as conn:
            analysis = (
                conn.execute(
                    text(
                        """
                        SELECT a.id, a.detector, a.provider, a.model, a.prompt_version,
                               a.reading_direction, a.cost_usd, a.created_at
                          FROM page p JOIN page_analysis a ON a.render_sha256 = p.render_sha256
                         WHERE p.document_id = :doc AND p.number = :n AND a.status = 'SUCCEEDED'
                         ORDER BY a.created_at DESC LIMIT 1
                        """
                    ),
                    {"doc": document_id, "n": number},
                )
                .mappings()
                .one_or_none()
            )
            if analysis is None:
                return None
            panels = conn.execute(
                text(
                    'SELECT "index", x, y, width, height FROM panel '
                    'WHERE analysis_id = :a ORDER BY "index"'
                ),
                {"a": analysis["id"]},
            ).mappings()
            texts = conn.execute(
                text(
                    'SELECT "order", panel_index, kind, text, language, confidence, speaker, '
                    "speaker_confidence, x, y, width, height FROM text_region "
                    'WHERE analysis_id = :a ORDER BY "order"'
                ),
                {"a": analysis["id"]},
            ).mappings()
            panel_list = [{"index": p["index"], "bbox": _bbox(p)} for p in panels]
            text_list = [
                {
                    "order": t["order"],
                    "panel_index": t["panel_index"],
                    "kind": TextKind(t["kind"]).value,
                    "text": t["text"],
                    "language": t["language"],
                    "confidence": t["confidence"],
                    "speaker": t["speaker"],
                    "speaker_confidence": t["speaker_confidence"],
                    "bbox": _bbox(t),
                }
                for t in texts
            ]
        return {
            "analysis_id": str(analysis["id"]),
            "detector": analysis["detector"],
            "provider": analysis["provider"],
            "model": analysis["model"],
            "prompt_version": analysis["prompt_version"],
            "reading_direction": analysis["reading_direction"],
            "cost_usd": str(analysis["cost_usd"]),
            "created_at": analysis["created_at"].isoformat(),
            "panels": panel_list,
            "texts": text_list,
        }

    def run_report(self, run_id: UUID) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            run = (
                conn.execute(
                    text(
                        "SELECT id, kind, status, params, created_at, finished_at "
                        "FROM pipeline_run WHERE id = :id"
                    ),
                    {"id": run_id},
                )
                .mappings()
                .one_or_none()
            )
            if run is None or run["kind"] != RUN_KIND:
                return None
            stats = (
                conn.execute(
                    text(
                        """
                        SELECT count(*) FILTER (WHERE status = 'SUCCEEDED') AS succeeded,
                               count(*) FILTER (WHERE status = 'FAILED') AS failed,
                               COALESCE(sum(cost_usd), 0) AS cost,
                               COALESCE(sum(input_tokens), 0) AS tin,
                               COALESCE(sum(output_tokens), 0) AS tout
                          FROM page_analysis WHERE run_id = :id
                        """
                    ),
                    {"id": run_id},
                )
                .mappings()
                .one()
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
        params = run["params"]
        return {
            "run_id": str(run["id"]),
            "status": run["status"],
            "provider": params.get("provider"),
            "model": params.get("model"),
            "budget_usd": params.get("budget_usd"),
            "estimated_cost_usd": params.get("estimated_cost_usd"),
            "spent_usd": str(stats["cost"]),
            "pages_succeeded": int(stats["succeeded"]),
            "pages_failed": int(stats["failed"]),
            "input_tokens": int(stats["tin"]),
            "output_tokens": int(stats["tout"]),
            "steps_by_status": steps,
            "created_at": run["created_at"].isoformat(),
            "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None,
        }


def _bbox(row: Any) -> dict[str, float]:
    return {k: float(row[k]) for k in ("x", "y", "width", "height")}
