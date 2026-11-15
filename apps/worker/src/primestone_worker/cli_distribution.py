"""Ligne de commande Distribution et portefeuille (gratuite, aucune publication).

primestone-distribution channels | channel-add PLATEFORME LANGUE HANDLE NOM [--stats …]
primestone-distribution channel-status CHANNEL_ID ACTIVE|PAUSED|RETIRED
primestone-distribution plan [--start AAAA-MM-JJ] [--end AAAA-MM-JJ]
primestone-distribution propose CHANNEL_ID "titre" [--script-id ID] [--at ISO8601] [--format F]
primestone-distribution declare ITEM_ID URL ID_PUBLIC   (après publication par toi)
primestone-distribution portfolio-create objectifs.json  (nom, période, parts visées)
primestone-distribution portfolio PORTFOLIO_ID | portfolios | performance

Les éléments proposés s'approuvent avec primestone-brand approve DECISION_ID.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.distribution import DistributionService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-distribution")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("channels", "portfolios", "performance"):
        sub.add_parser(name)
    add = sub.add_parser("channel-add")
    for arg in ("platform", "language", "handle", "name"):
        add.add_argument(arg)
    add.add_argument("--stats", default="NONE", choices=["NONE", "CSV_EXPORT", "OAUTH_READONLY"])
    st = sub.add_parser("channel-status")
    st.add_argument("channel_id", type=UUID)
    st.add_argument("status", choices=["ACTIVE", "PAUSED", "RETIRED"])
    plan = sub.add_parser("plan")
    plan.add_argument("--start", type=date.fromisoformat)
    plan.add_argument("--end", type=date.fromisoformat)
    prop = sub.add_parser("propose")
    prop.add_argument("channel_id", type=UUID)
    prop.add_argument("title")
    prop.add_argument("--script-id", type=UUID)
    prop.add_argument("--series-id", type=UUID)
    prop.add_argument("--at", type=datetime.fromisoformat)
    prop.add_argument("--format")
    dec = sub.add_parser("declare")
    dec.add_argument("item_id", type=UUID)
    dec.add_argument("url")
    dec.add_argument("external_id")
    sub.add_parser("portfolio-create").add_argument("file", type=Path)
    sub.add_parser("portfolio").add_argument("portfolio_id", type=UUID)
    args = parser.parse_args(argv)

    svc = DistributionService(create_db_engine(get_settings().database_url))
    out: object
    try:
        if args.command == "channels":
            out = svc.channels()
        elif args.command == "portfolios":
            out = svc.portfolios()
        elif args.command == "performance":
            out = svc.channel_performance()
        elif args.command == "channel-add":
            out = {
                "channel_id": str(
                    svc.add_channel(
                        platform=args.platform,
                        language=args.language,
                        handle=args.handle,
                        name=args.name,
                        stats_authorization=args.stats,
                    )
                )
            }
        elif args.command == "channel-status":
            svc.set_channel_status(args.channel_id, args.status)
            out = {"status": args.status}
        elif args.command == "plan":
            out = svc.plan(start=args.start, end=args.end)
        elif args.command == "propose":
            out = svc.propose(
                channel_id=args.channel_id,
                title=args.title,
                proposed_by=args.author,
                script_id=args.script_id,
                series_id=args.series_id,
                format=args.format,
                scheduled_for=args.at,
            )
        elif args.command == "declare":
            out = {
                "content_id": str(
                    svc.declare_published(
                        args.item_id,
                        url=args.url,
                        external_id=args.external_id,
                        declared_by=args.author,
                    )
                )
            }
        elif args.command == "portfolio-create":
            spec = json.loads(args.file.read_text(encoding="utf-8"))
            out = {
                "portfolio_id": str(
                    svc.create_portfolio(
                        spec["name"],
                        period_start=date.fromisoformat(spec["period_start"]),
                        period_end=date.fromisoformat(spec["period_end"]),
                        targets=spec["targets"],
                        created_by=args.author,
                    )
                )
            }
        else:
            out = svc.portfolio(args.portfolio_id)
    except (LookupError, ValueError) as exc:
        parser.exit(2, f"refusé : {exc}\n")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
