import pytest
from pydantic import ValidationError

from primestone.config import Settings


def test_development_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.ai_provider == "fake"


@pytest.mark.parametrize("env", ["staging", "production"])
def test_cloud_requires_explicit_database_url(env: str) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None, environment=env, ai_provider="real")


@pytest.mark.parametrize("env", ["staging", "production"])
def test_fake_ai_forbidden_in_cloud(env: str) -> None:
    with pytest.raises(ValidationError, match="fake"):
        Settings(
            _env_file=None,
            environment=env,
            database_url="postgresql+psycopg://u@host/db",
        )


def test_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIMESTONE_LOG_LEVEL", "DEBUG")
    assert Settings(_env_file=None).log_level == "DEBUG"


def test_selfhosted_requires_db_password_and_real_vision() -> None:
    url = "postgresql+psycopg://primestone:secret@db:5432/primestone"
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None, environment="selfhosted", vision_provider="ollama")
    with pytest.raises(ValidationError, match="fake"):
        Settings(_env_file=None, environment="selfhosted", database_url=url)
    ok = Settings(
        _env_file=None, environment="selfhosted", database_url=url, vision_provider="ollama"
    )
    assert ok.storage_backend == "local"  # disque persistant de la machine
    assert ok.iap_audience is None  # accès protégé par Tailscale et le proxy
