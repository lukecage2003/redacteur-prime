"""Ligne de commande Audience Intelligence (gratuite, sans données personnelles).

primestone-audience segments
primestone-audience segment --name … --description … --motivation … [--motivation …]
                    [--level NOVICE|INTERMEDIATE|EXPERT]
primestone-audience evidence SEGMENT_ID --kind METRIC|COMMENT_CLUSTER|MARKET|DECLARED
                    --statement … [--data '{"videos": 6}'] [--class PRIVATE_AUTHORIZED]
primestone-audience link SEGMENT_ID --target-kind TOPIC --target ID --relation ASKS_ABOUT
                    --evidence EVIDENCE_ID
primestone-audience collect [--videos 20]   (commentaires publics de TA chaîne, clé gratuite)
primestone-audience community
primestone-audience brief [--process]       (mission AUDIENCE_BRIEF)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from uuid import UUID

from primestone.audience import AudienceService, YouTubeComments
from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.editorial import editorial_service_from_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-audience")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("segments")
    sub.add_parser("community")
    seg = sub.add_parser("segment")
    seg.add_argument("--name", required=True)
    seg.add_argument("--description", required=True)
    seg.add_argument("--motivation", action="append", required=True)
    seg.add_argument("--level", choices=("NOVICE", "INTERMEDIATE", "EXPERT"))
    ev = sub.add_parser("evidence")
    ev.add_argument("segment_id", type=UUID)
    ev.add_argument(
        "--kind", choices=("METRIC", "COMMENT_CLUSTER", "MARKET", "DECLARED"), required=True
    )
    ev.add_argument("--statement", required=True)
    ev.add_argument("--data", default="{}")
    ev.add_argument("--class", dest="data_class", default="PUBLIC")
    link = sub.add_parser("link")
    link.add_argument("segment_id", type=UUID)
    link.add_argument(
        "--target-kind", choices=("ENTITY", "TOPIC", "FORMAT", "PLATFORM"), required=True
    )
    link.add_argument("--target", required=True)
    link.add_argument("--relation", required=True)
    link.add_argument("--evidence", type=UUID, required=True)
    sub.add_parser("collect").add_argument("--videos", type=int, default=20)
    sub.add_parser("brief").add_argument("--process", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    svc = AudienceService(engine)
    out: object
    if args.command == "segments":
        out = svc.segments()
    elif args.command == "community":
        out = svc.community()
    elif args.command == "segment":
        out = {
            "segment_id": str(
                svc.create_segment(
                    name=args.name,
                    description=args.description,
                    motivations=args.motivation,
                    knowledge_level=args.level,
                    author=args.author,
                )
            )
        }
    elif args.command == "evidence":
        out = svc.add_evidence(
            args.segment_id,
            kind=args.kind,
            statement=args.statement,
            data=json.loads(args.data),
            data_class=args.data_class,
            author=args.author,
        )
    elif args.command == "link":
        svc.link(
            args.segment_id,
            target_kind=args.target_kind,
            target=args.target,
            relation=args.relation,
            evidence_id=args.evidence,
        )
        out = {"linked": True}
    elif args.command == "collect":
        if not settings.youtube_api_key:
            raise SystemExit(
                "PRIMESTONE_YOUTUBE_API_KEY requis (clé gratuite, voir docs/modules/market.md)"
            )
        out = svc.collect_youtube(
            YouTubeComments(settings.youtube_api_key.get_secret_value()), max_videos=args.videos
        )
    else:
        editorial = editorial_service_from_settings(settings, engine)
        mission_id = editorial.create_mission("AUDIENCE_BRIEF", [], {})
        if args.process:
            asyncio.run(editorial.run_mission({"mission_id": str(mission_id)}))
        out = editorial.mission(mission_id)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
