"""Render deterministic documentation screenshots for the README.

Usage:
    QT_QPA_PLATFORM=offscreen ./venv/bin/python tools/capture_screenshots.py

The script boots the real desktop app against the configured PostgreSQL
catalog, then writes 1440x920 PNGs into docs/screenshots/. The Download
Center is seeded with an in-memory demo queue so the screenshot is stable
and never starts a real download.
"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QEventLoop  # noqa: E402
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from gui.dialogs.wizard import AddWizard  # noqa: E402
from gui.infrastructure.download_queue import DownloadTask  # noqa: E402
from gui.theme import F_BODY, app_stylesheet  # noqa: E402
from gui.window import MainWindow  # noqa: E402

OUT = ROOT / "docs" / "screenshots"
WIDTH, HEIGHT = 1440, 920


def pump(app: QApplication, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        time.sleep(0.03)


def wait_until(app: QApplication, predicate, timeout: float = 30.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        pump(app, 0.1)
    return False


def save(widget, name: str) -> None:
    path = OUT / name
    pix = widget.grab()
    pix.save(str(path), "PNG")
    print(f"wrote {path.relative_to(ROOT)} ({pix.width()}x{pix.height()})")


def build_window(app: QApplication) -> MainWindow:
    window = MainWindow()
    window.resize(WIDTH, HEIGHT)
    window.show()
    loaded = wait_until(app, lambda: bool(window.home_view._all), timeout=30)
    if not loaded:
        raise SystemExit("Catalog did not load. Is PostgreSQL running?")
    # Let the poster cache and the first layout settle.
    pump(app, 3.0)
    return window


def capture_home(app: QApplication, window: MainWindow) -> None:
    window.navigateTo("home")
    window.home_view.scroll_to_top()
    pump(app, 1.0)
    save(window, "home.png")


def capture_explore(app: QApplication, window: MainWindow) -> None:
    window.navigateTo("explore")
    view = window.explore_view
    view.ensure_loaded()
    wait_until(app, lambda: not view._busy, timeout=15)
    wait_until(app, lambda: sum(
        1 for c in view._cards
        if c.thumb._pix and not c.thumb._pix.isNull()) >= 8, timeout=25)
    pump(app, 1.0)
    save(window, "explore.png")
    print(f"explore cards: {len(view._cards)} (bundled feed, 0 API quota)")


def capture_explore_search(app: QApplication, window: MainWindow) -> None:
    view = window.explore_view
    view.search_for("Battle Through the Heavens")
    wait_until(app, lambda: not view._busy and view._mode == "search", timeout=40)
    wait_until(app, lambda: sum(
        1 for c in view._cards
        if c.thumb._pix and not c.thumb._pix.isNull()) >= 12, timeout=25)
    pump(app, 1.0)
    save(window, "explore-search.png")
    print(f"search cards: {len(view._cards)}")


def capture_library(app: QApplication, window: MainWindow) -> None:
    window.navigateTo("library")
    pump(app, 1.0)
    save(window, "library.png")


def capture_detail(app: QApplication, window: MainWindow) -> None:
    series = max(window.home_view._all, key=lambda s: int(s.get("total_episodes") or 0))
    window.open_series(int(series["id"]))
    wait_until(app, lambda: window._detail_sid == int(series["id"]), timeout=10)
    pump(app, 2.0)
    save(window, "series-detail.png")
    print(f"detail series: {series.get('name')} ({series.get('total_episodes')} eps)")


def capture_downloads(app: QApplication, window: MainWindow) -> None:
    window.navigateTo("downloads")
    manager = window.manager
    view = window.downloads_view

    # Deterministic demo state only: nothing is enqueued or started.
    active = DownloadTask(
        2, "Throne of Seal", "~/Videos/Throne of Seal",
        ["demo://episode-12", "demo://episode-13", "demo://episode-14"],
        quality="1080p", label="throne_of_seal")
    active.status = "downloading"
    active.progress = 0.42
    manager.active_task = active
    manager.queue = [
        DownloadTask(4, "Jade Dynasty", "~/Videos/Jade Dynasty",
                     ["demo://episode-81"] * 6, label="jade_dynasty"),
        DownloadTask(3, "Herding The Gods", "~/Videos/Herding The Gods",
                     ["demo://episode-08"] * 3, label="herding_the_gods"),
        DownloadTask(2, "Throne of Seal", "~/Videos/Throne of Seal",
                     ["demo://episode-15"] * 4, label="throne_of_seal"),
    ]
    manager.finished_log = [{"series": "Coiling Dragon", "dir": "~/Videos/Coiling Dragon",
                            "urls": [], "label": "coiling_dragon", "time": "just now"}]
    view.on_state_changed()
    view.on_event("progress", {
        "status": "downloading", "speed": 4.7 * 1024 * 1024,
        "downloaded_bytes": 432 * 1024 * 1024,
        "total_bytes": 1.02 * 1024 * 1024 * 1024, "eta": 128,
    })
    for line in [
        "[status] Now playing: Throne of Seal - 3 video(s) (throne_of_seal)",
        "[download] Destination: Throne of Seal - Episode 12 [1080p].mp4",
        "[download]  42.3% of 1020.00MiB at 4.70MiB/s ETA 02:08",
        "[Merger] Merging formats into \"Throne of Seal - Episode 12.mp4\"",
        "[archive] Added video to downloaded.txt",
    ]:
        view.on_log_line(line)
    pump(app, 1.0)
    save(window, "download-center.png")


def capture_settings(app: QApplication, window: MainWindow) -> None:
    window.navigateTo("settings")
    pump(app, 1.5)
    save(window, "settings.png")


def capture_wizard(app: QApplication, window: MainWindow) -> None:
    wizard = AddWizard(window.settings, window)
    wizard.resize(860, 700)
    wizard.show()
    pump(app, 1.0)
    save(wizard, "add-donghua-wizard.png")
    wizard.close()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setApplicationName("Donghua Stream")
    app.setStyle("Fusion")
    app.setFont(QFont(F_BODY, 10))
    app.setStyleSheet(app_stylesheet())

    window = build_window(app)
    capture_home(app, window)
    capture_explore(app, window)
    capture_explore_search(app, window)
    capture_library(app, window)
    capture_detail(app, window)
    capture_downloads(app, window)
    capture_settings(app, window)
    capture_wizard(app, window)

    window.explore_view.shutdown()
    window.manager.shutdown()
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
