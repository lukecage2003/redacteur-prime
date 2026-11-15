"""Identité indépendante : voix sous licence, règles par langue, narration sans le fondateur."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import Engine

from primestone.creative import DEFAULT_CHARTER, CreativeService
from primestone.forensic import forensic_service
from primestone.governance import FOUNDER, GovernanceService
from primestone.identity import IdentityError, IdentityService, narration_text
from primestone.storage import LocalObjectStore
from primestone.storytelling import StorytellingService
from primestone.voice.providers import FakeTTS

pytestmark = pytest.mark.integration
SCRIPT = "00:00 - Mystère\nQui est Despair [p. 12] ?\n01:00 - Indices\nLes pages le montrent.\n"
VOICE = {
    "tone": "posé",
    "kind": "SYNTHETIC",
    "provider": "piper",
    "voice": "modèle local choisi par le fondateur",
    "license": "licence du modèle (à recopier depuis sa fiche)",
    "allowed_use": "narration non commerciale",
}


def test_voice_profiles_need_license_and_founder(db_engine: Engine) -> None:
    identity, gov = IdentityService(db_engine), GovernanceService(db_engine)
    with pytest.raises(IdentityError, match="licence"):
        identity.propose_voice(
            name="x", language="fr", proposed_by="agent", **(VOICE | {"license": " "})
        )
    with pytest.raises(IdentityError, match="autorisation"):
        identity.propose_voice(
            name="y", language="fr", proposed_by="agent", **(VOICE | {"kind": "HUMAN_LICENSED"})
        )
    proposed = identity.propose_voice(name="Voix FR", language="fr", proposed_by="agent", **VOICE)
    with pytest.raises(IdentityError, match="aucune voix"):
        identity.voice_for("fr")  # non approuvée : inutilisable
    gov.approve(proposed["decision_id"], decided_by="moi", role=FOUNDER)
    assert identity.voice_for("fr")["name"] == "Voix FR"
    with pytest.raises(IdentityError, match="en"):
        identity.voice_for("en")  # une voix FR ne sert pas un contenu EN
    rejected = identity.propose_voice(name="Voix EN", language="en", proposed_by="agent", **VOICE)
    gov.reject(rejected["decision_id"], decided_by="moi", role=FOUNDER, reason="timbre")
    assert {v["name"]: v["status"] for v in identity.voices()}["Voix EN"] == "RETIRED"


def test_language_rules_never_cross(db_engine: Engine) -> None:
    identity = IdentityService(db_engine)
    identity.add_visual({"palette": "nuit", "font": "Inter"}, created_by="moi")
    identity.add_visual({"title_case": "phrase"}, created_by="moi", language="fr")
    identity.add_visual({"title_case": "Title Case"}, created_by="moi", language="en")
    second = identity.add_visual({"title_case": "Phrase"}, created_by="moi", language="fr")
    assert second["version"] == 2
    fr = identity.visual_for(language="fr", platform="YOUTUBE")
    en = identity.visual_for(language="en")
    assert fr["rules"] == {"palette": "nuit", "font": "Inter", "title_case": "Phrase"}
    assert en["rules"]["title_case"] == "Title Case"

    creative, gov = CreativeService(db_engine), GovernanceService(db_engine)
    creative.publish_charter(
        DEFAULT_CHARTER, name="Charte FR", author="moi", note=None, language="fr"
    )
    for d in gov.decisions("PROPOSED"):
        gov.approve(d["id"], decided_by="moi", role=FOUNDER)
    assert creative.charter("fr")["name"] == "Charte FR"
    assert creative.charter("en")["version"] == 0  # la charte FR ne s'applique pas à l'EN


def test_narration_without_founder(db_engine: Engine, tmp_path: Path) -> None:
    identity, gov = IdentityService(db_engine), GovernanceService(db_engine)
    stories = StorytellingService(db_engine, forensic_service(db_engine))
    script_id = stories.create(title="Despair", language="fr", content=SCRIPT, author="moi")
    with pytest.raises(IdentityError, match="aucune voix"):
        identity.narrate(script_id)
    proposed = identity.propose_voice(name="Voix FR", language="fr", proposed_by="agent", **VOICE)
    gov.approve(proposed["decision_id"], decided_by="moi", role=FOUNDER)
    store = LocalObjectStore(tmp_path)
    plan = identity.narrate(script_id, tts=FakeTTS(), store=store)
    assert plan["founder_required"] is False
    assert plan["voice"]["name"] == "Voix FR"
    assert [s["title"] for s in plan["sections"]] == ["Mystère", "Indices"]
    assert "[p. 12]" not in plan["sections"][0]["text"]
    assert store.exists(plan["sections"][0]["audio_key"])
    assert narration_text("Voir (p. 4) puis [note]  fin") == "Voir puis fin"


def test_narration_mission(db_engine: Engine) -> None:
    from primestone.editorial import EditorialError, EditorialService
    from primestone.jobs import PostgresJobQueue
    from primestone.knowledge import KnowledgeService

    forensic = forensic_service(db_engine)
    stories = StorytellingService(db_engine, forensic)
    identity, gov = IdentityService(db_engine), GovernanceService(db_engine)
    editorial = EditorialService(
        db_engine,
        forensic,
        KnowledgeService(db_engine, forensic),
        PostgresJobQueue(db_engine),
        storytelling=stories,
        identity=identity,
    )
    script_id = stories.create(title="Despair", language="fr", content=SCRIPT, author="moi")
    with pytest.raises(EditorialError, match="aucune voix"):
        editorial.create_mission("NARRATION", [], {"script_id": str(script_id)})
    proposed = identity.propose_voice(name="Voix FR", language="fr", proposed_by="agent", **VOICE)
    gov.approve(proposed["decision_id"], decided_by="moi", role=FOUNDER)
    mission_id = editorial.create_mission("NARRATION", [], {"script_id": str(script_id)})
    asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
    mission = editorial.mission(mission_id)
    assert mission["title"] == "Narration : Despair"
    assert mission["result"]["deliverable"].startswith("# Narration")
    assert "fondateur non requis" in " ".join(mission["result"]["findings"])
    assert mission["result"]["recommendation"] == "VALIDER AVEC RÉSERVES"  # script non validé
