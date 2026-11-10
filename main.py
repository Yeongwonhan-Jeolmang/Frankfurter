#!/usr/bin/env python3
"""
Frankfurter Currency Intelligence — entry point.

Run:
    python main.py
"""

import os
import sys

# Ensure project root is on the path so relative imports work regardless of
# where the script is launched from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

from ui.theme import FONT_BODY, apply_dark_palette, build_stylesheet, qfont


def create_application(argv=None) -> QApplication:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Frankfurter")
    app.setApplicationDisplayName("Frankfurter")
    app.setOrganizationName("Frankfurter")
    apply_dark_palette(app)
    app.setFont(qfont(FONT_BODY))
    app.setStyleSheet(build_stylesheet())
    return app


def main():
    app = create_application()
    from ui.app import App  # after QApplication exists (matplotlib Qt backend)

    window = App()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
