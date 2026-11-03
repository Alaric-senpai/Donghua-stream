"""Unit tests for the shared JSON config (stdlib unittest)."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app_config


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name) / "donghua-stream"
        self.dir_patch = mock.patch.object(app_config, "CONFIG_DIR", base)
        self.path_patch = mock.patch.object(
            app_config, "CONFIG_PATH", base / "config.json")
        self.dir_patch.start()
        self.path_patch.start()
        self.addCleanup(self.dir_patch.stop)
        self.addCleanup(self.path_patch.stop)

    def test_defaults_are_merged_without_a_file(self):
        cfg = app_config.load_config()
        self.assertEqual(cfg["database"]["host"], "localhost")
        self.assertEqual(cfg["database"]["user"], "")
        self.assertEqual(cfg["settings"]["default_quality"], "720p")
        self.assertFalse(app_config.CONFIG_PATH.exists())

    def test_missing_credentials_are_reported(self):
        labels = app_config.missing_labels()
        self.assertIn("PostgreSQL user", labels)
        self.assertIn("YouTube Data API key", labels)
        self.assertFalse(app_config.database_ready())
        app_config.set_database({"user": "charles"})
        self.assertTrue(app_config.database_ready())
        self.assertFalse(app_config.youtube_ready())
        app_config.set_youtube({"api_key": "AIza-test"})
        self.assertTrue(app_config.youtube_ready())

    def test_saved_config_is_private_and_round_trips(self):
        app_config.set_database({
            "host": "db.local", "port": 5544, "user": "alice",
            "password": "s3cret", "dbname": "donghua_test",
        })
        app_config.set_youtube({"api_key": "AIza-test", "region_code": "GB"})
        app_config.set_setting("default_quality", "1080p")

        raw = json.loads(app_config.CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(raw["database"]["port"], 5544)
        self.assertEqual(raw["youtube"]["api_key"], "AIza-test")
        self.assertEqual(raw["settings"]["default_quality"], "1080p")

        mode = stat.S_IMODE(os.stat(app_config.CONFIG_PATH).st_mode)
        self.assertEqual(mode, 0o600)
        dir_mode = stat.S_IMODE(os.stat(app_config.CONFIG_DIR).st_mode)
        self.assertEqual(dir_mode, 0o700)

    def test_unknown_settings_are_ignored(self):
        self.assertFalse(app_config.set_setting("not_a_setting", "x"))
        app_config.set_settings({"default_quality": "480p", "bogus": "nope"})
        self.assertEqual(app_config.get_setting("default_quality"), "480p")
        self.assertNotIn("bogus", app_config.settings())

    def test_reset_preserves_credentials(self):
        app_config.set_database({"user": "alice"})
        app_config.set_youtube({"api_key": "AIza-test"})
        app_config.set_setting("default_quality", "2160p")
        app_config.reset_settings()
        self.assertEqual(app_config.get_setting("default_quality"), "720p")
        self.assertEqual(app_config.database_config()["user"], "alice")
        self.assertEqual(app_config.get_youtube_api_key(), "AIza-test")

    def test_legacy_import_does_not_overwrite_explicit_values(self):
        app_config.set_setting("default_quality", "1080p")
        imported = app_config.import_legacy_settings({
            "default_quality": "360p",
            "max_retries": "7",
        })
        self.assertEqual(imported, 1)
        self.assertEqual(app_config.get_setting("default_quality"), "1080p")
        self.assertEqual(app_config.get_setting("max_retries"), "7")
        # A second import is a no-op.
        self.assertEqual(app_config.import_legacy_settings({"max_retries": "9"}), 0)

    def test_corrupt_json_raises_a_helpful_error(self):
        app_config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        app_config.CONFIG_PATH.write_text("{not json", encoding="utf-8")
        with self.assertRaises(app_config.ConfigError) as ctx:
            app_config.load_config()
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_config_path_can_be_displayed_with_tilde(self):
        with mock.patch.dict(os.environ, {"HOME": str(Path(self.tmp.name))}):
            # display_path uses expanduser, which reads HOME on POSIX.
            shown = app_config.display_path()
        self.assertTrue(shown.endswith("config.json"))


if __name__ == "__main__":
    unittest.main()
