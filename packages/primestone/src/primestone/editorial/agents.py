"""Agents éditoriaux : rôles, entrées/sorties structurées, limites explicites.

Tous les agents disponibles sont déterministes et gratuits. Le seul agent qui peut utiliser un
modèle (le rédacteur du Chief Editor) passe par `ai_gateway` en mode zéro coût, et son texte
n'est retenu que s'il passe le vérificateur de faits.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from primestone.audience import AudienceService
from primestone.editorial.factcheck import Corpus, check_text
from primestone.forensic import ForensicService, fold
from primestone.knowledge import KnowledgeService
from primestone.lab import TheoryLab
from primestone.market import MarketService
from primestone.performance import PerformanceService
from primestone.social import PLATFORMS, build_package, render

if TYPE_CHECKING:  # import circulaire : storytelling utilise le Fact Checker
    from primestone.storytelling import StorytellingService


@dataclass
class MissionContext:
    mission_id: UUID
    mission_type: str
    document_ids: list[UUID]
    params: dict[str, Any]
    forensic: ForensicService
    knowledge: KnowledgeService
    titles: dict[UUID, str]
    page_counts: dict[UUID, int]
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    writer: Callable[[str, str], Awaitable[tuple[str, dict[str, Any]]]] | None = None
    lab: TheoryLab | None = None
    market: MarketService | None = None
    source_mission: dict[str, Any] | None = None
    storytelling: StorytellingService | None = None
    performance: PerformanceService | None = None
    audience: AudienceService | None = None

    def corpus(self) -> Corpus:
        return Corpus(
            titles=self.titles,
            page_counts=self.page_counts,
            rows=self.forensic.text_rows(self.document_ids),
            claims=self.forensic.observations(self.document_ids, kind="CLAIM", limit=10_000),
        )

    def cite(self, document_id: str | UUID, page: int, panel: int | None = None) -> str:
        title = self.titles.get(UUID(str(document_id)), "?")
        return f"[{title}, p. {page}" + (f", case {panel}]" if panel else "]")


AgentFn = Callable[[MissionContext, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class AgentSpec:
    key: str
    name: str
    role: str
    limits: str
    phase: int
    run: AgentFn | None = None  # None : pas encore disponible

    @property
    def available(self) -> bool:
        return self.run is not None


# --- Agents disponibles ---------------------------------------------------------------------


async def research_director(ctx: MissionContext, _inputs: dict[str, Any]) -> dict[str, Any]:
    """Prépare les données : forensique puis connaissances, à jour (gratuit, idempotent)."""
    _run_id, forensic_stats = ctx.forensic.analyze(
        ctx.document_ids, set(ctx.params.get("known_characters", []))
    )
    knowledge_stats = ctx.knowledge.build(ctx.document_ids)
    report = ctx.forensic.report(ctx.document_ids)
    return {
        "forensic": forensic_stats,
        "knowledge": knowledge_stats,
        "complete": report["status"] == "COMPLETE",
        "missing_pages": {k: v["missing_pages"] for k, v in report["documents"].items()},
    }


async def comics_analyst(ctx: MissionContext, _: dict[str, Any]) -> dict[str, Any]:
    report = ctx.forensic.report(ctx.document_ids)
    return {
        "status": report["status"],
        "characters": {
            name: {"speeches": c["speeches"], "mentions": c["mentions"]}
            for name, c in report["characters"].items()
        },
        "observations_by_kind": report["observations_by_kind"],
    }


async def continuity_editor(ctx: MissionContext, inputs: dict[str, Any]) -> dict[str, Any]:
    report = ctx.forensic.report(ctx.document_ids)
    focus = fold(inputs["character"]) if inputs.get("character") else None

    def concerns(o: dict[str, Any]) -> bool:
        return focus is None or focus in (fold(o.get("subject") or ""), fold(o.get("value") or ""))

    return {
        "contradictions": [o for o in report["contradiction_candidates"] if concerns(o)],
        "aliases": [o for o in report["alias_candidates"] if concerns(o)],
        "incomplete": {
            k: v["missing_pages"] for k, v in report["documents"].items() if not v["complete"]
        },
    }


async def character_researcher(ctx: MissionContext, inputs: dict[str, Any]) -> dict[str, Any]:
    name = inputs["character"]
    candidates = [
        e
        for e in ctx.knowledge.entities(type_="CHARACTER", query=name)
        if fold(e["canonical_name"]) == fold(name)
    ] or ctx.knowledge.entities(type_="CHARACTER", query=name)
    if not candidates:
        raise LookupError(
            f"personnage inconnu : « {name} » (aucune réplique ni mention transcrite)"
        )
    entity = ctx.knowledge.entity(UUID(candidates[0]["id"]))
    if entity is None:
        raise LookupError(f"entité introuvable : {candidates[0]['id']}")
    claims = ctx.forensic.observations(
        ctx.document_ids, kind="CLAIM", subject=entity["canonical_name"]
    )
    return {
        "entity": {
            "id": entity["id"],
            "name": entity["canonical_name"],
            "aliases": [a["alias"] for a in entity["aliases"]],
        },
        "relations": [r for r in entity["relations"] if not r["retracted"]],
        "claims": claims,
    }


async def fact_checker(ctx: MissionContext, inputs: dict[str, Any]) -> dict[str, Any]:
    text = inputs.get("text") or ctx.outputs.get("synthesis", {}).get("text", "")
    return check_text(text, ctx.corpus()).as_dict()


async def theory_researcher(ctx: MissionContext, inputs: dict[str, Any]) -> dict[str, Any]:
    """Cherche preuves et contre-preuves candidates (théorie) ou sources (question)."""
    if ctx.lab is None:
        raise RuntimeError("laboratoire des théories non configuré")
    if inputs.get("theory_id"):
        theory_id = UUID(inputs["theory_id"])
        research = ctx.lab.research(theory_id)
        theory = ctx.lab.theory(theory_id)
        if theory is None:
            raise LookupError("théorie introuvable")
        return {"theory": theory, "research": research}
    return {"search": ctx.lab.search(inputs["question"], ctx.document_ids, limit=12)}


async def market_analyst(ctx: MissionContext, inputs: dict[str, Any]) -> dict[str, Any]:
    """Écarts EN→FR sur données publiques collectées : estimations, jamais de métrique privée."""
    if ctx.market is None:
        raise RuntimeError("Market Intelligence non configurée")
    return ctx.market.analysis(
        window_days=int(inputs.get("window_days", 90)), min_items=int(inputs.get("min_items", 5))
    )


def _market_angle(ctx: MissionContext, text: str) -> str | None:
    """Sujet de marché chiffré présent dans le livrable (le plus fort écart EN→FR)."""
    if ctx.market is None:
        return None
    folded = f" {fold(text)} "
    for topic in ctx.market.analysis()["topics"]:
        if topic["status"] == "SCORED" and f" {fold(topic['topic'])} " in folded:
            return (
                f"{topic['topic']} : écart EN→FR {topic['gap_score']}, saturation FR "
                f"{topic['saturation_fr']}"
            )
    return None


async def content_strategist(ctx: MissionContext, inputs: dict[str, Any]) -> dict[str, Any]:
    """Déclinaisons par plateforme à partir des faits VÉRIFIÉS d'un livrable approuvé."""
    source = ctx.source_mission
    if source is None or source["status"] != "APPROVED":
        raise RuntimeError("le livrable source doit être approuvé")
    result = source["result"]
    deliverable = result.get("deliverable") or ""
    return build_package(
        source_title=source["title"],
        deliverable=deliverable,
        checks=result["fact_check"]["checks"],
        platforms=inputs.get("platforms") or tuple(PLATFORMS),
        market_angle=_market_angle(ctx, deliverable),
    )


