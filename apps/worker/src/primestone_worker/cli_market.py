"""Ligne de commande Market Intelligence (gratuite).

    primestone-market sources
    primestone-market add-source KEY --name … --kind MANUAL|RSS|YOUTUBE_API --access … \\
                      --quota … --terms-url … [--language fr|en] [--url https://…]
    primestone-market verify KEY                 (validation humaine de la fiche)
    primestone-market import KEY fichier.csv     (colonnes : platform, external_id, title,
                      language, observed_at, [published_at, url, channel, views, likes, comments])
    primestone-market collect KEY [--query "…" --language fr|en]   (RSS ou YouTube)
    primestone-market snapshot                   (toutes les sources validées ; 1 fois par jour)
    primestone-market topic NOM [--fr mot]… [--en word]…
    primestone-market topics | collections
    primestone-market analysis [--window-days 90] [--min-items 5]
    primestone-market brief [--process]          (mission MARKET_BRIEF du Chief Editor)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.editorial import editorial_service_from_settings
from primestone.market import market_service_from_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-market")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sources", "topics", "collections", "snapshot"):
        sub.add_parser(name)
    add = sub.add_parser("add-source")
    add.add_argument("key")
    add.add_argument("--name", required=True)
    add.add_argument("--kind", choices=("MANUAL", "RSS", "YOUTUBE_API"), required=True)
    add.add_argument("--access", required=True)
    add.add_argument("--quota", required=True)
    add.add_argument("--terms-url", required=True)
    add.add_argument("--language", choices=("fr", "en"))
    add.add_argument("--url")
    sub.add_parser("verify").add_argument("key")
    imp = sub.add_parser("import")
    imp.add_argument("key")
    imp.add_argument("file", type=Path)
    collect = sub.add_parser("collect")
    collect.add_argument("key")
    collect.add_argument("--query")
    collect.add_argument("--language", choices=("fr", "en"), default="en")
    collect.add_argument("--max-results", type=int, default=25)
    topic = sub.add_parser("topic")
    topic.add_argument("name")
    topic.add_argument("--fr", action="append", default=[])
    topic.add_argument("--en", action="append", default=[])
    analysis = sub.add_parser("analysis")
    analysis.add_argument("--window-days", type=int, default=90)
    analysis.add_argument("--min-items", type=int, default=5)
    sub.add_parser("brief").add_argument("--process", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    market = market_service_from_settings(settings, engine)
    out: object
    if args.command == "sources":
        out = market.sources()
    elif args.command == "topics":
        out = market.topics()
    elif args.command == "collections":
        out = market.collections()
    elif args.command == "snapshot":
        out = market.snapshot(author=args.author)
    elif args.command == "add-source":
        out = {
            "id": str(
                market.register_source(
                    key=args.key,
                    name=args.name,
                    kind=args.kind,
                    access=args.access,
                    quota=args.quota,
                    terms_url=args.terms_url,
                    language=args.language,
                    config={"url": args.url} if args.url else {},
                )
            )
        }
    elif args.command == "verify":
        market.verify_source(args.key, author=args.author)
        out = {"verified": args.key}
    elif args.command == "import":
        with args.file.open(encoding="utf-8", newline="") as handle:
            records = list(csv.DictReader(handle))
        out = market.import_records(args.key, records, author=args.author)
    elif args.command == "collect":
        kind = next((s["kind"] for s in market.sources() if s["key"] == args.key), None)
        if kind == "YOUTUBE_API":
            out = market.collect_youtube(
                args.key,
                args.query or "",
                language=args.language,
                max_results=args.max_results,
                author=args.author,
            )
        else:
            out = market.collect_rss(args.key, author=args.author)
    elif args.command == "topic":
        out = {
            "id": str(
                market.add_topic(
                    args.name, keywords_fr=args.fr, keywords_en=args.en, author=args.author
                )
            )
        }
    elif args.command == "analysis":
        out = market.analysis(window_days=args.window_days, min_items=args.min_items)
    else:
        editorial = editorial_service_from_settings(settings, engine)
        mission_id = editorial.create_mission("MARKET_BRIEF", [], {})
        if args.process:
            asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
        out = editorial.mission(mission_id)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
