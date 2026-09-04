from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CultivationArchitectureTests(unittest.TestCase):
    def test_module_and_loader_identity(self):
        self.assertEqual(ROOT.name, "mod-cultivation")
        loader = (ROOT / "src/mod_cultivation_loader.cpp").read_text(encoding="utf-8")
        self.assertIn("Addmod_cultivationScripts", loader)
        self.assertIn("Cultivation::AddRogueSubsystemScripts", loader)
        self.assertNotIn("Addmod_rogue_pathsScripts", loader)

    def test_namespaced_command_surface(self):
        command = (ROOT / "src/CultivationCommand.cpp").read_text(encoding="utf-8")
        rogue = (ROOT / "src/rogue/RoguePathCommand.cpp").read_text(encoding="utf-8")
        self.assertIn('{ "cultivation", cultivationCommandTable', command)
        self.assertIn('{ "rogue", rogueCommandTable', command)
        for action in ("celestial", "sha", "status", "sync", "reset"):
            self.assertIn('{ "' + action + '"', command)
        self.assertNotIn('{ "roguepath"', command + rogue)
        self.assertIn(".cultivation rogue", command + rogue)

    def test_active_config_and_persistence_names(self):
        config = (ROOT / "conf/mod_cultivation.conf.dist").read_text(encoding="utf-8")
        self.assertIn("Cultivation.Rogue.", config)
        self.assertNotIn("RoguePaths.", config)
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "src").rglob("*.cpp")
        )
        self.assertIn("character_cultivation_rogue", source)
        self.assertNotIn('"character_rogue_path"', source)

    def test_active_sql_and_script_names(self):
        base_files = list((ROOT / "data/sql").glob("*/base/*.sql"))
        active_sql = "\n".join(path.read_text(encoding="utf-8") for path in base_files)
        self.assertIn("character_cultivation_rogue", active_sql)
        self.assertIn("spell_cultivation_rogue_", active_sql)
        self.assertNotIn("spell_rogue_path_active", active_sql)
        self.assertNotIn("spell_rog_path_", active_sql)
        command_sql = (ROOT / "data/sql/world/base/cultivation_command.sql").read_text(encoding="utf-8")
        self.assertIn("('cultivation'", command_sql)

    def test_schema6_manifest(self):
        data = json.loads((ROOT / "data/cultivation_rogue_spell_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 6)
        migration = json.loads((ROOT / "data/sql/migrations/2.0.0/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(migration["schema_version"], 6)
        self.assertEqual(migration["database_scope"], "cultivation_test_*_v1 only")
        preflights = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "data/sql/migrations/2.0.0").glob("*.preflight.sql")
        )
        self.assertIn("cultivation_test_auth_v1", preflights)
        self.assertIn("cultivation_test_world_v1", preflights)
        self.assertIn("cultivation_test_characters_v1", preflights)
        self.assertNotIn("rogue_paths_test_", preflights)


if __name__ == "__main__":
    unittest.main(verbosity=2)