async def story_architect(ctx: MissionContext, inputs: dict[str, Any]) -> dict[str, Any]:
    """Architecture du script : sections horodatées, durée, références d'œuvres."""
    if ctx.storytelling is None:
        raise RuntimeError("Storytelling non configuré")
    script = ctx.storytelling.script(UUID(inputs["script_id"]))
    if not script["versions"]:
        raise LookupError("script sans version")
    return {
        "script_id": script["id"],
        "title": script["title"],
        "version": script["versions"][-1]["number"],
    }


async def editorial_critic(ctx: MissionContext, inputs: dict[str, Any]) -> dict[str, Any]:
    """Pré-notation sur 100 (8 critères) avec veto factuel ; enregistrée sur la version."""
    if ctx.storytelling is None:
        raise RuntimeError("Storytelling non configuré")
    return ctx.storytelling.evaluate(UUID(inputs["script_id"]))


def script_template(ctx: MissionContext) -> str:
    review = ctx.outputs["critique"]
    title = ctx.outputs["architecture"]["title"]
    analysis = review["analysis"]
    lines = [
        f"# Critique du script : {title} (version {review['version']})",
        f"Note : {review['nature']} ({review['method']}).",
        f"Note : total {review['total']}/100"
        + (" — VETO FACTUEL : erreur factuelle majeure." if review["factual_veto"] else "."),
        f"Note : {analysis['words']} mots, environ {analysis['estimated_minutes']} min à voix "
        f"haute, {len(analysis['sections'])} section(s).",
        "## Critères",
    ]
    for key, c in review["criteria"].items():
        lines.append(f"Note : {key} : {c['score']}/{c['max']} — {' ; '.join(c['notes'])}.")
    external = [w for w in analysis["works"] if w["status"] == "EXTERNAL_TO_SOURCE"]
    if external:
        lines.append("## Références hors bibliothèque, à sourcer")
        lines.extend(f"Note : {w['title']} ({w['year']})." for w in external)
    return "\n".join(lines)


