"""Voix et visuels institutionnels de PRIMESTONE, indépendants du fondateur.

- Un profil de voix exige une licence enregistrée et un usage autorisé ; une voix humaine
  exige en plus une référence d'autorisation écrite (contrainte en base). Aucun clonage de
  la voix du fondateur n'est requis ni proposé.
- Un profil de voix n'est utilisable qu'après approbation (décision VOICE_PROFILE).
- Les règles s'appliquent par langue : une règle FR ne s'applique jamais à un contenu EN ; une
  règle sans langue vaut pour toutes.
"""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from primestone.governance.service import (
    GovernanceService,
    register_handler,
    register_reject_hook,
)
from primestone.storage import ObjectStore
from primestone.storytelling.analysis import sections
from primestone.voice.providers import TTSProvider

METHOD = "narration@1"
WORDS_PER_MINUTE = 150
_REFERENCE = re.compile(r"\[[^\]]*\]|\([^)]*\b(p\.|page|#)\s*\d+[^)]*\)", re.IGNORECASE)


class IdentityError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def narration_text(section_text: str) -> str:
    """Texte à dire : références de pages et notes entre crochets retirées."""
    return " ".join(_REFERENCE.sub("", section_text).split())


def _voice(conn: Connection, decision: dict[str, Any], forward: bool) -> dict[str, Any] | None:
    conn.execute(
        text("UPDATE brand_voice_profile SET status = :s WHERE id = :id"),
        {"s": "APPROVED" if forward else "RETIRED", "id": decision["subject_id"]},
    )
    return {"status": "PROPOSED"} if forward else None


def _voice_rejected(conn: Connection, decision: dict[str, Any]) -> None:
    conn.execute(
        text("UPDATE brand_voice_profile SET status = 'RETIRED' WHERE id = :id"),
        {"id": decision["subject_id"]},
    )


register_handler("VOICE_PROFILE", _voice)
register_reject_hook("VOICE_PROFILE", _voice_rejected)


