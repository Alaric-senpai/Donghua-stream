# Source Explore & Detail Views — Design

## Context

Explore currently conflates YouTube and non-YouTube sources into one view. YouTube search is video-based and stays as-is. AnimeCube and DonghuaStream are series-catalog sites and need a richer, standalone experience.

## What exists

- `ExploreView` — unified search page with a source-combo selector. Non-YouTube searches return series cards but the "add to library" flow just opens `SourceEpisodesDialog`.
- `SeriesDetailView` — the library's series detail page; pulls episodes from PostgreSQL, not from a source site.
- `gui/components/poster.py` — `PosterWidget`: 16:10 artwork tile with hover actions and a badge.
- `gui/components/poster_grid.py` — `PosterGrid`: responsive wrapping grid of `PosterWidget` tiles.
- `gui/components/series_cards.py` — `SeriesCard`: the label beneath the poster used in library/home rails.
- `sources.py` — has `AnimeCubeSource.search()` (catalog search) and `.details()` (episodes). DonghuaStream has the same.

## What is missing

- No default "browse trending" state for non-YouTube sources — Explore jumps straight to the search prompt.
- No source-specific detail page — AnimeCube/DonghuaStream series open `SourceEpisodesDialog` which is a quick picker, not a proper detail view.
- No recommendations/related section from source sites in any GUI view.
- Source-specific posters and metadata (rating, genres, status, year) are not surfaced in the Explore grid.

---

## Design

### `SourceExploreView` (`gui/pages/source_explore.py`)

Replaces the inline search/grid flow for AnimeCube and DonghuaStream.

**Layout (top to bottom):**
1. **Source header** — eyebrow chip (`ANIMECUBE · EXPLORE`), source name, subtitle ("Browse the public catalog. No account required."), API-mode chip.
2. **Search row** — source combo (locked to current source, greyed out), `QLineEdit` with source-specific placeholder (`"Search AnimeCube for a donghua series…"`), Search button.
3. **Content area** (switches between two states):
   - **_idle / trending_**: `PosterGrid` of top-rated series from the source's catalog (sorted by `rating` desc, 24 items). Each tile is a `SeriesCard`. Eyebrow: `"TRENDING · {count} SERIES"`. Tapping a card navigates to `SourceDetailView`.
   - **_search results_**: `PosterGrid` of search results (same card type). Eyebrow: `"RESULTS FOR "{query}""`. Tapping navigates to detail.

**Cards (`SeriesCard`):** The existing `SeriesCard` (poster + title + meta). Hover actions include:
- **+ Add** → opens `SourceDetailView` (same as clicking the card)
- No download action in the explore grid (that's a detail-view action)

**Navigation signals:**
- `series_selected[str, Dict]` — emitted with `(source_key, series_dict)` when a card is clicked. Window handles navigation to detail view.
- `connect_requested` — only for YouTube; non-YouTube sources have no credentials flow.

**Loading/empty/error states** identical to `ExploreView`'s patterns.

---

### `SourceDetailView` (`gui/pages/source_detail.py`)

Full series detail page for a source series. Mirrors `SeriesDetailView`'s layout language but reads from `sources.py` instead of PostgreSQL.

**Layout (top to bottom):**

1. **Series hero card** (`<div class="info">` equivalent):
   - Left: `PosterThumb` (232×145, 12px radius, same as library detail)
   - Right: chip row (status badge, `{N} EPS`, quality badge), title (titleXl), sub-line (source URL · year · genres), synopsis (body, word-wrap, max 3 lines expandable), path note ("Source: animecube.live")
   - Action buttons: **Add Full Series** (primary), **Add Selected** (ghost), **Download Selected** (ghost, quality picker), **Open Source** (link button)

2. **Episode registry section** (same visual language as `SeriesDetailView`):
   - Header bar: `EPISODE REGISTRY` eyebrow + count, All/None/Latest action buttons, tab group (All / Queued / Downloaded / Failed — filtering local registration state), search filter
   - Scroll area with `EpisodeRow` list — shows episode number, title, status icon, action buttons (queue one, copy URL, delete)
   - Episodes are **pre-checked** by default; user picks a subset to register

3. **Recommendations rail** (new — drawn from source site's related data):
   - `HORIZONTAL SCROLL` with a row of `SeriesCard` tiles (compact, 180×112 poster)
   - Eyebrow: `"RECOMMENDED · {source}"`
   - Loaded lazily when the detail view opens; a separate network call
   - Tapping a recommendation opens its `SourceDetailView`

4. **"Record to Library" actions:**
   - **Add Full Series** — registers ALL episodes to an existing or new library series
   - **Add Selected** — registers only checked episodes
   - Both open `SourceEpisodesDialog` (reuse) for library-series targeting, then save via `db.add_episode_entries()`
   - **Download Selected** — immediately queues checked episodes after saving

**State:**
- Episodes with `status == "downloaded"` (matched against local archive) are pre-checked and shown with a green check
- Episodes already in the library are shown with a amber indicator

---

### Explore page changes (`gui/pages/explore.py`)

- When `source_key != "youtube"`, `_submit_search` **navigates to `SourceExploreView`** with the source key instead of running inline search
- The `SourceExploreView` is created once per source key and cached in `MainWindow`

---

### Window changes (`gui/window.py`)

- `self.source_explore_views: Dict[str, SourceExploreView]` — one per non-YouTube source
- `self.source_detail_view: SourceDetailView` — shared, reused for any source series
- `navigateTo("source_explore", key=source_key)` — shows the relevant explore view
- `navigateTo("source_detail", source=key, url=url)` — loads series details
- `series_selected` signal from explore → `navigateTo("source_detail", …)`
- `SourceDetailView.toast` → same as other views

---

### New signals

| Component | Signal | Payload |
|---|---|---|
| `SourceExploreView` | `series_selected` | `(source_key: str, series_data: Dict)` |
| `SourceDetailView` | `back_requested` | — |
| `SourceDetailView` | `toast` | `(message: str, success: bool)` |
| `SourceDetailView` | `add_to_library` | `(source_key, series_data, selected_episodes, download_now)` |

---

## Implementation order

1. `source_explore.py` — the view, cards, trending default, search navigation
2. `source_detail.py` — the detail page with episodes + recommendations
3. `window.py` — wire the views and navigation
4. `explore.py` — redirect non-YouTube to the new views
5. Tests for both new views
6. Install and review
