"""Configuration centralisée, lue depuis les variables d'environnement `PRIMESTONE_*`.

Aucun secret n'a de valeur par défaut utilisable hors développement local :
en staging/production, les valeurs viennent de Secret Manager (montées par Cloud Run).
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
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

    # Mode zéro coût (défaut) : tout fournisseur payant est refusé AVANT tout appel.
    zero_cost: bool = True

    # Comic Vision (phase 3) : "fake" (gratuit, CI), "ollama" (gratuit, modèle local)
    # ou "claude" (payant : exige zero_cost=false et un budget explicite).
    vision_provider: str = "fake"
    vision_model: str | None = None
    ollama_url: str = "http://localhost:11434"

    # Editorial Director (phase 6) : rédaction optionnelle par un modèle de texte GRATUIT.
    # "none" (gabarits déterministes, défaut), "fake" (tests) ou "ollama" (modèle local).
    editorial_writer: Literal["none", "fake", "ollama"] = "none"
    ollama_text_model: str = "qwen2.5:7b"

    # Knowledge (phase 5) : plongements gratuits. "hashing" (local, sans modèle, lexical) ou
    # "ollama" (modèle sémantique open source local, ex. nomic-embed-text).
    embedder: Literal["hashing", "ollama"] = "hashing"
    embedding_model: str = "nomic-embed-text"

    # Market Intelligence (phases 2b, 8) : YouTube Data API v3 est GRATUITE dans la limite d'un
    # quota quotidien (10 000 unités par défaut) ; sans clé, ce connecteur est désactivé.
    youtube_api_key: SecretStr | None = None
    youtube_daily_quota_units: int = Field(default=10_000, ge=0)
    market_http_timeout_seconds: float = Field(default=20.0, gt=0)
    # Performance (phase 14) : OAuth « application installée » de la chaîne du propriétaire.
    youtube_oauth_client_id: str | None = None
    youtube_oauth_client_secret: SecretStr | None = None
    youtube_oauth_refresh_token: SecretStr | None = None

    # Adaptive Voice (phase 12) : fournisseurs GRATUITS. "fake" (tests) ou serveurs LOCAUX :
    # whisper.cpp (`server`, STT) et Piper (`piper.http_server`, TTS) — modèles à installer
    # par le propriétaire sur sa machine ; rien n'est téléchargé par la plateforme.
    voice_stt: Literal["fake", "whisper_cpp"] = "fake"
    voice_tts: Literal["fake", "piper", "none"] = "fake"
    whisper_cpp_url: str = "http://localhost:8080"
    piper_url: str = "http://localhost:5000"

    # Stockage objet : "local" (développement) ou "gcs" (cloud : bucket privé).
    storage_backend: Literal["local", "gcs"] = "local"
    gcs_bucket: str | None = None
    # Authentification (phase 13) : en staging/production, l'API exige l'en-tête signé par
    # Identity-Aware Proxy et vérifie son audience (numéro de projet + service de backend).
    iap_audience: str | None = None
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
            if self.vision_provider == "fake":
                raise ValueError("Le fournisseur vision 'fake' est interdit en staging/production")
            if self.storage_backend == "local":
                raise ValueError("Le stockage local est interdit en staging/production (éphémère)")
            if not self.iap_audience:
                raise ValueError("PRIMESTONE_IAP_AUDIENCE est requis hors développement")
        if self.storage_backend == "gcs" and not self.gcs_bucket:
            raise ValueError("PRIMESTONE_GCS_BUCKET est requis pour le stockage gcs")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