class IdentityService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._governance = GovernanceService(engine)

    # --- Voix -------------------------------------------------------------------------------

    def propose_voice(
        self,
        *,
        name: str,
        language: str,
        tone: str,
        kind: str,
        provider: str,
        voice: str,
        license: str,
        allowed_use: str,
        proposed_by: str,
        license_url: str | None = None,
        consent_reference: str | None = None,
    ) -> dict[str, Any]:
        if language not in ("fr", "en"):
            raise IdentityError("langues possibles : fr, en")
        if not license.strip() or not allowed_use.strip():
            raise IdentityError("profil refusé : licence et usage autorisé obligatoires")
        if kind not in ("SYNTHETIC", "HUMAN_LICENSED"):
            raise IdentityError("nature possible : SYNTHETIC ou HUMAN_LICENSED")
        if kind == "HUMAN_LICENSED" and not (consent_reference or "").strip():
            raise IdentityError("voix humaine refusée sans autorisation écrite référencée")
        with self._engine.begin() as conn:
            if conn.execute(
                text("SELECT 1 FROM brand_voice_profile WHERE name = :n"), {"n": name}
            ).first():
                raise IdentityError(f"profil déjà défini : {name}")
            profile_id = conn.execute(
                text(
                    "INSERT INTO brand_voice_profile (brand_id, name, language, tone, kind, "
                    "provider, voice, license, license_url, allowed_use, consent_reference, "
                    "created_by) VALUES ((SELECT id FROM media_brand WHERE slug = 'primestone'), "
                    ":name, :language, :tone, :kind, :provider, :voice, :license, :license_url, "
                    ":allowed_use, :consent, :by) RETURNING id"
                ),
                {
                    "name": name,
                    "language": language,
                    "tone": tone,
                    "kind": kind,
                    "provider": provider,
                    "voice": voice,
                    "license": license.strip(),
                    "license_url": license_url,
                    "allowed_use": allowed_use.strip(),
                    "consent": consent_reference,
                    "by": proposed_by,
                },
            ).scalar_one()
            decision = self._governance.propose_in(
                conn,
                "VOICE_PROFILE",
                subject_type="brand_voice_profile",
                subject_id=str(profile_id),
                proposal={"name": name, "language": language, "kind": kind, "voice": voice},
                proposed_by=proposed_by,
            )
        return decision | {"profile_id": profile_id}

    def voices(self, language: str | None = None) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT * FROM brand_voice_profile "
                        "WHERE (CAST(:l AS text) IS NULL OR language = :l) "
                        "ORDER BY language, status, name"
                    ),
                    {"l": language},
                ).mappings()
            ]

    def voice_for(self, language: str) -> dict[str, Any]:
        approved = [v for v in self.voices(language) if v["status"] == "APPROVED"]
        if not approved:
            raise IdentityError(
                f"aucune voix de marque approuvée en {language} : en proposer une "
                "(primestone-identity voice-propose), puis l'approuver"
            )
        return approved[0]

    # --- Visuels ----------------------------------------------------------------------------

    def add_visual(
        self,
        rules: dict[str, Any],
        *,
        created_by: str,
        series_id: UUID | None = None,
        platform: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        if not rules:
            raise IdentityError("un profil visuel exige des règles")
        if language not in (None, "fr", "en"):
            raise IdentityError("langues possibles : fr, en")
        with self._engine.begin() as conn:
            # Une nouvelle version remplace la précédente pour la même portée (conservée).
            previous = (
                conn.execute(
                    text(
                        "UPDATE brand_visual_profile SET status = 'RETIRED' "
                        "WHERE status = 'ACTIVE' AND series_id IS NOT DISTINCT FROM :s "
                        "AND platform IS NOT DISTINCT FROM :p "
                        "AND language IS NOT DISTINCT FROM :l RETURNING version"
                    ),
                    {"s": series_id, "p": platform, "l": language},
                )
                .scalars()
                .all()
            )
            row = (
                conn.execute(
                    text(
                        "INSERT INTO brand_visual_profile (brand_id, series_id, platform, "
                        "language, rules, version, created_by) VALUES ((SELECT id FROM "
                        "media_brand WHERE slug = 'primestone'), :s, :p, :l, CAST(:r AS jsonb), "
                        ":v, :by) RETURNING id, version"
                    ),
                    {
                        "s": series_id,
                        "p": platform,
                        "l": language,
                        "r": _json(rules),
                        "v": max(previous, default=0) + 1,
                        "by": created_by,
                    },
                )
                .mappings()
                .one()
            )
        return dict(row)

    def visuals(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT * FROM brand_visual_profile "
                        "ORDER BY status, series_id NULLS FIRST, platform NULLS FIRST, language"
                    )
                ).mappings()
            ]

    def visual_for(
        self, *, language: str, series_id: UUID | None = None, platform: str | None = None
    ) -> dict[str, Any]:
        """Règles visuelles applicables, de la plus générale à la plus précise.

        Seuls les profils sans langue ou de la même langue sont retenus : une règle FR ne
        s'applique jamais à un contenu EN.
        """
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT id, series_id, platform, language, rules, version "
                        "FROM brand_visual_profile WHERE status = 'ACTIVE' "
                        "AND (language IS NULL OR language = :l) "
                        "AND (series_id IS NULL OR series_id = :s) "
                        "AND (platform IS NULL OR platform = :p)"
                    ),
                    {"l": language, "s": series_id, "p": platform},
                )
                .mappings()
                .all()
            )
        ordered = sorted(
            rows,
            key=lambda r: (
                r["series_id"] is not None,
                r["platform"] is not None,
                r["language"] is not None,
            ),
        )
        rules: dict[str, Any] = {}
        for r in ordered:
            rules.update(r["rules"])
        return {
            "language": language,
            "rules": rules,
            "applied": [
                {k: (str(r[k]) if r[k] is not None else None) for k in ("id", "series_id")}
                | {"platform": r["platform"], "language": r["language"], "version": r["version"]}
                for r in ordered
            ],
        }

    # --- Narration --------------------------------------------------------------------------

    def narrate(
        self,
        script_id: UUID,
        *,
        tts: TTSProvider | None = None,
        store: ObjectStore | None = None,
    ) -> dict[str, Any]:
        """Plan de narration par la voix de marque ; synthèse locale facultative.

        Aucune voix ni aucun visage du fondateur : seule une voix approuvée de la langue du
        script est utilisée.
        """
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT s.title, s.language, s.status, v.number, v.content FROM script s "
                        "JOIN script_version v ON v.script_id = s.id WHERE s.id = :s "
                        "ORDER BY v.number DESC LIMIT 1"
                    ),
                    {"s": script_id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise LookupError("script introuvable ou sans version")
        voice = self.voice_for(row["language"])
        parts = []
        for index, section in enumerate(sections(row["content"]), start=1):
            spoken = narration_text(section.text)
            if not spoken:
                continue
            part: dict[str, Any] = {
                "index": index,
                "title": section.title,
                "text": spoken,
                "estimated_seconds": round(len(spoken.split()) / WORDS_PER_MINUTE * 60),
            }
            if tts is not None and store is not None:
                audio = tts.synthesize(spoken, language=row["language"])
                key = f"narration/{script_id}/v{row['number']}/{index:03d}.wav"
                store.put_bytes(key, audio, "audio/wav")
                part["audio_key"] = key
            parts.append(part)
        return {
            "method": METHOD,
            "script_id": str(script_id),
            "script_version": row["number"],
            "script_status": row["status"],
            "language": row["language"],
            "voice": {
                k: voice[k] for k in ("name", "kind", "provider", "voice", "license", "allowed_use")
            },
            "sections": parts,
            "estimated_seconds": sum(p["estimated_seconds"] for p in parts),
            "founder_required": False,
            "rule": "Voix de marque approuvée uniquement ; aucune publication automatique.",
        }
