"""Ligne de commande Identité indépendante (gratuite, voix locale facultative).

primestone-identity voices [--language fr|en]
primestone-identity voice-propose voix.json        (nom, langue, ton, nature, fournisseur,
                                                    voix, licence, usage autorisé…)
primestone-identity visuals
primestone-identity visual-add regles.json [--series-id ID] [--platform P] [--language fr|en]
primestone-identity visual-resolve --language fr|en [--series-id ID] [--platform P]
primestone-identity narrate SCRIPT_ID [--synthesize]   (plan ; WAV par la voix approuvée)

Une voix proposée s'approuve avec primestone-brand approve DECISION_ID.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from primestone.config import get_settings
from primestone.db import create_db_engine
from primestone.identity import IdentityService
from primestone.storage import create_object_store
from primestone.voice.providers import FakeTTS, PiperTTS, TTSProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="primestone-identity")
    parser.add_argument("--author", default="propriétaire")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("voices").add_argument("--language", choices=["fr", "en"])
    sub.add_parser("voice-propose").add_argument("file", type=Path)
    sub.add_parser("visuals")
    for name in ("visual-add", "visual-resolve"):
        p = sub.add_parser(name)
        if name == "visual-add":
            p.add_argument("file", type=Path)
        p.add_argument("--series-id", type=UUID)
        p.add_argument("--platform")
        p.add_argument("--language", choices=["fr", "en"], required=name == "visual-resolve")
    narrate = sub.add_parser("narrate")
    narrate.add_argument("script_id", type=UUID)
    narrate.add_argument("--synthesize", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    svc = IdentityService(create_db_engine(settings.database_url))
    out: object
    try:
        if args.command == "voices":
            out = svc.voices(args.language)
        elif args.command == "voice-propose":
            fields = json.loads(args.file.read_text(encoding="utf-8"))
            out = svc.propose_voice(proposed_by=args.author, **fields)
        elif args.command == "visuals":
            out = svc.visuals()
        elif args.command == "visual-add":
            rules = json.loads(args.file.read_text(encoding="utf-8"))
            out = svc.add_visual(
                rules,
                created_by=args.author,
                series_id=args.series_id,
                platform=args.platform,
                language=args.language,
            )
        elif args.command == "visual-resolve":
            out = svc.visual_for(
                language=args.language, series_id=args.series_id, platform=args.platform
            )
        else:
            tts: TTSProvider | None = None
            if args.synthesize:
                # Voix locale gratuite (Piper) ; « fake » en développement. Aucun service payant.
                tts = PiperTTS(settings.piper_url) if settings.voice_tts == "piper" else FakeTTS()
            out = svc.narrate(
                args.script_id,
                tts=tts,
                store=create_object_store(
                    settings.storage_backend,
                    settings.storage_local_root,
                    gcs_bucket=settings.gcs_bucket,
                )
                if tts
                else None,
            )
    except (LookupError, ValueError) as exc:
        parser.exit(2, f"refusé : {exc}\n")
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
