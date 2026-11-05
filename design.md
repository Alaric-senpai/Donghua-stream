# Donghua Stream UI/UX Specification & Design System
> **Prompt & Design Specification for Google Stitch**  
> **Application:** Donghua & YouTube Desktop Video Downloader & Streaming Hub  
> **Theme Philosophy:** Cinematic TV Streaming Platform (Plex / Stremio / Netflix / Apple TV Desktop)  
> **Color Identity:** Deep Slate Dark Mode (`slate-900` / `slate-800`) with vibrant Cyan (`#38bdf8`), Emerald (`#10b981`), and Amber (`#f59e0b`) accents.

---

## 1. Executive Design Prompt for Google Stitch

```text
Create a modern, high-fidelity desktop TV streaming-style application interface for "Donghua Stream" — an anime/donghua video downloader and media library manager. 

The aesthetic is ultra-clean, cinematic dark mode utilizing Tailwind CSS slate color palettes (bg-slate-950 and bg-slate-900 base, bg-slate-800/80 cards and panels, border-slate-700/60 hairline dividers, and text-slate-100/text-slate-400 typography). Subtle glassmorphism (backdrop-blur-md) is applied to sticky headers, modals, and navigation bars.

The design must feel like a premium entertainment streaming app (Netflix/Stremio/Apple TV) rather than a utilitarian downloader. It includes rich poster artwork cards, episode progress bars, quality badge tags (1080p, 720p, 480p, 360p), quick directory selectors (Videos, Downloads, Documents), a step-by-step interactive series registration wizard, detailed episode management tables with CRUD actions, and an active downloading dashboard with live telemetry (speed, ETA, percentage).
```

---

## 2. Design Tokens & Styling Architecture

### 2.1 Color Palette (Tailwind CSS Slate System)

| Token Name | Hex Code | Tailwind Utility | Purpose / Application |
|---|---|---|---|
| **App Background** | `#020617` | `bg-slate-950` | Root background for window & canvas |
| **Surface Deep** | `#0f172a` | `bg-slate-900` | Sidebar, navigation rails, and modal backdrops |
| **Surface Card** | `#1e293b` | `bg-slate-800` | Card bodies, table rows, input containers |
| **Surface Hover** | `#334155` | `bg-slate-700` | Interactive card hover, button secondary states |
| **Hairline Borders** | `#334155` (40%) | `border-slate-700/40` | Subtle structural dividers and card outlines |
| **Primary Accent** | `#38bdf8` | `text-sky-400`, `bg-sky-500` | Primary buttons, active tabs, focus glow |
| **Primary Glow** | `rgba(56, 189, 248, 0.25)` | `shadow-sky-500/20` | Ambient glow on active media elements |
| **Success (Complete)**| `#10b981` | `text-emerald-400`, `bg-emerald-500` | 100% Downloaded badge, verified checkmarks |
| **Warning (Pending)** | `#f59e0b` | `text-amber-400`, `bg-amber-500` | Pending downloads, queued episodes badge |
| **Danger (Failed)** | `#f43f5e` | `text-rose-400`, `bg-rose-500` | Failed attempts, delete actions, alerts |
| **Text Primary** | `#f8fafc` | `text-slate-50` | Donghua titles, hero headlines, modal headers |
| **Text Secondary** | `#94a3b8` | `text-slate-400` | Episode metadata, sub-labels, paths |
| **Text Muted** | `#64748b` | `text-slate-500` | Placeholders, inactive state icons |

### 2.2 Typography & Iconography
- **Font Family:** `Inter`, `system-ui`, `-apple-system`, `sans-serif`
- **Headlines:** Semi-bold to Extra-bold (`font-bold`, `tracking-tight`)
- **Metadata & Badges:** Monospace / uppercase condensed (`font-mono`, `text-xs`, `tracking-wider`)
- **Icon Set:** Lucide Icons / Heroicons (feather stroke `1.75px` or `2px`)

---

## 3. Global Information Architecture & Navigation

The desktop application is built around a fixed **Left Navigation Rail (Sidebar)** and a **Dynamic Main Canvas**:

```
+----------------------------------------------------------------------------------------------------+
|  [DONGHUA STREAM]                   Top Bar: Global Search | Quality Preset | DB Status: Online    |
+-------------------+--------------------------------------------------------------------------------+
|  NAVIGATION       |  MAIN VIEW CANVAS                                                              |
|  * 🏠 Home        |                                                                                |
|  * 📺 Library     |  [Screen 1: Hero Banner & Streaming Media Grid]                                |
|  * 📥 Downloads   |  [Screen 2: Series Detail & Episode Manager]                                   |
|  * 🆕 Add Donghua |  [Screen 3: Step-by-Step Registration Wizard]                                  |
|  * ⚙️ Settings    |  [Screen 4: Active Downloads Telemetry Center]                                 |
|                   |  [Screen 5: Global & Per-Donghua Storage Settings]                             |
+-------------------+--------------------------------------------------------------------------------+
|  DB: Connected    |  Footer Status: Storage used | 13 Series | 40/131 Episodes Downloaded          |
+-------------------+--------------------------------------------------------------------------------+
```

