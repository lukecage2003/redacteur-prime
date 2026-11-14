from uuid import uuid4

import pytest
from pydantic import ValidationError

from primestone.provenance import (
    BoundingBox,
    DocumentRef,
    EvidenceLevel,
    Observation,
    Theory,
    is_analysis_complete,
    missing_pages,
)

DOC = uuid4()


def ref(page: int = 1, panel: int | None = 2) -> DocumentRef:
    return DocumentRef(document_id=DOC, page=page, panel=panel)


class TestObservation:
    def test_requires_at_least_one_evidence(self) -> None:
        with pytest.raises(ValidationError):
            Observation(
                statement="X apparaît", level=EvidenceLevel.CANON, confidence=1, evidence=[]
            )

    def test_valid_canon_observation(self) -> None:
        obs = Observation(
            statement="Le symbole apparaît sur la cape",
            level=EvidenceLevel.CANON,
            confidence=0.95,
            evidence=[ref(12, 3)],
        )
        assert obs.evidence[0].page == 12

    def test_theory_level_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Theory"):
            Observation(statement="s", level=EvidenceLevel.THEORY, confidence=0.4, evidence=[ref()])

    @pytest.mark.parametrize("confidence", [-0.1, 1.1])
    def test_confidence_bounds(self, confidence: float) -> None:
        with pytest.raises(ValidationError):
            Observation(
                statement="s", level=EvidenceLevel.CANON, confidence=confidence, evidence=[ref()]
            )


class TestTheory:
    def base(self, **overrides: object) -> dict[str, object]:
        data: dict[str, object] = {
            "title": "Le mentor est le traître",
            "claim": "Les indices des pages 4 et 18 convergent",
            "confidence": 0.35,
            "supporting": [ref(4), ref(18)],
            "counter_evidence": [ref(22)],
            "alternatives": ["Manipulation par un tiers"],
            "counter_evidence_searched": True,
        }
        data.update(overrides)
        return data

    def test_valid_theory(self) -> None:
        theory = Theory.model_validate(self.base())
        assert theory.level is EvidenceLevel.THEORY

    def test_counter_evidence_search_is_mandatory(self) -> None:
        with pytest.raises(ValidationError, match="contre-preuves"):
            Theory.model_validate(self.base(counter_evidence_searched=False))

    def test_alternatives_are_mandatory(self) -> None:
        with pytest.raises(ValidationError, match="alternative"):
            Theory.model_validate(self.base(alternatives=[]))

    def test_theory_cannot_be_canon(self) -> None:
        with pytest.raises(ValidationError):
            Theory.model_validate(self.base(level=EvidenceLevel.CANON))

    def test_supporting_evidence_is_mandatory(self) -> None:
        with pytest.raises(ValidationError):
            Theory.model_validate(self.base(supporting=[]))


class TestBoundingBox:
    def test_inside_page(self) -> None:
        BoundingBox(x=0.5, y=0.5, width=0.5, height=0.5)

    def test_overflow_rejected(self) -> None:
        with pytest.raises(ValidationError, match="limites"):
            BoundingBox(x=0.6, y=0.1, width=0.5, height=0.2)


class TestCompleteness:
    def test_missing_pages_listed(self) -> None:
        assert missing_pages(5, {1, 2, 4}) == [3, 5]

    def test_complete_only_when_all_pages_processed(self) -> None:
        assert is_analysis_complete(3, {1, 2, 3})
        assert not is_analysis_complete(3, {1, 3})

    def test_empty_document_is_never_complete(self) -> None:
        assert not is_analysis_complete(0, set())

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="positif"):
            missing_pages(-1, set())
