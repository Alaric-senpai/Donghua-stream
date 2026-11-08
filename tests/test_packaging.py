"""Packaging regression tests for the wheel/editable install contract."""
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


class PackagingTests(unittest.TestCase):
    def test_flat_modules_are_declared(self):
        modules = set(CONFIG["tool"]["setuptools"]["py-modules"])
        required = {
            "script", "db", "downloader", "urls", "app_config", "youtube_api",
            "gui_entry",
        }
        missing = required - modules
        self.assertFalse(missing, f"missing py-modules: {sorted(missing)}")

    def test_bundled_icons_are_package_data(self):
        data = CONFIG["tool"]["setuptools"]["package-data"]["gui"]
        self.assertIn("assets/icons/*.svg", data)

    def test_frontend_dependencies_are_separate_extras(self):
        core = CONFIG["project"]["dependencies"]
        extras = CONFIG["project"]["optional-dependencies"]
        self.assertFalse(any(dep.startswith("PyQt6") for dep in core))
        self.assertFalse(any(dep.startswith("rich") for dep in core))
        self.assertTrue(any(dep.startswith("PyQt6") for dep in extras["gui"]))
        self.assertTrue(any(dep.startswith("rich") for dep in extras["cli"]))
        self.assertTrue(any(dep.startswith("questionary") for dep in extras["cli"]))

    def test_gui_entry_point_uses_the_safe_wrapper(self):
        scripts = CONFIG["project"]["scripts"]
        self.assertEqual(scripts["donghua-gui"], "gui_entry:main")


if __name__ == "__main__":
    unittest.main()