---

## 4. Screen-by-Screen Detailed Specifications

### Screen 1: Home & Media Library Grid (Streaming Catalog)

#### Purpose
Primary landing view presenting registered Donghua in a Netflix/Apple TV style card grid with hero spotlight banner and instant filters.

#### UI Layout & Components
1. **Hero Spotlight Carousel / Banner (Top 260px)**:
   - High-contrast gradient backdrop (`from-slate-900 via-slate-900/80 to-transparent`).
   - Title: e.g. **"Throne of Seal"** (Bold 32px, white).
   - Metadata pills: `1080p Full HD` • `15 Episodes` • `9 Pending` • `~/Videos/ThroneOfSeal`.
   - Action buttons:
     - `▶ Download Pending (9 Videos)` (Cyan button with play icon).
     - `ℹ More Details` (Slate-800 translucent button).
2. **Filter & Search Bar**:
   - Search input: Real-time search by Donghua title or YouTube URL.
   - Filter Tabs:
     - `All Series (13)`
     - `Pending Episodes (4)`
     - `Completed (9)`
   - Sort dropdown: `Recently Added`, `Title (A-Z)`, `Pending Count`.
3. **Donghua Card Grid (4 to 5 cards per row)**:
   - Card structure:
     - **Artwork / Poster Thumbnail**: 16:9 or 3:4 aspect ratio with gradient placeholder or high-res thumbnail.
     - **Overlay Badges**:
       - Top Right: Status tag (`[9 Pending]` in amber or `[Complete]` in emerald).
       - Bottom Right: Resolution tag (`1080p` / `720p`).
     - **Card Content**:
       - Title (e.g., *Jade Dynasty*).
       - Progress Bar: Dual-tone bar showing percentage of downloaded episodes (e.g. `6 / 15` downloaded = 40% filled).
       - Sub-caption: Save directory shortcut (`~/Downloads/JadeDynasty`).
     - **Quick Hover Actions**:
       - Instant "Download Next" button.
       - "Open Folder" icon button.

---

### Screen 2: Donghua Detail & Episode Manager View

#### Purpose
Deep-dive page for an individual Donghua series. Displays series overview, bulk actions, and an interactive episode table with complete CRUD capabilities.

#### UI Layout & Components
1. **Series Header Hero**:
   - Breadcrumb: `Library > Throne of Seal`.
   - Large Donghua Title with edit pencil icon.
   - Description block & tag list (`Cultivation`, `3D Donghua`, `Action`).
   - Save Path Pill: Clickable path indicator `📁 ~/Videos/ThroneOfSeal` with an `[Open in File Manager]` button.
   - Bulk Action Toolbar:
     - Quality Selector Dropdown: `[ 1080p (Full HD) ▼ ]` (options: `1080p`, `720p`, `480p`, `360p`, `Best`).
     - `[ ▶ Download All Pending ]` (Primary Cyan).
     - `[ ⚡ Re-download / Verify All ]` (Secondary Slate).
     - `[ ➕ Add Episode URLs ]` (Launches slide-over drawer).
     - `[ 🔄 Sync with Disk ]` (Scans `downloaded.txt`).
     - `[ 🗑️ Delete Series ]` (Ghost danger button).
2. **Episode Management Table / List (CRUD Support)**:
   - Headers: `#`, `Episode / Title`, `Video ID`, `Resolution`, `Status`, `Download Date`, `Actions`.
   - Rows:
     - Status Icons:
       - Green Checkmark for `Downloaded`.
       - Amber Clock for `Pending`.
       - Blue Pulsing Spinner for `Downloading`.
       - Red Warning for `Failed`.
     - Direct URL: Clickable YouTube link with copy-to-clipboard button.
     - Interactive Row Actions:
       - `[ 📥 Download ]` (Single episode download trigger).
       - `[ ✏️ Rename Title / Ep # ]`.
       - `[ 📋 Copy Link ]`.
       - `[ 🗑️ Delete Episode ]` (Prompts instant confirmation with undo toast).

---

### Screen 3: Step-by-Step Donghua Registration Wizard

#### Purpose
A structured 3-step wizard that allows users to register a new Donghua and immediately associate episode URLs without writing code or editing files.

#### Step 1: Donghua Profile
- **Input: Donghua Title**: Text input with real-time slug preview (e.g. Typing `"Battle Through the Heavens"` shows key: `battle_through_the_heavens`).
- **Input: Alternative / English Title** (Optional).
- **Textarea: Description / Synopsis**.
- **Action:** `[ Next: Storage Location → ]`.

#### Step 2: Storage Destination (Global & Per-Donghua Preset Selector)
- **Primary Prompt:** *"Where would you like to store the video files for this Donghua?"*
- **Quick Preset Selector Cards (1-Click selection)**:
  - `[ 📁 Videos: ~/Videos/<Title> ]` (Default recommended).
  - `[ 📥 Downloads: ~/Downloads/<Title> ]`.
  - `[ 📄 Documents: ~/Documents/<Title> ]`.
  - `[ 💽 Custom Directory: [ Browse Folder... ] ]`.
