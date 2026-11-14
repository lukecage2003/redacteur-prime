from uuid import UUID, uuid4

import pytest

from primestone.forensic import ObservationKind, TextRow, extract, fold
from primestone.forensic.extract import EvidenceRole, ForensicObservation
from primestone.provenance import BoundingBox, EvidenceLevel

DOC = uuid4()
BOX = BoundingBox(x=0.1, y=0.1, width=0.2, height=0.1)


def row(
    text: str,
    *,
    page: int = 1,
    order: int = 1,
    speaker: str | None = None,
    human: bool = True,
    confidence: float = 1.0,
    kind: str = "DIALOGUE",
    document: UUID = DOC,
) -> TextRow:
    return TextRow(
        id=uuid4(),
        analysis_id=uuid4(),
        document_id=document,
        page=page,
        order=order,
        panel_index=1,
        kind=kind,
        text=text,
        language="fr",
        confidence=confidence,
        speaker=speaker,
        speaker_confidence=1.0 if human else 0.6,
        bbox=BOX,
        human=human,
    )


def of_kind(
    observations: list[ForensicObservation], kind: ObservationKind
) -> list[ForensicObservation]:
    return [o for o in observations if o.kind is kind]


def test_every_observation_has_exact_evidence() -> None:
    observations = extract([row("Je suis Batman.", speaker="Batman"), row("BOUM", kind="SFX")])
    assert observations
    for obs in observations:
        assert obs.evidence
        assert all(e.document_id == DOC and e.page == 1 and e.text_region_id for e in obs.evidence)


def test_human_transcription_is_canon_uncertain_model_text_is_not() -> None:
    human = row("Bonjour.", human=True)
    shaky = row("B0nj0ur?", human=False, confidence=0.5, order=2)
    sure = row("Salut.", human=False, confidence=0.95, order=3)
    levels = {
        o.statement: o.level
        for o in of_kind(extract([human, shaky, sure]), ObservationKind.LETTERING)
    }
    assert levels["Réplique : « Bonjour. »"] is EvidenceLevel.CANON
    assert levels["Réplique : « B0nj0ur? »"] is EvidenceLevel.INTERPRETATION
    assert levels["Réplique : « Salut. »"] is EvidenceLevel.CANON


def test_model_speaker_attribution_is_never_canon() -> None:
    model = row("Qui va là ?", speaker="Gardien", human=False, confidence=0.99)
    speech = of_kind(extract([model]), ObservationKind.SPEECH)
    assert speech[0].level is EvidenceLevel.INTERPRETATION
    assert speech[0].confidence == pytest.approx(0.6)
    verified = of_kind(extract([row("Qui va là ?", speaker="Gardien")]), ObservationKind.SPEECH)
    assert verified[0].level is EvidenceLevel.CANON


def test_mentions_are_accent_and_case_insensitive() -> None:
    rows = [
        row("Je m'appelle Élodie.", speaker="Élodie"),
        row("ELODIE EST EN RETARD !", speaker="Marc", page=2),
    ]
    mentions = of_kind(extract(rows), ObservationKind.MENTION)
    assert {(m.subject, m.evidence[0].page) for m in mentions} >= {("Élodie", 1), ("Élodie", 2)}


def test_first_appearance_per_document() -> None:
    other = uuid4()
    rows = [
        row("…", speaker="Robin", page=5),
        row("Robin ?", speaker="Batman", page=2),
        row("Me voilà.", speaker="Robin", page=1, document=other),
    ]
    firsts = {
        (o.subject, o.evidence[0].document_id): int(o.value or 0)
        for o in of_kind(extract(rows), ObservationKind.FIRST_APPEARANCE)
    }
    assert firsts[("Robin", DOC)] == 2  # mentionné page 2 avant de parler page 5
    assert firsts[("Robin", other)] == 1


def test_claims_are_reported_as_claims_not_facts() -> None:
    claims = of_kind(extract([row("J'ai 32 ans.", speaker="Bruce")]), ObservationKind.CLAIM)
    assert len(claims) == 1
    assert (claims[0].predicate, claims[0].value) == ("age", "32")
    assert "affirmation, non vérifiée" in claims[0].statement


def test_conflicting_claims_become_contradiction_candidates() -> None:
    rows = [
        row("I'm 32 years old.", speaker="Bruce", page=3),
        row("J'ai 40 ans, figure-toi.", speaker="Bruce", page=18),
    ]
    contradictions = of_kind(extract(rows), ObservationKind.CONTRADICTION_CANDIDATE)
    assert len(contradictions) == 1
    candidate = contradictions[0]
    assert candidate.level is EvidenceLevel.INTERPRETATION
    assert "temps écoulé" in candidate.statement
    assert sorted(e.role for e in candidate.evidence) == [
        EvidenceRole.REFUTES,
        EvidenceRole.SUPPORTS,
    ]


def test_identity_claims_in_all_caps_need_a_known_name() -> None:
    rows = [
        row("I AM HUNGRY.", speaker="Bruce"),
        row("I AM BATMAN.", speaker="Bruce", order=2),
    ]
    identities = [
        o.value
        for o in of_kind(extract(rows, {"Batman"}), ObservationKind.CLAIM)
        if o.predicate == "identity"
    ]
    assert identities == ["Batman"]
    # Sans lexique, rien n'est inventé à partir de capitales.
    assert not [
        o for o in of_kind(extract(rows), ObservationKind.CLAIM) if o.predicate == "identity"
    ]


def test_secret_identity_is_flagged_for_review() -> None:
    rows = [
        row("Je suis Bruce Wayne.", speaker="Inconnu"),
        row("Je suis Batman.", speaker="Inconnu", page=9),
    ]
    contradictions = of_kind(extract(rows), ObservationKind.CONTRADICTION_CANDIDATE)
    assert contradictions
    assert contradictions[0].value == "Batman / Bruce Wayne"


def test_alias_candidates() -> None:
    rows = [
        row("…", speaker="Catwoman"),
        row("…", speaker="Cat-Woman", order=2),
        row("…", speaker="Joker", order=3),
    ]
    aliases = of_kind(extract(rows), ObservationKind.ALIAS_CANDIDATE)
    assert [(a.subject, a.value) for a in aliases] == [("Cat-Woman", "Catwoman")]
    assert aliases[0].level is EvidenceLevel.INTERPRETATION


def test_keys_are_stable_and_unique() -> None:
    rows = [
        row("Je suis Batman.", speaker="Batman"),
        row("I'm 30 years old.", speaker="Batman", order=2),
    ]
    first = [o.key for o in extract(rows, {"Batman"})]
    second = [o.key for o in extract(rows, {"Batman"})]
    assert first == second
    assert len(set(first)) == len(first)


def test_guards() -> None:
    with pytest.raises(ValueError, match="sans preuve"):
        ForensicObservation(
            kind=ObservationKind.LETTERING,
            level=EvidenceLevel.CANON,
            statement="x",
            confidence=1,
            evidence=(),
        )
    assert fold("  Élodie-Marie  ") == "elodie-marie"
