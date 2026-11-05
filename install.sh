#!/usr/bin/env bash
# =============================================================================
# install.sh — install Donghua Stream as a globally available package/app.
#
#   * creates/refreshes the project virtualenv (./venv)
#   * installs the package in editable mode (pip install -e .)
#     → console entry points: donghua (CLI), donghua-cli, donghua-gui (GUI)
#   * symlinks the launchers into ~/.local/bin so they resolve from anywhere
#   * writes a desktop entry (menu "Donghua Stream") into
#     ~/.local/share/applications
#
# CLI is untouched: `donghua` still runs the interactive script (script.py),
# and `donghua --gui` also launches the desktop app.
# =============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$PROJECT_DIR/venv"

echo "==> Donghua Stream installer"
echo "    project: $PROJECT_DIR"

# ---- 1. virtualenv ----------------------------------------------------------
if [ ! -x "$VENV/bin/python" ]; then
    echo "==> creating virtualenv $VENV"
    python3 -m venv "$VENV"
fi

echo "==> upgrading pip tooling"
"$VENV/bin/pip" install --upgrade pip -q

# ---- 2. editable install ------------------------------------------------------
echo "==> pip install -e . (entry points: donghua, donghua-cli, donghua-gui)"
cd "$PROJECT_DIR"
"$VENV/bin/pip" install -e . -q

# ---- 3. ~/.local/bin launchers -------------------------------------------------
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"
for cmd in donghua donghua-cli donghua-gui; do
    if [ -x "$VENV/bin/$cmd" ]; then
        ln -sfn "$VENV/bin/$cmd" "$BIN_DIR/$cmd"
        echo "    symlinked $BIN_DIR/$cmd -> $VENV/bin/$cmd"
    else
        echo "    WARNING: $VENV/bin/$cmd not produced (check pyproject entry points)"
    fi
done

case ":$PATH:" in
    *":$BIN_DIR:"*) : ;;
    *) echo "    NOTE: $BIN_DIR is not in your PATH; add it to ~/.bashrc:"
       echo "          export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# ---- 4. desktop entry -----------------------------------------------------------
DESKTOP_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/donghua-stream.desktop"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Donghua Stream
GenericName=Donghua Video Downloader
Comment=TV-streaming-style desktop app for downloading donghua episodes (yt-dlp + PostgreSQL)
Exec=$BIN_DIR/donghua-gui
Icon=video-x-generic
Terminal=false
Categories=Network;AudioVideo;Video;
Keywords=donghua;anime;youtube;downloader;yt-dlp;
StartupNotify=true
EOF
echo "    desktop entry: $DESKTOP_FILE"

# ---- 5. verify -------------------------------------------------------------------
echo "==> verification"
"$VENV/bin/python" -c "import gui, db, downloader, script; print('    imports OK')"
"$VENV/bin/donghua" --help >/dev/null 2>&1 && echo "    donghua CLI OK" || echo "    donghua CLI FAILED"
"$VENV/bin/donghua-gui" --version >/dev/null 2>&1 || QT_QPA_PLATFORM=offscreen \
    "$VENV/bin/python" -c "import gui; print('    donghua-gui import OK')"

echo
echo "✔ Donghua Stream installed."
echo "   Desktop app : $BIN_DIR/donghua-gui   (or the 'Donghua Stream' menu entry)"
echo "   Interactive : $BIN_DIR/donghua       (rich CLI, same as before)"
echo "   From --gui  : $BIN_DIR/donghua --gui"