async def performance_analyst(ctx: MissionContext, inputs: dict[str, Any]) -> dict[str, Any]:
    """Performances de la chaîne Primestone et signaux d'apprentissage (jamais de concurrent)."""
    if ctx.performance is None:
        raise RuntimeError("Performance Intelligence non configurée")
    return ctx.performance.report(min_items=int(inputs.get("min_items", 5)))


def performance_template(ctx: MissionContext) -> str:
    report = ctx.outputs["performance"]
    lines = [
        "# Bilan de performance de la chaîne",
        f"Note : {report['method']}, données {report['data_class']} ; {report['caveat']}",
        f"Note : {report['contents']} contenu(s), dont "
        f"{report['linked_to_scored_script']} relié(s) à un script noté.",
        "## Repères (médianes de la chaîne)",
    ]
    lines.extend(f"Note : {m} : {v:g}." for m, v in report["benchmarks"].items())
    lines.append("## Signaux")
    if report["status"] != "OK":
        lines.append(
            f"Note : données insuffisantes (minimum {report['min_items']} contenus reliés à un "
            "script noté) : aucun signal calculé."
        )
    lines.extend(f"Note : {r}" for r in report["recommendations"])
    if report["status"] == "OK" and not report["recommendations"]:
        lines.append("Note : aucun lien net (|rho| < 0,5) entre critères et performances.")
    return "\n".join(lines)


async def audience_analyst(ctx: MissionContext, _: dict[str, Any]) -> dict[str, Any]:
    """Segments (prouvés ou hypothétiques) et voix de la communauté, sans données personnelles."""
    if ctx.audience is None:
        raise RuntimeError("Audience Intelligence non configurée")
    return {"segments": ctx.audience.segments(), "community": ctx.audience.community()}


def audience_template(ctx: MissionContext) -> str:
    out = ctx.outputs["audience"]
    lines = [
        "# Note d'audience",
        "Note : segments définis par motivations et niveau de connaissance, jamais par l'âge.",
        "## Segments",
    ]
    if not out["segments"]:
        lines.append("Note : aucun segment défini.")
    for s in out["segments"]:
        kinds = sorted({e["kind"] for e in s["evidence"]})
        lines.append(
            f"Note : {s['name']} ({s['status']}) — motivations : {', '.join(s['motivations'])} ; "
            f"preuves : {', '.join(kinds) or 'aucune'}."
        )
    community = out["community"]
    lines.append("## Communauté (commentaires publics de la chaîne)")
    lines.append(f"Note : {community['comments']} commentaire(s) : {community['by_kind']}.")
    lines.extend(f"Note : proposition : {p}" for p in community["proposals"])
    return "\n".join(lines)


THEORY_RECOMMENDATIONS = {
    "REFUTED": "ABANDONNER OU REFORMULER (réfutée par une preuve canon)",
    "CONTESTED": "MAINTENIR COMME CONTESTÉE (preuves dans les deux sens)",
    "OPEN": "À INSTRUIRE (aucune preuve)",
}


