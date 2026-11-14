"""Extracteurs forensiques déterministes (aucun modèle, aucun coût).

Discipline de preuve :
- le TEXTE lettré est CANON s'il a été transcrit par un humain ou avec une confiance ≥ 0,9 ;
  sinon INTERPRETATION (transcription incertaine) ;
- l'ATTRIBUTION d'une réplique à un personnage est CANON seulement si un humain l'a validée ;
  une attribution par modèle reste INTERPRETATION ;
- une AFFIRMATION d'un personnage (« j'ai 32 ans ») est rapportée comme affirmation, jamais
  comme fait : le personnage peut mentir, se tromper ou être déguisé ;
- les contradictions et les variantes de noms sont des CANDIDATS à examiner, jamais des
  conclusions ;
- chaque observation porte au moins une référence documentaire exacte.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from primestone.provenance import BoundingBox, EvidenceLevel
from primestone.vision.evaluation import levenshtein

EXTRACTOR_VERSION = "forensic-rules@1.0.0"
CANON_TRANSCRIPTION_CONFIDENCE = 0.9
ALIAS_MAX_DISTANCE_RATIO = 0.25


class ObservationKind(StrEnum):
    LETTERING = "LETTERING"  # texte lettré sur la page
    SPEECH = "SPEECH"  # réplique attribuée à un personnage
    MENTION = "MENTION"  # nom d'un personnage écrit dans un texte
    CLAIM = "CLAIM"  # affirmation d'un personnage (âge, identité…)
    FIRST_APPEARANCE = "FIRST_APPEARANCE"  # première page où un personnage est attesté
    ALIAS_CANDIDATE = "ALIAS_CANDIDATE"  # deux graphies probablement du même nom
    CONTRADICTION_CANDIDATE = "CONTRADICTION_CANDIDATE"  # affirmations incompatibles


class EvidenceRole(StrEnum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"


@dataclass(frozen=True)
class TextRow:
    """Zone de texte de la dernière analyse d'une page (entrée des extracteurs)."""

    id: UUID
    analysis_id: UUID
    document_id: UUID
    page: int
    order: int
    panel_index: int | None
    kind: str
    text: str
    language: str | None
    confidence: float
    speaker: str | None
    speaker_confidence: float | None
    bbox: BoundingBox
    human: bool  # transcription saisie / validée par un humain


@dataclass(frozen=True)
class Evidence:
    document_id: UUID
    page: int
    panel_index: int | None
    text_region_id: UUID | None
    analysis_id: UUID | None
    bbox: BoundingBox | None
    excerpt: str | None
    role: EvidenceRole = EvidenceRole.SUPPORTS

    @classmethod
    def of(cls, row: TextRow, role: EvidenceRole = EvidenceRole.SUPPORTS) -> Evidence:
        return cls(
            document_id=row.document_id,
            page=row.page,
            panel_index=row.panel_index,
            text_region_id=row.id,
            analysis_id=row.analysis_id,
            bbox=row.bbox,
            excerpt=row.text[:2000],
            role=role,
        )


@dataclass(frozen=True)
class ForensicObservation:
    kind: ObservationKind
    level: EvidenceLevel
    statement: str
    confidence: float
    evidence: tuple[Evidence, ...]
    subject: str | None = None
    predicate: str | None = None
    value: str | None = None
    extractor: str = EXTRACTOR_VERSION
    notes: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("une observation sans preuve est interdite")
        if self.level is EvidenceLevel.THEORY:
            raise ValueError("les théories relèvent du laboratoire (phase 7), pas des extracteurs")

    @property
    def key(self) -> str:
        """Identité stable : ré-exécuter les extracteurs ne crée aucun doublon."""
        parts = [
            self.extractor,
            self.kind.value,
            self.level.value,
            self.subject or "",
            self.predicate or "",
            self.value or "",
            self.statement,
            *sorted(f"{e.text_region_id}:{e.role.value}" for e in self.evidence),
        ]
        return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


# --- Normalisation des noms ----------------------------------------------------------------


