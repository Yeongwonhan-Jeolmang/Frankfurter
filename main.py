#!/usr/bin/env python3
"""
Frankfurter Currency Intelligence — entry point.

Run:
    python main.py
"""

import sys
import os

# Ensure project root is on the path so relative imports work regardless of
# where the script is launched from.
sys.path.insert(0, os.path.dirname(__file__))

from ui.app import App


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