def theory_recommendation(theory: dict[str, Any]) -> str:
    stale = [e for e in theory["evidence"] if not e["retracted_at"] and e["still_found"] is False]
    if stale:
        return "À CORRIGER (extrait cité absent de la transcription actuelle)"
    if theory["status"] in THEORY_RECOMMENDATIONS:
        return THEORY_RECOMMENDATIONS[theory["status"]]
    if theory["level"] == "THEORY":
        return "MAINTENIR EN THÉORIE (soutenue, contre-preuves cherchées)"
    return "RÉTROGRADER EN SPÉCULATION (pas de preuve canon solide)"


# --- Rédaction (Chief Editor) -----------------------------------------------------------------


# Libellés lisibles d'une relation, vue depuis la source (OUT) ou la cible (IN).
RELATION_LABELS_OUT = {
    "APPEARS_IN": "apparaît dans",
    "REFERENCES": "cite",
    "REVEALS": "se présente comme",
    "RELATED_TO": "lié à",
    "OPPOSES": "s'oppose à",
    "PRECEDES": "précède",
    "FORESHADOWS": "annonce",
    "CONTRADICTS": "contredit",
}
RELATION_LABELS_IN = {
    "APPEARS_IN": "accueille",
    "REFERENCES": "cité dans",
    "REVEALS": "revendiqué par",
    "RELATED_TO": "lié à",
    "OPPOSES": "opposé à",
    "PRECEDES": "suit",
    "FORESHADOWS": "annoncé par",
    "CONTRADICTS": "contredit par",
}


def _quote(excerpt: str | None) -> str:
    return f"« {excerpt.strip()} »" if excerpt and excerpt.strip() else ""


def dossier_template(ctx: MissionContext) -> str:
    research = ctx.outputs["character_research"]
    continuity = ctx.outputs.get("continuity", {})
    name = research["entity"]["name"]
    lines = [f"# Dossier : {name}"]
    others = [a for a in research["entity"]["aliases"] if fold(a) != fold(name)]
    if others:
        lines.append(f"Note : autres noms relevés : {', '.join(others)}.")
    lines.append("## Présence dans l'œuvre")
    for r in research["relations"]:
        if r["type"] != "APPEARS_IN":
            continue
        for e in r["evidence"][:3]:
            lines.append(
                f"{name} parle dans {r['target']['name']} : {_quote(e['excerpt'])} "
                f"{ctx.cite(e['document_id'], e['page'], e['panel'])}."
            )
    if research["claims"]:
        lines.append("## Affirmations du personnage")
        lines.append("Note : ce qu'un personnage affirme n'est pas un fait établi.")
        seen: set[tuple[str, int, int | None]] = set()
        for c in research["claims"]:
            e = c["evidence"][0]
            key = (e["document_id"], e["page"], e["panel"])
            if key in seen:  # une même réplique peut porter deux affirmations (âge, identité)
                continue
            seen.add(key)
            lines.append(
                f"{name} affirme : {_quote(e['excerpt'])} "
                f"{ctx.cite(e['document_id'], e['page'], e['panel'])}."
            )
    links = [r for r in research["relations"] if r["type"] != "APPEARS_IN"]
    if links:
        lines.append("## Liens relevés")
        for r in links:
            e = r["evidence"][0]
            outgoing = r["source"]["name"] == name
            other = r["target"]["name"] if outgoing else r["source"]["name"]
            label = r["qualifier"] or (RELATION_LABELS_OUT if outgoing else RELATION_LABELS_IN).get(
                r["type"], r["type"].lower()
            )
            lines.append(
                f"{name} — {label} {other} ({r['level']}) : {_quote(e['excerpt'])} "
                f"{ctx.cite(e['document_id'], e['page'], e['panel'])}."
            )
    if continuity.get("contradictions"):
        lines.append("## Points de continuité à examiner")
        for o in continuity["contradictions"]:
            parts = [
                f"{_quote(e['excerpt'])} {ctx.cite(e['document_id'], e['page'], e['panel'])}"
                for e in o["evidence"]
            ]
            lines.append(f"Contradiction possible ({o['predicate']}) : " + " et ".join(parts) + ".")
    for doc_id, missing in continuity.get("incomplete", {}).items():
        title = ctx.titles.get(UUID(doc_id), doc_id)
        lines.append(f"Note : pages non transcrites dans {title} : {', '.join(map(str, missing))}.")
    return "\n".join(lines)


