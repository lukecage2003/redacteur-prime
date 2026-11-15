"""Propositions de départ : piliers et émissions issus de l'audit « média autonome ».

Tout naît PROPOSÉ ou en BROUILLON : rien ne s'applique sans décision du fondateur. Les textes
sont des concepts à reprendre, pas des choix définitifs. Idempotent : ce qui existe déjà (même
nom) est laissé intact.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, text

STARTER_PILLARS: tuple[dict[str, Any], ...] = (
    {
        "name": "Enquêtes",
        "description": "Une question précise, résolue page par page, preuves citées.",
        "rules": {"evidence": "citations de pages obligatoires", "levels": ["EXPLORATION"]},
    },
    {
        "name": "Comprendre",
        "description": "Expliquer un personnage, un univers ou un événement à un nouveau venu.",
        "rules": {"evidence": "faits vérifiés", "levels": ["DISCOVERY"]},
    },
    {
        "name": "Théories et débats",
        "description": "Théories instruites au laboratoire, jamais présentées comme des faits.",
        "rules": {"evidence": "preuves et contre-preuves", "levels": ["EXPERTISE"]},
    },
)

STARTER_SHOWS: tuple[dict[str, Any], ...] = (
    {
        "name": "PRIMESTONE COSMOS",
        "pillar": "Comprendre",
        "promise": "Comprendre un univers de comics en un épisode, sans prérequis.",
        "identity": "carte du cosmos, voix posée, chronologie claire",
        "tone": "pédagogique",
        "structure": [
            "Accroche",
            "Contexte",
            "Personnages clés",
            "Chronologie",
            "Pour aller plus loin",
        ],
        "target_minutes": 12,
        "expertise_level": "DISCOVERY",
    },
    {
        "name": "THE COMIC FILES",
        "pillar": "Enquêtes",
        "promise": "Un dossier ouvert, une question, la réponse dans les pages.",
        "identity": "dossier d'enquête, pièces à conviction (cases citées)",
        "tone": "enquête sobre",
        "structure": ["Mystère", "Pièces", "Contradictions", "Verdict des pages"],
        "target_minutes": 15,
        "expertise_level": "EXPLORATION",
    },
    {
        "name": "BEYOND THE PANEL",
        "pillar": "Comprendre",
        "promise": "Ce que la case montre sans le dire : mise en page, symboles, coulisses.",
        "identity": "zoom sur la case, lecture lente",
        "tone": "curieux",
        "structure": ["La case", "Ce qu'on voit", "Ce que ça signifie", "Ailleurs dans l'œuvre"],
        "target_minutes": 10,
        "expertise_level": "EXPLORATION",
    },
    {
        "name": "THE VERDICT",
        "pillar": "Théories et débats",
        "promise": "Une théorie de fans jugée sur pièces : preuves, contre-preuves, verdict.",
        "identity": "tribunal, deux colonnes de preuves",
        "tone": "contradictoire",
        "structure": ["La théorie", "Pour", "Contre", "Alternatives", "Verdict"],
        "target_minutes": 14,
        "expertise_level": "EXPERTISE",
    },
)


def bootstrap(engine: Engine, *, proposed_by: str) -> dict[str, list[str]]:
    """Propose les piliers et crée les émissions en brouillon (chacune soumise au fondateur)."""
    from primestone.creative import CreativeService  # import différé : creative → shows
    from primestone.governance import GovernanceService

    governance, creative = GovernanceService(engine), CreativeService(engine)
    created: dict[str, list[str]] = {"pillars": [], "shows": [], "skipped": []}
    existing_pillars = {p["name"]: p["id"] for p in governance.pillars()}
    for pillar in STARTER_PILLARS:
        if pillar["name"] in existing_pillars:
            created["skipped"].append(pillar["name"])
            continue
        result = governance.propose_pillar(
            pillar["name"], pillar["description"], rules=pillar["rules"], proposed_by=proposed_by
        )
        existing_pillars[pillar["name"]] = result["pillar_id"]
        created["pillars"].append(pillar["name"])
    with engine.connect() as conn:
        shows = set(conn.execute(text("SELECT name FROM series")).scalars())
    for show in STARTER_SHOWS:
        if show["name"] in shows:
            created["skipped"].append(show["name"])
            continue
        fields = {k: v for k, v in show.items() if k != "pillar"}
        creative.create_series(
            **fields,
            pillar_id=existing_pillars.get(show["pillar"]),
            languages=["fr", "en"],
            art_direction="charte PRIMESTONE (à préciser)",
            evolution="concept de départ, à valider par un épisode pilote",
            distribution=["YouTube long", "Shorts"],
            author=proposed_by,
        )
        created["shows"].append(show["name"])
    return created
