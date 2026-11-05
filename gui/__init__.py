"""Donghua Stream desktop app (PyQt6), built on the Stitch design system.

Singular entry point::

    from gui import main
    main()

Package layout::

    gui/
      app.py            QApplication bootstrap + main()
      window.py         MainWindow (composition root)
      theme.py          design tokens + global QSS
      utils.py          UI-free helpers
      components/       reusable sections (cards, hero, rail, header, toast…)
      infrastructure/   adapters (yt-dlp queue, thumbnails, DB worker, scanner)
      dialogs/          modal workflows (wizard, bulk import, quick add)
      pages/            one module per page (home, library, detail,
                        downloads, settings)
"""

from .app import main
from .window import MainWindow

__all__ = ["main", "MainWindow"]
