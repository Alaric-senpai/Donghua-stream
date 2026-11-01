#!/usr/bin/env python3
"""script.py - Interactive CLI & runner for YouTube Donghua and Video Downloader.

Features:
- PostgreSQL Storage Engine (username: charles, password: password, db: donghua_db)
- Register new Donghua series interactively without touching files
- Interactive Quality Selector (360p - 1080p, Best, Custom)
- Full Episode Management (Bulk URL add, status tracking, disk sync)
- Rich terminal tables, banners, and CLI argument support
"""

import argparse
import os
import sys
from typing import List, Optional, Dict, Any

# Third-party styling & interactive prompts
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
import questionary
from questionary import Choice, Style

# Database & Modularized components
import db
from db import (
    init_db,
    create_series,
    get_all_series as db_get_all_series,
    get_series as db_get_series,
    update_series,
    delete_series,
    add_episode,
    add_episodes_bulk,
    get_episodes,
    mark_episode_status,
    sync_series_with_archive,
    delete_episode,
    get_db_stats,
    extract_video_id,
)
import urls
from urls import (
    Series,
    # Re-exported for 100% backward compatibility
    swallowedStarUrls,
    spiritSwordUrls,
    slaytheGodsURL,
    demonsAndGodsURl,
    heaveenlyFatedVilliansUrls,
    jadDynastyUrls,
    coilingDragonUrls,
    worldOfImortalsUrls,
    soulLandUrls,
    herdingTheGods,
    throneOfSeal,
    seniorBrotherIsTooSteadyUrls,
    aWillEternalUrls,
    sbits,
    tossave,
    herdingTheGodsSaveLocation,
    svl,
    talessaveloc,
    heaveenlyFatedVilliansSavelocation,
    savelocation,
    jadeDynastySavelocation,
    coilingDragonSavelocation,
    imortalsSavelOcation,
    slaySaveLocale,
    spiritSwordSaveLocation,
    aWillEternalSaveLocation,
    DEFAULT_BROWSER,
)
import downloader
from downloader import (
    VideoDownloader,
    DownloadSummary,
    resolve_format_string,
    already_downloaded,
    download_urls,
)

console = Console()

# Custom Questionary styling for an elegant CLI feel
custom_style = Style([
    ("qmark", "fg:#00ffff bold"),
    ("question", "bold fg:#ffffff"),
    ("answer", "fg:#00ff88 bold"),
    ("pointer", "fg:#00ffff bold"),
    ("highlighted", "fg:#00ffff bold"),
    ("selected", "fg:#00ff88"),
    ("separator", "fg:#666666"),
    ("instruction", "fg:#888888 italic"),
])

# Global session preferences
SESSION_SETTINGS = {
    "quality": "720p",
    "browser": DEFAULT_BROWSER,
    "max_retries": 3,
}

DB_INITIALIZED = False


def ensure_db_ready(quiet: bool = False):
    """Ensure PostgreSQL database exists, schema is migrated, and records are synced."""
    global DB_INITIALIZED
    if DB_INITIALIZED:
        return
    try:
        res = init_db()
        DB_INITIALIZED = True
        if not quiet and res.get("db_created"):
            console.print("[bold green]✔ Created PostgreSQL database 'donghua_db'.[/bold green]")
    except Exception as exc:
        console.print(f"[bold red]⚠ PostgreSQL Connection Warning:[/bold red] {exc}")
        console.print("[dim]Falling back to file-based static catalog.[/dim]\n")


