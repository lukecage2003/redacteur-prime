"""Forensic de bout en bout, à coût nul : import → transcription humaine → observations."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import Engine, text

from primestone.comic import ImportSource, LibraryService, RenderProfile
from primestone.forensic import forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.storage import LocalObjectStore
from primestone.vision import TextKind
from primestone.vision.providers import FakeVisionProvider
from primestone.vision.service import HumanText, VisionService
from primestone_worker.handlers import default_registry
from primestone_worker.library import register_library_handlers
from primestone_worker.main import Worker
from primestone_worker.vision import register_vision_handlers

pytestmark = pytest.mark.integration


@pytest.fixture
def env(db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace) -> SimpleNamespace:
    store = LocalObjectStore(tmp_path / "storage")
    queue = PostgresJobQueue(db_engine)
    library = LibraryService(db_engine, store, queue, profile=RenderProfile(max_dimension=600))
    vision = VisionService(db_engine, store, queue, lambda _n: FakeVisionProvider())
    files = [
        comic_factory.pdf(pages=3, name="tome-1.pdf"),
        comic_factory.cbz(pages=2, name="tome-2.cbz"),
    ]
    result = library.start_import([ImportSource(path=f, filename=f.name) for f in files])

    registry = default_registry()
    register_library_handlers(registry, library)
    register_vision_handlers(registry, vision)
    worker = Worker(queue, registry, worker_id="t")

    async def drain() -> None:
        for _ in range(3):
            while await worker.run_once():
                pass

    asyncio.run(drain())
    ids: list[UUID] = [i.document_id for i in result.items if i.document_id]
    return SimpleNamespace(
        vision=vision, forensic=forensic_service(db_engine), ids=ids, drain=drain
    )


def say(content: str, speaker: str | None = None, panel: int = 1) -> HumanText:
    return HumanText(
        text=content, kind=TextKind.DIALOGUE, panel_index=panel, speaker=speaker, language="fr"
    )


def test_human_transcription_then_forensic_report(env: SimpleNamespace) -> None:
    tome1, tome2 = env.ids
    env.vision.save_human_transcription(
        tome1,
        1,
        [say("Je m'appelle Bruce.", "Bruce"), say("Bruce ? Tu es en retard.", "Alfred", 2)],
        author="moi",
    )
    env.vision.save_human_transcription(
        tome1, 2, [say("J'ai 32 ans, Alfred.", "Bruce", 3)], author="moi"
    )
    env.vision.save_human_transcription(tome2, 1, [say("J'ai 40 ans.", "Bruce")], author="moi")

    analysis = env.vision.latest_analysis(tome1, 1)
    assert analysis["provider"] == "human"
    assert analysis["cost_usd"] == "0.000000"
    assert [(t["text"], t["panel_index"]) for t in analysis["texts"]] == [
        ("Je m'appelle Bruce.", 1),
        ("Bruce ? Tu es en retard.", 2),
    ]

    _, stats = env.forensic.analyze(env.ids)
    assert stats["new"] == stats["extracted"] > 0
    report = env.forensic.report(env.ids)

    # Pages non transcrites : l'analyse forensique n'est PAS complète.
    assert report["status"] == "INCOMPLETE"
    assert report["documents"][str(tome1)]["missing_pages"] == [3]
    assert report["documents"][str(tome2)]["missing_pages"] == [2]

    bruce = report["characters"]["Bruce"]
    assert bruce["speeches"] == 3
    assert bruce["mentions"] >= 2  # « Bruce ? » et « Je m'appelle Bruce »
    # Document incomplet : « première apparition » rétrogradée en interprétation.
    assert {fa["level"] for fa in bruce["first_appearances"]} == {"INTERPRETATION"}

    [contradiction] = report["contradiction_candidates"]
    assert contradiction["value"] == "32 / 40"
    assert contradiction["level"] == "INTERPRETATION"
    pages = {(e["document_id"], e["page"], e["role"]) for e in contradiction["evidence"]}
    assert pages == {(str(tome1), 2, "SUPPORTS"), (str(tome2), 1, "REFUTES")}

    speeches = env.forensic.observations(env.ids, kind="SPEECH")
    assert {o["level"] for o in speeches} == {"CANON"}  # attribution validée par un humain
    assert all(o["evidence"] and o["evidence"][0]["excerpt"] for o in speeches)


def test_rerun_is_idempotent_and_corrections_supersede(
    env: SimpleNamespace, db_engine: Engine
) -> None:
    tome1 = env.ids[0]
    env.vision.save_human_transcription(tome1, 1, [say("J'ai 32 ans.", "Bruce")], author="moi")
    env.forensic.analyze([tome1])
    _, second = env.forensic.analyze([tome1])
    assert second["new"] == 0  # aucune duplication

    # Correction : la réplique était mal transcrite. L'ancienne version est conservée en base
    # mais ses observations ne sont plus servies.
    env.vision.save_human_transcription(tome1, 1, [say("J'ai 23 ans.", "Bruce")], author="moi")
    env.forensic.analyze([tome1])
    claims = env.forensic.observations([tome1], kind="CLAIM")
    assert [c["value"] for c in claims] == ["23"]
    with db_engine.connect() as conn:
        total = conn.execute(
            text("SELECT count(*) FROM observation WHERE kind = 'CLAIM'")
        ).scalar_one()
        analyses = conn.execute(
            text("SELECT count(*) FROM page_analysis WHERE provider = 'human'")
        ).scalar_one()
    assert (total, analyses) == (2, 2)  # historique intact


def test_complete_only_when_every_page_is_transcribed(env: SimpleNamespace) -> None:
    tome2 = env.ids[1]
    env.vision.save_human_transcription(tome2, 1, [say("Bonjour.", "Alfred")], author="moi")
    env.forensic.analyze([tome2])
    assert env.forensic.report([tome2])["status"] == "INCOMPLETE"
    env.vision.save_human_transcription(tome2, 2, [say("Au revoir.", "Alfred")], author="moi")
    env.forensic.analyze([tome2])
    report = env.forensic.report([tome2])
    assert report["status"] == "COMPLETE"
    assert report["characters"]["Alfred"]["first_appearances"][0]["level"] == "CANON"


def test_free_vision_run_then_forensic(env: SimpleNamespace) -> None:
    """Chaîne entièrement gratuite : analyse par fournisseur local (ici simulé) puis forensic."""
    tome1 = env.ids[0]
    _, estimate = env.vision.start([tome1], "fake", Decimal("0"))
    assert estimate.estimated_cost_usd == Decimal("0")
    asyncio.run(env.drain())
    report = env.forensic.report([tome1])
    assert report["documents"][str(tome1)]["missing_pages"] == []


def test_invalid_human_input(env: SimpleNamespace) -> None:
    with pytest.raises(ValueError, match="case 9"):
        env.vision.save_human_transcription(env.ids[0], 1, [say("x", panel=9)], author="moi")
    with pytest.raises(LookupError):
        env.vision.save_human_transcription(env.ids[0], 99, [say("x")], author="moi")
