"""db.py - PostgreSQL storage engine for Donghua series and episode URLs.

Handles automatic database creation, schema migrations, synchronization with
urls.py and local downloaded archives, and full CRUD operations.
"""

import os
import re
from typing import List, Dict, Optional, Any, Tuple
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import RealDictCursor

# Default Database Configuration
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "user": os.environ.get("DB_USER", "charles"),
    "password": os.environ.get("DB_PASSWORD", "password"),
    "dbname": os.environ.get("DB_NAME", "donghua_db"),
}


def sanitize_slug(name: str) -> str:
    """Generate a clean identifier key from a series name."""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "series"


def extract_video_id(url: str) -> str:
    """Extract YouTube 11-char video ID from various URL formats."""
    m = re.search(r"(?:v=|youtu\.be\/|\/embed\/|\/v\/)([0-9A-Za-z_-]{11})", url)
    return m.group(1) if m else url.strip()


def ensure_database_exists() -> bool:
    """Check if the target PostgreSQL database exists; if not, create it."""
    target_db = DB_CONFIG["dbname"]
    admin_conn = None
    try:
        # Connect to maintenance db 'postgres'
        admin_conn = psycopg2.connect(
            dbname="postgres",
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
        )
        admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with admin_conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
            exists = cur.fetchone() is not None
            if not exists:
                # Safe execution to create database with owner
                cur.execute(f'CREATE DATABASE "{target_db}" OWNER "{DB_CONFIG["user"]}"')
                return True
        return False
    except Exception as e:
        raise RuntimeError(f"Failed to check or create database '{target_db}': {e}")
    finally:
        if admin_conn:
            admin_conn.close()


def get_connection():
    """Establish and return a connection to the donghua database."""
    return psycopg2.connect(
        dbname=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
    )


def init_schema():
    """Create the series and episodes tables and indexes if they do not exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS series (
                    id SERIAL PRIMARY KEY,
                    key VARCHAR(100) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    save_dir VARCHAR(500) NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS episodes (
                    id SERIAL PRIMARY KEY,
                    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
                    video_id VARCHAR(50) NOT NULL,
                    url TEXT NOT NULL,
                    episode_number INTEGER DEFAULT NULL,
                    title TEXT DEFAULT '',
                    status VARCHAR(50) DEFAULT 'pending',
                    downloaded_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(series_id, video_id)
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_episodes_series_id ON episodes(series_id);
                CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);
                CREATE INDEX IF NOT EXISTS idx_series_key ON series(key);
            """)
        conn.commit()