- **Custom Path Input**: Auto-fills from presets, editable at any moment.
- **Directory Validation Pill**: Shows `✔ Folder will be created automatically` with disk free space indicator (`182 GB available`).
- **Action:** `[ ← Back ]` | `[ Next: Add Episode URLs → ]`.

#### Step 3: Interactive Episode URL Addition
- **Mode Toggle:** `[ Step-by-Step Mode ]` vs `[ Bulk Paste Mode ]`.
  - *Step-by-Step Mode*:
    - Input: `Paste YouTube URL`.
    - Input: `Optional Episode Title / Ep #`.
    - Button: `[ + Add to Queue ]`.
    - Real-time preview list of added episodes with delete buttons.
  - *Bulk Paste Mode*:
    - Large multi-line textarea with placeholder:
      ```
      https://www.youtube.com/watch?v=episode1
      https://www.youtube.com/watch?v=episode2
      https://youtu.be/episode3
      ```
    - Live parser badge: Shows `12 valid YouTube URLs detected • 0 duplicates`.
- **Final Actions**:
  - `[ Save Donghua & Download Immediately ]` (Primary Cyan).
  - `[ Save to Library Only ]` (Secondary Slate).

---

### Screen 4: Active Downloads Telemetry Center

#### Purpose
Dedicated dashboard showing real-time downloading activity, active connections, network speed, ETA, and execution logs.

#### UI Layout & Components
1. **Active Task Card**:
   - Title: `Downloading: Throne of Seal — Episode 145`.
   - Quality Tag: `1080p • MP4 (H.264 + AAC)`.
   - Live Progress Bar: Animated gradient fill (`sky-500` to `indigo-500`) with percentage label (`68.4%`).
   - Telemetry Grid (3 columns):
     - **Speed:** `5.8 MB/s`.
     - **Downloaded / Size:** `342.1 MB / 500.2 MB`.
     - **ETA:** `00:27 remaining`.
   - Control Buttons: `[ ⏸ Pause ]` • `[ ⏹ Cancel ]`.
2. **Download Queue Table**:
   - List of upcoming queued videos across all series.
   - Drag handle to reorder queue priority.
3. **Embedded Diagnostics / Log Console (Collapsible)**:
   - Monospace terminal log window with color-coded yt-dlp outputs (`[download]`, `[ffmpeg]`, `[archive]`).

---

### Screen 5: Settings & Storage Preferences

#### Purpose
Configuration panel for global storage presets, video quality defaults, network limits, and browser cookie management.

#### UI Layout & Components
1. **Global Storage Defaults**:
   - Default primary save directory for newly added Donghua:
     - Radio group: `~/Videos` (Recommended) | `~/Downloads` | `~/Documents` | `Custom`.
   - Option: `Auto-create subfolder named after series title` (Toggle Switch: ON).
2. **Quality & Format Defaults**:
   - Default Resolution: `[ 1080p Full HD ▼ ]` (Options: `1080p`, `720p`, `480p`, `360p`, `Best Available`).
   - Merge Output Format: `[ MP4 (Maximum Compatibility) ▼ ]`.
   - Subtitle Language: `[ English ('en') ▼ ]` • Automatic captions toggle.
3. **Browser Cookie Integration**:
   - Select browser: `[ Brave ▼ ]` (`Brave`, `Chrome`, `Firefox`, `Edge`, `Disabled`).
   - Status: `✔ Cookies active (allows member-only and restricted video extraction)`.
4. **PostgreSQL Database Connection**:
   - Status Pill: `● Connected to PostgreSQL (donghua_db) as user charles`.
   - Host: `localhost:5432` | DB: `donghua_db`.
   - `[ Force Re-Sync with urls.py ]` button.

---

## 5. Micro-Interactions & State Transitions

- **Card Hover:** Subtle scale (`scale-[1.02]`), border transition from `border-slate-700/60` to `border-sky-500/50`, elevation shadow.
- **Download Click:** Immediate status transition to `Queued` with animated pulse indicator.
- **Folder Click:** Native Linux file manager (`xdg-open` / Nautilus) opens the exact folder.
- **Copy Link:** Toast notification slides up from bottom-right (`"YouTube URL copied to clipboard"`).
- **Deletion:** Modal dialogue with slate-900 blurred backdrop: *"Are you sure you want to remove this URL?"* with `[Cancel]` and `[Delete]`.

---

## 6. Google Stitch Ready Prompt Snippet

```markdown
Generate the HTML / Tailwind CSS markup and UI components for the "Donghua Stream" desktop application following this specification:
- Background: bg-slate-950 with slate-900 sidebar and slate-800 cards.
- Layout: 250px fixed left sidebar with streaming logo and navigation items, fluid right content area.
- Top section: Featured Hero card with dark gradient overlay, 1080p badge, and download action button.
- Main section: Grid of Donghua series cards with poster thumbnails, title, dual-tone progress bars (e.g. 6/15 episodes), and quality tags.
- Include the "Add Donghua" 3-step modal with storage quick presets (Videos, Downloads, Documents) and bulk URL input.
- Include the Episode Management Table with interactive CRUD buttons (download, copy link, delete) and status badges (complete, pending, downloading).
```
