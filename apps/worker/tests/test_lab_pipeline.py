"""Laboratoire des théories, coût nul : preuves vérifiées, contre-preuves, journal, revue."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from primestone.comic import ImportSource, LibraryService, RenderProfile
from primestone.editorial import EditorialError, EditorialService
from primestone.forensic import forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import KnowledgeService
from primestone.lab import LabError, TheoryLab
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
            say("Le masque reste dans la tour.", "Bruce", 2),
        ],
        author="moi",
    )
    vision.save_human_transcription(t1, 2, [say("Je suis Catwoman.", "Selina", 2)], author="moi")
    vision.save_human_transcription(t2, 1, [say("J'ai 31 ans, idiot.", "Selina")], author="moi")
    forensic = forensic_service(db_engine)
    knowledge = KnowledgeService(db_engine, forensic)
    forensic.analyze([t1, t2], {"Selina", "Bruce"})
    knowledge.build([t1, t2])
    lab = TheoryLab(db_engine, forensic, knowledge)
    editorial = EditorialService(db_engine, forensic, knowledge, queue, lab=lab)
    register_editorial_handlers(registry, editorial)
    return SimpleNamespace(
        lab=lab, editorial=editorial, drain=drain, t1=t1, t2=t2, vision=vision, engine=db_engine
    )


def new_theory(env: SimpleNamespace) -> UUID:
    return env.lab.create(
        title="Selina est Catwoman",
        claim="Selina et Catwoman sont la même personne.",
        document_ids=[env.t1, env.t2],
        subjects=["Selina"],
        author="moi",
    )


def test_theory_lifecycle_with_verified_evidence(env: SimpleNamespace) -> None:
    lab: TheoryLab = env.lab
    theory_id = new_theory(env)
    assert lab.theory(theory_id)["level"] == "SPECULATION"

    added = lab.add_evidence(
        theory_id,
        role="SUPPORTS",
        document_id=env.t1,
        page=2,
        panel=2,
        excerpt="Je suis Catwoman",
        author="moi",
    )
    assert added["verified"] is True
    # Sans recherche de contre-preuves : jamais THEORY, confiance plafonnée.
    assert (added["level"], added["status"]) == ("SPECULATION", "SUPPORTED")

    research = lab.research(theory_id)
    assert research["level"] == "THEORY"
    # Le passage déjà cité n'est pas reproposé ; la contradiction d'âge est proposée.
    assert all("Catwoman" not in p["content"] for p in research["passages"])
    assert research["possible_counter_evidence"]
    assert {c["predicate"] for c in research["claims"]} >= {"age"}

    # Un extrait absent de la page transcrite est refusé (traçabilité).
    with pytest.raises(LabError, match="absent"):
        lab.add_evidence(
            theory_id,
            role="SUPPORTS",
            document_id=env.t1,
            page=2,
            excerpt="Je suis Batman",
            author="moi",
        )
    # Page non transcrite : acceptée mais non vérifiée (et donc non solide).
    unverified = lab.add_evidence(
        theory_id,
        role="REFUTES",
        document_id=env.t2,
        page=3,
        excerpt="Tu n'es pas elle",
        author="moi",
    )
    assert (unverified["verified"], unverified["status"]) == (False, "CONTESTED")
    with pytest.raises(LabError, match="note"):
        lab.add_evidence(
            theory_id,
            role="SUPPORTS",
            document_id=env.t1,
            page=1,
            level="INTERPRETATION",
            author="moi",
        )
    with pytest.raises(LabError, match="inexistante"):
        lab.add_evidence(theory_id, role="SUPPORTS", document_id=env.t1, page=9, author="moi")
    lab.add_alternative(theory_id, text_="Catwoman est un surnom donné par Bruce.", author="moi")

    after = lab.retract_evidence(UUID(unverified["id"]), author="moi", reason="lecture erronée")
    assert after["status"] == "SUPPORTED"
    with pytest.raises(LabError, match="déjà"):
        lab.retract_evidence(UUID(unverified["id"]), author="moi", reason="encore")

    theory = lab.theory(theory_id)
    assert [e["action"] for e in theory["events"]] == [
        "CREATED",
        "EVIDENCE_ADDED",
        "COUNTER_SEARCH",
        "EVIDENCE_ADDED",
        "ALTERNATIVE_ADDED",
        "EVIDENCE_RETRACTED",
    ]
    # Rien n'est effacé : la preuve retirée reste visible, avec son motif.
    retracted = [e for e in theory["evidence"] if e["retracted_at"]]
    assert retracted[0]["retraction_reason"] == "lecture erronée"
    assert theory["scoring"]["method"] == "lab-confidence@1"
    assert [t["id"] for t in lab.theories(level="THEORY")] == [str(theory_id)]

    # Une transcription corrigée rend la preuve obsolète : signalé, jamais effacé.
    env.vision.save_human_transcription(
        env.t1, 2, [say("Je ne suis personne.", "Selina", 2)], author="moi"
    )
    stale = [e for e in lab.theory(theory_id)["evidence"] if not e["retracted_at"]]
    assert stale[0]["still_found"] is False
    with env.engine.connect() as conn, pytest.raises(IntegrityError, match="ck_theory_level"):
        conn.execute(text("UPDATE theory SET level = 'CANON' WHERE id = :t"), {"t": theory_id})


def test_theory_review_and_research_missions(env: SimpleNamespace) -> None:
    lab: TheoryLab = env.lab
    theory_id = new_theory(env)
    lab.add_evidence(
        theory_id,
        role="SUPPORTS",
        document_id=env.t1,
        page=2,
        panel=2,
        excerpt="Je suis Catwoman",
        author="moi",
    )
    lab.add_alternative(theory_id, text_="Un simple déguisement.", author="moi")
    mission_id = env.editorial.create_mission("THEORY_REVIEW", [], {"theory_id": str(theory_id)})
    env.drain()
    mission = env.editorial.mission(mission_id)
    assert mission["title"] == "Revue de théorie : Selina est Catwoman"
    assert [t["status"] for t in mission["tasks"]] == ["SUCCEEDED"] * 4
    result = mission["result"]
    review = result["deliverable"]
    assert review.startswith("# Revue de théorie : Selina est Catwoman")
    assert "Élément pour (CANON) : « Je suis Catwoman » [Nuit noire #1, p. 2, case 2]." in review
    assert "Note : alternative : Un simple déguisement." in review
    assert "Contre-preuve possible (age)" in review
    assert result["fact_check"]["verdict"] in ("PASS", "NEEDS_REVIEW")
    assert result["fact_check"]["counts"]["VERIFIED"] >= 2
    assert any("MAINTENIR EN THÉORIE" in f for f in result["findings"])
    assert lab.theory(theory_id)["level"] == "THEORY"

    research_id = env.editorial.create_mission(
        "RESEARCH_DOSSIER", [env.t1, env.t2], {"question": "Quel âge a Selina ?"}
    )
    env.drain()
    dossier = env.editorial.mission(research_id)["result"]
    assert dossier["deliverable"].startswith("# Dossier de recherche : Quel âge a Selina ?")
    assert "« J'ai 31 ans, idiot. » [Nuit noire #2, p. 1, case 1]" in dossier["deliverable"]
    assert dossier["fact_check"]["verdict"] != "FAIL"

    with pytest.raises(EditorialError, match="théorie introuvable"):
        env.editorial.create_mission("THEORY_REVIEW", [], {"theory_id": "nope"})
    with pytest.raises(EditorialError, match="question"):
        env.editorial.create_mission("RESEARCH_DOSSIER", [env.t1], {"question": " "})
