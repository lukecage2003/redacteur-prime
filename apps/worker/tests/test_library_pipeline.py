"""Pipeline Comic Library de bout en bout sur PostgreSQL réel.

Couvre les critères de validation de la phase 2 (ROADMAP.md) : lot de 50+ comics,
reprise après panne sans doublon ni perte, doublons, rejets, et règle « une page
manquante interdit COMPLETE ».
"""

from __future__ import annotations

import asyncio
import io
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import Engine, text

from primestone.comic import (
    ImportOutcome,
    ImportSource,
    LibraryService,
    Limits,
    RenderProfile,
)
from primestone.jobs import PostgresJobQueue
from primestone.storage import LocalObjectStore
from primestone_worker.handlers import default_registry
from primestone_worker.library import register_library_handlers
from primestone_worker.main import Worker

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def service(db_engine: Engine, tmp_path: Path) -> LibraryService:
    return LibraryService(
        db_engine,
        LocalObjectStore(tmp_path / "storage"),
        PostgresJobQueue(db_engine),
        limits=Limits(),
        profile=RenderProfile(max_dimension=160, webp_quality=60),
    )


def make_workers(service: LibraryService, engine: Engine, count: int = 1) -> list[Worker]:
    registry = default_registry()
    register_library_handlers(registry, service)
    queue = PostgresJobQueue(engine)
    return [Worker(queue, registry, worker_id=f"w{i}", retry_delay_seconds=0) for i in range(count)]


async def drain(workers: list[Worker]) -> None:
    async def loop(worker: Worker) -> None:
        while await worker.run_once():
            pass

    # Plusieurs passes : une étape de validation enfile ensuite les rendus.
    for _ in range(3):
        await asyncio.gather(*(loop(w) for w in workers))


def sources(*paths: Path, **kw: Any) -> list[ImportSource]:
    return [ImportSource(path=p, filename=p.name, **kw) for p in paths]


def document_statuses(engine: Engine) -> dict[str, str]:
    with engine.connect() as conn:
        return dict(
            conn.execute(  # type: ignore[arg-type]
                text("SELECT original_filename, status FROM document")
            ).all()
        )


