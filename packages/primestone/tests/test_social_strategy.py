import pytest

from primestone.social import PLATFORMS, beats, build_package, render

DELIVERABLE = """# Dossier : Selina
## Présence dans l'œuvre
Selina parle dans Nuit noire #1 : « Je m'appelle Selina. » [Nuit noire #1, p. 1, case 1].
Selina parle dans Nuit noire #2 : « Encore toi. » [Nuit noire #2, p. 3, case 1].
## Affirmations du personnage
Selina affirme : « Je suis Catwoman. » [Nuit noire #1, p. 2, case 2].
Selina vole des diamants depuis des années.
## Points de continuité à examiner
Contradiction possible (age) : « J'ai 28 ans. » [Nuit noire #1, p. 1, case 1] \
et « J'ai 31 ans. » [Nuit noire #2, p. 1, case 1]."""

LINES = [line for line in DELIVERABLE.splitlines() if line.strip()]
CHECKS = [
    {"sentence": line, "status": "NOT_FACTUAL" if line.startswith("#") else "VERIFIED"}
    for line in LINES
]
CHECKS[6]["status"] = "NO_CITATION"  # « Selina vole des diamants… » : non sourcé


def test_beats_keep_only_verified_facts_with_role_and_section() -> None:
    found = beats(DELIVERABLE, CHECKS)
    assert len(found) == 4
    assert all("diamants" not in b.text for b in found)
    roles = {b.role for b in found}
    assert roles == {"FACT", "CLAIM", "TENSION"}
    tension = next(b for b in found if b.role == "TENSION")
    assert tension.section == "Points de continuité à examiner"
    assert len(tension.citations) == 2


def test_package_structures_differ_per_platform() -> None:
    package = build_package(source_title="Dossier : Selina", deliverable=DELIVERABLE, checks=CHECKS)
    p = package["platforms"]
    assert set(p) == set(PLATFORMS)
    youtube = p["youtube_long"]["content"]
    assert [c["title"] for c in youtube["chapters"]] == [
        "Présence dans l'œuvre",
        "Affirmations du personnage",
        "Points de continuité à examiner",
    ]
    assert youtube["warnings"] == []
    tiktok, reels = p["tiktok"]["content"], p["instagram_reels"]["content"]
    assert tiktok["hook_role"] == "TENSION"  # la tension ouvre la découverte
    assert reels["hook"] != tiktok["hook"]  # autre angle, pas une copie
    assert tiktok["estimated_seconds"] > 0
    carousel = p["instagram_carousel"]["content"]
    assert carousel["slides"] == 4 + 2
    assert package["excluded_unverified"] == ["Selina vole des diamants depuis des années."]
    assert p["tiktok"]["spec"]["status"] == "à revérifier avant publication"


def test_render_keeps_citations_and_marks_framing() -> None:
    text = render(build_package(source_title="Dossier", deliverable=DELIVERABLE, checks=CHECKS))
    assert "« Je suis Catwoman. » [Nuit noire #1, p. 2, case 2]." in text
    assert "diamants" not in text
    for line in text.splitlines():
        # Toute ligne est soit un titre, soit une note, soit un fait cité, soit une question.
        assert line.startswith(("#", "Note :", "Et vous")) or "[Nuit noire" in line, line


def test_guards() -> None:
    with pytest.raises(ValueError, match="aucun fait vérifié"):
        build_package(source_title="x", deliverable="# x", checks=[])
    with pytest.raises(ValueError, match="inconnue"):
        build_package(
            source_title="x", deliverable=DELIVERABLE, checks=CHECKS, platforms=["myspace"]
        )
    many = "\n".join(f"Fait {i} : « a » [T, p. {i}]." for i in range(1, 25))
    checks = [{"sentence": s, "status": "VERIFIED"} for s in many.splitlines()]
    package = build_package(source_title="x", deliverable=many, checks=checks)
    carousel = package["platforms"]["instagram_carousel"]["content"]
    assert carousel["slides"] == 20
    assert carousel["warnings"]
    assert package["platforms"]["youtube_long"]["content"]["warnings"]  # 1 seul chapitre
