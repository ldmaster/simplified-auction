#!/usr/bin/env bash
# Build local (macOS) dos binarios: GUI (.app) e CLI.
set -euo pipefail
cd "$(dirname "$0")/.."

echo ">> limpando saidas anteriores"
rm -rf build dist

echo ">> criando venv com Python gerenciado pelo uv (tem Tkinter)"
uv venv --clear --python-preference only-managed --python 3.12 .venv-mac
uv pip install --python .venv-mac/bin/python -e ".[gui,maps]" "pyinstaller>=6.6,<7"

echo ">> gerando o icone"
.venv-mac/bin/python scripts/make_icon.py

echo ">> gerando a CLI (dist/simplified-auction)"
.venv-mac/bin/pyinstaller --noconfirm --onefile --name simplified-auction \
    --paths src packaging/simplified_auction_entry.py

echo ">> gerando a GUI (dist/simplified-auction-gui.app)"
.venv-mac/bin/pyinstaller --noconfirm --windowed --name simplified-auction-gui \
    --paths src --icon packaging/icon.icns packaging/simplified_auction_gui_entry.py

echo
echo "Pronto. Abra com:"
echo "  open dist/simplified-auction-gui.app"
echo "CLI:"
echo "  ./dist/simplified-auction --help"