def _evidence_line(ctx: MissionContext, label: str, e: dict[str, Any]) -> str:
    cite = ctx.cite(e["document_id"], e["page_number"], e["panel_index"])
    kind = e["level"] + ("" if e["excerpt"] else ", visuel")
    note = f" — {e['note']}" if e.get("note") else ""
    if e["excerpt"]:
        return f"{label} ({kind}) : {_quote(e['excerpt'])} {cite}{note}."
    return f"{label} ({kind}), page citée {cite}{note}."


def theory_template(ctx: MissionContext) -> str:
    out = ctx.outputs["theory_research"]
    theory, research = out["theory"], out["research"]
    active = [e for e in theory["evidence"] if not e["retracted_at"]]
    lines = [
        f"# Revue de théorie : {theory['title']}",
        f"Note : énoncé étudié, jamais canon : {theory['claim']}",
        f"Note : niveau {theory['level']}, statut {theory['status']}, confiance "
        f"{theory['confidence']} (méthode {theory['scoring']['method']}).",
        f"Note : recommandation : {theory_recommendation(theory)}.",
    ]
    for role, heading, label in (
        ("SUPPORTS", "## Preuves pour", "Élément pour"),
        ("REFUTES", "## Contre-preuves", "Élément contre"),
    ):
        items = [e for e in active if e["role"] == role]
        lines.append(heading)
        if not items:
            lines.append("Note : aucune.")
        lines.extend(_evidence_line(ctx, label, e) for e in items)
    if theory["alternatives"]:
        lines.append("## Explications alternatives")
        lines.extend(f"Note : alternative : {a['text']}" for a in theory["alternatives"])
    lines.append("## À examiner (proposé par le Theory Researcher, non classé)")
    if not research["passages"] and not research["possible_counter_evidence"]:
        lines.append("Note : aucun passage nouveau trouvé.")
    for p in research["passages"][:8]:
        lines.append(
            f"Passage à classer : {_quote(p['content'])} "
            f"{ctx.cite(p['document_id'], p['page'], p['panel'])}."
        )
    for o in research["possible_counter_evidence"]:
        parts = [
            f"{_quote(e['excerpt'])} {ctx.cite(e['document_id'], e['page'], e['panel'])}"
            for e in o["evidence"]
        ]
        lines.append(f"Contre-preuve possible ({o['predicate']}) : " + " et ".join(parts) + ".")
    return "\n".join(lines)


def research_template(ctx: MissionContext) -> str:
    found = ctx.outputs["research"]["search"]
    lines = [f"# Dossier de recherche : {found['query']}"]
    lines.append("Note : sources trouvées dans les pages transcrites ; aucune conclusion tirée.")
    if not found["passages"] and not found["observations"]:
        lines.append("Note : aucune source trouvée dans les pages transcrites.")
    if found["passages"]:
        lines.append("## Passages")
    for p in found["passages"]:
        lines.append(
            f"Source : {_quote(p['content'])} {ctx.cite(p['document_id'], p['page'], p['panel'])}."
        )
    if found["observations"]:
        lines.append("## Observations forensiques liées")
    for o in found["observations"]:
        e = o["evidence"][0]
        lines.append(
            f"Observation ({o['kind']}, {o['level']}) : {_quote(e['excerpt'])} "
            f"{ctx.cite(e['document_id'], e['page'], e['panel'])}."
        )
    return "\n".join(lines)


def market_template(ctx: MissionContext) -> str:
    analysis = ctx.outputs["market"]
    lines = [
        "# Note de marché : écarts EN → FR",
        f"Note : estimations ({analysis['method']}, fenêtre de {analysis['window_days']} jours, "
        f"{analysis['items_considered']} contenus) : {analysis['caveat']}",
    ]
    scored = [t for t in analysis["topics"] if t["status"] == "SCORED"]
    thin = [t for t in analysis["topics"] if t["status"] != "SCORED"]
    lines.append("## Sujets chiffrés (du plus grand écart au plus petit)")
    if not scored:
        lines.append("Note : aucun sujet n'a assez de données pour être chiffré.")
    for t in scored:
        en, fr = t["languages"]["en"], t["languages"]["fr"]
        culture = (
            f", différence culturelle {t['cultural_difference']:+.3f}"
            if t["cultural_difference"] is not None
            else ""
        )
        lines.append(
            f"Note : {t['topic']} : écart {t['gap_score']} (demande EN {t['demand_en']}, "
            f"saturation FR {t['saturation_fr']} ; {en['items']} contenu(s) EN, médiane "
            f"{en['median_views']:g} vues ; {fr['items']} contenu(s) FR{culture})."
        )
        for src in en["sources"][:2]:
            lines.append(
                f"Note : source publique : {src['title']} ({src['views']} vues relevées le "
                f"{str(src['observed_at'])[:10]}) {src['url'] or ''}".rstrip()
            )
    for key, label in (
        ("opportunities", "Opportunités"),
        ("niches", "Niches"),
        ("saturated_fr", "Déjà saturés en français"),
    ):
        if analysis[key]:
            lines.append(f"Note : {label} : {', '.join(analysis[key])}.")
    if thin:
        lines.append("## Données insuffisantes (à collecter)")
        lines.extend(f"Note : {t['topic']} : {t['explanation'][0]}." for t in thin)
    return "\n".join(lines)


