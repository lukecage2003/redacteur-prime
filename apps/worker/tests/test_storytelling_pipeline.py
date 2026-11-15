"""Scripts de bout en bout (coût nul) : versions, étapes, notation, veto, adaptation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pypdfium2 as pdfium
import pytest
from sqlalchemy import Engine

from primestone.comic import ImportSource, LibraryService, RenderProfile
from primestone.jobs import PostgresJobQueue
from primestone.storage import LocalObjectStore
from primestone.storytelling import ScriptError, read_script_file, storytelling_service
from primestone.vision import TextKind
from primestone.vision.providers import FakeVisionProvider
from primestone.vision.service import HumanText, VisionService
from primestone_worker.handlers import default_registry
from primestone_worker.library import register_library_handlers
from primestone_worker.main import Worker

pytestmark = pytest.mark.integration

GOOD = """00:00 - Introduction
Et si Selina n'était pas celle que vous croyez ? Dans Nuit noire, tout tient en une phrase.
Pourtant, personne ne la remarque.

01:00 - L'aveu
Selina le dit elle-même : « Je suis Catwoman. » [Nuit noire #1, p. 1, case 1].
Mais pourquoi l'avouer si tôt ? Vous allez voir que la réponse est dans la case suivante.

02:00 - Conclusion
En résumé, l'aveu change tout. Et vous, l'aviez-vous remarqué ?"""


@pytest.fixture
def env(db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace) -> SimpleNamespace:
    store = LocalObjectStore(tmp_path / "storage")
    queue = PostgresJobQueue(db_engine)
    library = LibraryService(db_engine, store, queue, profile=RenderProfile(max_dimension=600))
    result = library.start_import(
        [ImportSource(path=comic_factory.pdf(pages=2), filename="t.pdf", title="Nuit noire #1")]
    )
    registry = default_registry()
    register_library_handlers(registry, library)
    worker = Worker(queue, registry, worker_id="t", retry_delay_seconds=0)

    async def drain() -> None:
        for _ in range(3):
            while await worker.run_once():
                pass

    asyncio.run(drain())
    doc = result.items[0].document_id
    VisionService(
        db_engine, store, queue, lambda _n: FakeVisionProvider()
    ).save_human_transcription(
        doc,
        1,
        [
            HumanText(
                text="Je suis Catwoman.", kind=TextKind.DIALOGUE, panel_index=1, speaker="Selina"
            )
        ],
        author="moi",
    )
    return SimpleNamespace(service=storytelling_service(db_engine), doc=doc)


def test_script_lifecycle(env: SimpleNamespace) -> None:
    svc = env.service
    script_id = svc.create(
        title="L'aveu de Selina", language="fr", content=GOOD, author="moi", document_ids=[env.doc]
    )
    svc.move(script_id, "DRAFT", author="moi")
    svc.move(script_id, "HOOK", author="moi", reason="accroche à reprendre")  # retour arrière
    with pytest.raises(ScriptError, match="validate"):
        svc.move(script_id, "FINAL_VALIDATION", author="moi")
    with pytest.raises(ScriptError, match="évaluée"):
        svc.validate(script_id, author="moi")

    good = svc.evaluate(script_id)
    assert good["factual_veto"] is False
    assert good["analysis"]["fact_check"]["counts"]["VERIFIED"] == 1
    assert good["total"] >= 70, good["criteria"]

    # Une version avec une citation fausse : veto, validation impossible quel que soit le score.
    bad = GOOD.replace("Je suis Catwoman.", "Je suis Batman.")
    svc.add_version(script_id, bad, author="moi")
    vetoed = svc.evaluate(script_id)
    assert vetoed["factual_veto"] is True
    with pytest.raises(ScriptError, match="veto"):
        svc.validate(script_id, author="moi")

    svc.add_version(script_id, GOOD, author="moi")
    svc.evaluate(script_id)
    svc.validate(script_id, author="moi")
    detail = svc.script(script_id)
    assert (detail["status"], detail["step"]) == ("VALIDATED", "FINAL_VALIDATION")
    assert [v["number"] for v in detail["versions"]] == [1, 2, 3]  # rien n'est effacé
    assert [s["factual_veto"] for s in detail["scores"]] == [False, True, False]
    assert [e["action"] for e in detail["events"]][:3] == ["CREATED", "VERSION_ADDED", "STEP"]
    with pytest.raises(ScriptError, match="validé"):
        svc.add_version(script_id, GOOD, author="moi")

    english = svc.adapt(
        script_id, content=GOOD.replace("Et si", "What if"), title=None, author="moi"
    )
    adapted = svc.script(english)
    assert (adapted["language"], adapted["step"], adapted["adapted_from"]) == (
        "en",
        "ADAPTATION",
        str(script_id),
    )
    assert svc.script(script_id)["adaptations"] == [str(english)]
    assert {s["title"] for s in svc.scripts()} == {"L'aveu de Selina", "L'aveu de Selina (EN)"}


def test_read_pdf_script(tmp_path: Path) -> None:
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(200, 200)
    path = tmp_path / "script.pdf"
    pdf.save(path)
    assert read_script_file(path) == ""  # page sans texte : extraction vide, pas d'erreur
    md = tmp_path / "s.md"
    md.write_text("# Titre\ntexte", encoding="utf-8")
    assert read_script_file(md).startswith("# Titre")


def test_script_review_mission(env: SimpleNamespace, db_engine: Engine) -> None:
    from primestone.editorial import EditorialService
    from primestone.forensic import forensic_service
    from primestone.knowledge import KnowledgeService

    forensic = forensic_service(db_engine)
    editorial = EditorialService(
        db_engine,
        forensic,
        KnowledgeService(db_engine, forensic),
        PostgresJobQueue(db_engine),
        storytelling=env.service,
    )
    script_id = env.service.create(
        title="Aveu",
        language="fr",
        content=GOOD.replace("Catwoman", "Batman"),
        author="moi",
        document_ids=[env.doc],
    )
    mission_id = editorial.create_mission("SCRIPT_REVIEW", [], {"script_id": str(script_id)})
    asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
    mission = editorial.mission(mission_id)
    result = mission["result"]
    assert mission["title"] == "Critique du script : Aveu"
    assert result["recommendation"] == "NE PAS VALIDER"
    assert result["fact_check"]["verdict"] == "FAIL"
    assert result["deliverable"].startswith("# Critique du script : Aveu (version 1)")
    assert "VETO FACTUEL" in result["deliverable"]
    # Même avec une approbation humaine demandée, un veto bloque la validation.
    from primestone.editorial import EditorialError

    with pytest.raises(EditorialError, match="erreur factuelle"):
        editorial.decide(
            UUID(mission["approvals"][0]["id"]), approve=True, author="moi", comment=None
        )
    with pytest.raises(EditorialError, match="introuvable"):
        editorial.create_mission("SCRIPT_REVIEW", [], {"script_id": "nope"})


def test_level_variants_share_the_same_fact_check(env: SimpleNamespace) -> None:
    svc = env.service
    base = svc.create(
        title="Aveu",
        language="fr",
        content=GOOD,
        author="moi",
        document_ids=[env.doc],
        level="EXPLORATION",
    )
    discovery = svc.variant(
        base,
        level="DISCOVERY",
        content=GOOD.replace("Catwoman", "Batman"),
        title=None,
        author="moi",
    )
    detail = svc.script(discovery)
    assert (detail["level"], detail["level_of"]) == ("DISCOVERY", str(base))
    result = svc.evaluate(discovery)
    assert result["factual_veto"] is True  # l'accessibilité n'excuse jamais une erreur
    assert result["analysis"]["level_checks"]["level"] == "DISCOVERY"
    assert result["analysis"]["retention"]["method"] == "script-retention@1"
    with pytest.raises(ScriptError, match="niveau"):
        svc.create(title="x", language="fr", content="x", author="moi", level="EXPERT")
