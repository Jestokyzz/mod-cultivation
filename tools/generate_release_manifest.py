"""Generate the source manifest for the unaccepted Cultivation candidate."""

from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "release-manifest.json"
EXCLUDED_PARTS = {".git", "__pycache__", "build", "staging", "generated", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".dmp", ".zip"}
EXCLUDED_PREFIXES = ("client_patch/addon/", "data/sql/legacy/")
EXCLUDED_FILES = {"tools/test_talent_ui.py"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if path == OUTPUT or any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    relative_name = relative.as_posix()
    if relative_name in EXCLUDED_FILES or relative_name.startswith(EXCLUDED_PREFIXES):
        return False
    return path.suffix.lower() not in EXCLUDED_SUFFIXES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--accepted-release', choices=['v2.0.0'])
    args = parser.parse_args()
    files = {
        path.relative_to(ROOT).as_posix(): {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(ROOT.rglob("*"))
        if path.is_file() and included(path)
    }
    manifest = {
        "module": "mod-cultivation",
        "candidate": "v2.0.0-audit-candidate5",
        "status": "candidate-unaccepted",
        "core_revision": "7c8ed00e7f654617a47bdf728b49707f60aa1aae",
        "subsystems": ["rogue"],
        "public_command": ".cultivation rogue <action>",
        "schema_version": 6,
        "production_modified": False,
        "audit_status": "audit-fixes-manifest.json",
        "installable_package": False,
        "publish_policy": "candidate branch only until explicit user acceptance",
        "files": files,
    }
    if args.accepted_release:
        acceptance = json.loads((ROOT / 'audit-fixes-manifest.json').read_text(encoding='utf8'))
        if acceptance['status'] != 'user-accepted-production-installed-startup-passed':
            raise ValueError('Missing user acceptance / production startup gate')
        manifest.update(candidate=args.accepted_release, status='user-accepted-production-installed',
                        production_modified=True, installable_package=True,
                        publish_policy='accepted release; private repository; compatible JestokyCraft only')
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS source manifest: {len(files)} files -> {OUTPUT}")


if __name__ == "__main__":
    main()
