"""Validate the Cultivation rename migration and generate its SHA-256 manifest."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/sql/migrations/2.0.0"
EXPECTED = {
    f"{database}.{phase}.sql"
    for database in ("auth", "characters", "world")
    for phase in ("preflight", "up", "postflight", "rollback")
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    present = {path.name for path in OUT.glob("*.sql")}
    missing = sorted(EXPECTED - present)
    unexpected = sorted(present - EXPECTED)
    if missing or unexpected:
        raise SystemExit(f"schema-6 SQL set mismatch: missing={missing}, unexpected={unexpected}")

    files = {name: digest(OUT / name) for name in sorted(EXPECTED)}
    manifest = {
        "version": "2.0.0",
        "schema_version": 6,
        "status": "candidate-unaccepted",
        "database_scope": "cultivation_test_*_v1 only",
        "source_manifest_sha256": digest(ROOT / "data/cultivation_rogue_spell_manifest.json"),
        "transition": {
            "module": "mod-rogue-paths -> mod-cultivation",
            "command": ".roguepath <action> -> .cultivation rogue <action>",
            "characters_table": "character_rogue_path -> character_cultivation_rogue",
            "state_preserved": True,
        },
        "files": files,
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS schema-6 migration manifest: {manifest_path}")


if __name__ == "__main__":
    main()