def get_archive_downloaded_ids(save_dir: str) -> set:
    """Read video IDs already marked as downloaded in the directory's downloaded.txt."""
    archive_path = os.path.join(save_dir, "downloaded.txt")
    if not os.path.exists(archive_path):
        return set()
    ids = set()
    try:
        with open(archive_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split()
                if parts:
                    ids.add(parts[-1])
    except Exception:
        pass
    return ids


def sync_existing_records() -> Dict[str, int]:
    """Sync all series and episode URLs from urls.py into PostgreSQL.

    Also synchronizes status against existing downloaded.txt files.
    """
    import urls as file_urls

    synced_series = 0
    synced_episodes = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            for s in file_urls.get_all_series():
                cur.execute(
                    """
                    INSERT INTO series (key, name, save_dir, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (key) DO UPDATE
                    SET name = EXCLUDED.name,
                        save_dir = EXCLUDED.save_dir,
                        description = COALESCE(NULLIF(EXCLUDED.description, ''), series.description),
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id;
                    """,
                    (s.key, s.name, s.save_dir, s.description or f"{s.name} donghua episodes"),
                )
                series_id = cur.fetchone()[0]
                synced_series += 1

                # Check existing downloaded.txt
                downloaded_ids = get_archive_downloaded_ids(s.save_dir)

                for url in s.urls:
                    clean_url = url.strip()
                    if not clean_url or clean_url.startswith("#"):
                        continue
                    vid = extract_video_id(clean_url)
                    status = "downloaded" if vid in downloaded_ids else "pending"

                    cur.execute(
                        """
                        INSERT INTO episodes (series_id, video_id, url, status)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (series_id, video_id) DO UPDATE
                        SET status = CASE
                            WHEN EXCLUDED.status = 'downloaded' THEN 'downloaded'
                            ELSE episodes.status
                        END
                        """,
                        (series_id, vid, clean_url, status),
                    )
                    synced_episodes += 1
        conn.commit()

    return {"series": synced_series, "episodes": synced_episodes}


def init_db() -> Dict[str, Any]:
    """Initialize database: create db if missing, run migrations, and sync existing records."""
    db_created = ensure_database_exists()
    init_schema()
    sync_stats = sync_existing_records()
    return {
        "db_created": db_created,
        "synced_series": sync_stats["series"],
        "synced_episodes": sync_stats["episodes"],
    }


# ==============================================================================
# Series Operations
# ==============================================================================

def create_series(name: str, save_dir: Optional[str] = None, description: str = "") -> Dict[str, Any]:
    """Register a new donghua series in PostgreSQL."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Series name cannot be empty.")

    key = sanitize_slug(clean_name)
    if not save_dir or not save_dir.strip():
        # Default save directory under ~/Videos/<SeriesName>
        sanitized_dir_name = re.sub(r"[^\w\s-]", "", clean_name).strip().replace(" ", "")
        save_dir = os.path.expanduser(f"~/Videos/{sanitized_dir_name}")
    else:
        save_dir = os.path.expanduser(save_dir.strip())

    os.makedirs(save_dir, exist_ok=True)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if key already exists, append number if duplicate key with different name
            cur.execute("SELECT id, name FROM series WHERE key = %s", (key,))
            existing = cur.fetchone()
            if existing:
                if existing["name"].lower() == clean_name.lower():
                    return existing
                # Key collision with different name: make key unique
                cur.execute("SELECT COUNT(*) FROM series WHERE key LIKE %s", (f"{key}%",))
                count = cur.fetchone()["count"]
                key = f"{key}_{count + 1}"

            cur.execute(
                """
                INSERT INTO series (key, name, save_dir, description)
                VALUES (%s, %s, %s, %s)
                RETURNING id, key, name, save_dir, description, created_at;
                """,
                (key, clean_name, save_dir, description),
            )
            created = cur.fetchone()
        conn.commit()
    return dict(created)


def get_all_series() -> List[Dict[str, Any]]:
    """Retrieve all series from PostgreSQL along with episode statistics."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    s.id,
                    s.key,
                    s.name,
                    s.save_dir,
                    s.description,
                    s.created_at,
                    COUNT(e.id) AS total_episodes,
                    COUNT(CASE WHEN e.status = 'downloaded' THEN 1 END) AS downloaded_episodes,
                    COUNT(CASE WHEN e.status != 'downloaded' THEN 1 END) AS pending_episodes
                FROM series s
                LEFT JOIN episodes e ON s.id = e.series_id
                GROUP BY s.id
                ORDER BY s.name ASC;
            """)
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def get_series(query: Any) -> Optional[Dict[str, Any]]:
    """Look up a series by integer ID, unique key, or exact/fuzzy title."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
                cur.execute(
                    """
                    SELECT s.*,
                           COUNT(e.id) AS total_episodes,
                           COUNT(CASE WHEN e.status = 'downloaded' THEN 1 END) AS downloaded_episodes,
                           COUNT(CASE WHEN e.status != 'downloaded' THEN 1 END) AS pending_episodes
                    FROM series s
                    LEFT JOIN episodes e ON s.id = e.series_id
                    WHERE s.id = %s
                    GROUP BY s.id;
                    """,
                    (int(query),),
                )
                row = cur.fetchone()
                return dict(row) if row else None

            q_str = str(query).strip().lower()
            cur.execute(
                """
                SELECT s.*,
                       COUNT(e.id) AS total_episodes,
                       COUNT(CASE WHEN e.status = 'downloaded' THEN 1 END) AS downloaded_episodes,
                       COUNT(CASE WHEN e.status != 'downloaded' THEN 1 END) AS pending_episodes
                FROM series s
                LEFT JOIN episodes e ON s.id = e.series_id
                WHERE LOWER(s.key) = %s OR LOWER(s.name) = %s
                GROUP BY s.id;
                """,
                (q_str, q_str),
            )
            row = cur.fetchone()
            if row:
                return dict(row)

            # Fuzzy match
            cur.execute(
                """
                SELECT s.*,
                       COUNT(e.id) AS total_episodes,
                       COUNT(CASE WHEN e.status = 'downloaded' THEN 1 END) AS downloaded_episodes,
                       COUNT(CASE WHEN e.status != 'downloaded' THEN 1 END) AS pending_episodes
                FROM series s
                LEFT JOIN episodes e ON s.id = e.series_id
                WHERE LOWER(s.name) LIKE %s OR LOWER(s.key) LIKE %s
                GROUP BY s.id
                ORDER BY s.name ASC
                LIMIT 1;
                """,
                (f"%{q_str}%", f"%{q_str}%"),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def update_series(series_id: int, name: Optional[str] = None, save_dir: Optional[str] = None, description: Optional[str] = None) -> bool:
    """Update name, destination directory, or description of a series."""
    updates = []
    params = []
    if name is not None and name.strip():
        updates.append("name = %s")
        params.append(name.strip())
    if save_dir is not None and save_dir.strip():
        exp = os.path.expanduser(save_dir.strip())
        os.makedirs(exp, exist_ok=True)
        updates.append("save_dir = %s")
        params.append(exp)
    if description is not None:
        updates.append("description = %s")
        params.append(description.strip())

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(series_id)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE series SET {', '.join(updates)} WHERE id = %s",
                params,
            )
        conn.commit()
    return True


def delete_series(series_id: int) -> bool:
    """Delete a series and its associated episode records."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM series WHERE id = %s", (series_id,))
        conn.commit()
    return True


# ==============================================================================
# Episode Operations
# ==============================================================================

def add_episode(
    series_id: int,
    url: str,
    title: str = "",
    episode_number: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Add a single episode URL to a series in PostgreSQL."""
    clean_url = url.strip()
    if not clean_url:
        return None
    vid = extract_video_id(clean_url)

    # Check series archive to set initial status
    series = get_series(series_id)
    initial_status = "pending"
    if series:
        arch_ids = get_archive_downloaded_ids(series["save_dir"])
        if vid in arch_ids:
            initial_status = "downloaded"

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO episodes (series_id, video_id, url, title, episode_number, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (series_id, video_id) DO UPDATE
                SET title = COALESCE(NULLIF(EXCLUDED.title, ''), episodes.title),
                    episode_number = COALESCE(EXCLUDED.episode_number, episodes.episode_number)
                RETURNING id, series_id, video_id, url, title, episode_number, status, created_at;
                """,
                (series_id, vid, clean_url, title, episode_number, initial_status),
            )
            ep = cur.fetchone()
        conn.commit()
    return dict(ep) if ep else None


def add_episodes_bulk(series_id: int, urls: List[str]) -> Dict[str, int]:
    """Add multiple URLs to a series, ignoring duplicates."""
    series = get_series(series_id)
    if not series:
        raise ValueError(f"Series ID {series_id} not found.")

    arch_ids = get_archive_downloaded_ids(series["save_dir"])

    added = 0
    skipped = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            for u in urls:
                clean_url = u.strip()
                if not clean_url or clean_url.startswith("#"):
                    continue
                vid = extract_video_id(clean_url)
                status = "downloaded" if vid in arch_ids else "pending"

                cur.execute(
                    """
                    INSERT INTO episodes (series_id, video_id, url, status)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (series_id, video_id) DO NOTHING
                    RETURNING id;
                    """,
                    (series_id, vid, clean_url, status),
                )
                res = cur.fetchone()
                if res:
                    added += 1
                else:
                    skipped += 1
        conn.commit()

    return {"added": added, "skipped": skipped, "total": added + skipped}


def get_episodes(series_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all episodes for a series, optionally filtered by status ('pending' or 'downloaded')."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if status:
                cur.execute(
                    """
                    SELECT * FROM episodes
                    WHERE series_id = %s AND status = %s
                    ORDER BY id ASC;
                    """,
                    (series_id, status),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM episodes
                    WHERE series_id = %s
                    ORDER BY id ASC;
                    """,
                    (series_id,),
                )
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def mark_episode_status(series_id: int, video_id: str, status: str) -> bool:
    """Update status ('downloaded' or 'failed') for an episode."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if status == "downloaded":
                cur.execute(
                    """
                    UPDATE episodes
                    SET status = 'downloaded', downloaded_at = CURRENT_TIMESTAMP
                    WHERE series_id = %s AND video_id = %s;
                    """,
                    (series_id, video_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE episodes
                    SET status = %s
                    WHERE series_id = %s AND video_id = %s;
                    """,
                    (status, series_id, video_id),
                )
        conn.commit()
    return True


