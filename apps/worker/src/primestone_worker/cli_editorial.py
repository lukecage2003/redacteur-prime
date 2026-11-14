"""Ligne de commande Editorial Director (gratuite).

    primestone-editorial agents
    primestone-editorial dossier  --documents ID… --character "Selina" [--process]
    primestone-editorial audit    --documents ID… [--process]
    primestone-editorial check    --documents ID… --draft fichier.md [--process]
    primestone-editorial social   MISSION_ID [--process]   (déclinaisons d'un livrable approuvé)
    primestone-editorial show     MISSION_ID
    primestone-editorial approve  APPROVAL_ID [--comment "…"]
    primestone-editorial reject   APPROVAL_ID [--comment "…"]

Les documents se donnent dans l'ordre de lecture. Sans --process, la mission est exécutée
par le worker (primestone-worker).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.editorial import editorial_service_from_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-editorial")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("agents")
    for name in ("dossier", "audit", "check"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--documents", nargs="+", type=UUID, required=True)
        cmd.add_argument("--process", action="store_true", help="exécuter ici, sans worker")
        cmd.add_argument("--character-hint", action="append", default=[], dest="known")
        if name == "dossier":
            cmd.add_argument("--character", required=True)
        if name == "check":
            cmd.add_argument("--draft", type=Path, required=True)
    sub.add_parser("show").add_argument("mission_id", type=UUID)
    social = sub.add_parser("social")
    social.add_argument("mission_id", type=UUID)
    social.add_argument("--process", action="store_true", help="exécuter ici, sans worker")
    for name in ("approve", "reject"):
        cmd = sub.add_parser(name)
        cmd.add_argument("approval_id", type=UUID)
        cmd.add_argument("--comment")
        cmd.add_argument("--author", default="propriétaire")
    args = parser.parse_args(argv)

    settings = get_settings()
    service = editorial_service_from_settings(settings, create_db_engine(settings.database_url))
    out: object
    if args.command == "agents":
        out = service.agents()
    elif args.command in ("dossier", "audit", "check"):
        mission_type = {
            "dossier": "CHARACTER_DOSSIER",
            "audit": "CONTINUITY_AUDIT",
            "check": "FACT_CHECK",
        }[args.command]
        params: dict[str, object] = {"known_characters": args.known}
        if args.command == "dossier":
            params["character"] = args.character
        if args.command == "check":
            params["draft"] = args.draft.read_text(encoding="utf-8")
        mission_id = service.create_mission(mission_type, args.documents, params)
        if args.process:
            asyncio.run(service.run_mission({"mission_id": str(mission_id)}))
        out = service.mission(mission_id)
    elif args.command == "social":
        mission_id = service.create_mission(
            "SOCIAL_PACKAGE", [], {"source_mission_id": str(args.mission_id)}
        )
        if args.process:
            asyncio.run(service.run_mission({"mission_id": str(mission_id)}))
        out = service.mission(mission_id)
    elif args.command == "show":
        out = service.mission(args.mission_id)
    else:
        service.decide(
            args.approval_id,
            approve=args.command == "approve",
            author=args.author,
            comment=args.comment,
        )
        out = {"decision": args.command, "approval_id": str(args.approval_id)}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
