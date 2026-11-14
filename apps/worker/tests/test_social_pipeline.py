"""Social Intelligence de bout en bout, coût nul : dossier approuvé → déclinaisons vérifiées."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import Engine

from primestone.comic import ImportSource, LibraryService, RenderProfile
from primestone.editorial import EditorialError, EditorialService
from primestone.forensic import forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import KnowledgeService
from primestone.market import MarketService
from primestone.storage import LocalObjectStore
from primestone.vision import TextKind
from primestone.vision.providers import FakeVisionProvider
from primestone.vision.service import HumanText, VisionService
from primestone_worker.handlers import default_registry
from primestone_worker.library import register_library_handlers
from primestone_worker.main import Worker

pytestmark = pytest.mark.integration


def say(content: str, speaker: str, panel: int = 1) -> HumanText:
    return HumanText(text=content, kind=TextKind.DIALOGUE, panel_index=panel, speaker=speaker)


@pytest.fixture
def env(db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace) -> SimpleNamespace:
    store = LocalObjectStore(tmp_path / "storage")
    queue = PostgresJobQueue(db_engine)
    library = LibraryService(db_engine, store, queue, profile=RenderProfile(max_dimension=600))
    result = library.start_import(
        [
            ImportSource(path=comic_factory.pdf(pages=2), filename="t1.pdf", title="Nuit noire #1"),
            ImportSource(path=comic_factory.pdf(pages=2), filename="t2.pdf", title="Nuit noire #2"),
        ]
    )
    registry = default_registry()
    register_library_handlers(registry, library)
    worker = Worker(queue, registry, worker_id="t", retry_delay_seconds=0)

    async def drain() -> None:
        for _ in range(3):
            while await worker.run_once():
                pass

    asyncio.run(drain())
    t1, t2 = (i.document_id for i in result.items)
    vision = VisionService(db_engine, store, queue, lambda _n: FakeVisionProvider())
    vision.save_human_transcription(
        t1, 1, [say("Je m'appelle Selina. J'ai 28 ans.", "Selina")], author="moi"
    )
    vision.save_human_transcription(t1, 2, [say("Je suis Catwoman.", "Selina", 2)], author="moi")
    vision.save_human_transcription(t2, 1, [say("J'ai 31 ans, idiot.", "Selina")], author="moi")
    vision.save_human_transcription(t2, 2, [say("Selina ? Encore toi ?", "Bruce")], author="moi")
    forensic = forensic_service(db_engine)
    market = MarketService(db_engine)
    editorial = EditorialService(
        db_engine, forensic, KnowledgeService(db_engine, forensic), queue, market=market
    )

    def run(mission_id: UUID) -> dict:
        asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
        return editorial.mission(mission_id)

    return SimpleNamespace(editorial=editorial, market=market, run=run, t1=t1, t2=t2)


def test_social_package_from_approved_dossier(env: SimpleNamespace) -> None:
    editorial: EditorialService = env.editorial
    dossier_id = editorial.create_mission(
        "CHARACTER_DOSSIER", [env.t1, env.t2], {"character": "Selina"}
    )
    dossier = env.run(dossier_id)
    with pytest.raises(EditorialError, match="approuvé"):
        editorial.create_mission("SOCIAL_PACKAGE", [], {"source_mission_id": str(dossier_id)})
    editorial.decide(UUID(dossier["approvals"][0]["id"]), approve=True, author="moi", comment=None)

    env.market.add_topic("Selina", keywords_fr=["selina"], keywords_en=["selina"], author="moi")
    social_id = editorial.create_mission(
        "SOCIAL_PACKAGE", [], {"source_mission_id": str(dossier_id)}
    )
    mission = env.run(social_id)
    assert mission["title"] == "Déclinaisons sociales : Dossier : Selina"
    assert mission["document_ids"] == dossier["document_ids"]
    assert [t["status"] for t in mission["tasks"]] == ["SUCCEEDED"] * 4
    result = mission["result"]
    package = result["deliverable"]
    assert package.startswith("# Déclinaisons sociales : Dossier : Selina")
    for heading in (
        "## YouTube (vidéo longue)",
        "## TikTok",
        "## Instagram Reels",
        "## Instagram (carrousel)",
    ):
        assert heading in package
    # La tension (contradiction d'âge) ouvre la vidéo de découverte, mot pour mot.
    tiktok = package.split("## TikTok")[1].split("## Instagram Reels")[0]
    assert tiktok.split("### Accroche (3 premières secondes)\n")[1].startswith(
        "Contradiction possible (age) : « J'ai 31 ans, idiot. » [Nuit noire #2, p. 1, case 1]"
    )
    # Le paquet repasse le Fact Checker : aucune erreur, chaque fait reste vérifié.
    assert result["fact_check"]["verdict"] in ("PASS", "NEEDS_REVIEW")
    assert result["fact_check"]["counts"]["VERIFIED"] >= 4
    assert "QUOTE_NOT_FOUND" not in result["fact_check"]["counts"]
    assert any("à revérifier" in f for f in result["findings"])
    assert result["recommendation"] in ("VALIDER", "VALIDER AVEC RÉSERVES")

    with pytest.raises(EditorialError, match="ne se décline pas"):
        editorial.create_mission("SOCIAL_PACKAGE", [], {"source_mission_id": str(social_id)})
    with pytest.raises(EditorialError, match="introuvable"):
        editorial.create_mission("SOCIAL_PACKAGE", [], {"source_mission_id": "nope"})