async def test_single_pdf_end_to_end(
    service: LibraryService, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    result = service.start_import(sources(comic_factory.pdf(pages=4, name="a.pdf")))
    assert [i.outcome for i in result.items] == [ImportOutcome.NEW]

    await drain(make_workers(service, db_engine))

    report = service.batch_report(result.run_id)
    assert report is not None
    assert report["status"] == "SUCCEEDED"
    item = report["items"][0]
    assert (item["status"], item["page_count"], item["pages_rendered"]) == ("COMPLETE", 4, 4)
    assert report["totals"]["rendered_bytes"] > 0
    assert report["duration_seconds"] >= 0
    with db_engine.connect() as conn:
        dims = conn.execute(text("SELECT max(greatest(width, height)) FROM page")).scalar_one()
    assert dims == 160  # profil de rendu respecté


async def test_batch_of_55_comics_with_concurrent_workers(
    service: LibraryService, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    files = [comic_factory.pdf(pages=3) for _ in range(30)]
    files += [comic_factory.cbz(pages=2) for _ in range(25)]
    result = service.start_import(sources(*files), label="lot-55")
    assert all(i.outcome is ImportOutcome.NEW for i in result.items)

    await drain(make_workers(service, db_engine, count=4))

    report = service.batch_report(result.run_id)
    assert report is not None
    totals = report["totals"]
    assert report["status"] == "SUCCEEDED"
    assert totals["files"] == 55
    assert totals["documents_by_status"] == {"COMPLETE": 55}
    assert totals["pages_total"] == totals["pages_rendered"] == 30 * 3 + 25 * 2
    assert totals["steps_by_status"] == {"SUCCEEDED": 55 + 140}
    with db_engine.connect() as conn:
        dupes = conn.execute(
            text(
                "SELECT count(*) FROM (SELECT document_id, number FROM page "
                "GROUP BY 1, 2 HAVING count(*) > 1) d"
            )
        ).scalar_one()
    assert dupes == 0


async def test_resume_after_worker_crash(
    service: LibraryService, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    files = [comic_factory.pdf(pages=3) for _ in range(5)]
    result = service.start_import(sources(*files))
    queue = PostgresJobQueue(db_engine)
    workers = make_workers(service, db_engine)

    # Validation des 5 documents, puis rendu partiel.
    for _ in range(5):
        assert await workers[0].run_once()
    for _ in range(4):
        assert await workers[0].run_once()
    # Un worker réserve une étape puis « meurt » sans la terminer.
    crashed = queue.claim("crashed-worker")
    assert crashed is not None
    with db_engine.begin() as conn:
        conn.execute(
            text("UPDATE pipeline_step SET locked_at = now() - interval '2 hours' WHERE id = :id"),
            {"id": crashed.id},
        )
    assert queue.run_status(result.run_id) == "RUNNING"

    # Redémarrage : récupération des baux expirés, puis fin du lot.
    assert queue.recover_stale(lease_seconds=60) == 1
    await drain(make_workers(service, db_engine, count=2))

    report = service.batch_report(result.run_id)
    assert report is not None
    assert report["status"] == "SUCCEEDED"
    assert report["totals"]["documents_by_status"] == {"COMPLETE": 5}
    assert report["totals"]["pages_rendered"] == 15
    with db_engine.connect() as conn:
        pages = conn.execute(text("SELECT count(*) FROM page")).scalar_one()
    assert pages == 15  # ni doublon ni perte


async def test_reimport_is_deduplicated(
    service: LibraryService, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    files = [comic_factory.pdf(pages=2), comic_factory.cbz(pages=2)]
    first = service.start_import(sources(*files))
    await drain(make_workers(service, db_engine))

    second = service.start_import(sources(*files))
    assert [i.outcome for i in second.items] == [ImportOutcome.DUPLICATE] * 2
    assert [i.document_id for i in second.items] == [i.document_id for i in first.items]
    report = service.batch_report(second.run_id)
    assert report is not None
    assert report["status"] == "SUCCEEDED"  # rien de nouveau à traiter
    assert report["totals"]["steps_by_status"] == {}
    with db_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM document")).scalar_one() == 2


async def test_same_file_twice_in_one_batch(
    service: LibraryService, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    path = comic_factory.pdf(pages=2)
    copy = path.with_name("copie.pdf")
    copy.write_bytes(path.read_bytes())
    result = service.start_import(sources(path, copy))
    assert [i.outcome for i in result.items] == [ImportOutcome.NEW, ImportOutcome.DUPLICATE]
    await drain(make_workers(service, db_engine))
    assert list(document_statuses(db_engine).values()) == ["COMPLETE"]


async def test_missing_pages_block_complete(
    service: LibraryService, db_engine: Engine, comic_factory: SimpleNamespace
) -> None:
    path = comic_factory.pdf(pages=3, name="incomplet.pdf")
    result = service.start_import(sources(path, expected_page_count=5))
    await drain(make_workers(service, db_engine))

    report = service.batch_report(result.run_id)
    assert report is not None
    item = report["items"][0]
    assert item["status"] == "INCOMPLETE"
    assert item["pages_rendered"] == 3  # les pages présentes sont tout de même rendues
    assert "5 attendue" in item["error"]


async def test_invalid_files_are_rejected_without_failing_the_batch(
    service: LibraryService, db_engine: Engine, comic_factory: SimpleNamespace, tmp_path: Path
) -> None:
    text_file = tmp_path / "notes.pdf"
    text_file.write_text("pas un PDF")
    fake_pdf = tmp_path / "corrompu.pdf"
    fake_pdf.write_bytes(b"%PDF-1.7\n garbage")
    empty = tmp_path / "vide.cbz"
    empty.write_bytes(b"")
    good = comic_factory.cbz(pages=2, name="bon.cbz")

    result = service.start_import(sources(text_file, fake_pdf, empty, good))
    outcomes = {i.filename: i.outcome for i in result.items}
    assert outcomes["notes.pdf"] is ImportOutcome.REJECTED  # signature inconnue
    assert outcomes["vide.cbz"] is ImportOutcome.REJECTED
    assert outcomes["corrompu.pdf"] is ImportOutcome.NEW  # rejeté plus tard, à la validation

    await drain(make_workers(service, db_engine))
    statuses = document_statuses(db_engine)
    assert statuses == {"corrompu.pdf": "REJECTED", "bon.cbz": "COMPLETE"}
    report = service.batch_report(result.run_id)
    assert report is not None
    assert report["status"] == "SUCCEEDED"
    assert report["totals"]["rejected_at_import"] == 2


async def test_unreadable_page_fails_document(
    service: LibraryService, db_engine: Engine, tmp_path: Path
) -> None:
    path = tmp_path / "abime.cbz"
    with zipfile.ZipFile(path, "w") as archive:
        buffer = io.BytesIO()
        Image.new("RGB", (60, 90), "white").save(buffer, format="PNG")
        archive.writestr("p1.png", buffer.getvalue())
        archive.writestr("p2.png", b"\x89PNG\r\n\x1a\n corrompu")
        archive.writestr("p3.png", buffer.getvalue())
    result = service.start_import(sources(path))
    await drain(make_workers(service, db_engine))

    report = service.batch_report(result.run_id)
    assert report is not None
    item = report["items"][0]
    assert item["status"] == "FAILED"
    assert (item["pages_rendered"], item["pages_failed"]) == (2, 1)
    assert item["error"].startswith("page 2")


async def test_unknown_run_report(service: LibraryService) -> None:
    from uuid import uuid4

    assert service.batch_report(uuid4()) is None


COMIC_INFO = (
    b'<?xml version="1.0"?><ComicInfo><Series>Sandman</Series><Number>1</Number>'
    b"<LanguageISO>EN</LanguageISO><PageCount>5</PageCount></ComicInfo>"
)


def test_comic_info_fills_missing_metadata(
    service: LibraryService, comic_factory: SimpleNamespace, db_engine: Engine
) -> None:
    with_info = comic_factory.cbz(pages=3, extra={"ComicInfo.xml": COMIC_INFO})
    hostile = comic_factory.cbz(
        pages=2,
        extra={"ComicInfo.xml": b'<!DOCTYPE x [<!ENTITY a "b">]><ComicInfo>&a;</ComicInfo>'},
    )
    service.start_import(
        [
            ImportSource(path=with_info, filename="s1.cbz"),
            ImportSource(path=hostile, filename="h.cbz", series_title="Choisi"),
        ]
    )
    with db_engine.connect() as conn:
        rows = {
            r.title: r
            for r in conn.execute(
                text(
                    "SELECT title, series_title, issue_number, language, "
                    "expected_page_count FROM comic"
                )
            )
        }
    assert rows["Sandman #1"].language == "en"
    assert rows["Sandman #1"].expected_page_count == 5  # 3 pages présentes : jamais COMPLETE
    assert rows["h"].series_title == "Choisi"  # DOCTYPE ignoré, choix de l'utilisateur gardé
