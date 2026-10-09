"""Entrypoint do PyInstaller para a CLI (auction)."""

from __future__ import annotations

import sys

from simplified_auction.cli import main

if __name__ == "__main__":
    sys.exit(main())