TEMPLATES: dict[str, Callable[[MissionContext], str]] = {}


def audit_template(ctx: MissionContext) -> str:
    continuity = ctx.outputs["continuity"]
    lines = ["# Audit de continuité"]
    if not continuity["contradictions"]:
        lines.append("Note : aucune contradiction candidate relevée dans les pages transcrites.")
    for o in continuity["contradictions"]:
        parts = [
            f"{_quote(e['excerpt'])} {ctx.cite(e['document_id'], e['page'], e['panel'])}"
            for e in o["evidence"]
        ]
        lines.append(
            f"{o['subject']} — contradiction possible ({o['predicate']}) : "
            + " et ".join(parts)
            + "."
        )
    for o in continuity["aliases"]:
        lines.append(
            f"Note : « {o['subject']} » et « {o['value']} » désignent peut-être le même "
            "personnage (à confirmer)."
        )
    for doc_id, missing in continuity["incomplete"].items():
        title = ctx.titles.get(UUID(doc_id), doc_id)
        lines.append(f"Note : pages non transcrites dans {title} : {', '.join(map(str, missing))}.")
    return "\n".join(lines)


WRITER_PROMPT_ID = "editorial.dossier_writer"
WRITER_PROMPT_VERSION = "1.0.0"
WRITER_SYSTEM = (
    "Tu es rédacteur d'un dossier documentaire sur des comics. Réécris le dossier fourni en "
    "français fluide, sans rien ajouter qui n'y figure pas. Conserve À L'IDENTIQUE chaque "
    "citation entre « » et chaque référence entre crochets, placée juste après la citation. "
    "Garde les lignes commençant par « Note : » et les titres « # ». N'invente aucun fait, "
    "aucun nom, aucun âge, aucune date."
)


async def synthesis(ctx: MissionContext, _: dict[str, Any]) -> dict[str, Any]:
    template = TEMPLATES[ctx.mission_type](ctx)
    result: dict[str, Any] = {"text": template, "author": "gabarit déterministe", "writer": None}
    if ctx.writer is None:
        return result
    corpus = ctx.corpus()
    baseline = check_text(template, corpus)
    try:
        prose, call = await ctx.writer(WRITER_SYSTEM, template)
    except Exception as exc:  # le rédacteur est facultatif : on garde le gabarit
        result["writer"] = {
            "accepted": False,
            "reason": f"rédacteur indisponible ({type(exc).__name__})",
        }
        return result
    checked = check_text(prose, corpus)
    verified = sum(1 for c in checked.checks if c.status == "VERIFIED")
    expected = sum(1 for c in baseline.checks if c.status == "VERIFIED")
    accepted = checked.verdict != "FAIL" and verified >= expected
    result["writer"] = {
        **call,
        "accepted": accepted,
        "reason": "texte vérifié"
        if accepted
        else f"rejeté par le vérificateur ({checked.verdict}, "
        f"{verified}/{expected} citations vérifiées)",
    }
    if accepted:
        result.update(text=prose, author=f"modèle local {call.get('model')}")
    return result


