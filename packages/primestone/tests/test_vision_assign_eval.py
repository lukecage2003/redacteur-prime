import pytest

from primestone.provenance import BoundingBox
from primestone.vision import Panel, ReadingDirection, TextKind, TextRegion, assign_texts, iou
from primestone.vision.evaluation import character_error_rate, levenshtein, score_panels


def box(x: float, y: float, w: float, h: float) -> BoundingBox:
    return BoundingBox(x=x, y=y, width=w, height=h)


def text(t: str, b: BoundingBox) -> TextRegion:
    return TextRegion(text=t, kind=TextKind.DIALOGUE, bbox=b)


PANELS = [
    Panel(index=1, bbox=box(0.0, 0.0, 0.5, 0.5)),
    Panel(index=2, bbox=box(0.5, 0.0, 0.5, 0.5)),
    Panel(index=3, bbox=box(0.0, 0.5, 1.0, 0.5)),
]


def test_texts_assigned_and_ordered() -> None:
    texts = [
        text("C", box(0.1, 0.6, 0.2, 0.1)),
        text("B", box(0.6, 0.1, 0.2, 0.1)),
        text("A2", box(0.1, 0.3, 0.2, 0.1)),
        text("A1", box(0.1, 0.05, 0.2, 0.1)),
    ]
    result = assign_texts(PANELS, texts)
    assert [(t.text, t.panel_index, t.order) for t in result] == [
        ("A1", 1, 1),
        ("A2", 1, 2),
        ("B", 2, 3),
        ("C", 3, 4),
    ]


def test_text_outside_panels() -> None:
    panels = [
        Panel(index=1, bbox=box(0.05, 0.05, 0.9, 0.4)),
        Panel(index=2, bbox=box(0.05, 0.55, 0.9, 0.4)),
    ]
    caption = text("hors case", box(0.2, 0.46, 0.6, 0.08))  # dans la gouttière
    inside = text("dedans", box(0.2, 0.6, 0.2, 0.1))
    result = assign_texts(panels, [inside, caption])
    assert [(t.text, t.panel_index, t.order) for t in result] == [
        ("hors case", None, 1),  # rangé après la case 1, avant la case 2
        ("dedans", 2, 2),
    ]


def test_rtl_order_inside_panel() -> None:
    texts = [text("gauche", box(0.6, 0.6, 0.1, 0.1)), text("droite", box(0.85, 0.6, 0.1, 0.1))]
    result = assign_texts(PANELS, texts, ReadingDirection.RTL)
    assert [t.text for t in result] == ["droite", "gauche"]


def test_iou() -> None:
    assert iou(box(0, 0, 0.5, 0.5), box(0, 0, 0.5, 0.5)) == pytest.approx(1.0)
    assert iou(box(0, 0, 0.5, 0.5), box(0.5, 0.5, 0.5, 0.5)) == 0.0
    assert iou(box(0, 0, 0.5, 0.5), box(0.25, 0, 0.5, 0.5)) == pytest.approx(1 / 3)


def test_panel_scores() -> None:
    truth = [p.bbox for p in PANELS]
    perfect = score_panels(truth, truth)
    assert (perfect.precision, perfect.recall, perfect.f1, perfect.order_accuracy) == (1, 1, 1, 1)
    merged = score_panels([box(0, 0, 1, 0.5), truth[2]], truth)  # 2 cases fusionnées
    assert (merged.true_positives, merged.false_negatives) == (2, 1)  # IoU 0,5 : apparié
    missed = score_panels([box(0, 0, 1, 0.45), truth[2]], truth, threshold=0.5)
    assert (missed.true_positives, missed.false_negatives) == (1, 2)
    swapped = score_panels([truth[1], truth[0], truth[2]], truth)
    assert swapped.f1 == 1.0
    assert swapped.order_accuracy == pytest.approx(2 / 3)
    assert score_panels([], []).f1 == 1.0  # page blanche correctement vide


def test_cer() -> None:
    assert levenshtein("kitten", "sitting") == 3
    assert character_error_rate("Je suis  BATMAN", "JE SUIS BATMAN") == 0.0
    assert character_error_rate("JE SUIS BATMEN", "JE SUIS BATMAN") == pytest.approx(1 / 14)
    assert character_error_rate("", "") == 0.0
    assert character_error_rate("X", "") == 1.0
