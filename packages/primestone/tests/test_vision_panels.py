import random

from PIL import Image, ImageDraw

from primestone.provenance import BoundingBox
from primestone.vision import ReadingDirection, detect_panels
from primestone.vision.evaluation import score_panels
from primestone.vision.synthetic import generate_page


def f1_over(pages: range, **kw: object) -> float:
    tp = fp = fn = 0
    for seed in pages:
        page = generate_page(seed, **kw)  # type: ignore[arg-type]
        predicted = [p.bbox for p in detect_panels(page.image, direction=page.direction)]
        score = score_panels(predicted, page.panels)
        tp, fp, fn = (
            tp + score.true_positives,
            fp + score.false_positives,
            fn + score.false_negatives,
        )
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    return 2 * precision * recall / (precision + recall)


def test_synthetic_benchmark_ltr() -> None:
    assert f1_over(range(40)) >= 0.99


def test_synthetic_benchmark_rtl_reading_order() -> None:
    for seed in range(10):
        page = generate_page(seed, direction=ReadingDirection.RTL)
        predicted = [p.bbox for p in detect_panels(page.image, direction=ReadingDirection.RTL)]
        assert score_panels(predicted, page.panels).order_accuracy == 1.0


def test_tilted_scans_are_straightened() -> None:
    tp = fp = fn = 0
    for seed in range(20):
        page = generate_page(seed)
        angle = random.Random(seed).choice([-1, 1]) * 0.8  # noqa: S311
        tilted = page.image.rotate(
            angle, fillcolor=page.image.getpixel((2, 2)), resample=Image.Resampling.BILINEAR
        )
        score = score_panels([p.bbox for p in detect_panels(tilted)], page.panels)
        tp, fp, fn = (
            tp + score.true_positives,
            fp + score.false_positives,
            fn + score.false_negatives,
        )
    assert 2 * tp / (2 * tp + fp + fn) >= 0.98


def test_splash_page_is_one_panel() -> None:
    image = Image.new("RGB", (600, 900), "white")
    ImageDraw.Draw(image).rectangle((30, 30, 570, 870), outline="black", width=4)
    panels = detect_panels(image)
    assert len(panels) == 1
    assert panels[0].index == 1
    assert panels[0].bbox.width > 0.85


def test_blank_page_has_no_panel() -> None:
    assert detect_panels(Image.new("RGB", (600, 900), "white")) == []


def test_reading_order_two_rows_two_columns() -> None:
    image = Image.new("RGB", (600, 900), "white")
    draw = ImageDraw.Draw(image)
    for box in ((20, 20, 290, 440), (310, 20, 580, 440), (20, 460, 290, 880), (310, 460, 580, 880)):
        draw.rectangle(box, outline="black", width=3)
    ltr = [(round(p.bbox.x, 1), round(p.bbox.y, 1)) for p in detect_panels(image)]
    rtl = [
        (round(p.bbox.x, 1), round(p.bbox.y, 1))
        for p in detect_panels(image, direction=ReadingDirection.RTL)
    ]
    assert ltr == [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5)]
    assert rtl == [(0.5, 0.0), (0.0, 0.0), (0.5, 0.5), (0.0, 0.5)]


def test_boxes_are_normalized() -> None:
    page = generate_page(3)
    for panel in detect_panels(page.image):
        assert isinstance(panel.bbox, BoundingBox)
        assert panel.bbox.x + panel.bbox.width <= 1.0 + 1e-9


def test_gutter_crossing_is_a_known_limit_not_a_crash() -> None:
    # Une bulle à cheval sur une gouttière fusionne des cases : limite documentée (ROADMAP).
    assert 0.4 <= f1_over(range(20), gutter_crossing=True) < 0.99