AGENTS: dict[str, AgentSpec] = {
    spec.key: spec
    for spec in (
        AgentSpec(
            "research_director",
            "Research Director",
            "prépare des données fraîches (forensique, connaissances) et l'état de complétude",
            "ne conclut rien ; ne lit que les transcriptions servies",
            6,
            research_director,
        ),
        AgentSpec(
            "comics_analyst",
            "Comics Analyst",
            "synthèse chiffrée : personnages, répliques, mentions, observations",
            "aucune interprétation narrative",
            6,
            comics_analyst,
        ),
        AgentSpec(
            "continuity_editor",
            "Continuity Editor",
            "contradictions candidates, variantes de noms, pages manquantes",
            "signale des candidats, ne tranche jamais",
            6,
            continuity_editor,
        ),
        AgentSpec(
            "character_researcher",
            "Character Researcher",
            "dossier d'un personnage depuis le graphe : présence, liens, affirmations",
            "uniquement ce qui est prouvé par une page",
            6,
            character_researcher,
        ),
        AgentSpec(
            "fact_checker",
            "Fact Checker",
            "vérifie chaque citation sur la page citée, signale le non-sourcé "
            "et les âges contredits",
            "ne juge pas le style ; une erreur majeure bloque la validation",
            6,
            fact_checker,
        ),
        AgentSpec(
            "chief_editor_writer",
            "Chief Editor (rédaction)",
            "rédige le dossier ; gabarit déterministe, modèle local gratuit en option",
            "un texte de modèle n'est retenu que s'il passe le Fact Checker",
            6,
            synthesis,
        ),
        AgentSpec(
            "visual_analyst",
            "Visual Analyst",
            "analyse des images (décors, objets, symboles)",
            "exige un modèle de vision",
            3,
        ),
        AgentSpec(
            "theory_researcher",
            "Theory Researcher",
            "cherche preuves et contre-preuves candidates, sources d'une question",
            "propose, ne classe jamais : un humain décide pour/contre",
            7,
            theory_researcher,
        ),
        AgentSpec(
            "market_analyst",
            "Market Analyst",
            "écarts EN→FR, sujets populaires, niches, saturation, différences culturelles",
            "données publiques collectées uniquement ; estimations ; aucune métrique privée",
            8,
            market_analyst,
        ),
        AgentSpec(
            "content_strategist",
            "Content Strategist",
            "déclinaisons YouTube, TikTok, Reels, carrousel depuis un livrable approuvé",
            "reprend mot pour mot les faits vérifiés ; formats datés à revérifier",
            9,
            content_strategist,
        ),
        AgentSpec(
            "story_architect",
            "Story Architect",
            "sections horodatées, durée, références d'œuvres (bibliothèque ou à sourcer)",
            "analyse ; ne réécrit pas le script",
            10,
            story_architect,
        ),
        AgentSpec(
            "editorial_critic",
            "Editorial Critic",
            "pré-notation sur 100 (8 critères) et veto factuel",
            "heuristique à confirmer par un humain ; le veto est absolu",
            10,
            editorial_critic,
        ),
        AgentSpec(
            "audience_analyst",
            "Audience Analyst",
            "segments prouvés ou hypothétiques, questions et demandes de la communauté",
            "jamais d'âge, jamais d'identité de commentateur ; propose sans publier",
            15,
            audience_analyst,
        ),
        AgentSpec(
            "performance_analyst",
            "Performance Analyst",
            "repères de la chaîne et signaux critères du script → rétention / CTR",
            "chaîne Primestone uniquement ; corrélation ≠ causalité",
            11,
            performance_analyst,
        ),
    )
}


@dataclass(frozen=True)
class PlannedTask:
    key: str
    agent: str
    critical: bool
    inputs: dict[str, Any] = field(default_factory=dict)


