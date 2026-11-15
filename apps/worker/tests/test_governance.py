"""Gouvernance : propositions, approbation réservée au fondateur, journal, réversibilité."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine

from primestone.governance import FOUNDER, GovernanceError, GovernanceService

pytestmark = pytest.mark.integration


def test_brand_and_default_policies(db_engine: Engine) -> None:
    gov = GovernanceService(db_engine)
    brand = gov.brand()
    assert brand["name"] == "PRIMESTONE"
    assert brand["languages"] == ["fr", "en"]
    assert brand["primary_language"] == "fr"
    policies = {p["action"]: p["requires_approval"] for p in gov.policies()}
    for sensitive in ("CHARTER_CHANGE", "SHOW_LIFECYCLE", "VOICE_PROFILE", "COST_SETTINGS"):
        assert policies[sensitive] is True
    assert policies["PACKAGING_PROPOSAL"] is False


def test_pillar_lifecycle_founder_only_and_reversible(db_engine: Engine) -> None:
    gov = GovernanceService(db_engine)
    created = gov.propose_pillar(
        "Enquêtes", "Une question, des preuves", rules={"evidence": "pages"}, proposed_by="agent"
    )
    assert created["status"] == "PROPOSED"
    assert gov.pillars()[0]["status"] == "PROPOSED"
    with pytest.raises(GovernanceError, match="fondateur"):
        gov.approve(created["decision_id"], decided_by="chief_editor", role="AGENT")
    approved = gov.approve(created["decision_id"], decided_by="moi", role=FOUNDER)
    assert approved["status"] == "APPROVED"
    assert approved["decided_by"] == "moi"
    assert gov.pillars()[0]["status"] == "ACTIVE"
    with pytest.raises(GovernanceError, match="déjà"):
        gov.approve(created["decision_id"], decided_by="moi", role=FOUNDER)
    with pytest.raises(GovernanceError, match="motif"):
        gov.revert(created["decision_id"], decided_by="moi", role=FOUNDER, reason=" ")
    gov.revert(created["decision_id"], decided_by="moi", role=FOUNDER, reason="essai")
    assert gov.pillars()[0]["status"] == "RETIRED"
    with pytest.raises(GovernanceError, match="déjà défini"):
        gov.propose_pillar("Enquêtes", "x", rules={}, proposed_by="agent")
    rejected = gov.propose_pillar("Bases", "Comprendre", rules={}, proposed_by="agent")
    gov.reject(rejected["decision_id"], decided_by="moi", role=FOUNDER, reason="hors ligne")
    assert {p["name"]: p["status"] for p in gov.pillars()}["Bases"] == "RETIRED"
    journal = gov.decisions()
    assert {d["status"] for d in journal} == {"REVERTED", "REJECTED"}


def test_policy_changes_always_need_founder_and_revert_exactly(db_engine: Engine) -> None:
    gov = GovernanceService(db_engine)
    with pytest.raises(GovernanceError, match="toujours"):
        gov.propose_policy("POLICY_CHANGE", False, note=None, proposed_by="moi")
    change = gov.propose_policy("PACKAGING_PROPOSAL", True, note="prudence", proposed_by="moi")
    assert change["status"] == "PROPOSED"  # même pour le fondateur : décision explicite
    gov.approve(change["decision_id"], decided_by="moi", role=FOUNDER)
    policy = {p["action"]: p for p in gov.policies()}["PACKAGING_PROPOSAL"]
    assert policy["requires_approval"] is True
    assert policy["version"] == 2
    # Une action non sensible s'applique d'office, mais reste journalisée.
    gov.revert(change["decision_id"], decided_by="moi", role=FOUNDER, reason="retour")
    assert {p["action"]: p for p in gov.policies()}["PACKAGING_PROPOSAL"][
        "requires_approval"
    ] is False
    auto = gov.propose(
        "PACKAGING_PROPOSAL",
        subject_type="script",
        subject_id=None,
        proposal={"titles": 10},
        proposed_by="packaging_agent",
    )
    assert auto["status"] == "APPROVED"
    assert gov.decision(auto["decision_id"])["decided_by"] == "POLICY"
    # Action inconnue : approbation exigée par défaut.
    unknown = gov.propose(
        "PUBLISH", subject_type="x", subject_id=None, proposal={}, proposed_by="a"
    )
    assert unknown["status"] == "PROPOSED"
