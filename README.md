# Donghua Stream

A donghua / YouTube downloader with two front-ends:

- **`donghua`** — the original rich interactive CLI (backed by PostgreSQL)
- **`donghua-gui`** — a TV-streaming-style PyQt6 desktop app built on the
  Stitch "donghua stream" design system (canvas `#020617`, rail `#0f172a`,
  cards `#1e293b`, primary `#38bdf8`)

Both share the same engine (`downloader.py`), database layer (`db.py`),
episode catalog (`urls.py`) and one user-owned config file
(`~/.config/donghua-stream/config.json`). The GUI does not replace the CLI.

---

## Configuration

Everything that survives a restart lives in one JSON file:

```text
~/.config/donghua-stream/config.json
```

The folder is created with `0700` and the file with `0600` permissions on
first launch. Credentials are **not** read from environment variables and no
values are hard-coded in the source tree. The file is the single source of
truth for both front-ends.

On first run, the GUI and CLI prompt for any missing values and write them
straight to the config file using an atomic replace. You can also edit the
file while the apps are closed, or use **Settings → Database & Daemon /
YouTube Data API** in the GUI.

```json
{
  "version": 2,
  "database": {
    "host": "localhost",
    "port": 5432,
    "user": "your-postgres-user",
    "password": "your-postgres-password",
    "dbname": "donghua_db"
  },
  "youtube": {
    "api_key": "YOUR_YOUTUBE_DATA_API_V3_KEY",
    "region_code": "US",
    "language": "en",
    "safe_search": "moderate"
  },
  "settings": {
    "global_save_dir": "~/Videos",
    "default_quality": "720p",
    "browser_cookies": "none",
    "max_retries": "3",
    "default_container": "mp4",
    "sub_langs": "en",
    "rate_limit_mb": "0",
    "per_series_subfolder": "1"
  },
  "explore": {
    "curated_query": "donghua english sub",
    "curated_order": "viewCount",
    "trending_category": "1",
    "result_limit": 18,
    "cache_minutes": 20
  },
  "meta": {
    "legacy_settings_imported": false
  }
}
```

Existing installs import the old PostgreSQL `app_settings` rows once. After
that, config values win, so edits are never silently overwritten.

### YouTube Data API key

