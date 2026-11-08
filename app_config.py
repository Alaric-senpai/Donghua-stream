"""Central JSON configuration shared by the GUI and the CLI.

Everything that must survive a restart lives in one user-owned file:

    ``~/.config/donghua-stream/config.json``

That includes PostgreSQL credentials, the YouTube Data API key and every
download default.  The old ``app_settings`` table is only read once, by the
legacy importer in :mod:`db`, so existing installs keep their preferences.

The module deliberately has no dependency on ``db`` or ``PyQt6``: both
front-ends and the storage layer import *it*, never the other way around.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

APP_DIR_NAME = "donghua-stream"
CONFIG_VERSION = 2

_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
    os.path.expanduser("~"), ".config")
CONFIG_DIR = Path(_CONFIG_HOME) / APP_DIR_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"

# Credentials are intentionally blank in source.  A first run prompts for
# them and writes the user's values into the config file; nothing secret is
# ever hard-coded or read from process environment variables.
DEFAULT_DATABASE: Dict[str, Any] = {
    "host": "localhost",
    "port": 5432,
    "user": "",
    "password": "",
    "dbname": "donghua_db",
}

DEFAULT_YOUTUBE: Dict[str, Any] = {
    "api_key": "",
    "region_code": "US",
    "language": "en",
    "safe_search": "moderate",
}

DEFAULT_SETTINGS: Dict[str, str] = {
    "global_save_dir": os.path.expanduser("~/Videos"),
    "default_quality": "720p",
    "browser_cookies": "none",
    "max_retries": "3",
    "default_container": "mp4",
    "sub_langs": "en",
    "rate_limit_mb": "0",
    "per_series_subfolder": "1",
}

DEFAULT_EXPLORE: Dict[str, Any] = {
    # Explore never loads anything automatically.  Only an explicit search
    # spends quota, and its responses are cached on disk.
    "result_limit": 18,
    "cache_minutes": 20,
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": CONFIG_VERSION,
    "database": copy.deepcopy(DEFAULT_DATABASE),
    "youtube": copy.deepcopy(DEFAULT_YOUTUBE),
    "settings": copy.deepcopy(DEFAULT_SETTINGS),
    "explore": copy.deepcopy(DEFAULT_EXPLORE),
    "meta": {"legacy_settings_imported": False},
}

VALID_SECTIONS = ("database", "youtube", "settings", "explore", "meta")
_LOCK = threading.RLock()


class ConfigError(RuntimeError):
    """Raised when the config file exists but cannot be parsed."""


# ---------------------------------------------------------------------------
# Paths / low-level IO
# ---------------------------------------------------------------------------
def config_path() -> str:
    """Absolute path of the active config file (handy for the UI)."""
    return str(CONFIG_PATH)


def display_path() -> str:
    """Compact ``~/.config/...`` form for labels and tooltips."""
    path = str(CONFIG_PATH)
    home = os.path.expanduser("~")
    return path.replace(home, "~", 1) if path.startswith(home) else path


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass


def _read_raw() -> Dict[str, Any]:
    """Read the file as-is, treating a missing file as an empty config."""
    try:
        text = CONFIG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ConfigError(f"Could not read {display_path()}: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"{display_path()} is not valid JSON (line {exc.lineno}, "
            f"column {exc.colno}): {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{display_path()} must contain a JSON object.")
    return data


def _write(data: Dict[str, Any]) -> None:
    """Atomically replace the config file with owner-only permissions."""
    _ensure_dir()
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=".config-", suffix=".tmp", dir=str(CONFIG_DIR))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(CONFIG_PATH))
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value).strip()


def _database(raw: Any) -> Dict[str, Any]:
    data = copy.deepcopy(DEFAULT_DATABASE)
    if isinstance(raw, dict):
        data.update(raw)
    # Accept the older `name` spelling if a hand-edited file uses it.
    if isinstance(raw, dict) and "name" in raw and "dbname" not in raw:
        data["dbname"] = raw.get("name", data["dbname"])
    try:
        port = int(data.get("port") or 5432)
    except (TypeError, ValueError):
        port = 5432
    return {
        "host": _text(data.get("host"), DEFAULT_DATABASE["host"]),
        "port": max(1, min(65535, port)),
        "user": _text(data.get("user")),
        "password": str(data.get("password") or ""),
        "dbname": _text(data.get("dbname"), DEFAULT_DATABASE["dbname"]),
    }


def _youtube(raw: Any) -> Dict[str, Any]:
    data = copy.deepcopy(DEFAULT_YOUTUBE)
    if isinstance(raw, dict):
        data.update(raw)
    data["api_key"] = _text(data.get("api_key"))
    data["region_code"] = (_text(data.get("region_code"), "US") or "US").upper()
    data["language"] = _text(data.get("language"), "en") or "en"
    safe = _text(data.get("safe_search"), "moderate").lower()
    data["safe_search"] = safe if safe in ("none", "moderate", "strict") else "moderate"
    return data


def _settings(raw: Any) -> Dict[str, str]:
    data = dict(DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in DEFAULT_SETTINGS and value is not None:
                data[str(key)] = str(value)
    return data


def _explore(raw: Any) -> Dict[str, Any]:
    data = copy.deepcopy(DEFAULT_EXPLORE)
    if isinstance(raw, dict):
        data.update(raw)
    try:
        data["result_limit"] = max(1, min(50, int(data.get("result_limit") or 18)))
    except (TypeError, ValueError):
        data["result_limit"] = 18
    try:
        data["cache_minutes"] = max(0, min(1440, int(data.get("cache_minutes") or 20)))
    except (TypeError, ValueError):
        data["cache_minutes"] = 20
    data["safe_search"] = _youtube(data).get("safe_search", "moderate")
    return data


def normalize(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge an arbitrary dictionary onto the shipped defaults."""
    raw = raw if isinstance(raw, dict) else {}
    meta = copy.deepcopy(DEFAULT_CONFIG["meta"])
    if isinstance(raw.get("meta"), dict):
        meta.update(raw["meta"])
    return {
        "version": CONFIG_VERSION,
        "database": _database(raw.get("database")),
        "youtube": _youtube(raw.get("youtube")),
        "settings": _settings(raw.get("settings")),
        "explore": _explore(raw.get("explore")),
        "meta": meta,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_config() -> Dict[str, Any]:
    """Return the merged, normalized config (defaults fill missing keys)."""
    with _LOCK:
        return normalize(_read_raw())


def save_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and atomically persist the whole config."""
    if not isinstance(config, dict):
        raise ConfigError("Config must be a dictionary.")
    data = normalize(config)
    data["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds")
    with _LOCK:
        _write(data)
    return copy.deepcopy(data)


def ensure_config_file() -> Dict[str, Any]:
    """Create the config file with defaults if it does not exist yet."""
    if CONFIG_PATH.exists():
        return load_config()
    return save_config(load_config())


def update_section(section: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """Patch one section and persist the result."""
    if section not in VALID_SECTIONS:
        raise ValueError(f"Unknown config section: {section}")
    config = load_config()
    current = config.get(section)
    if not isinstance(current, dict):
        current = {}
        config[section] = current
    current.update(values or {})
    return save_config(config)


def database_config() -> Dict[str, Any]:
    return load_config()["database"]


def youtube_config() -> Dict[str, Any]:
    return load_config()["youtube"]


def explore_config() -> Dict[str, Any]:
    return load_config()["explore"]


def get_youtube_api_key() -> str:
    return str(youtube_config().get("api_key") or "")


def settings() -> Dict[str, str]:
    """All persisted download/UI settings, with defaults applied."""
    return load_config()["settings"]


def get_setting(key: str, default: Optional[str] = None) -> str:
    values = settings()
    if key in values:
        return values[key]
    if default is not None:
        return default
    return str(DEFAULT_SETTINGS.get(key, ""))


def set_setting(key: str, value: Any) -> bool:
    if key not in DEFAULT_SETTINGS:
        return False
    config = load_config()
    config["settings"][str(key)] = "" if value is None else str(value)
    save_config(config)
    return True


def set_settings(values: Dict[str, Any]) -> bool:
    """Persist several settings in one atomic write."""
    config = load_config()
    changed = False
    for key, value in (values or {}).items():
        if key in DEFAULT_SETTINGS:
            config["settings"][str(key)] = "" if value is None else str(value)
            changed = True
    if changed:
        save_config(config)
    return changed


def reset_settings() -> Dict[str, str]:
    """Restore the shipped download defaults, preserving credentials."""
    config = load_config()
    config["settings"] = copy.deepcopy(DEFAULT_SETTINGS)
    save_config(config)
    return copy.deepcopy(DEFAULT_SETTINGS)


def set_database(values: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    config["database"].update(values or {})
    return save_config(config)["database"]


def set_youtube(values: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    config["youtube"].update(values or {})
    return save_config(config)["youtube"]


def set_explore(values: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    config["explore"].update(values or {})
    return save_config(config)["explore"]


def credential_issues(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Human-readable list of missing/blank credentials.

    Each entry carries the config ``section`` and ``key`` so a dialog can
    route the user directly to the right field.
    """
    cfg = config or load_config()
    db = cfg.get("database", {})
    yt = cfg.get("youtube", {})
    issues: List[Dict[str, str]] = []

    def add(section: str, key: str, label: str) -> None:
        issues.append({"section": section, "key": key, "label": label})

    if not _text(db.get("host")):
        add("database", "host", "PostgreSQL host")
    try:
        port = int(db.get("port") or 0)
        if not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        add("database", "port", "PostgreSQL port")
    if not _text(db.get("user")):
        add("database", "user", "PostgreSQL user")
    if not _text(db.get("dbname")):
        add("database", "dbname", "PostgreSQL database name")
    if not _text(yt.get("api_key")):
        add("youtube", "api_key", "YouTube Data API key")
    return issues


def database_ready(config: Optional[Dict[str, Any]] = None) -> bool:
    return not any(i["section"] == "database"
                   for i in credential_issues(config))


def youtube_ready(config: Optional[Dict[str, Any]] = None) -> bool:
    return not any(i["section"] == "youtube"
                   for i in credential_issues(config))


def missing_labels(config: Optional[Dict[str, Any]] = None) -> List[str]:
    return [issue["label"] for issue in credential_issues(config)]


# ---------------------------------------------------------------------------
# Legacy app_settings migration (called by db.init_db)
# ---------------------------------------------------------------------------
def import_legacy_settings(values: Dict[str, Any]) -> int:
    """Copy old PostgreSQL preferences once, without overwriting user edits.

    Returns the number of keys imported.  The flag lives in ``meta`` so the
    import never resurrects settings the user has deliberately reset.
    """
    if not isinstance(values, dict) or not values:
        return 0
    raw = _read_raw()
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    if meta.get("legacy_settings_imported"):
        return 0
    config = normalize(raw)
    imported = 0
    for key, value in values.items():
        if key not in DEFAULT_SETTINGS:
            continue
        # A value that differs from the shipped default was deliberately
        # chosen before the import; honour it.  Untouched defaults are safe
        # to replace with the old PostgreSQL preference.
        current = str(config["settings"].get(key, ""))
        if current == str(DEFAULT_SETTINGS.get(key, "")) and current != str(value):
            config["settings"][key] = str(value)
            imported += 1
    config["meta"]["legacy_settings_imported"] = True
    config["meta"]["legacy_imported_at"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds")
    save_config(config)
    return imported


def mark_legacy_imported() -> None:
    """Record a completed import even when the old table was empty."""
    config = load_config()
    if config["meta"].get("legacy_settings_imported"):
        return
    config["meta"]["legacy_settings_imported"] = True
    save_config(config)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
def summarize(config: Optional[Dict[str, Any]] = None) -> str:
    """Short, non-secret summary for Settings / error reports."""
    cfg = config or load_config()
    db = cfg["database"]
    yt = cfg["youtube"]
    return (
        f"Config:  {display_path()}\n"
        f"DB:      {db.get('dbname')} @ {db.get('host')}:{db.get('port')} "
        f"(user {db.get('user') or '-'})\n"
        f"YouTube: {'configured' if yt.get('api_key') else 'API key missing'} "
        f"({yt.get('region_code', 'US')})\n"
    )


def iter_sections() -> Iterable[str]:
    return VALID_SECTIONS
