#!/usr/bin/env python3
"""Install the I'm on Windows Agent Skill for Claude Code or Codex."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import uuid
from pathlib import Path


SKILL_NAME = "im-on-windows"


def destinations(home: Path, agent: str) -> list[Path]:
    choices = {
        "codex": home / ".agents" / "skills" / SKILL_NAME,
        "claude": home / ".claude" / "skills" / SKILL_NAME,
    }
    return list(choices.values()) if agent == "both" else [choices[agent]]


def owns_destination(path: Path) -> bool:
    skill_file = path / "SKILL.md"
    if not skill_file.is_file():
        return False
    try:
        front = skill_file.read_text(encoding="utf-8")[:600]
    except OSError:
        return False
    return "name: im-on-windows" in front


def install_one(source: Path, destination: Path, force: bool, dry_run: bool) -> None:
    if destination.exists() and not force:
        raise FileExistsError(f"{destination} already exists; rerun with --force to update this skill")
    if destination.exists() and not owns_destination(destination):
        raise RuntimeError(f"refusing to replace an unrelated directory: {destination}")
    if dry_run:
        print(f"Would install {SKILL_NAME} to {destination}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{SKILL_NAME}-", dir=destination.parent))
    backup: Path | None = None
    try:
        shutil.copytree(source, stage, dirs_exist_ok=True)
        if destination.exists():
            backup = destination.with_name(f".{SKILL_NAME}-backup-{uuid.uuid4().hex}")
            destination.rename(backup)
        stage.rename(destination)
        if backup:
            shutil.rmtree(backup)
    except Exception:
        if destination.exists() and not owns_destination(destination):
            shutil.rmtree(destination, ignore_errors=True)
        if backup and backup.exists() and not destination.exists():
            backup.rename(destination)
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(f"Installed {SKILL_NAME} to {destination}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=["codex", "claude", "both"], default="both")
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--force", action="store_true", help="Update an existing im-on-windows installation")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = Path(__file__).resolve().parent / "skill"
    if not (source / "SKILL.md").is_file():
        print("error: skill/SKILL.md is missing", file=sys.stderr)
        return 1
    try:
        for destination in destinations(args.home.expanduser(), args.agent):
            install_one(source, destination, args.force, args.dry_run)
    except (FileExistsError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
