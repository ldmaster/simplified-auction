"""Entrypoint do PyInstaller para a GUI."""

from __future__ import annotations

import sys

from simplified_auction.gui import main

if __name__ == "__main__":
    sys.exit(main())
