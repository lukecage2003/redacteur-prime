"""Moteur d'émissions : cycle de vie gouverné, règles versionnées, formats, épisodes."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, text

from primestone.creative import CreativeService
from primestone.forensic import forensic_service
from primestone.governance import FOUNDER, GovernanceError, GovernanceService
from primestone.shows import ShowError, ShowService
from primestone.storytelling import StorytellingService

pytestmark = pytest.mark.integration
SCRIPT = "00:00 - Mystère\nQui est Despair ?\n01:00 - Indices\nLes pages le montrent.\n"


def _approve_pending(gov: GovernanceService) -> None:
    for decision in reversed(gov.decisions("PROPOSED")):
        gov.approve(decision["id"], decided_by="moi", role=FOUNDER)


def _show(engine: Engine) -> tuple[ShowService, GovernanceService, object]:
    series_id = CreativeService(engine).create_series(
        name="Enquêtes Endless",
        promise="Un mystère des Endless résolu preuves à l'appui",
        identity="enquête",
        tone="sobre",
        structure=["Mystère", "Indices"],
        target_minutes=1,
        art_direction="charte",
        evolution="un Endless par épisode",
        author="agent",
        languages=["fr", "en"],
        expertise_level="EXPLORATION",
    )
    return ShowService(engine), GovernanceService(engine), series_id


def test_lifecycle_is_governed(db_engine: Engine) -> None:
    shows, gov, series_id = _show(db_engine)
    assert shows.show(series_id)["status"] == "DRAFT"
    with pytest.raises(ShowError, match="en attente"):
        shows.transition(series_id, "RETIRED", proposed_by="agent")
    _approve_pending(gov)
    assert shows.show(series_id)["status"] == "TESTING"
    with pytest.raises(ShowError, match="interdite"):
        shows.transition(series_id, "SUSPENDED", proposed_by="agent")
    activation = shows.transition(series_id, "ACTIVE", proposed_by="agent")
    gov.approve(activation["decision_id"], decided_by="moi", role=FOUNDER)
    suspension = shows.transition(series_id, "SUSPENDED", proposed_by="moi", reason="pause")
    gov.approve(suspension["decision_id"], decided_by="moi", role=FOUNDER)
    stories = StorytellingService(db_engine, forensic_service(db_engine))
    script_id = stories.create(title="Despair", language="fr", content=SCRIPT, author="moi")
    with pytest.raises(ShowError, match="SUSPENDED"):
        shows.add_episode(series_id, script_id)
    gov.revert(suspension["decision_id"], decided_by="moi", role=FOUNDER, reason="reprise")
    assert shows.show(series_id)["status"] == "ACTIVE"
    assert shows.add_episode(series_id, script_id) == 1


def test_guidelines_formats_episodes_performance(db_engine: Engine) -> None:
    shows, gov, series_id = _show(db_engine)
    _approve_pending(gov)
    change = shows.propose_guidelines(
        series_id, {"tone": "curieux", "evidence_requirements": {"pages": True}}, author="agent"
    )
    assert change["version"] == 2
    assert shows.show(series_id)["tone"] == "sobre"  # rien sans le fondateur
    with pytest.raises(ShowError, match="inconnues"):
        shows.propose_guidelines(series_id, {"name": "x"}, author="agent")
    gov.approve(change["decision_id"], decided_by="moi", role=FOUNDER)
    show = shows.show(series_id)
    assert show["tone"] == "curieux"
    assert show["guideline_version"] == 2
    gov.revert(change["decision_id"], decided_by="moi", role=FOUNDER, reason="trop tôt")
    show = shows.show(series_id)
    assert show["tone"] == "sobre"
    assert show["evidence_requirements"] == {}
    assert show["guideline_version"] == 1
    assert shows.guidelines(series_id)[0]["decision_status"] == "REVERTED"

    long_fr = shows.add_format(
        series_id,
        name="Enquête longue",
        platform="YOUTUBE",
        language="fr",
        min_minutes=8,
        max_minutes=20,
        structure=["Mystère", "Indices", "Verdict"],
    )
    with pytest.raises(ShowError, match="déjà"):
        shows.add_format(
            series_id,
            name="Enquête longue",
            platform="YOUTUBE",
            language="fr",
            min_minutes=8,
            max_minutes=20,
            structure=["x"],
        )
    stories = StorytellingService(db_engine, forensic_service(db_engine))
    script_id = stories.create(title="Despair", language="fr", content=SCRIPT, author="moi")
    assert shows.add_episode(series_id, script_id, format_id=long_fr) == 1
    [episode] = shows.show(series_id)["episodes"]
    assert episode["language"] == "fr"
    assert episode["guideline_version"] == 1
    assert any("hors format" in i for i in episode["conformance"])
    assert any("Verdict" in i for i in episode["conformance"])

    shows.start_production(series_id, 1)
    validation = shows.propose_final_validation(series_id, 1, proposed_by="agent")
    with pytest.raises(GovernanceError, match="pas validé"):
        gov.approve(validation["decision_id"], decided_by="moi", role=FOUNDER)
    with db_engine.begin() as conn:  # validation factuelle simulée du script
        conn.execute(text("UPDATE script SET status = 'VALIDATED' WHERE id = :s"), {"s": script_id})
    validation = shows.propose_final_validation(series_id, 1, proposed_by="agent")
    with pytest.raises(ShowError, match="approuvé"):
        shows.declare_published(series_id, 1, script_id)
    gov.approve(validation["decision_id"], decided_by="moi", role=FOUNDER)
    assert shows.performance(series_id)["status"] == "NON FOURNI"
    with db_engine.begin() as conn:
        content_id = conn.execute(
            text(
                "INSERT INTO content_item (platform, external_id, title, language) "
                "VALUES ('YOUTUBE', 'v1', 'Despair', 'fr') RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO performance_metric (content_id, metric, value, source, data_class, "
                "imported_by) VALUES (:c, 'views', 120, 'MANUAL', 'PRIVATE_AUTHORIZED', 'moi')"
            ),
            {"c": content_id},
        )
    shows.declare_published(series_id, 1, content_id)
    assert shows.show(series_id)["episodes"][0]["status"] == "PUBLISHED"
    perf = shows.performance(series_id)
    assert perf["total"]["views"] == 120
    assert perf["by_language"]["fr"]["contents"] == 1

    fit = shows.fit("Le mystère de Despair chez les Endless")
    assert fit["shows"][0]["name"] == "Enquêtes Endless"
    assert "endless" in fit["shows"][0]["matched"]


def test_starter_bootstrap_is_proposed_and_idempotent(db_engine: Engine) -> None:
    from primestone.shows.starter import STARTER_SHOWS, bootstrap

    first = bootstrap(db_engine, proposed_by="système")
    assert len(first["shows"]) == len(STARTER_SHOWS)
    assert len(first["pillars"]) == 3
    gov = GovernanceService(db_engine)
    assert {p["status"] for p in gov.pillars()} == {"PROPOSED"}
    pending = gov.decisions("PROPOSED")
    assert len(pending) == 3 + len(STARTER_SHOWS)  # rien d'appliqué sans le fondateur
    again = bootstrap(db_engine, proposed_by="système")
    assert again["shows"] == []
    assert len(again["skipped"]) == 3 + len(STARTER_SHOWS)
