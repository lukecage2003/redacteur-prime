"""Ligne de commande Creative Intelligence (gratuite).

primestone-creative charter                        (charte en vigueur)
primestone-creative charter-publish charte.json --name "Primestone v1" [--note …]
primestone-creative series
primestone-creative series-create serie.json      (promesse, identité, ton, structure…)
primestone-creative episode SERIES_ID SCRIPT_ID
primestone-creative package SCRIPT_ID             (10 titres, 5 miniatures, promesses, accroches)
primestone-creative review SCRIPT_ID [--process]  (mission PACKAGING_REVIEW)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from primestone.config import get_settings
from primestone.creative import creative_service_from_settings
from primestone.db import create_db_engine
from primestone.editorial import editorial_service_from_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-creative")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("charter")
    pub = sub.add_parser("charter-publish")
    pub.add_argument("file", type=Path)
    pub.add_argument("--name", required=True)
    pub.add_argument("--note")
    sub.add_parser("series")
    sub.add_parser("series-create").add_argument("file", type=Path)
    ep = sub.add_parser("episode")
    ep.add_argument("series_id", type=UUID)
    ep.add_argument("script_id", type=UUID)
    sub.add_parser("package").add_argument("script_id", type=UUID)
    review = sub.add_parser("review")
    review.add_argument("script_id", type=UUID)
    review.add_argument("--process", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    svc = creative_service_from_settings(settings, engine)
    out: object
    if args.command == "charter":
        out = svc.charter()
    elif args.command == "charter-publish":
        rules = json.loads(args.file.read_text(encoding="utf-8"))
        out = {
            "version": svc.publish_charter(
                rules, name=args.name, author=args.author, note=args.note
            )
        }
    elif args.command == "series":
        out = svc.series()
    elif args.command == "series-create":
        fields = json.loads(args.file.read_text(encoding="utf-8"))
        out = {"series_id": str(svc.create_series(author=args.author, **fields))}
    elif args.command == "episode":
        out = {"episode": svc.add_episode(args.series_id, args.script_id)}
    elif args.command == "package":
        out = asyncio.run(svc.package(args.script_id))
    else:
        editorial = editorial_service_from_settings(settings, engine)
        mission_id = editorial.create_mission(
            "PACKAGING_REVIEW", [], {"script_id": str(args.script_id)}
        )
        if args.process:
            asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
        out = editorial.mission(mission_id)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
