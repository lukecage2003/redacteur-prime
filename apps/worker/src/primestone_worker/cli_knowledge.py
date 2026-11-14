"""Ligne de commande Knowledge (gratuite).

primestone-knowledge build    --documents ID…
primestone-knowledge entities [--type CHARACTER] [--query nom]
primestone-knowledge entity   ENTITY_ID
primestone-knowledge graph    ENTITY_ID [--depth 2]
primestone-knowledge path     FROM_ID TO_ID
primestone-knowledge search   "texte" [--documents ID…]
primestone-knowledge merge    KEEP_ID ABSORB_ID --reason "…"
primestone-knowledge alias    ENTITY_ID "alias" [--language fr] --reason "…"
primestone-knowledge rename   ENTITY_ID "nom" --reason "…"
primestone-knowledge retract  RELATION_ID --reason "…"
"""

from __future__ import annotations

import argparse
import json
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.knowledge import hybrid_search, knowledge_service_from_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-knowledge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build").add_argument("--documents", nargs="+", type=UUID, required=True)
    ent = sub.add_parser("entities")
    ent.add_argument("--type")
    ent.add_argument("--query")
    sub.add_parser("entity").add_argument("entity_id", type=UUID)
    graph = sub.add_parser("graph")
    graph.add_argument("entity_id", type=UUID)
    graph.add_argument("--depth", type=int, default=1)
    path = sub.add_parser("path")
    path.add_argument("from_id", type=UUID)
    path.add_argument("to_id", type=UUID)
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--documents", nargs="+", type=UUID)
    for name, extra in (
        ("merge", ["keep", "absorb"]),
        ("alias", ["entity", "value"]),
        ("rename", ["entity", "value"]),
        ("retract", ["relation"]),
    ):
        cmd = sub.add_parser(name)
        for arg in extra:
            cmd.add_argument(arg)
        cmd.add_argument("--reason", required=True)
        cmd.add_argument("--author", default="propriétaire")
        if name == "alias":
            cmd.add_argument("--language")
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    kb = knowledge_service_from_settings(settings, engine)
    out: object
    if args.command == "build":
        out = kb.build(args.documents)
    elif args.command == "entities":
        out = kb.entities(type_=args.type, query=args.query)
    elif args.command == "entity":
        out = kb.entity(args.entity_id)
    elif args.command == "graph":
        out = kb.neighbors(args.entity_id, args.depth)
    elif args.command == "path":
        out = kb.path(args.from_id, args.to_id)
    elif args.command == "search":
        out = hybrid_search(engine, kb.embedder, args.query, document_ids=args.documents)
    elif args.command == "merge":
        kb.merge(UUID(args.keep), UUID(args.absorb), author=args.author, reason=args.reason)
        out = kb.entity(UUID(args.keep))
    elif args.command == "alias":
        kb.add_alias(
            UUID(args.entity),
            args.value,
            language=args.language,
            author=args.author,
            reason=args.reason,
        )
        out = kb.entity(UUID(args.entity))
    elif args.command == "rename":
        kb.rename(UUID(args.entity), args.value, author=args.author, reason=args.reason)
        out = kb.entity(UUID(args.entity))
    else:
        kb.retract_relation(UUID(args.relation), author=args.author, reason=args.reason)
        out = {"retracted": args.relation}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
