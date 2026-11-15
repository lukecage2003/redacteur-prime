"""Ligne de commande Droits, mémoire éditoriale et coûts (gratuite).

primestone-memory rights [--script-id ID] | rights-add droit.json | rights-withdraw ID
primestone-memory rights-check SCRIPT_ID          (citations de cases sans droit)
primestone-memory lessons [--series-id ID]
primestone-memory lesson "leçon" content_item|experiment SOURCE_ID [--series-id ID]
primestone-memory lesson-retract LESSON_ID --reason "…"
primestone-memory journal | costs
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.memory import MemoryService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-memory")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("rights").add_argument("--script-id", type=UUID)
    sub.add_parser("rights-add").add_argument("file", type=Path)
    sub.add_parser("rights-withdraw").add_argument("record_id", type=UUID)
    sub.add_parser("rights-check").add_argument("script_id", type=UUID)
    sub.add_parser("lessons").add_argument("--series-id", type=UUID)
    lesson = sub.add_parser("lesson")
    lesson.add_argument("lesson")
    lesson.add_argument("source_type", choices=["content_item", "experiment"])
    lesson.add_argument("source_id", type=UUID)
    lesson.add_argument("--series-id", type=UUID)
    retract = sub.add_parser("lesson-retract")
    retract.add_argument("lesson_id", type=UUID)
    retract.add_argument("--reason", required=True)
    sub.add_parser("journal")
    sub.add_parser("costs")
    args = parser.parse_args(argv)

    settings = get_settings()
    svc = MemoryService(create_db_engine(settings.database_url), zero_cost=settings.zero_cost)
    out: object
    try:
        if args.command == "rights":
            out = svc.rights(args.script_id)
        elif args.command == "rights-add":
            fields = json.loads(args.file.read_text(encoding="utf-8"))
            if fields.get("expires_on"):
                fields["expires_on"] = date.fromisoformat(fields["expires_on"])
            out = {"record_id": str(svc.record_rights(recorded_by=args.author, **fields))}
        elif args.command == "rights-withdraw":
            svc.withdraw_rights(args.record_id)
            out = {"status": "WITHDRAWN"}
        elif args.command == "rights-check":
            out = svc.rights_check(args.script_id)
        elif args.command == "lessons":
            out = svc.lessons(args.series_id)
        elif args.command == "lesson":
            out = svc.record_lesson(
                args.lesson,
                source_type=args.source_type,
                source_id=args.source_id,
                recorded_by=args.author,
                series_id=args.series_id,
            )
        elif args.command == "lesson-retract":
            svc.retract_lesson(args.lesson_id, reason=args.reason)
            out = {"status": "RETRACTED"}
        elif args.command == "journal":
            out = svc.journal()
        else:
            out = svc.costs()
    except (LookupError, ValueError) as exc:
        parser.exit(2, f"refusé : {exc}\n")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
