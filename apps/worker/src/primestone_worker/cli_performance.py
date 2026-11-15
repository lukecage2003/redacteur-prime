"""Ligne de commande Performance Intelligence (chaîne Primestone, gratuite).

primestone-performance import export.csv [--from 2026-10-01 --to 2026-10-31]
primestone-performance contents
primestone-performance link CONTENT_ID SCRIPT_ID [--language fr|en]
primestone-performance report [--min-items 5]
primestone-performance review [--process]     (mission PERFORMANCE_REVIEW)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.editorial import editorial_service_from_settings
from primestone.performance import PerformanceService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-performance")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("file", type=Path)
    imp.add_argument("--from", dest="start", type=date.fromisoformat)
    imp.add_argument("--to", dest="end", type=date.fromisoformat)
    sub.add_parser("contents")
    link = sub.add_parser("link")
    link.add_argument("content_id", type=UUID)
    link.add_argument("script_id", type=UUID)
    link.add_argument("--language", choices=("fr", "en"))
    report = sub.add_parser("report")
    report.add_argument("--min-items", type=int, default=5)
    sub.add_parser("review").add_argument("--process", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    svc = PerformanceService(engine)
    out: object
    if args.command == "import":
        out = svc.import_studio_csv(
            args.file.read_text(encoding="utf-8"), author=args.author, period=(args.start, args.end)
        )
    elif args.command == "contents":
        out = svc.contents()
    elif args.command == "link":
        svc.link_script(args.content_id, args.script_id, language=args.language)
        out = {"linked": str(args.content_id)}
    elif args.command == "report":
        out = svc.report(min_items=args.min_items)
    else:
        editorial = editorial_service_from_settings(settings, engine)
        mission_id = editorial.create_mission("PERFORMANCE_REVIEW", [], {})
        if args.process:
            asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
        out = editorial.mission(mission_id)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
