#!/usr/bin/env bash
# =============================================================================
# install.sh — build Donghua Stream and install it outside the source tree.
#
# Modes:
#   ./install.sh          install the CLI and desktop app
#   ./install.sh cli      install only the CLI runtime
#   ./install.sh app      install only the desktop app runtime
#   ./install.sh dev      create/refresh ./venv as an editable dev environment
#
# Production modes build a wheel and install it into two isolated runtimes:
#   ${XDG_DATA_HOME:-$HOME/.local/share}/donghua-stream/cli
#   ${XDG_DATA_HOME:-$HOME/.local/share}/donghua-stream/app
#
# The project venv is never linked into ~/.local/bin.  Re-run the same mode to
# upgrade; the selected runtime is recreated from the freshly built wheel.
# =============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PYTHON="${PYTHON:-python3}"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
RUNTIME_ROOT="$DATA_HOME/donghua-stream"
WHEELHOUSE="$RUNTIME_ROOT/wheels"
BUILD_VENV="$RUNTIME_ROOT/.build"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$DATA_HOME/applications"
DESKTOP_FILE="$DESKTOP_DIR/donghua-stream.desktop"

MODE="${1:-all}"
WHEEL=""

usage() {
    cat <<'EOF'
Usage: ./install.sh [all|cli|app|dev]

  all   install both the CLI and the desktop app (default)
  cli   install only the CLI runtime and its launchers
  app   install only the desktop app runtime and its launcher
  dev   create/refresh ./venv as an editable development environment
EOF
}

case "$MODE" in
    all|cli|app|dev) ;;
    -h|--help|help) usage; exit 0 ;;
    *) echo "Unknown mode: $MODE" >&2; usage >&2; exit 2 ;;
esac