def print_banner():
    """Display an attractive header banner with live database status."""
    ensure_db_ready(quiet=True)
    db_status = "[bold red]Offline (Static fallback)[/bold red]"
    stats_str = ""
    try:
        stats = get_db_stats()
        db_status = f"[bold green]🐘 Connected (donghua_db)[/bold green]"
        stats_str = (
            f"[dim]• {stats['total_series']} Donghua  •  "
            f"{stats['total_episodes']} Episodes ({stats['total_downloaded']} downloaded, "
            f"{stats['total_pending']} pending)[/dim]"
        )
    except Exception:
        pass

    console.print(
        Panel.fit(
            f"[bold cyan]🎬 DONGHUA & YOUTUBE VIDEO DOWNLOADER[/bold cyan]\n"
            f"[dim]Interactive Quality Selector (360p - 1080p) • PostgreSQL Store[/dim]\n"
            f"{db_status}  {stats_str}",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )


def prompt_quality(current_quality: Optional[str] = None) -> str:
    """Interactive prompt for choosing video quality."""
    default_val = current_quality or SESSION_SETTINGS["quality"]
    choices = [
        Choice("1080p  [Full HD 1920x1080]", value="1080p"),
        Choice("720p   [HD 1280x720 - Recommended]", value="720p"),
        Choice("480p   [Standard Definition 854x480]", value="480p"),
        Choice("360p   [Low / Mobile 640x360]", value="360p"),
        Choice("Best   [Highest Available Resolution]", value="best"),
        Choice("Custom [Enter custom resolution height]", value="custom"),
    ]

    default_choice = next((c for c in choices if c.value == default_val), None)

    selected = questionary.select(
        "Select target video quality:",
        choices=choices,
        default=default_choice,
        style=custom_style,
    ).ask()

    if selected is None:
        return default_val

    if selected == "custom":
        custom_val = questionary.text(
            "Enter resolution height (e.g. 1080, 720, 480, 360, 1440, 2160):",
            validate=lambda v: (
                True if v.strip().isdigit() and int(v.strip()) > 0 else "Please enter a valid positive number."
            ),
            style=custom_style,
        ).ask()
        return f"{custom_val.strip()}p" if custom_val else "720p"

    return selected


def display_series_table():
    """Print a clean Rich table of all registered series and their download status."""
    ensure_db_ready(quiet=True)

    table = Table(
        title="📚 Registered Donghua & Status",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold magenta",
    )
    table.add_column("ID", justify="center", style="dim", width=4)
    table.add_column("Donghua Name", style="bold white", min_width=25)
    table.add_column("Key", style="dim cyan", min_width=16)
    table.add_column("Total", justify="right", style="cyan")
    table.add_column("Downloaded", justify="right", style="green")
    table.add_column("Pending", justify="right", style="yellow")
    table.add_column("Save Location", style="dim", min_width=30)

    total_all = 0
    downloaded_all = 0
    pending_all = 0

    series_data = []
    try:
        series_data = db_get_all_series()
    except Exception:
        pass

    if series_data:
        for s in series_data:
            t = s["total_episodes"]
            d = s["downloaded_episodes"]
            p = s["pending_episodes"]
            total_all += t
            downloaded_all += d
            pending_all += p

            status_pending = "[bold green]Complete[/bold green]" if p == 0 else f"[yellow]{p}[/yellow]"
            table.add_row(
                str(s["id"]),
                s["name"],
                s["key"],
                str(t),
                str(d),
                status_pending,
                s["save_dir"].replace(os.path.expanduser("~"), "~"),
            )
    else:
        # Fallback to static catalog
        for s in urls.get_all_series():
            stats = s.get_stats()
            total_all += stats["total"]
            downloaded_all += stats["downloaded"]
            pending_all += stats["pending"]
            status_pending = "[bold green]Complete[/bold green]" if stats["pending"] == 0 else f"[yellow]{stats['pending']}[/yellow]"
            table.add_row(
                "-",
                s.name,
                s.key,
                str(stats["total"]),
                str(stats["downloaded"]),
                status_pending,
                s.save_dir.replace(os.path.expanduser("~"), "~"),
            )

    table.add_section()
    table.add_row(
        "",
        "[bold]Grand Total[/bold]",
        f"[dim]{len(series_data or urls.get_all_series())} Donghua[/dim]",
        f"[bold cyan]{total_all}[/bold cyan]",
        f"[bold green]{downloaded_all}[/bold green]",
        f"[bold yellow]{pending_all}[/bold yellow]",
        "",
    )

    console.print(table)


def run_download_with_events(
    urls_list: List[str],
    save_dir: str,
    series_name: str,
    quality: str,
    series_id: Optional[int] = None,
    browser: Optional[str] = None,
    max_retries: int = 3,
) -> DownloadSummary:
    """Execute download with formatted interactive notifications and sync to PostgreSQL."""
    _, quality_label = resolve_format_string(quality)
    console.print(
        Panel(
            f"🚀 [bold cyan]Starting Download for:[/bold cyan] [bold white]{series_name}[/bold white]\n"
            f"🎯 [bold]Quality:[/bold] [bold yellow]{quality_label}[/bold yellow]  •  "
            f"📁 [bold]Destination:[/bold] [dim]{save_dir}[/dim]  •  "
            f"🔗 [bold]Count:[/bold] [bold green]{len(urls_list)}[/bold green] URLs",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )

    def on_event(event_name: str, data: dict):
        if event_name == "skip":
            console.print(f"[dim]⏭ [{data['index']}/{data['total']}] Already downloaded: {data['url']}[/dim]")
            if series_id:
                try:
                    vid = extract_video_id(data["url"])
                    mark_episode_status(series_id, vid, "downloaded")
                except Exception:
                    pass
        elif event_name == "attempt":
            console.print(
                f"\n[bold cyan]📥 [{data['index']}/{data['total']}][/bold cyan] Downloading: [cyan]{data['url']}[/cyan] "
                f"[dim](Attempt {data['attempt']}/{data['max_retries']} | Quality: {data['quality']})[/dim]"
            )
        elif event_name == "success":
            console.print(f"[bold green]✔ [{data['index']}/{data['total']}] Successfully downloaded![/bold green]")
            if series_id:
                try:
                    vid = extract_video_id(data["url"])
                    mark_episode_status(series_id, vid, "downloaded")
                except Exception:
                    pass
        elif event_name == "retry_error":
            console.print(f"[yellow]⚠ Attempt {data['attempt']}/{data['max_retries']} failed: {data['error']}[/yellow]")
        elif event_name == "failure":
            console.print(f"[bold red]✘ Failed after {max_retries} attempts: {data['url']}[/bold red]")
            if series_id:
                try:
                    vid = extract_video_id(data["url"])
                    mark_episode_status(series_id, vid, "failed")
                except Exception:
                    pass

    dl = VideoDownloader(
        quality=quality,
        max_retries=max_retries,
        browser=browser,
        on_event=on_event,
    )

    summary = dl.download_urls(urls_list, save_dir)

    console.print("\n" + "─" * 60)
    console.print(
        f"[bold cyan]Download Summary for {series_name}:[/bold cyan] "
        f"[bold green]{summary.success_count} completed[/bold green], "
        f"[dim]{summary.skipped_count} skipped[/dim], "
        f"[bold red]{summary.failed_count} failed[/bold red] "
        f"(Total: {summary.total})"
    )
    if summary.failed:
        console.print("[bold red]Failed URLs:[/bold red]")
        for item in summary.failed:
            console.print(f"  • {item['url']} - [dim]{item['error']}[/dim]")
    console.print("─" * 60 + "\n")

    return summary


# ==============================================================================
# Upgraded Interactive Menu Handlers
# ==============================================================================

def interactive_register_donghua():
    """Register a new Donghua in the PostgreSQL store without editing files."""
    ensure_db_ready()
    console.print(
        Panel(
            "[bold cyan]🆕 Register New Donghua Series[/bold cyan]\n"
            "[dim]Add a new donghua to your collection. The system creates the database record\n"
            "and folder automatically so you don't need to manually edit code files.[/dim]",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )

    name = questionary.text(
        "Enter Donghua Name (e.g. 'Battle Through the Heavens'):",
        validate=lambda v: True if v.strip() else "Donghua name cannot be empty.",
        style=custom_style,
    ).ask()

    if not name or not name.strip():
        return

    clean_name = name.strip()

    # Propose default save directory
    sanitized_dir_name = "".join(c for c in clean_name.title() if c.isalnum())
    default_dir = os.path.expanduser(f"~/Videos/{sanitized_dir_name}")

    save_dir = questionary.text(
        "Confirm or customize save destination folder:",
        default=default_dir,
        style=custom_style,
    ).ask()

    if not save_dir:
        save_dir = default_dir

    description = questionary.text(
        "Optional description / notes:",
        default="",
        style=custom_style,
    ).ask() or ""

    try:
        new_series = create_series(clean_name, save_dir=save_dir, description=description)
        console.print(
            Panel(
                f"[bold green]✔ Successfully Registered Donghua![/bold green]\n\n"
                f"• [bold]ID:[/bold] {new_series['id']}\n"
                f"• [bold]Name:[/bold] {new_series['name']}\n"
                f"• [bold]Key:[/bold] [cyan]{new_series['key']}[/cyan]\n"
                f"• [bold]Folder:[/bold] [dim]{new_series['save_dir']}[/dim]",
                border_style="green",
                box=box.ROUNDED,
            )
        )

        # Ask to immediately add episode URLs
        add_now = questionary.confirm(
            f"Would you like to add episode URLs for '{clean_name}' right now?",
            default=True,
            style=custom_style,
        ).ask()

        if add_now:
            interactive_add_urls_to_series(preselected_id=new_series["id"])

    except Exception as exc:
        console.print(f"[bold red]Failed to register Donghua:[/bold red] {exc}")


def interactive_add_urls_to_series(preselected_id: Optional[int] = None):
    """Add one or multiple YouTube URLs to a Donghua series in PostgreSQL."""
    ensure_db_ready()

    target_series = None
    if preselected_id:
        target_series = db_get_series(preselected_id)

    if not target_series:
        all_series = db_get_all_series()
        if not all_series:
            console.print("[yellow]No Donghua series found in the database. Please register one first![/yellow]")
            return

        choices = [
            Choice(f"{s['name']} (ID: {s['id']} | {s['total_episodes']} episodes)", value=s["id"])
            for s in all_series
        ]
        choices.append(Choice("← Back", value="__back__"))

        selected_id = questionary.select(
            "Select Donghua to add episode URLs to:",
            choices=choices,
            style=custom_style,
        ).ask()

        if not selected_id or selected_id == "__back__":
            return

        target_series = db_get_series(selected_id)

    if not target_series:
        console.print("[bold red]Donghua series not found.[/bold red]")
        return

    console.print(
        f"\n[cyan]Adding episode URLs for:[/cyan] [bold white]{target_series['name']}[/bold white]\n"
        "[dim]Paste YouTube URL(s). Multiple URLs can be separated by spaces, commas, or newlines.[/dim]"
    )

    raw_input = questionary.text(
        "Enter/paste URL(s):",
        style=custom_style,
    ).ask()

    if not raw_input or not raw_input.strip():
        return

    # Extract all candidate tokens
    tokens = raw_input.replace(",", " ").split()
    urls_found = [
        t.strip()
        for t in tokens
        if ("youtube.com" in t or "youtu.be" in t or t.startswith("http"))
    ]

    if not urls_found:
        console.print("[bold red]No valid YouTube URLs detected in input.[/bold red]")
        return

    res = add_episodes_bulk(target_series["id"], urls_found)
    console.print(
        f"[bold green]✔ Added {res['added']} new episode(s) to '{target_series['name']}'![/bold green] "
        f"[dim]({res['skipped']} duplicate(s) skipped)[/dim]"
    )


def interactive_download_series():
    """Select and download a specific Donghua series with quality selection."""
    ensure_db_ready()

    all_series = db_get_all_series()
    if not all_series:
        console.print("[yellow]No Donghua found. Please register one first![/yellow]")
        return

    choices = []
    for s in all_series:
        p = s["pending_episodes"]
        t = s["total_episodes"]
        badge = f"[Complete ({t})]" if p == 0 else f"[{p} pending / {t} total]"
        choices.append(Choice(f"{s['name']:<32} {badge}", value=s["id"]))
    choices.append(Choice("← Back to Main Menu", value="__back__"))

    selected_id = questionary.select(
        "Choose a Donghua to download:",
        choices=choices,
        style=custom_style,
    ).ask()

    if not selected_id or selected_id == "__back__":
        return

    chosen = db_get_series(selected_id)
    if not chosen:
        console.print("[bold red]Series not found![/bold red]")
        return

    # Select Quality (360p to 1080p, Best)
    quality = prompt_quality(SESSION_SETTINGS["quality"])

    # Download Scope
    scope_choices = [
        Choice(f"Pending episodes only ({chosen['pending_episodes']} videos)", value="pending"),
        Choice(f"All registered episodes ({chosen['total_episodes']} videos)", value="all"),
        Choice("Select specific episodes manually...", value="custom"),
        Choice("← Cancel", value="__cancel__"),
    ]

    scope = questionary.select(
        f"Which episodes of '{chosen['name']}' do you want to download?",
        choices=scope_choices,
        style=custom_style,
    ).ask()

    if not scope or scope == "__cancel__":
        return

    episodes = get_episodes(chosen["id"])
    target_urls = []

    if scope == "pending":
        target_urls = [e["url"] for e in episodes if e["status"] != "downloaded"]
        if not target_urls:
            console.print(f"[bold green]All {len(episodes)} episodes are already marked as downloaded![/bold green]")
            force = questionary.confirm("Do you want to re-check all episodes against disk?", default=False).ask()
            if not force:
                return
            target_urls = [e["url"] for e in episodes]
    elif scope == "all":
        target_urls = [e["url"] for e in episodes]
    elif scope == "custom":
        ep_choices = [
            Choice(
                f"[{e['status']}] {e['title'] or e['video_id']} - {e['url']}",
                value=e["url"],
                checked=(e["status"] != "downloaded"),
            )
            for e in episodes
        ]
        selected_eps = questionary.checkbox(
            "Select episodes to download (Space to toggle, Enter to confirm):",
            choices=ep_choices,
            style=custom_style,
        ).ask()
        if not selected_eps:
            console.print("[yellow]No episodes selected.[/yellow]")
            return
        target_urls = selected_eps

    if not target_urls:
        console.print("[yellow]No URLs to download.[/yellow]")
        return

    run_download_with_events(
        urls_list=target_urls,
        save_dir=chosen["save_dir"],
        series_name=chosen["name"],
        quality=quality,
        series_id=chosen["id"],
        browser=SESSION_SETTINGS["browser"],
        max_retries=SESSION_SETTINGS["max_retries"],
    )


def interactive_download_all_series():
    """Batch download pending or all episodes across all Donghua in database."""
    ensure_db_ready()
    all_series = db_get_all_series()
    if not all_series:
        console.print("[yellow]No Donghua series found.[/yellow]")
        return

    quality = prompt_quality(SESSION_SETTINGS["quality"])
    scope = questionary.select(
        "Download scope for ALL Donghua:",
        choices=[
            Choice("Download only pending (missing) episodes across all Donghua", value="pending"),
            Choice("Check and download all episodes across all Donghua", value="all"),
            Choice("← Cancel", value="__cancel__"),
        ],
        style=custom_style,
    ).ask()

    if not scope or scope == "__cancel__":
        return

    for s in all_series:
        episodes = get_episodes(s["id"])
        if scope == "pending":
            target_urls = [e["url"] for e in episodes if e["status"] != "downloaded"]
            if not target_urls:
                console.print(f"[dim]⏭ Skipping {s['name']}: all {len(episodes)} episodes completed.[/dim]")
                continue
        else:
            target_urls = [e["url"] for e in episodes]

        if not target_urls:
            continue

        run_download_with_events(
            urls_list=target_urls,
            save_dir=s["save_dir"],
            series_name=s["name"],
            quality=quality,
            series_id=s["id"],
            browser=SESSION_SETTINGS["browser"],
            max_retries=SESSION_SETTINGS["max_retries"],
        )


def interactive_manage_donghua():
    """Management sub-menu for viewing, editing, or deleting series and episodes."""
    ensure_db_ready()
    all_series = db_get_all_series()
    if not all_series:
        console.print("[yellow]No Donghua found.[/yellow]")
        return

    choices = [Choice(f"{s['name']} (ID: {s['id']})", value=s["id"]) for s in all_series]
    choices.append(Choice("← Back to Main Menu", value="__back__"))

    selected_id = questionary.select(
        "Select Donghua to manage:",
        choices=choices,
        style=custom_style,
    ).ask()

    if not selected_id or selected_id == "__back__":
        return

    series = db_get_series(selected_id)
    if not series:
        return

    while True:
        action = questionary.select(
            f"Manage '{series['name']}':",
            choices=[
                Choice("📋  View All Episodes & Status", value="view_eps"),
                Choice("➕  Add Episode URLs", value="add_urls"),
                Choice("🔄  Sync with Disk (downloaded.txt)", value="sync_disk"),
                Choice("📁  Edit Save Directory", value="edit_dir"),
                Choice("🗑️   Delete an Episode", value="del_ep"),
                Choice("❌  Delete Entire Donghua Series", value="del_series"),
                Choice("← Back", value="__back__"),
            ],
            style=custom_style,
        ).ask()

        if not action or action == "__back__":
            break

        if action == "view_eps":
            episodes = get_episodes(series["id"])
            table = Table(
                title=f"Episodes for {series['name']} ({len(episodes)} total)",
                box=box.ROUNDED,
            )
            table.add_column("ID", justify="center", width=5)
            table.add_column("Video ID", style="cyan", width=12)
            table.add_column("Status", width=12)
            table.add_column("URL", style="dim")

            for ep in episodes:
                status_colored = (
                    "[green]downloaded[/green]"
                    if ep["status"] == "downloaded"
                    else "[yellow]pending[/yellow]"
                )
                table.add_row(str(ep["id"]), ep["video_id"], status_colored, ep["url"])
            console.print(table)

        elif action == "add_urls":
            interactive_add_urls_to_series(preselected_id=series["id"])
            series = db_get_series(series["id"])

        elif action == "sync_disk":
            updated_count = sync_series_with_archive(series["id"])
            console.print(f"[bold green]✔ Synced with disk: marked {updated_count} episodes as downloaded![/bold green]")
            series = db_get_series(series["id"])

        elif action == "edit_dir":
            new_dir = questionary.text(
                "Enter new save directory:",
                default=series["save_dir"],
                style=custom_style,
            ).ask()
            if new_dir and new_dir.strip() != series["save_dir"]:
                update_series(series["id"], save_dir=new_dir)
                series = db_get_series(series["id"])
                console.print(f"[bold green]✔ Updated save directory to: {series['save_dir']}[/bold green]")

        elif action == "del_ep":
            episodes = get_episodes(series["id"])
            if not episodes:
                console.print("[dim]No episodes to delete.[/dim]")
                continue
            ep_choices = [
                Choice(f"ID {e['id']} [{e['status']}]: {e['url']}", value=e["id"])
                for e in episodes
            ]
            ep_choices.append(Choice("← Cancel", value="__cancel__"))
            chosen_ep_id = questionary.select("Select episode to remove:", choices=ep_choices).ask()
            if chosen_ep_id and chosen_ep_id != "__cancel__":
                delete_episode(chosen_ep_id)
                console.print(f"[bold green]✔ Episode removed from database.[/bold green]")
                series = db_get_series(series["id"])

        elif action == "del_series":
            confirm = questionary.confirm(
                f"Are you SURE you want to delete '{series['name']}' and ALL its episodes?",
                default=False,
            ).ask()
            if confirm:
                delete_series(series["id"])
                console.print(f"[bold green]✔ Donghua '{series['name']}' deleted.[/bold green]")
                break


def interactive_custom_url_download():
    """Quick download of arbitrary YouTube URL(s) entered by the user."""
    raw_input = questionary.text(
        "Enter YouTube URL(s) (space, comma, or newline separated):",
        style=custom_style,
    ).ask()

    if not raw_input or not raw_input.strip():
        return

    candidates = raw_input.replace(",", " ").split()
    target_urls = [
        c.strip()
        for c in candidates
        if "youtube" in c or "youtu.be" in c or c.startswith("http")
    ]

    if not target_urls:
        console.print("[bold red]No valid URLs found in input.[/bold red]")
        return

    save_dir_input = questionary.text(
        "Enter destination directory:",
        default=os.path.expanduser("~/Downloads"),
        style=custom_style,
    ).ask() or os.path.expanduser("~/Downloads")

    save_dir = os.path.expanduser(save_dir_input.strip())
    quality = prompt_quality(SESSION_SETTINGS["quality"])

    run_download_with_events(
        urls_list=target_urls,
        save_dir=save_dir,
        series_name="Custom URLs",
        quality=quality,
        browser=SESSION_SETTINGS["browser"],
        max_retries=SESSION_SETTINGS["max_retries"],
    )


def interactive_resync_database():
    """Force re-synchronization of database with urls.py and disk archives."""
    ensure_db_ready()
    try:
        res = init_db()
        console.print(
            Panel(
                f"[bold green]✔ PostgreSQL Database Synchronization Complete![/bold green]\n\n"
                f"• Series synced: {res['synced_series']}\n"
                f"• Episode URLs synced: {res['synced_episodes']}",
                border_style="green",
                box=box.ROUNDED,
            )
        )
    except Exception as exc:
        console.print(f"[bold red]Sync failed:[/bold red] {exc}")


def interactive_settings():
    """Sub-menu to adjust session preferences."""
    while True:
        choices = [
            Choice(f"Default Quality: [{SESSION_SETTINGS['quality']}]", value="quality"),
            Choice(f"Browser Cookies: [{SESSION_SETTINGS['browser'] or 'Disabled'}]", value="browser"),
            Choice(f"Max Retries:     [{SESSION_SETTINGS['max_retries']}]", value="retries"),
            Choice("← Back to Main Menu", value="__back__"),
        ]

        action = questionary.select(
            "Configure Preferences:",
            choices=choices,
            style=custom_style,
        ).ask()

        if not action or action == "__back__":
            break

        if action == "quality":
            SESSION_SETTINGS["quality"] = prompt_quality(SESSION_SETTINGS["quality"])
            console.print(f"[green]Default quality set to {SESSION_SETTINGS['quality']}[/green]")
        elif action == "browser":
            b_choices = [
                Choice("brave", value="brave"),
                Choice("chrome", value="chrome"),
                Choice("firefox", value="firefox"),
                Choice("chromium", value="chromium"),
                Choice("None (Disabled)", value="none"),
            ]
            chosen_b = questionary.select("Select browser to read YouTube cookies from:", choices=b_choices).ask()
            SESSION_SETTINGS["browser"] = None if chosen_b == "none" else chosen_b
            console.print(f"[green]Browser cookie source set to: {SESSION_SETTINGS['browser']}[/green]")
        elif action == "retries":
            new_r = questionary.text(
                "Enter max retries (1-10):",
                default=str(SESSION_SETTINGS["max_retries"]),
                validate=lambda v: True if v.isdigit() and 1 <= int(v) <= 10 else "Enter an integer between 1 and 10",
            ).ask()
            if new_r:
                SESSION_SETTINGS["max_retries"] = int(new_r)
                console.print(f"[green]Max retries set to {SESSION_SETTINGS['max_retries']}[/green]")


def main_interactive_menu():
    """Main application loop."""
    print_banner()

    while True:
        choices = [
            Choice("📥  Download a Donghua Series", value="download_series"),
            Choice("⚡  Batch Download All Donghua", value="download_all"),
            Choice("🆕  Register New Donghua Series", value="register"),
            Choice("➕  Add Episode URL(s) to Donghua", value="add_urls"),
            Choice("📊  View All Donghua & Status", value="status"),
            Choice("📋  Manage Donghua & Episodes", value="manage"),
            Choice("🔗  Quick Download Custom URL(s)", value="custom"),
            Choice("🔄  Re-Sync Database from urls.py", value="resync"),
            Choice("⚙️   Settings & Quality Defaults", value="settings"),
            Choice("🚪  Exit", value="exit"),
        ]

        choice = questionary.select(
            "What would you like to do?",
            choices=choices,
            style=custom_style,
        ).ask()

        if choice is None or choice == "exit":
            console.print("[bold cyan]Goodbye![/bold cyan]")
            break

        try:
            if choice == "download_series":
                interactive_download_series()
            elif choice == "download_all":
                interactive_download_all_series()
            elif choice == "register":
                interactive_register_donghua()
            elif choice == "add_urls":
                interactive_add_urls_to_series()
            elif choice == "status":
                display_series_table()
            elif choice == "manage":
                interactive_manage_donghua()
            elif choice == "custom":
                interactive_custom_url_download()
            elif choice == "resync":
                interactive_resync_database()
            elif choice == "settings":
                interactive_settings()
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user.[/yellow]")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="YouTube Donghua Downloader CLI with PostgreSQL Store & Quality Selection (360p - 1080p).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python script.py                                  # Launch upgraded interactive menu
  python script.py --list                           # View series & status table
  python script.py --register "Martial Universe"    # Register a new Donghua
  python script.py -s "Throne of Seal" -q 1080      # Download series in 1080p
  python script.py --all -q 720                     # Batch download all in 720p
  python script.py -u "https://youtu.be/..." -d ~/Downloads -q 720
        """,
    )

    parser.add_argument("-s", "--series", type=str, help="Series key or title to download")
    parser.add_argument(
        "-q",
        "--quality",
        type=str,
        default="720p",
        help="Target video quality (e.g. 1080p, 720p, 480p, 360p, best). Default: 720p",
    )
    parser.add_argument("-u", "--url", nargs="+", help="One or more YouTube URLs to download")
    parser.add_argument("-d", "--dir", type=str, help="Destination directory for custom URLs")
    parser.add_argument("-a", "--all", action="store_true", help="Download all registered series")
    parser.add_argument("-l", "--list", action="store_true", help="List all series, status, and exit")
    parser.add_argument("--register", type=str, help="Register a new Donghua series by name")
    parser.add_argument("--sync", action="store_true", help="Force sync PostgreSQL with urls.py and disk")
    parser.add_argument("-b", "--browser", type=str, default=DEFAULT_BROWSER, help="Browser to read cookies from (e.g. brave, chrome)")
    parser.add_argument("-r", "--retries", type=int, default=3, help="Max retry attempts per video (default: 3)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Force interactive mode")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Determine if CLI flags were provided or if we should run interactively
    has_cli_action = (
        args.series
        or args.url
        or args.all
        or args.list
        or args.register
        or args.sync
    )

    if not has_cli_action or args.interactive:
        if not sys.stdin.isatty() and not args.interactive:
            display_series_table()
            console.print(
                "\n[dim]Notice: Interactive menu requires a terminal TTY. "
                "Run with --help to view command-line flags for automated scripts.[/dim]"
            )
            sys.exit(0)
        try:
            main_interactive_menu()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold yellow]Exiting YouTube Downloader. Goodbye![/bold yellow]")
            sys.exit(0)
    else:
        # Non-interactive CLI flags mode
        ensure_db_ready(quiet=True)

        if args.sync:
            interactive_resync_database()
            sys.exit(0)

        if args.register:
            save_dir = args.dir
            created = create_series(args.register, save_dir=save_dir)
            console.print(
                f"[bold green]✔ Registered '{created['name']}' (ID: {created['id']}, Key: {created['key']}) -> {created['save_dir']}[/bold green]"
            )
            sys.exit(0)

        if args.list:
            display_series_table()
            sys.exit(0)

        if args.url:
            save_dir = os.path.expanduser(args.dir or "~/Downloads")
            run_download_with_events(
                urls_list=args.url,
                save_dir=save_dir,
                series_name="Custom URLs",
                quality=args.quality,
                browser=args.browser,
                max_retries=args.retries,
            )
            sys.exit(0)

        if args.series:
            matched = db_get_series(args.series) or urls.get_series(args.series)
            if not matched:
                console.print(f"[bold red]Unknown series: '{args.series}'. Run --list to see available series.[/bold red]")
                sys.exit(1)

            # Extract URLs
            if isinstance(matched, dict):
                episodes = get_episodes(matched["id"])
                target_urls = [e["url"] for e in episodes if e["status"] != "downloaded"] or [e["url"] for e in episodes]
                series_name = matched["name"]
                save_dir = matched["save_dir"]
                series_id = matched["id"]
            else:
                target_urls = matched.get_pending_urls() or matched.urls
                series_name = matched.name
                save_dir = matched.save_dir
                series_id = matched.id

            run_download_with_events(
                urls_list=target_urls,
                save_dir=save_dir,
                series_name=series_name,
                quality=args.quality,
                series_id=series_id,
                browser=args.browser,
                max_retries=args.retries,
            )
            sys.exit(0)

        if args.all:
            all_series = db_get_all_series()
            for s in all_series:
                episodes = get_episodes(s["id"])
                pending = [e["url"] for e in episodes if e["status"] != "downloaded"]
                if not pending:
                    console.print(f"[dim]Skipping {s['name']}: all episodes downloaded.[/dim]")
                    continue
                run_download_with_events(
                    urls_list=pending,
                    save_dir=s["save_dir"],
                    series_name=s["name"],
                    quality=args.quality,
                    series_id=s["id"],
                    browser=args.browser,
                    max_retries=args.retries,
                )
            sys.exit(0)
