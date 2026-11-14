"""Knowledge de bout en bout, coût nul : transcription → forensique → entités/relations →
corrections → graphe → recherche hybride."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import Engine, text

from primestone.comic import ImportSource, LibraryService, RenderProfile
from primestone.forensic import forensic_service
from primestone.jobs import PostgresJobQueue
from primestone.knowledge import KnowledgeError, KnowledgeService, ManualEvidence, hybrid_search
from primestone.provenance import EvidenceLevel
from primestone.storage import LocalObjectStore
from primestone.vision import TextKind
from primestone.vision.providers import FakeVisionProvider
from primestone.vision.service import HumanText, VisionService
from primestone_worker.handlers import default_registry
from primestone_worker.library import register_library_handlers
from primestone_worker.main import Worker

pytestmark = pytest.mark.integration


def say(content: str, speaker: str | None, panel: int = 1) -> HumanText:
    return HumanText(text=content, kind=TextKind.DIALOGUE, panel_index=panel, speaker=speaker)


@pytest.fixture
def kb(db_engine: Engine, tmp_path: Path, comic_factory: SimpleNamespace) -> SimpleNamespace:
    store = LocalObjectStore(tmp_path / "storage")
    queue = PostgresJobQueue(db_engine)
    library = LibraryService(db_engine, store, queue, profile=RenderProfile(max_dimension=600))
    sources = [
        ImportSource(
            path=comic_factory.pdf(pages=2),
            filename="t1.pdf",
            title="Nuit noire #1",
            series_title="Nuit noire",
            issue_number="1",
        ),
        ImportSource(
            path=comic_factory.pdf(pages=2),
            filename="t2.pdf",
            title="Nuit noire #2",
            series_title="Nuit noire",
            issue_number="2",
        ),
    ]
    result = library.start_import(sources)
    registry = default_registry()
    register_library_handlers(registry, library)
    worker = Worker(queue, registry, worker_id="t")

    async def drain() -> None:
        for _ in range(3):
            while await worker.run_once():
                pass

    asyncio.run(drain())
    t1, t2 = (i.document_id for i in result.items)
    vision = VisionService(db_engine, store, queue, lambda _n: FakeVisionProvider())
    vision.save_human_transcription(
        t1,
        1,
        [
            say("Je m'appelle Selina.", "Selina", 1),
            say("Selina ? Encore toi, Batman te cherche.", "Bruce", 1),
        ],
        author="moi",
    )
    vision.save_human_transcription(t1, 2, [say("Je suis Catwoman.", "Selina", 2)], author="moi")
    vision.save_human_transcription(t2, 1, [say("Où est Batman ?", "Cat-Woman", 1)], author="moi")
    forensic = forensic_service(db_engine)
    forensic.analyze([t1, t2], {"Batman"})
    service = KnowledgeService(db_engine, forensic)
    stats = service.build([t1, t2])
    return SimpleNamespace(
        service=service,
        vision=vision,
        forensic=forensic,
        t1=t1,
        t2=t2,
        stats=stats,
        engine=db_engine,
    )


def find(kb: SimpleNamespace, name: str, type_: str = "CHARACTER") -> dict:  # type: ignore[type-arg]
    [entity] = [e for e in kb.service.entities(type_=type_) if e["canonical_name"] == name]
    return kb.service.entity(UUID(entity["id"]))  # type: ignore[no-any-return]


def relation(entity: dict, type_: str, other: str) -> dict:  # type: ignore[type-arg]
    return next(
        r
        for r in entity["relations"]
        if r["type"] == type_ and other in (r["source"]["name"], r["target"]["name"])
    )


def test_entities_and_proven_relations(kb: SimpleNamespace) -> None:
    names = {(e["type"], e["canonical_name"]) for e in kb.service.entities()}
    assert {
        ("CHARACTER", "Selina"),
        ("CHARACTER", "Bruce"),
        ("CHARACTER", "Catwoman"),
        ("CHARACTER", "Batman"),
        ("COMIC", "Nuit noire #1"),
        ("SERIES", "Nuit noire"),
    } <= names

    selina = find(kb, "Selina")
    appears = relation(selina, "APPEARS_IN", "Nuit noire #1")
    assert appears["level"] == "CANON"  # elle parle, transcription humaine
    assert appears["evidence"]
    assert appears["evidence"][0]["page"] in (1, 2)
    reveals = relation(selina, "REVEALS", "Catwoman")
    assert (reveals["level"], reveals["qualifier"]) == ("INTERPRETATION", "se présente comme")
    assert relation(selina, "RELATED_TO", "Bruce")["qualifier"] == "parlent dans la même case"

    batman = find(kb, "Batman")
    referenced = relation(batman, "REFERENCES", "Nuit noire #1")
    assert referenced["source"]["name"] == "Nuit noire #1"  # cité, pas présent
    assert not [r for r in batman["relations"] if r["type"] == "APPEARS_IN"]
    for r in selina["relations"] + batman["relations"]:
        assert r["evidence"], f"relation sans preuve : {r}"


def test_rebuild_is_idempotent(kb: SimpleNamespace) -> None:
    with kb.engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM relation_evidence")).scalar_one()
    stats = kb.service.build([kb.t1, kb.t2])
    with kb.engine.connect() as conn:
        after = conn.execute(text("SELECT count(*) FROM relation_evidence")).scalar_one()
    assert stats["entities"] == 0
    assert stats["evidence"] == 0
    assert before == after


def test_corrections_are_logged_and_survive_rebuild(kb: SimpleNamespace) -> None:
    catwoman, variant = find(kb, "Catwoman"), find(kb, "Cat-Woman")
    kb.service.merge(
        UUID(catwoman["id"]), UUID(variant["id"]), author="moi", reason="même personnage"
    )
    kb.service.add_alias(
        UUID(catwoman["id"]), "Chatte", language="fr", author="moi", reason="nom VF"
    )
    kb.service.rename(
        UUID(catwoman["id"]), "Catwoman (Selina Kyle)", author="moi", reason="précision"
    )
    with pytest.raises(KnowledgeError, match="motivée"):
        kb.service.rename(UUID(catwoman["id"]), "X", author="moi", reason="  ")

    kb.service.build([kb.t1, kb.t2])
    names = [e["canonical_name"] for e in kb.service.entities(type_="CHARACTER")]
    assert "Cat-Woman" not in names  # la fusion tient après reconstruction
    merged = kb.service.entity(UUID(catwoman["id"]))
    assert {a["alias"] for a in merged["aliases"]} >= {"Catwoman", "Cat-Woman", "Chatte"}
    assert relation(merged, "APPEARS_IN", "Nuit noire #2")  # répliques de « Cat-Woman » rattachées
    assert [h["action"] for h in merged["history"]] == ["MERGE", "ADD_ALIAS", "RENAME"]
    assert kb.service.entity(UUID(variant["id"])) == {
        "id": variant["id"],
        "merged_into": catwoman["id"],
    }
    bruce = find(kb, "Bruce")
    with pytest.raises(KnowledgeError, match="autre entité"):
        kb.service.add_alias(
            UUID(bruce["id"]), "Chatte", language="fr", author="moi", reason="erreur"
        )


def test_retracted_relation_stays_retracted(kb: SimpleNamespace) -> None:
    selina = find(kb, "Selina")
    reveals = relation(selina, "REVEALS", "Catwoman")
    kb.service.retract_relation(UUID(reveals["id"]), author="moi", reason="ironie, pas un aveu")
    kb.service.build([kb.t1, kb.t2])
    again = relation(find(kb, "Selina"), "REVEALS", "Catwoman")
    assert again["retracted"] is True
    graph = kb.service.neighbors(UUID(selina["id"]))
    assert reveals["id"] not in {e["relation_id"] for e in graph["edges"]}
    with pytest.raises(KnowledgeError, match="déjà retirée"):
        kb.service.retract_relation(UUID(reveals["id"]), author="moi", reason="encore")


def test_manual_relation_requires_evidence(kb: SimpleNamespace) -> None:
    bruce, batman = find(kb, "Bruce"), find(kb, "Batman")
    with pytest.raises(KnowledgeError, match="sans preuve"):
        kb.service.create_relation(
            UUID(bruce["id"]),
            UUID(batman["id"]),
            "RELATED_TO",
            qualifier="x",
            level=EvidenceLevel.INTERPRETATION,
            evidence=[],
            author="moi",
            reason="r",
        )
    with pytest.raises(KnowledgeError, match="page 9"):
        kb.service.create_relation(
            UUID(bruce["id"]),
            UUID(batman["id"]),
            "RELATED_TO",
            qualifier="x",
            level=EvidenceLevel.INTERPRETATION,
            evidence=[ManualEvidence(kb.t1, 9)],
            author="moi",
            reason="r",
        )
    relation_id = kb.service.create_relation(
        UUID(bruce["id"]),
        UUID(batman["id"]),
        "OPPOSES",
        qualifier="rivalité supposée",
        level=EvidenceLevel.SPECULATION,
        evidence=[ManualEvidence(kb.t1, 1, 1, "Batman te cherche")],
        author="moi",
        reason="hypothèse de lecture",
    )
    created = relation(find(kb, "Bruce"), "OPPOSES", "Batman")
    assert (created["id"], created["origin"], created["level"]) == (
        str(relation_id),
        "HUMAN",
        "SPECULATION",
    )


def test_graph_neighbors_and_path(kb: SimpleNamespace) -> None:
    bruce, catwoman = find(kb, "Bruce"), find(kb, "Catwoman")
    graph = kb.service.neighbors(UUID(bruce["id"]), depth=1)
    near = {n["name"] for n in graph["nodes"] if n["distance"] == 1}
    assert {"Selina", "Nuit noire #1"} <= near
    path = kb.service.path(UUID(bruce["id"]), UUID(catwoman["id"]))
    assert path is not None
    assert path[0]["entity"]["name"] == "Bruce"
    assert path[-1]["entity"]["name"] == "Catwoman"
    assert all("via" in step for step in path[1:])


def test_hybrid_search_typos_and_supersession(kb: SimpleNamespace) -> None:
    embedder = kb.service.embedder
    exact = hybrid_search(kb.engine, embedder, "encore toi")
    assert exact[0]["content"] == "Selina ? Encore toi, Batman te cherche."
    assert exact[0]["fulltext_rank"] is not None
    typo = hybrid_search(kb.engine, embedder, "Catwomen")  # faute de frappe
    assert any("Catwoman" in r["content"] for r in typo[:3])
    scoped = hybrid_search(kb.engine, embedder, "Batman", document_ids=[kb.t2])
    assert all(r["document_id"] in (str(kb.t2), None) for r in scoped)

    # Correction de la transcription : l'ancienne version n'est plus trouvée.
    kb.vision.save_human_transcription(
        kb.t1, 2, [say("Je suis la Chatte.", "Selina", 2)], author="moi"
    )
    kb.service.index([kb.t1, kb.t2])
    results = hybrid_search(kb.engine, embedder, "Je suis Catwoman")
    assert not [r for r in results if r["kind"] == "TEXT" and r["content"] == "Je suis Catwoman."]
    assert hybrid_search(kb.engine, embedder, "   ") == []
