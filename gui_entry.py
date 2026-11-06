"""Console entry point for the desktop app.

The CLI and GUI share one distribution, but they are installed into separate
runtime environments.  Keeping this wrapper outside :mod:`gui` lets a
CLI-only environment expose the ``donghua-gui`` command without importing
PyQt6; it reports an actionable message (or delegates to a GUI runtime that
is already on ``PATH``) instead of a traceback.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import List, Optional


def _gui_launcher_on_path() -> Optional[str]:
    """Return a different ``donghua-gui`` launcher, if one is installed."""
    launcher = shutil.which("donghua-gui")
    if not launcher:
        return None
    if os.path.realpath(launcher) == os.path.realpath(sys.argv[0]):
        return None
    return launcher


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # ``donghua --gui`` reaches this wrapper with the flag still attached.
    args = [arg for arg in args if arg != "--gui"]

    try:
        from gui import main as run
    except ModuleNotFoundError as exc:
        if exc.name != "PyQt6":
            raise
        launcher = _gui_launcher_on_path()
        if launcher:
            return subprocess.call([launcher, *args])
        sys.stderr.write(
            "The desktop app is not installed in this environment.\n"
            "Install it with: pip install 'donghua-stream[gui]'\n"
            "Or run ./install.sh app from the project checkout.\n")
        return 1

    return run(args)
