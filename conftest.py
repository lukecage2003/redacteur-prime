"""Fixtures partagées.

Les tests marqués `integration` utilisent une base PostgreSQL + pgvector JETABLE désignée par
PRIMESTONE_TEST_DATABASE_URL (service CI ou `docker compose`). Garde-fou : le nom de la base
doit contenir « test ». Les tables sont migrées avec Alembic puis vidées entre les tests.
"""

from __future__ import annotations

import io
import os
import zipfile
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from PIL import Image, ImageDraw
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).parent


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("PRIMESTONE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PRIMESTONE_TEST_DATABASE_URL non défini (tests d'intégration ignorés)")
    if "test" not in (make_url(url).database or ""):
        pytest.fail("garde-fou : le nom de la base de test doit contenir « test »")
    return url


@pytest.fixture(scope="session")
def migrated_engine(database_url: str) -> Iterator[Engine]:
    command.upgrade(alembic_config(database_url), "head")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_engine(migrated_engine: Engine) -> Engine:
    """Moteur migré ; les tables de la file sont vidées avant chaque test (base de test)."""
    with migrated_engine.begin() as conn:
        for table in (
            "script_event",
            "script_score",
            "script_version",
            "script",
            "market_metric",
            "market_item",
            "market_collection",
            "market_source",
            "market_topic",
            "theory_event",
            "theory_alternative",
            "theory_evidence",
            "theory",
            "agent_run",
            "approval_request",
            "mission_task",
            "mission",
            "search_document",
            "correction",
            "relation_evidence",
            "relation",
            "entity_alias",
            "entity",
            "evidence_ref",
            "observation",
            "text_region",
            "panel",
            "page_analysis",
            "import_item",
            "page",
            "document",
            "comic",
            "pipeline_step",
            "pipeline_run",
        ):
            conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608 - liste fixe
    return migrated_engine


# --- Comics synthétiques (aucune œuvre protégée dans les tests) ----------------------------


def _page_image(number: int, size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", size, (250, 248, 240))
    draw = ImageDraw.Draw(image)
    w, h = size
    draw.rectangle((10, 10, w // 2 - 5, h // 2 - 5), outline=(0, 0, 0), width=3)  # case 1
    draw.rectangle((w // 2 + 5, 10, w - 10, h // 2 - 5), outline=(0, 0, 0), width=3)  # case 2
    draw.rectangle((10, h // 2 + 5, w - 10, h - 10), outline=(0, 0, 0), width=3)  # case 3
    draw.text((20, 20), f"PAGE {number}", fill=(0, 0, 0))
    return image


def write_pdf(path: Path, pages: int, size: tuple[int, int] = (300, 450), seed: str = "") -> Path:
    images = [_page_image(i, size) for i in range(1, pages + 1)]
    ImageDraw.Draw(images[0]).text((20, 40), seed, fill=(0, 0, 0))  # contenu unique
    images[0].save(path, format="PDF", save_all=True, append_images=images[1:])
    return path


def write_cbz(
    path: Path,
    pages: int,
    size: tuple[int, int] = (300, 450),
    seed: str = "",
    extra: dict[str, bytes] | None = None,
) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for i in range(1, pages + 1):
            image = _page_image(i, size)
            if i == 1:
                ImageDraw.Draw(image).text((20, 40), seed, fill=(0, 0, 0))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            archive.writestr(f"comic/page{i}.png", buffer.getvalue())
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return path


@pytest.fixture
def comic_factory(tmp_path: Path) -> SimpleNamespace:
    counter = {"n": 0}

    def pdf(pages: int = 3, name: str | None = None, **kw: object) -> Path:
        counter["n"] += 1
        target = tmp_path / (name or f"comic-{counter['n']:03d}.pdf")
        return write_pdf(target, pages, seed=f"pdf-{counter['n']}", **kw)  # type: ignore[arg-type]

    def cbz(pages: int = 3, name: str | None = None, **kw: object) -> Path:
        counter["n"] += 1
        target = tmp_path / (name or f"comic-{counter['n']:03d}.cbz")
        return write_cbz(target, pages, seed=f"cbz-{counter['n']}", **kw)  # type: ignore[arg-type]

    return SimpleNamespace(pdf=pdf, cbz=cbz, dir=tmp_path)