def plan(mission_type: str, params: dict[str, Any]) -> list[PlannedTask]:
    """Plan du Research Director selon le type de mission."""
    prepare = PlannedTask("prepare", "research_director", critical=True)
    if mission_type == "CHARACTER_DOSSIER":
        character = params.get("character")
        if not character:
            raise ValueError("le paramètre « character » est obligatoire")
        return [
            prepare,
            PlannedTask(
                "character_research", "character_researcher", True, {"character": character}
            ),
            PlannedTask("continuity", "continuity_editor", False, {"character": character}),
            PlannedTask("synthesis", "chief_editor_writer", True),
            PlannedTask("fact_check", "fact_checker", True),
        ]
    if mission_type == "CONTINUITY_AUDIT":
        return [
            prepare,
            PlannedTask("analysis", "comics_analyst", False),
            PlannedTask("continuity", "continuity_editor", True),
            PlannedTask("synthesis", "chief_editor_writer", True),
            PlannedTask("fact_check", "fact_checker", True),
        ]
    if mission_type == "FACT_CHECK":
        draft = params.get("draft")
        if not draft or not str(draft).strip():
            raise ValueError("le paramètre « draft » (texte à vérifier) est obligatoire")
        return [prepare, PlannedTask("fact_check", "fact_checker", True, {"text": draft})]
    if mission_type == "THEORY_REVIEW":
        theory_id = params.get("theory_id")
        if not theory_id:
            raise ValueError("le paramètre « theory_id » est obligatoire")
        return [
            prepare,
            PlannedTask(
                "theory_research", "theory_researcher", True, {"theory_id": str(theory_id)}
            ),
            PlannedTask("synthesis", "chief_editor_writer", True),
            PlannedTask("fact_check", "fact_checker", True),
        ]
    if mission_type == "AUDIENCE_BRIEF":
        return [
            PlannedTask("audience", "audience_analyst", True),
            PlannedTask("synthesis", "chief_editor_writer", True),
        ]
    if mission_type == "PERFORMANCE_REVIEW":
        return [
            PlannedTask(
                "performance",
                "performance_analyst",
                True,
                {k: params[k] for k in ("min_items",) if k in params},
            ),
            PlannedTask("synthesis", "chief_editor_writer", True),
        ]
    if mission_type == "SCRIPT_REVIEW":
        if not params.get("script_id"):
            raise ValueError("le paramètre « script_id » est obligatoire")
        script_inputs = {"script_id": str(params["script_id"])}
        return [
            PlannedTask("architecture", "story_architect", True, script_inputs),
            PlannedTask("critique", "editorial_critic", True, script_inputs),
            PlannedTask("synthesis", "chief_editor_writer", True),
        ]
    if mission_type == "SOCIAL_PACKAGE":
        if not params.get("source_mission_id"):
            raise ValueError("le paramètre « source_mission_id » est obligatoire")
        social_inputs: dict[str, Any] = {}
        if params.get("platforms"):
            social_inputs["platforms"] = list(params["platforms"])
        return [
            prepare,
            PlannedTask("social", "content_strategist", True, social_inputs),
            PlannedTask("synthesis", "chief_editor_writer", True),
            PlannedTask("fact_check", "fact_checker", True),
        ]
    if mission_type == "MARKET_BRIEF":
        inputs: dict[str, Any] = {k: params[k] for k in ("window_days", "min_items") if k in params}
        return [
            PlannedTask("market", "market_analyst", True, inputs),
            PlannedTask("synthesis", "chief_editor_writer", True),
        ]
    if mission_type == "RESEARCH_DOSSIER":
        question = str(params.get("question") or "").strip()
        if not question:
            raise ValueError("le paramètre « question » est obligatoire")
        return [
            prepare,
            PlannedTask("research", "theory_researcher", True, {"question": question}),
            PlannedTask("synthesis", "chief_editor_writer", True),
            PlannedTask("fact_check", "fact_checker", True),
        ]
    raise ValueError(f"type de mission inconnu : {mission_type}")


MISSION_TYPES = (
    "CHARACTER_DOSSIER",
    "CONTINUITY_AUDIT",
    "FACT_CHECK",
    "THEORY_REVIEW",
    "RESEARCH_DOSSIER",
    "MARKET_BRIEF",
    "SOCIAL_PACKAGE",
    "SCRIPT_REVIEW",
    "PERFORMANCE_REVIEW",
    "AUDIENCE_BRIEF",
)
# Livrables qu'on peut décliner pour les réseaux (ils citent des pages vérifiables).
DECLINABLE = ("CHARACTER_DOSSIER", "CONTINUITY_AUDIT", "THEORY_REVIEW", "RESEARCH_DOSSIER")
# Missions qui ne portent sur aucun comic (pas de documents, pas de citations de pages).
WITHOUT_DOCUMENTS = ("MARKET_BRIEF", "SCRIPT_REVIEW", "PERFORMANCE_REVIEW", "AUDIENCE_BRIEF")
TEMPLATES.update(
    CHARACTER_DOSSIER=dossier_template,
    CONTINUITY_AUDIT=audit_template,
    THEORY_REVIEW=theory_template,
    RESEARCH_DOSSIER=research_template,
    MARKET_BRIEF=market_template,
    SOCIAL_PACKAGE=lambda ctx: render(ctx.outputs["social"]),
    SCRIPT_REVIEW=script_template,
    PERFORMANCE_REVIEW=performance_template,
    AUDIENCE_BRIEF=audience_template,
)
