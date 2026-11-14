"""Ligne de commande Comic Vision.

    primestone-vision estimate  --documents ID… [--provider claude] [--direction LTR|RTL]
    primestone-vision analyze   --documents ID… --budget USD [--provider …] [--process]
    primestone-vision show      DOCUMENT_ID PAGE
    primestone-vision report    RUN_ID
    primestone-vision benchmark-panels [--pages 200] [--gutter-crossing]

Toute analyse payante exige un budget explicite ; l'estimation est affichée avant le lancement.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.jobs import PostgresJobQueue
from primestone.vision import ReadingDirection, detect_panels, vision_service_from_settings
from primestone.vision.evaluation import score_panels
from primestone.vision.service import VisionBudgetError
from primestone.vision.synthetic import generate_page
from primestone_worker.cli import drain


def benchmark_panels(pages: int, gutter_crossing: bool) -> dict[str, object]:
    tp = fp = fn = 0
    orders: list[float] = []
    for seed in range(pages):
        direction = ReadingDirection.RTL if seed % 5 == 0 else ReadingDirection.LTR
        page = generate_page(seed, direction=direction, gutter_crossing=gutter_crossing)
        predicted = [p.bbox for p in detect_panels(page.image, direction=direction)]
        score = score_panels(predicted, page.panels)
        tp, fp, fn = (
            tp + score.true_positives,
            fp + score.false_positives,
            fn + score.false_negatives,
        )
        orders.append(score.order_accuracy)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {
        "pages": pages,
        "gutter_crossing": gutter_crossing,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4) if tp else 0.0,
        "reading_order_accuracy": round(sum(orders) / len(orders), 4),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-vision")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("estimate", "analyze"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--documents", nargs="+", type=UUID, required=True)
        cmd.add_argument("--provider", default=None)
        cmd.add_argument("--direction", choices=["LTR", "RTL"], default="LTR")
        cmd.add_argument("--budget", type=Decimal, default=None)
        cmd.add_argument("--language")
        if name == "analyze":
            cmd.add_argument("--process", action="store_true")
            cmd.add_argument("--workers", type=int, default=2)
    show = sub.add_parser("show")
    show.add_argument("document_id", type=UUID)
    show.add_argument("page", type=int)
    report = sub.add_parser("report")
    report.add_argument("run_id", type=UUID)
    bench = sub.add_parser("benchmark-panels")
    bench.add_argument("--pages", type=int, default=200)
    bench.add_argument("--gutter-crossing", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "benchmark-panels":
        print(json.dumps(benchmark_panels(args.pages, args.gutter_crossing), indent=2))
        return 0

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    service = vision_service_from_settings(settings, engine)
    out: object

    if args.command in ("estimate", "analyze"):
        provider = args.provider or settings.vision_provider
        budget = args.budget if args.budget is not None else settings.ai_budget_per_mission_usd
        direction = ReadingDirection(args.direction)
        if args.command == "estimate":
            estimate, _ = service.estimate(args.documents, provider, budget, direction)
            out = estimate.as_dict()
        else:
            try:
                run_id, estimate = service.start(
                    args.documents,
                    provider,
                    budget,
                    direction=direction,
                    language_hint=args.language,
                )
            except VisionBudgetError as exc:
                print(f"refusé : {exc}", file=sys.stderr)
                print(json.dumps(exc.estimate.as_dict(), indent=2))
                return 2
            print(f"lot {run_id} lancé ({estimate.to_analyze} page(s))", file=sys.stderr)
            if args.process:
                asyncio.run(drain(PostgresJobQueue(engine), args.workers, run_id))
            out = service.run_report(run_id)
    elif args.command == "show":
        out = service.latest_analysis(args.document_id, args.page)
    else:
        out = service.run_report(args.run_id)

    if out is None:
        print("introuvable", file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