1. Open the [Google Cloud console](https://console.cloud.google.com/) and
   create (or select) a project.
2. Enable **YouTube Data API v3** for that project.
3. Create an **API key** under *APIs & Services → Credentials*.
4. Save it in the GUI (**Settings → YouTube Data API → Edit**) or in the CLI
   settings menu; both write to the shared config file.

Explore is deliberately quota-friendly: the discovery view uses one
`videos.list` trending call (1 unit) plus one curated `search.list` call
(100 units). Results are cached on disk for `explore.cache_minutes`
(20 minutes by default), so reopening the page or repeating a search does
not spend more quota.

---

## Install

```bash
./install.sh
```

The installer:

1. creates/refreshes `./venv`,
2. installs the project in editable mode (`pip install -e .`),
3. symlinks `donghua`, `donghua-cli`, `donghua-gui` into `~/.local/bin`,
4. writes `~/.local/share/applications/donghua-stream.desktop` (menu entry),
5. verifies imports, CLI and GUI entry points.

Requirements: Python 3.9+, PostgreSQL, and `yt-dlp` (installed as a
dependency). Database credentials are entered on first launch rather than
configured in source.

### Launch

```bash
donghua            # interactive CLI (unchanged)
donghua --gui      # same desktop app as below
donghua-gui        # desktop app
```

or click **Donghua Stream** in the application menu.

---

## Desktop app

| Page | What it does |
| --- | --- |
| **Home** | Hero spotlight, daemon-sync strip, filter tabs with count chips, poster grid / list switcher, hover quick actions |
| **Explore** | YouTube Data API v3 discovery: trending animation plus a curated donghua rail, live search, and one-click **Add** / **Add & Download** into an existing or brand-new series |
| **Library** | Compact registry of every series with ready/pending chips and disk usage |
| **Series Detail** | `N EPS` chip, sync-progress card, storage folder, quality selector, episode registry tabs (All / Downloaded / Queued / Failed) with download, copy, edit, delete and retry per row |
| **Add Donghua** | Three-step wizard: identity → storage tiles with live free-space chips → bulk episode paste (`URL  # Episode title`) with duplicate detection, then *Save to Library* or *Save & Download Immediately* |
| **Downloads** | Now-playing telemetry (rate, peak, transferred, ETA), priority queue with reordering, Pause All / Resume All / Stop Current / Clear Finished, colorized yt-dlp terminal |
| **Settings** | Storage presets, quality/container, retries + rate limit, cookie browser, database/daemon info, YouTube API key, config path, Test Connection, Force Re-Sync, Reset to Defaults |

Downloading is sequential (one active task) and cancellable; per-episode
status is reconciled against each series' `downloaded.txt` archive.

---

## Package layout

```
app_config.py             # central JSON config (credentials + settings + explore)
youtube_api.py            # YouTube Data API v3 client (urllib, disk cache)
gui/                      # desktop app package (single entry point: gui.main)
├── __init__.py           #   exports main, MainWindow
├── __main__.py           #   python -m gui
├── app.py                #   QApplication bootstrap (the entry point)
├── window.py             #   MainWindow — composition root
├── theme.py              #   design tokens + global QSS
├── utils.py              #   UI-free helpers (sizes, paths, URL parsing, settings)
├── components/           #   reusable sections
│   ├── primitives.py     #     chips, labels, buttons, bars, shadows
│   ├── sidebar.py        #     250px navigation rail
│   ├── header_bar.py     #     search, quality selector, status chips
│   ├── hero.py           #     cinematic spotlight
│   ├── telemetry.py      #     daemon-sync strip
│   ├── poster.py         #     16:10 poster tile
│   ├── poster_grid.py    #     wrapping catalog grid
│   ├── video_card.py     #     Explore 16:9 YouTube card
│   ├── series_cards.py   #     grid card + compact registry row
│   ├── storage_card.py   #     storage preset tile
│   ├── episode_row.py    #     episode registry row
│   ├── queue_row.py      #     priority-queue row
│   └── toast.py          #     bottom-right notifications
├── infrastructure/       #   adapters to the outside world
│   ├── download_queue.py #     yt-dlp worker + sequential queue
│   ├── thumbnails.py     #     async poster/remote thumbnail fetcher (disk cache)
│   ├── size_scanner.py   #     background disk-usage scan
│   └── db_worker.py      #     Postgres calls off the UI thread
├── pages/                #   one module per page
│   ├── home.py
│   ├── explore.py        #     YouTube discovery rails + search
│   ├── library.py
│   ├── detail.py
│   ├── downloads.py
│   └── settings.py
└── dialogs/              #   modal workflows
    ├── wizard.py         #     Add Donghua wizard
    ├── add_video.py      #     Explore → add to existing/new series
    ├── credentials.py    #     first-run / settings credential prompt
    ├── add_urls.py       #     bulk import drawer
    └── quick_url.py      #     single-URL quick add
```

CLI-side modules remain flat for backward compatibility:
`script.py`, `db.py`, `downloader.py`, `urls.py`.

`app_config.py` has no dependency on PostgreSQL or PyQt6, so both front-ends
and the storage layer can import it without circular imports.

### Adding a page

1. Create `gui/pages/<name>.py` exposing a `QWidget` subclass with
   `pyqtSignal`s for the actions the window should handle.
2. Register it in `gui/window.py` (`QStackedWidget` + `_page_by_key`).
3. Add the navigation item in `gui/components/sidebar.py`.
4. Reuse `components/primitives.py` and `theme.py` tokens — no raw colors.

---

## CLI quick reference

```bash
donghua --list                     # show series table
donghua --series "Throne of Seal"  # download all pending episodes
donghua --url URL --series NAME    # register + download one URL
donghua --all                      # download every pending episode
donghua --sync                     # reconcile DB with urls.py + disk
donghua --gui                      # open the desktop app
```

---

## Development

```bash
./venv/bin/python -m compileall -q .
./venv/bin/python -m pyflakes app_config.py youtube_api.py gui/ tests/
QT_QPA_PLATFORM=offscreen ./venv/bin/python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen ./venv/bin/python -m gui   # headless smoke run
```

The test suite covers the config file, YouTube response parsing/caching and
the offscreen Explore UI. A live smoke test needs a saved API key:

```bash
./venv/bin/python - <<'PY'
import youtube_api
for rail in youtube_api.discover(refresh=True)["rails"]:
    print(rail["title"], len(rail["items"]))
PY
```

Caches live in `~/.cache/donghua-stream/` (`youtube/` for API payloads,
`remote/` for Explore thumbnails). Delete those folders, or use
**Refresh** in Explore, to force a fresh fetch.

The design reference lives in `design.md`; the Stitch project is
`projects/7589936649701923770` ("donghua stream").
