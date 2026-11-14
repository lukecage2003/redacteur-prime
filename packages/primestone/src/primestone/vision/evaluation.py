"""Métriques du banc d'essai vision : cases (précision, rappel, F1, ordre) et texte (CER)."""

from __future__ import annotations

from dataclasses import dataclass

from primestone.provenance import BoundingBox
from primestone.vision.assign import iou


@dataclass(frozen=True)
class PanelScore:
    true_positives: int
    false_positives: int
    false_negatives: int
    order_accuracy: float  # part des paires appariées lues dans le bon ordre relatif

    @property
    def precision(self) -> float:
        found = self.true_positives + self.false_positives
        return self.true_positives / found if found else 1.0

    @property
    def recall(self) -> float:
        expected = self.true_positives + self.false_negatives
        return self.true_positives / expected if expected else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def match_boxes(
    predicted: list[BoundingBox], truth: list[BoundingBox], threshold: float = 0.5
) -> list[tuple[int, int]]:
    """Appariement glouton par IoU décroissant (indices prédits, vérité)."""
    pairs = sorted(
        (
            (iou(p, t), i, j)
            for i, p in enumerate(predicted)
            for j, t in enumerate(truth)
            if iou(p, t) >= threshold
        ),
        reverse=True,
    )
    used_p: set[int] = set()
    used_t: set[int] = set()
    matches: list[tuple[int, int]] = []
    for _, i, j in pairs:
        if i not in used_p and j not in used_t:
            used_p.add(i)
            used_t.add(j)
            matches.append((i, j))
    return matches


def score_panels(
    predicted: list[BoundingBox], truth: list[BoundingBox], threshold: float = 0.5
) -> PanelScore:
    """`predicted` et `truth` sont dans l'ordre de lecture."""
    matches = sorted(match_boxes(predicted, truth, threshold))
    truth_order = [j for _, j in matches]
    pairs = [(a, b) for k, a in enumerate(truth_order) for b in truth_order[k + 1 :]]
    ordered = sum(1 for a, b in pairs if a < b)
    return PanelScore(
        true_positives=len(matches),
        false_positives=len(predicted) - len(matches),
        false_negatives=len(truth) - len(matches),
        order_accuracy=ordered / len(pairs) if pairs else 1.0,
    )


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def normalize_text(text: str) -> str:
    return " ".join(text.split()).upper()  # le lettrage de comics est généralement en capitales


def character_error_rate(predicted: str, truth: str) -> float:
    """CER = distance d'édition / longueur de la vérité (0 = parfait)."""
    p, t = normalize_text(predicted), normalize_text(truth)
    if not t:
        return 0.0 if not p else 1.0
    return levenshtein(p, t) / len(t)
