"""Comic Vision de bout en bout : bibliothèque → rendu → analyse (fournisseur simulé)."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import Engine, text

from primestone.comic import ImportSource, LibraryService, RenderProfile
from primestone.jobs import PostgresJobQueue, StepStatus
from primestone.provenance import BoundingBox
from primestone.storage import LocalObjectStore
from primestone.vision import TextKind, TextRegion
from primestone.vision.providers import FakeVisionProvider, PageVisionProvider, VisionProviderError
from primestone.vision.service import ANALYZE_STEP, VisionBudgetError, VisionService
from primestone_worker.handlers import default_registry
from primestone_worker.library import register_library_handlers
from primestone_worker.main import Worker
from primestone_worker.vision import register_vision_handlers

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def balloon(content: str, x: float, y: float) -> TextRegion:
    return TextRegion(
        text=content,
        kind=TextKind.DIALOGUE,
        bbox=BoundingBox(x=x, y=y, width=0.2, height=0.06),
        language="fr",
        confidence=0.95,
        speaker="Héros",
        speaker_confidence=0.7,
    )


# Les pages synthétiques ont 3 cases : deux en haut, une en bas (voir conftest.py).
SCRIPT = [
    balloon("EN BAS", 0.2, 0.7),
    balloon("EN HAUT À DROITE", 0.6, 0.2),
    balloon("EN HAUT À GAUCHE", 0.1, 0.2),
]


class Env(SimpleNamespace):
    library: LibraryService
    vision: VisionService
    queue: PostgresJobQueue
    document_ids: list[UUID]

    async def drain(self) -> None:
        registry = default_registry()
        register_library_handlers(registry, self.library)
        register_vision_handlers(registry, self.vision)
        worker = Worker(self.queue, registry, worker_id="t", retry_delay_seconds=0)
        for _ in range(3):
            while await worker.run_once():
                pass


async def make_env(
    engine: Engine, root: Path, files: list[Path], provider: PageVisionProvider
) -> Env:
    store = LocalObjectStore(root / "storage")
    queue = PostgresJobQueue(engine)
    library = LibraryService(engine, store, queue, profile=RenderProfile(max_dimension=600))
    vision = VisionService(engine, store, queue, lambda _name: provider)
    result = library.start_import([ImportSource(path=f, filename=f.name) for f in files])
    env = Env(library=library, vision=vision, queue=queue)
    await env.drain()
    env.document_ids = [i.document_id for i in result.items if i.document_id]
    return env


async def test_analysis_end_to_end(
    db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace
) -> None:
    provider = FakeVisionProvider(script={0: SCRIPT}, cost_per_page_usd=Decimal("0.01"))
    env = await make_env(db_engine, tmp_path, [comic_factory.pdf(pages=2)], provider)

    estimate, _ = env.vision.estimate(env.document_ids, "fake", Decimal("1"))
    assert (estimate.pages, estimate.to_analyze) == (2, 2)
    assert estimate.estimated_cost_usd == Decimal("0.02")

    run_id, _ = env.vision.start(env.document_ids, "fake", Decimal("1"))
    await env.drain()

    report = env.vision.run_report(run_id)
    assert report is not None
    assert (report["status"], report["pages_succeeded"], report["spent_usd"]) == (
        "SUCCEEDED",
        2,
        "0.020000",
    )

    analysis = env.vision.latest_analysis(env.document_ids[0], 1)
    assert analysis is not None
    assert [p["index"] for p in analysis["panels"]] == [1, 2, 3]
    top_left, top_right, bottom = (p["bbox"] for p in analysis["panels"])
    assert top_left["x"] < top_right["x"]
    assert bottom["y"] > top_left["y"]
    # Textes rattachés à leur case et remis dans l'ordre de lecture.
    assert [(t["text"], t["panel_index"]) for t in analysis["texts"]] == [
        ("EN HAUT À GAUCHE", 1),
        ("EN HAUT À DROITE", 2),
        ("EN BAS", 3),
    ]
    assert analysis["texts"][0]["speaker"] == "Héros"
    assert analysis["detector"].startswith("xycut")


async def test_never_pays_twice(
    db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace
) -> None:
    provider = FakeVisionProvider(cost_per_page_usd=Decimal("0.01"))
    env = await make_env(db_engine, tmp_path, [comic_factory.cbz(pages=3)], provider)
    env.vision.start(env.document_ids, "fake", Decimal("1"))
    await env.drain()
    assert len(provider.calls) == 3

    estimate, _ = env.vision.estimate(env.document_ids, "fake", Decimal("1"))
    assert (estimate.already_analyzed, estimate.to_analyze) == (3, 0)
    run_id, _ = env.vision.start(env.document_ids, "fake", Decimal("1"))
    await env.drain()
    assert len(provider.calls) == 3  # aucun nouvel appel
    assert env.queue.run_status(run_id) == "SUCCEEDED"


async def test_estimate_over_budget_is_refused(
    db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace
) -> None:
    provider = FakeVisionProvider(cost_per_page_usd=Decimal("0.10"))
    env = await make_env(db_engine, tmp_path, [comic_factory.pdf(pages=3)], provider)
    with pytest.raises(VisionBudgetError) as info:
        env.vision.start(env.document_ids, "fake", Decimal("0.25"))
    assert info.value.estimate.estimated_cost_usd == Decimal("0.30")
    with db_engine.connect() as conn:
        steps = conn.execute(
            text("SELECT count(*) FROM pipeline_step WHERE name = :n"), {"n": ANALYZE_STEP}
        ).scalar_one()
    assert steps == 0  # rien n'a été lancé
    assert provider.calls == []


async def test_budget_rechecked_before_each_call(
    db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace
) -> None:
    provider = FakeVisionProvider(cost_per_page_usd=Decimal("0.10"))
    env = await make_env(db_engine, tmp_path, [comic_factory.pdf(pages=3)], provider)
    run_id, _ = env.vision.start(env.document_ids, "fake", Decimal("0.30"))
    # Le coût réel s'avère plus élevé que l'estimation : le budget doit arrêter la dépense.
    provider._cost = Decimal("0.15")
    await env.drain()

    report = env.vision.run_report(run_id)
    assert report is not None
    assert report["pages_succeeded"] == 2
    assert Decimal(report["spent_usd"]) <= Decimal("0.30")
    assert report["status"] == "FAILED"  # étape restante arrêtée : décision humaine requise
    assert report["steps_by_status"]["DEAD"] == 1


async def test_permanent_provider_failure_is_recorded(
    db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace
) -> None:
    provider = FakeVisionProvider(fail_with=VisionProviderError("refusée", permanent=True))
    env = await make_env(db_engine, tmp_path, [comic_factory.pdf(pages=1)], provider)
    run_id, _ = env.vision.start(env.document_ids, "fake", Decimal("1"))
    await env.drain()

    report = env.vision.run_report(run_id)
    assert report is not None
    assert (report["pages_failed"], report["status"]) == (1, "FAILED")
    assert env.vision.latest_analysis(env.document_ids[0], 1) is None
    assert len(provider.calls) == 1  # pas de nouvel essai payant


async def test_transient_provider_failure_is_retried(
    db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace
) -> None:
    class Flaky(FakeVisionProvider):
        async def analyze(self, context):  # type: ignore[no-untyped-def]
            if not self.calls:
                self.calls.append(context)
                raise VisionProviderError("timeout")
            return await super().analyze(context)

    provider = Flaky()
    env = await make_env(db_engine, tmp_path, [comic_factory.pdf(pages=1)], provider)
    run_id, _ = env.vision.start(env.document_ids, "fake", Decimal("1"))
    await env.drain()
    assert env.queue.run_status(run_id) == "SUCCEEDED"
    with db_engine.connect() as conn:
        step = conn.execute(
            text("SELECT status, attempts FROM pipeline_step WHERE run_id = :r"), {"r": run_id}
        ).one()
    assert (StepStatus(step[0]), step[1]) == (StepStatus.SUCCEEDED, 2)


async def test_parallel_workers_record_each_page_once(
    db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace
) -> None:
    provider = FakeVisionProvider(script={0: SCRIPT})
    files = [comic_factory.pdf(pages=3) for _ in range(4)]
    env = await make_env(db_engine, tmp_path, files, provider)
    run_id, _ = env.vision.start(env.document_ids, "fake", Decimal("1"))

    registry = default_registry()
    register_vision_handlers(registry, env.vision)
    workers = [Worker(env.queue, registry, worker_id=f"w{i}") for i in range(4)]

    async def loop(worker: Worker) -> None:
        while await worker.run_once():
            pass

    await asyncio.gather(*(loop(w) for w in workers))
    with db_engine.connect() as conn:
        analyses = conn.execute(
            text("SELECT count(*) FROM page_analysis WHERE run_id = :r"), {"r": run_id}
        ).scalar_one()
        texts = conn.execute(text("SELECT count(*) FROM text_region")).scalar_one()
    # Les pages 2 et 3 des comics synthétiques ont des rendus identiques d'un fichier à l'autre :
    # 4 premières pages distinctes + 2 pages partagées = 6 analyses payées, pas 12.
    assert analyses == 6
    assert texts == 6 * len(SCRIPT)
    for document_id in env.document_ids:  # …mais chaque page de chaque document a son analyse
        for number in (1, 2, 3):
            assert env.vision.latest_analysis(document_id, number) is not None
    estimate, _ = env.vision.estimate(env.document_ids, "fake", Decimal("1"))
    assert estimate.to_analyze == 0
