# Donghua Stream

A donghua / YouTube downloader with two front-ends:

- **`donghua`** — the original rich interactive CLI (backed by PostgreSQL)
- **`donghua-gui`** — a TV-streaming-style PyQt6 desktop app built on the
  Stitch "donghua stream" design system (canvas `#020617`, rail `#0f172a`,
  cards `#1e293b`, primary `#38bdf8`)

Both share the same engine (`downloader.py`), database layer (`db.py`) and
episode catalog (`urls.py`). The GUI does not replace the CLI.

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

Requirements: Python 3.9+, PostgreSQL reachable via `db.DB_CONFIG`, and
`yt-dlp` (installed as a dependency).

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
| **Library** | Compact registry of every series with ready/pending chips and disk usage |
| **Series Detail** | `N EPS` chip, sync-progress card, storage folder, quality selector, episode registry tabs (All / Downloaded / Queued / Failed) with download, copy, edit, delete and retry per row |
| **Add Donghua** | Three-step wizard: identity → storage tiles with live free-space chips → bulk episode paste (`URL  # Episode title`) with duplicate detection, then *Save to Library* or *Save & Download Immediately* |
| **Downloads** | Now-playing telemetry (rate, peak, transferred, ETA), priority queue with reordering, Pause All / Resume All / Stop Current / Clear Finished, colorized yt-dlp terminal |
| **Settings** | Storage presets, quality/container, retries + rate limit, cookie browser, database/daemon info, Test Connection, Force Re-Sync, Reset to Defaults |

Downloading is sequential (one active task) and cancellable; per-episode
status is reconciled against each series' `downloaded.txt` archive.

---

## Package layout

```
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
│   ├── series_cards.py   #     grid card + compact registry row
│   ├── storage_card.py   #     storage preset tile
│   ├── episode_row.py    #     episode registry row
│   ├── queue_row.py      #     priority-queue row
│   └── toast.py          #     bottom-right notifications
├── infrastructure/       #   adapters to the outside world
│   ├── download_queue.py #     yt-dlp worker + sequential queue
│   ├── thumbnails.py     #     async poster fetcher (disk cache)
│   ├── size_scanner.py   #     background disk-usage scan
│   └── db_worker.py      #     Postgres calls off the UI thread
├── pages/                #   one module per page
│   ├── home.py
│   ├── library.py
│   ├── detail.py
│   ├── downloads.py
│   └── settings.py
└── dialogs/              #   modal workflows
    ├── wizard.py         #     Add Donghua wizard
    ├── add_urls.py       #     bulk import drawer
    └── quick_url.py      #     single-URL quick add
```

CLI-side modules remain flat for backward compatibility:
`script.py`, `db.py`, `downloader.py`, `urls.py`.

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
./venv/bin/python -m compileall -q gui
./venv/bin/python -m pyflakes gui/
QT_QPA_PLATFORM=offscreen ./venv/bin/python -m gui   # headless smoke run
```

The design reference lives in `design.md`; the Stitch project is
`projects/7589936649701923770` ("donghua stream").
