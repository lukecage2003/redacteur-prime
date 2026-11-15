"""Distribution : plan gouverné, publication seulement déclarée, portefeuille, canaux."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, text

from primestone.distribution import DistributionError, DistributionService, balance
from primestone.forensic import forensic_service
from primestone.governance import FOUNDER, GovernanceError, GovernanceService
from primestone.storytelling import StorytellingService

pytestmark = pytest.mark.integration
SCRIPT = "00:00 - Mystère\nQui est Despair ?\n"


def test_plan_requires_founder_and_human_declaration(db_engine: Engine) -> None:
    dist, gov = DistributionService(db_engine), GovernanceService(db_engine)
    fr = dist.add_channel(platform="YOUTUBE", language="fr", handle="@primestone", name="FR")
    en = dist.add_channel(platform="YOUTUBE", language="en", handle="@primestone-en", name="EN")
    with pytest.raises(DistributionError, match="déjà"):
        dist.add_channel(platform="YOUTUBE", language="fr", handle="@primestone", name="x")
    stories = StorytellingService(db_engine, forensic_service(db_engine))
    script_id = stories.create(title="Despair", language="fr", content=SCRIPT, author="moi")
    with pytest.raises(DistributionError, match="adapter"):
        dist.propose(channel_id=en, title="Despair", proposed_by="agent", script_id=script_id)
    when = datetime(2026, 12, 1, 18, tzinfo=UTC)
    item = dist.propose(
        channel_id=fr, title="Despair", proposed_by="agent", script_id=script_id, scheduled_for=when
    )
    assert item["status"] == "PROPOSED"
    with pytest.raises(DistributionError, match="approuvé"):
        dist.declare_published(
            item["item_id"], url="https://youtu.be/x", external_id="x", declared_by="moi"
        )
    with pytest.raises(GovernanceError, match="pas validé"):
        gov.approve(item["decision_id"], decided_by="moi", role=FOUNDER)
    with db_engine.begin() as conn:
        conn.execute(text("UPDATE script SET status = 'VALIDATED' WHERE id = :s"), {"s": script_id})
    gov.approve(item["decision_id"], decided_by="moi", role=FOUNDER)
    with pytest.raises(DistributionError, match="incomplète"):
        dist.declare_published(item["item_id"], url="ftp://x", external_id="x", declared_by="moi")
    content_id = dist.declare_published(
        item["item_id"], url="https://youtu.be/abc", external_id="abc", declared_by="moi"
    )
    [row] = dist.plan()
    assert row["status"] == "PUBLISHED"
    assert row["declared_by"] == "moi"
    assert row["content_id"] == content_id
    with pytest.raises(GovernanceError, match="dépublier"):
        gov.revert(item["decision_id"], decided_by="moi", role=FOUNDER, reason="x")

    with db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO performance_metric (content_id, metric, value, source, data_class, "
                "imported_by) VALUES (:c, 'views', 300, 'MANUAL', 'PRIVATE_AUTHORIZED', 'moi')"
            ),
            {"c": content_id},
        )
    perf = {c["name"]: c["performance"] for c in dist.channel_performance()}
    assert perf["FR"]["views"] == 300
    assert perf["EN"]["status"] == "NON FOURNI"

    rejected = dist.propose(channel_id=en, title="Teaser", proposed_by="agent")
    gov.reject(rejected["decision_id"], decided_by="moi", role=FOUNDER, reason="trop tôt")
    assert {p["title"]: p["status"] for p in dist.plan()}["Teaser"] == "CANCELLED"
    dist.set_channel_status(en, "PAUSED")
    with pytest.raises(DistributionError, match="PAUSED"):
        dist.propose(channel_id=en, title="x", proposed_by="agent")

    portfolio_id = dist.create_portfolio(
        "Décembre",
        period_start=date(2026, 12, 1),
        period_end=date(2026, 12, 31),
        targets={"language": {"fr": 0.5, "en": 0.5}},
        created_by="moi",
    )
    report = dist.portfolio(portfolio_id)["balance"]
    assert report["items"] == 1
    assert any("en" in a and "sous-représenté" in a for a in report["alerts"])
    with pytest.raises(DistributionError, match="dimensions"):
        dist.create_portfolio(
            "x",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 2),
            targets={"mood": {}},
            created_by="moi",
        )


def test_balance_pure() -> None:
    items = [{"language": "fr", "level": "DISCOVERY"}] * 3 + [{"language": "en"}]
    report = balance(items, {"language": {"fr": 0.5, "en": 0.5}, "level": {"EXPERTISE": 0.2}})
    assert report["items"] == 4
    alerts = " ".join(report["alerts"])
    assert "fr" in alerts
    assert "EXPERTISE" in alerts
    assert balance([], {})["alerts"] == ["plan vide sur la période"]
