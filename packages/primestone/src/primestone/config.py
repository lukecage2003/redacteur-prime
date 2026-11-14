"""Configuration centralisée, lue depuis les variables d'environnement `PRIMESTONE_*`.

Aucun secret n'a de valeur par défaut utilisable hors développement local :
en staging/production, les valeurs viennent de Secret Manager (montées par Cloud Run).
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]

# Identifiants de la base Docker locale uniquement (docker-compose.yml).
_LOCAL_DATABASE_URL = "postgresql+psycopg://primestone:primestone@localhost:5432/primestone"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PRIMESTONE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = "development"
    log_level: str = "INFO"
    database_url: str = _LOCAL_DATABASE_URL

    # Passerelle IA : "fake" est le seul fournisseur autorisé en CI.
    ai_provider: str = "fake"
    # Plafond de dépense IA par mission/lot, en USD (garde-fou, voir COSTS.md).
    ai_budget_per_mission_usd: Decimal = Field(default=Decimal("5.00"), ge=0)

    # Worker
    worker_poll_interval_seconds: float = Field(default=2.0, gt=0)
    worker_lease_seconds: int = Field(default=900, gt=0)

    # Stockage objet : "local" (développement) ou "gcs" (cloud, phase 13 — non implémenté).
    storage_backend: Literal["local", "gcs"] = "local"
    storage_local_root: Path = Path("data/storage")

    # Comic Library (phase 2) — limites de sécurité et profil de rendu.
    library_max_file_bytes: int = Field(default=1024**3, gt=0)  # 1 Gio par fichier
    library_max_pages: int = Field(default=2000, gt=0)
    library_max_image_pixels: int = Field(default=150_000_000, gt=0)
    render_max_dimension: int = Field(default=2400, ge=64, le=10_000)
    render_webp_quality: int = Field(default=85, ge=1, le=100)

    @model_validator(mode="after")
    def _forbid_local_defaults_in_cloud(self) -> Settings:
        if self.environment in ("staging", "production"):
            if self.database_url == _LOCAL_DATABASE_URL:
                raise ValueError(
                    "PRIMESTONE_DATABASE_URL doit être fourni explicitement hors développement"
                )
            if self.ai_provider == "fake":
                raise ValueError("Le fournisseur IA 'fake' est interdit en staging/production")
            if self.storage_backend == "local":
                raise ValueError("Le stockage local est interdit en staging/production (éphémère)")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