def fold(name: str) -> str:
    """Forme de comparaison : sans accents, casse ni ponctuation superflue."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s-]", " ", stripped).casefold().split())


def _transcription_level(row: TextRow) -> EvidenceLevel:
    if row.human or row.confidence >= CANON_TRANSCRIPTION_CONFIDENCE:
        return EvidenceLevel.CANON
    return EvidenceLevel.INTERPRETATION


def _attribution_level(row: TextRow) -> EvidenceLevel:
    return EvidenceLevel.CANON if row.human else EvidenceLevel.INTERPRETATION


KIND_LABELS = {
    "DIALOGUE": "Réplique",
    "THOUGHT": "Pensée",
    "NARRATION": "Narration",
    "SFX": "Onomatopée",
    "CAPTION": "Légende",
    "OTHER": "Texte du décor",
}

# --- Affirmations (FR / EN) ----------------------------------------------------------------

_AGE = [
    re.compile(r"\bj'?\s?ai\s+(\d{1,3})\s+ans\b", re.IGNORECASE),
    re.compile(r"\bI(?:'m|\s+am)\s+(\d{1,3})\s+years?\s+old\b", re.IGNORECASE),
]
_IDENTITY = [
    re.compile(
        r"\b(?:je\s+m'appelle|je\s+suis|my\s+name\s+is|i\s+am|i'm)"
        r"\s+([\w'-]+(?:\s+[\w'-]+)?)",
        re.IGNORECASE,
    ),
]


def _identity_name(candidate: str, text: str, lexicon: dict[str, str]) -> str | None:
    """Nom revendiqué, ou None. Le lettrage de comics étant souvent en capitales, un nom
    n'est retenu que s'il est connu du lexique, ou s'il porte une majuscule dans un texte
    en casse mixte (« Je suis Batman » oui ; « I AM HUNGRY » non)."""
    words = candidate.split()
    for size in (len(words), 1):  # « Bruce Wayne » avant « Bruce »
        name = " ".join(words[:size])
        if fold(name) in lexicon:
            return lexicon[fold(name)]
    mixed_case = not text.isupper()
    if mixed_case and words and words[0][:1].isupper() and len(words[0]) > 2:
        two = " ".join(w for w in words[:2] if w[:1].isupper())
        return two or words[0]
    return None


def _claims(row: TextRow, lexicon: dict[str, str]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for pattern in _AGE:
        found += [("age", m.group(1)) for m in pattern.finditer(row.text)]
    for pattern in _IDENTITY:
        for m in pattern.finditer(row.text):
            name = _identity_name(m.group(1).strip(), row.text, lexicon)
            if name:
                found.append(("identity", name))
    return found


# --- Extraction ----------------------------------------------------------------------------


def extract(
    rows: list[TextRow], known_characters: set[str] | None = None
) -> list[ForensicObservation]:
    """Observations d'un ensemble de pages (un ou plusieurs documents d'une même continuité).

    Les documents sont lus dans l'ordre où ils apparaissent dans `rows`."""
    observations: list[ForensicObservation] = []
    # Ordre des documents = ordre fourni (tome 1, tome 2…) : il compte pour « qui l'a dit
    # en premier » ; les identifiants, aléatoires, ne doivent jamais décider de l'ordre.
    rank: dict[UUID, int] = {}
    for r in rows:
        rank.setdefault(r.document_id, len(rank))
    rows = sorted(rows, key=lambda r: (rank[r.document_id], r.page, r.order))

    for row in rows:
        level = _transcription_level(row)
        observations.append(
            ForensicObservation(
                kind=ObservationKind.LETTERING,
                level=level,
                predicate=row.kind,
                statement=f"{KIND_LABELS.get(row.kind, row.kind)} : « {row.text} »",
                confidence=1.0 if row.human else row.confidence,
                evidence=(Evidence.of(row),),
            )
        )
        if row.speaker and row.kind in ("DIALOGUE", "THOUGHT"):
            verb = "pense" if row.kind == "THOUGHT" else "dit"
            observations.append(
                ForensicObservation(
                    kind=ObservationKind.SPEECH,
                    level=_attribution_level(row),
                    subject=row.speaker,
                    statement=f"{row.speaker} {verb} : « {row.text} »",
                    confidence=1.0 if row.human else (row.speaker_confidence or 0.0),
                    evidence=(Evidence.of(row),),
                )
            )

    # Lexique des personnages : locuteurs attestés + noms fournis par l'utilisateur.
    lexicon: dict[str, str] = {}
    for name in sorted({r.speaker for r in rows if r.speaker} | (known_characters or set())):
        if len(fold(name)) >= 3:
            lexicon.setdefault(fold(name), name)

    appearances: dict[str, list[tuple[TextRow, EvidenceLevel]]] = defaultdict(list)
    for row in rows:
        if row.speaker:
            appearances[fold(row.speaker)].append((row, _attribution_level(row)))
        haystack = f" {fold(row.text)} "
        for folded, name in lexicon.items():
            if f" {folded} " in haystack:
                level = _transcription_level(row)
                observations.append(
                    ForensicObservation(
                        kind=ObservationKind.MENTION,
                        level=level,
                        subject=name,
                        statement=f"Le nom « {name} » est écrit dans le texte",
                        confidence=1.0 if row.human else row.confidence,
                        evidence=(Evidence.of(row),),
                    )
                )
                appearances[folded].append((row, level))

    # Première attestation de chaque personnage, par document.
    for folded, hits in appearances.items():
        name = lexicon.get(folded, hits[0][0].speaker or folded)
        by_document: dict[UUID, list[tuple[TextRow, EvidenceLevel]]] = defaultdict(list)
        for hit in hits:
            by_document[hit[0].document_id].append(hit)
        for document_hits in by_document.values():
            first_row, first_level = min(document_hits, key=lambda h: (h[0].page, h[0].order))
            observations.append(
                ForensicObservation(
                    kind=ObservationKind.FIRST_APPEARANCE,
                    # Dépend aussi de la complétude du document : voir ForensicService.
                    level=first_level,
                    subject=name,
                    value=str(first_row.page),
                    statement=f"{name} est attesté pour la première fois page {first_row.page}",
                    confidence=1.0 if first_level is EvidenceLevel.CANON else 0.7,
                    evidence=(Evidence.of(first_row),),
                )
            )

    # Affirmations des personnages, puis contradictions candidates.
    claims: dict[tuple[str, str], list[tuple[str, TextRow]]] = defaultdict(list)
    for row in rows:
        if not row.speaker:
            continue
        for predicate, value in _claims(row, lexicon):
            label = "affirme avoir" if predicate == "age" else "affirme être"
            suffix = " ans" if predicate == "age" else ""
            observations.append(
                ForensicObservation(
                    kind=ObservationKind.CLAIM,
                    level=_attribution_level(row),
                    subject=row.speaker,
                    predicate=predicate,
                    value=value,
                    statement=f"{row.speaker} {label} {value}{suffix} (affirmation, non vérifiée)",
                    confidence=1.0 if row.human else (row.speaker_confidence or 0.0),
                    evidence=(Evidence.of(row),),
                )
            )
            claims[(fold(row.speaker), predicate)].append((value, row))

    for (_, predicate), items in claims.items():
        values = sorted({fold(v) for v, _ in items})
        if len(values) < 2:
            continue
        first_value = fold(items[0][0])
        subject = items[0][1].speaker or ""
        evidence = tuple(
            Evidence.of(
                row, EvidenceRole.SUPPORTS if fold(v) == first_value else EvidenceRole.REFUTES
            )
            for v, row in items
        )
        shown = " / ".join(sorted({v for v, _ in items}))
        observations.append(
            ForensicObservation(
                kind=ObservationKind.CONTRADICTION_CANDIDATE,
                level=EvidenceLevel.INTERPRETATION,
                subject=subject,
                predicate=predicate,
                value=shown,
                statement=(
                    f"Affirmations incompatibles de {subject} ({predicate}) : {shown}. "
                    "Explications possibles : temps écoulé, mensonge, erreur, déguisement, "
                    "continuité différente."
                ),
                confidence=0.5,
                evidence=evidence,
            )
        )

    # Variantes probables d'un même nom (à confirmer par un humain).
    speakers: dict[str, TextRow] = {}
    for row in rows:
        if row.speaker:
            speakers.setdefault(row.speaker, row)
    names = sorted(speakers)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            fa, fb = fold(a), fold(b)
            distance_ratio = 0.0 if fa == fb else levenshtein(fa, fb) / max(len(fa), len(fb))
            if distance_ratio <= ALIAS_MAX_DISTANCE_RATIO and a != b:
                observations.append(
                    ForensicObservation(
                        kind=ObservationKind.ALIAS_CANDIDATE,
                        level=EvidenceLevel.INTERPRETATION,
                        subject=a,
                        predicate="same_name_as",
                        value=b,
                        statement=f"« {a} » et « {b} » désignent probablement le même personnage",
                        confidence=round(1 - distance_ratio, 3),
                        evidence=(Evidence.of(speakers[a]), Evidence.of(speakers[b])),
                    )
                )
    return observations
