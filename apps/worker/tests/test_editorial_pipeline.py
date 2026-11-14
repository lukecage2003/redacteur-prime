"""Chief Editor de bout en bout, coût nul : missions, agents, confrontation, approbation."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import Engine, text

from primestone.ai_gateway import FakeLLMProvider
from primestone.comic import ImportSource, LibraryService, RenderProfile
from primestone.editorial import AGENTS, EditorialError, EditorialService
from primestone.editorial.agents import AgentSpec
from primestone.forensic import forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import KnowledgeService
from primestone.storage import LocalObjectStore
from primestone.vision import TextKind
from primestone.vision.providers import FakeVisionProvider
from primestone.vision.service import HumanText, VisionService
from primestone_worker.editorial import register_editorial_handlers
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
            ImportSource(path=comic_factory.pdf(pages=3), filename="t2.pdf", title="Nuit noire #2"),
        ]
    )
    registry = default_registry()
    register_library_handlers(registry, library)
    worker = Worker(queue, registry, worker_id="t", retry_delay_seconds=0)

    def drain() -> None:
        async def run() -> None:
            for _ in range(3):
                while await worker.run_once():
                    pass

        asyncio.run(run())

    drain()
    t1, t2 = (i.document_id for i in result.items)
    vision = VisionService(db_engine, store, queue, lambda _n: FakeVisionProvider())
    vision.save_human_transcription(
        t1,
        1,
        [
            say("Je m'appelle Selina. J'ai 28 ans.", "Selina"),
            say("Selina ? Encore toi ?", "Bruce", 2),
        ],
        author="moi",
    )
    vision.save_human_transcription(t1, 2, [say("Je suis Catwoman.", "Selina", 2)], author="moi")
    vision.save_human_transcription(t2, 1, [say("J'ai 31 ans, idiot.", "Selina")], author="moi")
    forensic = forensic_service(db_engine)
    knowledge = KnowledgeService(db_engine, forensic)

    def service(writer: FakeLLMProvider | None = None) -> EditorialService:
        svc = EditorialService(
            db_engine, forensic, knowledge, queue, (lambda: writer) if writer else None
        )
        register_editorial_handlers(
            registry, svc
        ) if "editorial.run_mission" not in registry.names() else None
        registry._handlers["editorial.run_mission"] = lambda p: svc.run_mission(p)
        return svc

    return SimpleNamespace(service=service, drain=drain, t1=t1, t2=t2, engine=db_engine)


def test_character_dossier_end_to_end(env: SimpleNamespace) -> None:
    svc = env.service()
    mission_id = svc.create_mission("CHARACTER_DOSSIER", [env.t1, env.t2], {"character": "Selina"})
    env.drain()
    mission = svc.mission(mission_id)

    assert mission["status"] == "AWAITING_APPROVAL"
    assert [t["status"] for t in mission["tasks"]] == ["SUCCEEDED"] * 5
    result = mission["result"]
    dossier = result["deliverable"]
    assert dossier.startswith("# Dossier : Selina")
    assert "« Je suis Catwoman. » [Nuit noire #1, p. 2, case 2]" in dossier
    # Une réplique qui porte deux affirmations (âge et identité) n'est citée qu'une fois.
    assert dossier.count("Selina affirme : « Je m'appelle Selina. J'ai 28 ans. »") == 1
    # Libellés lisibles, vus depuis le personnage.
    assert "Selina — cité dans Nuit noire #1" in dossier
    assert "Selina — se présente comme Catwoman" in dossier
    # Le dossier du Chief Editor est lui-même vérifié : aucune erreur majeure.
    assert result["fact_check"]["verdict"] in ("PASS", "NEEDS_REVIEW")
    assert result["fact_check"]["counts"]["VERIFIED"] >= 3
    # Confrontation : pages manquantes et contradiction d'âge signalées.
    assert any("Pages non transcrites" in f for f in result["findings"])
    assert any("contradiction" in f for f in result["findings"])
    assert result["recommendation"] == "VALIDER AVEC RÉSERVES"
    [approval] = mission["approvals"]
    assert approval["status"] == "PENDING"
    assert {r["provider"] for r in mission["agent_runs"]} == {"deterministe"}
    assert all(r["cost_usd"] == "0.000000" for r in mission["agent_runs"])

    svc.decide(UUID(approval["id"]), approve=True, author="moi", comment="ok, réserves notées")
    assert svc.mission(mission_id)["status"] == "APPROVED"
    with pytest.raises(EditorialError, match="déjà traitée"):
        svc.decide(UUID(approval["id"]), approve=False, author="moi", comment=None)


def test_fact_check_mission_blocks_false_text(env: SimpleNamespace) -> None:
    svc = env.service()
    draft = (
        "Selina se présente comme Batman : « Je suis Batman. » [Nuit noire #1, p. 2]. "
        "Selina a 40 ans selon le tome 1."
    )
    mission_id = svc.create_mission("FACT_CHECK", [env.t1, env.t2], {"draft": draft})
    env.drain()
    mission = svc.mission(mission_id)
    result = mission["result"]
    assert result["fact_check"]["verdict"] == "FAIL"
    assert [c["status"] for c in result["fact_check"]["checks"]] == [
        "QUOTE_NOT_FOUND",
        "CONFLICTS_WITH_EVIDENCE",
    ]
    assert result["recommendation"] == "NE PAS VALIDER"
    approval = UUID(mission["approvals"][0]["id"])
    with pytest.raises(EditorialError, match="erreur factuelle majeure"):
        svc.decide(approval, approve=True, author="moi", comment=None)
    svc.decide(approval, approve=False, author="moi", comment="à corriger")
    assert svc.mission(mission_id)["status"] == "REJECTED"


def test_local_writer_is_kept_only_if_it_passes_the_fact_checker(env: SimpleNamespace) -> None:
    # Un « modèle » qui déforme une citation : son texte est écarté, le gabarit est gardé.
    liar = FakeLLMProvider(
        responses={
            "editorial.dossier_writer": "Selina avoue : « Je suis Batman. » [Nuit noire #1, p. 2]."
        }
    )
    svc = env.service(liar)
    mission_id = svc.create_mission("CHARACTER_DOSSIER", [env.t1], {"character": "Selina"})
    env.drain()
    result = svc.mission(mission_id)["result"]
    assert result["author"] == "gabarit déterministe"
    assert any("Rédaction par modèle écartée" in f for f in result["findings"])
    runs = svc.mission(mission_id)["agent_runs"]
    writer_run = next(r for r in runs if r["agent"] == "chief_editor_writer")
    assert (writer_run["provider"], writer_run["cost_usd"]) == ("fake", "0.000000")
    assert writer_run["error"].startswith("rejeté par le vérificateur")


def test_critical_failure_stops_the_mission(env: SimpleNamespace) -> None:
    svc = env.service()
    mission_id = svc.create_mission("CHARACTER_DOSSIER", [env.t1], {"character": "Personne"})
    env.drain()
    mission = svc.mission(mission_id)
    assert mission["status"] == "FAILED"
    assert "personnage inconnu" in mission["error"]
    statuses = [t["status"] for t in mission["tasks"]]
    assert statuses == ["SUCCEEDED", "FAILED", "SKIPPED", "SKIPPED", "SKIPPED"]
    assert mission["tasks"][1]["attempts"] == 2
    assert mission["approvals"] == []


def test_non_critical_failure_degrades_but_continues(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(ctx: object, inputs: object) -> dict[str, object]:
        raise RuntimeError("panne simulée")

    original = AGENTS["comics_analyst"]
    monkeypatch.setitem(
        AGENTS,
        "comics_analyst",
        AgentSpec(original.key, original.name, original.role, original.limits, 6, broken),
    )
    svc = env.service()
    mission_id = svc.create_mission("CONTINUITY_AUDIT", [env.t1, env.t2], {})
    env.drain()
    mission = svc.mission(mission_id)
    assert mission["status"] == "AWAITING_APPROVAL"
    assert [t["status"] for t in mission["tasks"]] == [
        "SUCCEEDED",
        "FAILED",
        "SUCCEEDED",
        "SUCCEEDED",
        "SUCCEEDED",
    ]
    assert any("Comics Analyst en échec" in f for f in mission["result"]["findings"])
    assert "Selina — contradiction possible (age)" in mission["result"]["deliverable"]


def test_resume_after_interruption(env: SimpleNamespace) -> None:
    svc = env.service()
    mission_id = svc.create_mission("CONTINUITY_AUDIT", [env.t1, env.t2], {})
    env.drain()
    # Simule un arrêt brutal après les deux premières tâches.
    with env.engine.begin() as conn:
        conn.execute(
            text("UPDATE mission SET status = 'RUNNING', result = NULL WHERE id = :m"),
            {"m": mission_id},
        )
        conn.execute(
            text(
                "UPDATE mission_task SET status = 'PENDING', output = NULL "
                "WHERE mission_id = :m AND position > 2"
            ),
            {"m": mission_id},
        )
        conn.execute(text("DELETE FROM approval_request WHERE mission_id = :m"), {"m": mission_id})
    asyncio.run(svc.run_mission({"mission_id": str(mission_id)}))
    mission = svc.mission(mission_id)
    assert mission["status"] == "AWAITING_APPROVAL"
    assert [t["attempts"] for t in mission["tasks"]][:2] == [1, 1]  # pas rejouées


def test_validation(env: SimpleNamespace) -> None:
    svc = env.service()
    with pytest.raises(EditorialError, match="inconnu"):
        svc.create_mission("NOPE", [env.t1], {})
    with pytest.raises(EditorialError, match="character"):
        svc.create_mission("CHARACTER_DOSSIER", [env.t1], {})
    with pytest.raises(EditorialError, match="document"):
        svc.create_mission("CONTINUITY_AUDIT", [], {})
    agents = {a["key"]: a for a in svc.agents()}
    assert agents["fact_checker"]["available"] is True
    assert agents["story_architect"]["available"] is False
    assert agents["story_architect"]["phase"] == 10
    assert Decimal("0") == Decimal("0")
