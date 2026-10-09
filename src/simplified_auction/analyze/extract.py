"""Extracao de texto de documentos (PDF) com pypdf."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_text(path: Path) -> str:
    """Extrai o texto de um PDF.

    PDFs escaneados (sem camada de texto) retornam pouco ou nada — nesse caso
    um OCR externo (``ocrmypdf``/``tesseract``) pode ser aplicado antes.

    Args:
        path: Caminho do PDF.

    Returns:
        O texto concatenado das paginas.
    """
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        content = page.extract_text()
        if content:
            parts.append(content)
    return "\n".join(parts).strip()
