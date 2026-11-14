from primestone.lab import EvidenceInput, score


def ev(role: str = "SUPPORTS", level: str = "CANON", verified: bool = True, excerpt: bool = True):
    return EvidenceInput(role, level, verified, excerpt)


def test_no_evidence_is_open_speculation() -> None:
    s = score([], counter_search_done=False)
    assert (s.level, s.status, s.confidence) == ("SPECULATION", "OPEN", 0)


def test_theory_requires_solid_canon_and_counter_search() -> None:
    before = score([ev()], counter_search_done=False)
    assert before.level == "SPECULATION"
    assert any("contre-preuves à faire" in e for e in before.explanation)
    after = score([ev()], counter_search_done=True)
    assert (after.level, after.status, after.confidence) == ("THEORY", "SUPPORTED", 0.5)


def test_unverified_or_interpretation_never_makes_a_theory() -> None:
    weak = [ev(verified=False), ev(level="INTERPRETATION", verified=False)]
    s = score(weak, counter_search_done=True)
    assert s.level == "SPECULATION"
    assert s.support == 1.0  # 0.6 + 0.4
    # Une preuve visuelle (sans extrait) attestée par un humain est solide.
    assert score([ev(verified=False, excerpt=False)], counter_search_done=True).level == "THEORY"


def test_confidence_is_capped_without_counter_search() -> None:
    many = [ev() for _ in range(5)]
    assert score(many, counter_search_done=False).confidence == 0.5
    assert score(many, counter_search_done=True).confidence == round(5 / 6, 3)


def test_status_contested_and_refuted() -> None:
    contested = score([ev(), ev("REFUTES", "INTERPRETATION", False)], counter_search_done=True)
    assert contested.status == "CONTESTED"
    refuted = score(
        [ev("SUPPORTS", "INTERPRETATION", False), ev("REFUTES")], counter_search_done=True
    )
    assert refuted.status == "REFUTED"
    weak_only = score([ev("REFUTES", "SPECULATION", False)], counter_search_done=True)
    assert weak_only.status == "CONTESTED"
