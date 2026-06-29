"""Assemble the Vocareum notebook bundle.

Additive packaging: the ladder notebooks stay single-source in
L100-foundations/, L200-capabilities/, L300-usecase/. This script stages them
under Vocareum-friendly ordered names, fills empty tiers with a placeholder
notebook (so the full course structure is testable before L200/L300 are built),
adds the authored wrapper notebooks (agenda, setup check, wrap up), and zips the
result to dist/akzonobel-agent-bricks-bundle.zip.

Run from anywhere:  python vocareum-course/scripts/build_bundle.py

Keeps notebooks as .ipynb (no format conversion). Markdown labs (.md) in a tier
are wrapped into a single-markdown-cell .ipynb so they appear in the bundle.
"""

import json
import shutil
import zipfile
from pathlib import Path

VC = Path(__file__).resolve().parents[1]          # vocareum-course/
REPO = VC.parents[0]                               # repo root
COURSEWARE = VC / "courseware"
STAGING = VC / "dist" / "staging"
BUNDLE = VC / "dist" / "akzonobel-agent-bricks-bundle.zip"

# Tier -> (numbering base, source dir, short label, subtitle for placeholders).
# Notebooks/markdown in each tier are picked up in sorted order; an empty tier
# gets one placeholder named with the subtitle.
TIERS = [
    (10, REPO / "L100-foundations", "L100", "Foundations"),
    (20, REPO / "L200-capabilities", "L200", "Capabilities"),
    (30, REPO / "L300-usecase", "L300", "Multi-domain Supervisor"),
]

# Acronyms that should not be title-cased into "Sql Ai".
ACRONYMS = {"sql": "SQL", "ai": "AI", "mcp": "MCP", "scm": "SCM", "mmf": "MMF",
            "esg": "ESG", "hitl": "HITL", "llm": "LLM", "uc": "UC"}


def md_cell(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def write_nb(path, cells):
    nb = {
        "cells": cells,
        "metadata": {
            "language_info": {"name": "python"},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(nb, indent=1), encoding="utf-8")


def pretty(stem):
    """'00_sql_ai_functions' -> 'SQL AI Functions' (acronym-aware)."""
    name = stem.split("_", 1)[-1] if stem[:2].isdigit() else stem
    words = name.replace("_", " ").replace("-", " ").split()
    return " ".join(ACRONYMS.get(w.lower(), w.title()) for w in words)


def placeholder(dst, label):
    write_nb(dst, [md_cell(
        f"# {label} — coming soon\n\n"
        f"This tier is part of the workshop ladder and will be added here as it is built.\n\n"
        f"For now it is a placeholder so the full course structure is testable end to end.\n"
    )])


def main():
    if STAGING.exists():
        shutil.rmtree(STAGING)
    (STAGING / "_AGENDA").mkdir(parents=True)

    # Wrapper notebooks authored in courseware/.
    shutil.copy2(COURSEWARE / "_AGENDA" / "00 - Start Here.ipynb", STAGING / "_AGENDA")
    shutil.copy2(COURSEWARE / "01 - Setup Check.ipynb", STAGING)

    # Tier notebooks, ordered. Empty tiers get a placeholder.
    for base, src_dir, label, subtitle in TIERS:
        items = []
        if src_dir.exists():
            items = sorted(
                [p for p in src_dir.iterdir()
                 if p.suffix in (".ipynb", ".md") and p.name.lower() != "readme.md"
                 and not p.name.startswith(".")],
                key=lambda p: p.name,
            )
        if not items:
            placeholder(STAGING / f"{base} - {label} - {subtitle} (coming soon).ipynb", f"{label} — {subtitle}")
            continue
        for i, p in enumerate(items):
            num = base + i
            title = pretty(p.stem)
            dst = STAGING / f"{num} - {label} - {title}.ipynb"
            if p.suffix == ".ipynb":
                shutil.copy2(p, dst)
            else:  # .md -> single markdown cell notebook
                write_nb(dst, [md_cell(p.read_text(encoding="utf-8"))])

    # Optional advanced: point at the hackathon starter kit.
    write_nb(STAGING / "90 - Optional Advanced - Hackathon Starter Kit.ipynb", [md_cell(
        "# 90 - Optional Advanced — Hackathon Starter Kit\n\n"
        "Fork a track and build your own AkzoNobel copilot. The kit ships 11 forkable "
        "tracks, one starter prompt each, and ai-dev-kit skills.\n\n"
        "See `hackathon-starter-kit/README.md` in the repo for the track catalog, "
        "the build path, and the judging rubric.\n"
    )])

    # Wrap up.
    shutil.copy2(COURSEWARE / "99 - Wrap Up.ipynb", STAGING)

    # Zip the staging tree (paths relative to staging root).
    BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    if BUNDLE.exists():
        BUNDLE.unlink()
    with zipfile.ZipFile(BUNDLE, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(STAGING.rglob("*.ipynb")):
            z.write(f, f.relative_to(STAGING))

    names = [f.relative_to(STAGING).as_posix() for f in sorted(STAGING.rglob("*.ipynb"))]
    print(f"Bundle written: {BUNDLE.relative_to(REPO)}")
    print(f"{len(names)} notebooks:")
    for n in names:
        print("  ", n)
    print("\nEntry (cfg): _AGENDA/00 - Start Here")


if __name__ == "__main__":
    main()