def sync_series_with_archive(series_id: int) -> int:
    """Scan the series save_dir for downloaded.txt and update DB episode statuses."""
    series = get_series(series_id)
    if not series:
        return 0

    downloaded_ids = get_archive_downloaded_ids(series["save_dir"])
    if not downloaded_ids:
        return 0

    updated = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE episodes
                SET status = 'downloaded', downloaded_at = COALESCE(downloaded_at, CURRENT_TIMESTAMP)
                WHERE series_id = %s AND video_id = ANY(%s) AND status != 'downloaded';
                """,
                (series_id, list(downloaded_ids)),
            )
            updated = cur.rowcount
        conn.commit()
    return updated


def delete_episode(episode_id: int) -> bool:
    """Delete an episode record from PostgreSQL."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM episodes WHERE id = %s", (episode_id,))
        conn.commit()
    return True


def update_episode_fields(episode_id: int, title: Optional[str] = None,
                          episode_number: Optional[int] = None,
                          url: Optional[str] = None) -> bool:
    """Edit an episode's title, number, and/or URL (CRUD support for the GUI/CLI)."""
    updates, params = [], []
    if title is not None:
        updates.append("title = %s")
        params.append(title.strip())
    if episode_number is not None and episode_number > 0:
        updates.append("episode_number = %s")
        params.append(episode_number)
    if url is not None and url.strip():
        clean_url = url.strip()
        updates.append("url = %s")
        params.append(clean_url)
        updates.append("video_id = %s")
        params.append(extract_video_id(clean_url))
    if not updates:
        return False
    params.append(episode_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE episodes SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
    return True


def get_series_poster_ids() -> Dict[int, str]:
    """Return {series_id: first_episode_video_id} for library poster thumbnails."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.series_id, e.video_id FROM episodes e
                WHERE e.id = (SELECT MIN(e2.id) FROM episodes e2
                              WHERE e2.series_id = e.series_id);
            """)
            return {r[0]: r[1] for r in cur.fetchall()}


