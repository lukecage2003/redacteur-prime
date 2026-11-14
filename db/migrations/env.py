"""Environnement Alembic : URL depuis la configuration Primestone, métadonnées du schéma."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from primestone.config import Settings
from primestone.db import metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata

# Index sur expression (plein texte) créés en SQL brut : hors du schéma déclaratif.
_EXPRESSION_INDEXES = {"ix_search_document_fts"}


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    return not (type_ == "index" and name in _EXPRESSION_INDEXES)


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or Settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
