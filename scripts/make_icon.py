#!/usr/bin/env python
"""Gera os arquivos de icone (PNG, ICO e ICNS) a partir de ``icon.render_icon``."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from simplified_auction.icon import render_icon  # noqa: E402

PACKAGING = ROOT / "packaging"

ICONSET = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def main() -> int:
    """Renderiza o icone e exporta PNG, ICO e (no macOS) ICNS."""
    PACKAGING.mkdir(exist_ok=True)
    master = render_icon(1024)
    master.save(PACKAGING / "icon.png")
    master.resize((512, 512)).save(PACKAGING / "preview_512.png")
    master.resize((64, 64)).save(PACKAGING / "preview_64.png")
    master.resize((32, 32)).save(PACKAGING / "preview_32.png")
    master.save(
        PACKAGING / "icon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    iconset = PACKAGING / "icon.iconset"
    if shutil.which("iconutil"):
        if iconset.exists():
            shutil.rmtree(iconset)
        iconset.mkdir()
        for name, size in ICONSET.items():
            render_icon(size).save(iconset / name)
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(PACKAGING / "icon.icns")],
            check=True,
        )
        shutil.rmtree(iconset)
        print("icon.icns gerado")
    else:
        print("iconutil ausente (normal fora do macOS); icns nao gerado")
    print("gerado em", PACKAGING)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