# ==============================================================================
# Settings Operations
# ==============================================================================

DEFAULT_SETTINGS = {
    "global_save_dir": os.path.expanduser("~/Videos"),
    "default_quality": "720p",
    "browser_cookies": "brave",
    "max_retries": "3",
    "default_container": "mp4",
    "sub_langs": "en",
    "rate_limit_mb": "0",
}


def get_setting(key: str, default: Optional[str] = None) -> str:
    """Retrieve an application setting from PostgreSQL or default."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
            row = cur.fetchone()
            if row:
                return row[0]
    return default if default is not None else DEFAULT_SETTINGS.get(key, "")


def set_setting(key: str, value: str) -> bool:
    """Save or update an application setting in PostgreSQL."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP;
                """,
                (key, str(value)),
            )
        conn.commit()
    return True


def get_all_settings() -> Dict[str, str]:
    """Retrieve all application settings as a dictionary."""
    result = dict(DEFAULT_SETTINGS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM app_settings;")
            for k, v in cur.fetchall():
                result[k] = v
    return result


def get_db_stats() -> Dict[str, int]:
    """Return high-level summary counts for the entire database."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM series) AS total_series,
                    (SELECT COUNT(*) FROM episodes) AS total_episodes,
                    (SELECT COUNT(*) FROM episodes WHERE status = 'downloaded') AS total_downloaded,
                    (SELECT COUNT(*) FROM episodes WHERE status != 'downloaded') AS total_pending;
            """)
            row = cur.fetchone()
            return dict(row) if row else {
                "total_series": 0,
                "total_episodes": 0,
                "total_downloaded": 0,
                "total_pending": 0,
            }