echo "==> Donghua Stream installer"
echo "    project: $PROJECT_DIR"
echo "    mode:    $MODE"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
remove_stale_source_link() {
    local cmd="$1"
    local dest="$BIN_DIR/$cmd"
    local target

    [ -L "$dest" ] || return 0
    target="$(readlink -f "$dest" 2>/dev/null || true)"
    case "$target" in
        "$PROJECT_DIR"/*)
            rm -f "$dest"
            echo "    removed stale source link: $dest"
            ;;
    esac
}

link_launcher() {
    local runtime="$1"
    local cmd="$2"
    local source="$RUNTIME_ROOT/$runtime/bin/$cmd"

    if [ ! -x "$source" ]; then
        echo "ERROR: $source was not produced (check pyproject entry points)" >&2
        exit 1
    fi
    ln -sfn "$source" "$BIN_DIR/$cmd"
    echo "    linked $BIN_DIR/$cmd -> $source"
}

path_note() {
    case ":$PATH:" in
        *":$BIN_DIR:"*) : ;;
        *) echo "    NOTE: $BIN_DIR is not in your PATH; add it to ~/.bashrc:"
           echo "          export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
    esac
}

build_wheel() {
    mkdir -p "$RUNTIME_ROOT" "$WHEELHOUSE"

    if [ ! -x "$BUILD_VENV/bin/python" ]; then
        echo "==> creating build virtualenv $BUILD_VENV"
        "$PYTHON" -m venv "$BUILD_VENV"
    fi

    echo "==> installing isolated build tooling"
    "$BUILD_VENV/bin/python" -m pip install --upgrade pip setuptools wheel -q

    echo "==> building wheel from source"
    rm -f "$WHEELHOUSE"/donghua_stream-*.whl
    "$BUILD_VENV/bin/python" -m pip wheel \
        --no-deps --no-build-isolation \
        --wheel-dir "$WHEELHOUSE" "$PROJECT_DIR" -q

    WHEEL="$(find "$WHEELHOUSE" -maxdepth 1 -name 'donghua_stream-*.whl' -print -quit)"
    if [ -z "$WHEEL" ] || [ ! -f "$WHEEL" ]; then
        echo "ERROR: wheel build produced no artifact" >&2
        exit 1
    fi
    echo "    wheel: $WHEEL"
}

install_runtime() {
    local name="$1"
    local extras="$2"
    local venv="$RUNTIME_ROOT/$name"
    local spec="$WHEEL"

    if [ -n "$extras" ]; then
        spec="${WHEEL}[${extras}]"
    fi

    echo "==> creating isolated $name runtime: $venv"
    "$PYTHON" -m venv --clear "$venv"
    "$venv/bin/python" -m pip install --upgrade pip -q
    echo "==> installing $(basename "$WHEEL") with extras: ${extras:-none}"
    "$venv/bin/python" -m pip install "$spec" -q
}

verify_runtime() {
    local name="$1"
    local venv="$RUNTIME_ROOT/$name"
    local verify_gui="${2:-0}"

    echo "==> verifying $name runtime from /tmp"
    (
        cd /tmp
        RUNTIME="$venv" VERIFY_GUI="$verify_gui" "$venv/bin/python" - <<'PY'
import os
import pathlib

runtime = pathlib.Path(os.environ["RUNTIME"]).resolve()


def assert_installed(module):
    path = pathlib.Path(module.__file__).resolve()
    if runtime not in path.parents:
        raise SystemExit(
            f"{module.__name__} loaded from {path}, not the isolated runtime {runtime}")
    print(f"    {module.__name__}: {path}")


import app_config
import db
import downloader
import explore_feed
import urls
import youtube_api

for module in (app_config, db, downloader, explore_feed, urls, youtube_api):
    assert_installed(module)

bundle = pathlib.Path(explore_feed.BUNDLED_PATH).resolve()
if not bundle.is_file():
    raise SystemExit(f"bundled Explore feed missing: {bundle}")
feed = explore_feed.load_bundled()
if not feed.get("items"):
    raise SystemExit("bundled Explore feed is empty")
print(f"    bundled Explore feed: {len(feed['items'])} videos at {bundle}")

if os.environ.get("VERIFY_GUI") == "1":
    import gui

    assert_installed(gui)
    from gui.icons import ASSET_DIR

    icon = pathlib.Path(ASSET_DIR / "play.svg")
    if not icon.is_file():
        raise SystemExit(f"packaged icon missing: {icon}")
    print(f"    GUI imports and packaged assets OK: {icon}")
PY
    )
}

verify_cli() {
    echo "==> verifying donghua CLI"
    (cd /tmp && "$RUNTIME_ROOT/cli/bin/donghua" --help >/dev/null)
    echo "    donghua --help OK"
}

write_desktop_entry() {
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Donghua Stream
GenericName=Donghua Video Downloader
Comment=TV-streaming-style desktop app for downloading donghua episodes (yt-dlp + PostgreSQL)
Exec=$BIN_DIR/donghua-gui
TryExec=$BIN_DIR/donghua-gui
Icon=video-x-generic
Terminal=false
Categories=Network;AudioVideo;Video;
Keywords=donghua;anime;youtube;downloader;yt-dlp;
StartupNotify=true
EOF
    echo "    desktop entry: $DESKTOP_FILE"
}

install_dev() {
    local venv="$PROJECT_DIR/venv"

    if [ ! -x "$venv/bin/python" ]; then
        echo "==> creating development virtualenv $venv"
        "$PYTHON" -m venv "$venv"
    fi

    echo "==> installing editable development environment"
    "$venv/bin/python" -m pip install --upgrade pip -q
    "$venv/bin/python" -m pip install -e "${PROJECT_DIR}[cli,gui,dev]" -q

    echo "==> verifying development imports from /tmp"
    (
        cd /tmp
        "$venv/bin/python" - <<'PY'
import pathlib

import explore_feed
import gui
import script

bundle = pathlib.Path(explore_feed.BUNDLED_PATH)
if not bundle.is_file():
    raise SystemExit(f"bundled Explore feed missing: {bundle}")
print("    editable imports OK")
PY
        "$venv/bin/donghua" --help >/dev/null
    )

    echo
    echo "✔ Development environment ready: $venv"
    echo "   Desktop app : $venv/bin/donghua-gui"
    echo "   Interactive : $venv/bin/donghua"
    echo "   Global launchers were not changed."
}

# ---------------------------------------------------------------------------
# Development mode
# ---------------------------------------------------------------------------
if [ "$MODE" = "dev" ]; then
    install_dev
    exit 0
fi

# ---------------------------------------------------------------------------
# Production modes: wheel + isolated runtimes
# ---------------------------------------------------------------------------
mkdir -p "$BIN_DIR"

# Remove any launchers that still resolve into this checkout's venv.  This is
# what keeps an old editable install from surviving an upgrade.
for cmd in donghua donghua-cli donghua-gui; do
    remove_stale_source_link "$cmd"
done

build_wheel

if [ "$MODE" = "all" ] || [ "$MODE" = "cli" ]; then
    install_runtime cli "cli"
    verify_runtime cli
    verify_cli
    link_launcher cli donghua
    link_launcher cli donghua-cli
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "app" ]; then
    # The app runtime includes the CLI extras too, so every entry point in the
    # app environment is usable (notably `donghua --gui`).  The CLI runtime
    # remains PyQt6-free.
    install_runtime app "cli,gui"
    verify_runtime app 1
    link_launcher app donghua-gui
    write_desktop_entry
fi

path_note

echo
echo "✔ Donghua Stream installed into isolated runtimes."
case "$MODE" in
    all)
        echo "   Desktop app : $BIN_DIR/donghua-gui"
        echo "   Interactive : $BIN_DIR/donghua"
        echo "   CLI alias   : $BIN_DIR/donghua-cli"
        ;;
    cli)
        echo "   Interactive : $BIN_DIR/donghua"
        echo "   CLI alias   : $BIN_DIR/donghua-cli"
        ;;
    app)
        echo "   Desktop app : $BIN_DIR/donghua-gui"
        ;;
esac
echo "   Runtimes    : $RUNTIME_ROOT/{cli,app}"
echo "   Source tree : not used at runtime (safe to move or delete)"
