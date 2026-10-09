"""Galeria de fotos do imovel: miniatura, previa, navegacao e exportar."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any

from .images import PILLOW_AVAILABLE, thumbnail, to_photoimage

if TYPE_CHECKING:
    from .app import AuctionApp

THUMB_SIZE = (140, 105)
PREVIEW_SIZE = (620, 460)
MAX_PHOTOS = 30


class PhotoGallery:
    """Mostra as fotos de um imovel, com previa grande e acoes."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.LabelFrame(parent, text="Fotos")
        self._urls: list[str] = []
        self._raw: dict[str, bytes] = {}
        self._previews: list[Any] = []
        self._thumbs: list[Any] = []
        self._index = 0
        self._refs: list[Any] = []
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=4)
        self.info = tk.StringVar(value="sem fotos")
        ttk.Label(bar, textvariable=self.info).pack(side="left")
        ttk.Button(bar, text="Recarregar", command=self.load).pack(side="right")
        ttk.Button(bar, text="Salvar como...", command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Abrir no navegador", command=self._open).pack(side="right")
        ttk.Button(bar, text="▶", width=3, command=lambda: self._step(1)).pack(side="right", padx=2)
        ttk.Button(bar, text="◀", width=3, command=lambda: self._step(-1)).pack(side="right")

        self.preview = ttk.Label(self.frame, text="(clique em Recarregar)", anchor="center")
        self.preview.pack(fill="both", expand=True, padx=4, pady=4)

        self.strip = ttk.Frame(self.frame)
        self.strip.pack(fill="x", padx=4, pady=(0, 4))

    # ------------------------------------------------------------------ entrada

    def set_urls(self, urls: list[str], *, autoload: bool = True) -> None:
        """Define as fotos do imovel exibido.

        Args:
            urls: URLs das fotos.
            autoload: Ja carrega as imagens em background.
        """
        self._urls = urls[:MAX_PHOTOS]
        self._raw.clear()
        self._previews.clear()
        self._thumbs.clear()
        self._index = 0
        self._clear_strip()
        self.preview.configure(image="", text="(carregando fotos...)" if self._urls else "(sem fotos)")
        self.info.set(f"{len(self._urls)} foto(s)" if self._urls else "sem fotos")
        if self._urls and autoload:
            self.load()

    # ------------------------------------------------------------------ acoes

    def load(self) -> None:
        """Baixa as fotos em background e monta miniaturas + previas."""
        if not self._urls:
            messagebox.showinfo("Fotos", "Este imovel nao tem fotos na ficha (rode Enriquecer).")
            return
        if not PILLOW_AVAILABLE:
            messagebox.showwarning("Fotos", "Pillow nao instalado (pip install .[gui]).")
            return
        urls = list(self._urls)
        cfg = self.app.cfg

        def work() -> Any:
            from ..http import HttpClient

            raw: dict[str, bytes] = {}
            with HttpClient(cfg.http) as client:
                for url in urls:
                    try:
                        raw[url] = client.get_bytes(url)
                    except Exception:
                        continue
            return raw

        def done(result: Any) -> None:
            if isinstance(result, Exception) or not result:
                self.preview.configure(image="", text="(falha ao carregar as fotos)")
                return
            self._raw = result
            self._rebuild()

        self.app.run_async(work, done, label="Carregando fotos")

    def _rebuild(self) -> None:
        self._previews = [thumbnail(data, PREVIEW_SIZE) for data in self._raw.values()]
        self._thumbs = [thumbnail(data, THUMB_SIZE) for data in self._raw.values()]
        self._clear_strip()
        for index, image in enumerate(self._thumbs):
            photo = to_photoimage(image)
            if photo is None:
                continue
            self._refs.append(photo)
            label = ttk.Label(self.strip, image=photo, relief="ridge")
            label.grid(row=0, column=index, padx=2)
            label.bind("<Button-1>", partial(self._on_thumb, index))
        self._index = 0
        self._show(0)

    def _on_thumb(self, index: int, _event: Any) -> None:
        self._show(index)

    def _show(self, index: int) -> None:
        if not self._previews:
            return
        self._index = index % len(self._previews)
        image = self._previews[self._index]
        photo = to_photoimage(image)
        if photo is None:
            return
        self._refs.append(photo)
        self.preview.configure(image=photo, text="")
        self.info.set(f"foto {self._index + 1} de {len(self._previews)}")

    def _step(self, delta: int) -> None:
        if self._previews:
            self._show(self._index + delta)

    def _current_bytes(self) -> bytes | None:
        if not self._raw:
            return None
        return list(self._raw.values())[self._index]

    def _open(self) -> None:
        if not self._urls:
            return
        webbrowser.open(self._urls[self._index])

    def _save(self) -> None:
        data = self._current_bytes()
        if data is None:
            messagebox.showinfo("Fotos", "Nada para salvar ainda.")
            return
        name = self._urls[self._index].rsplit("/", 1)[-1]
        path = filedialog.asksaveasfilename(initialfile=name, defaultextension=".jpg")
        if not path:
            return
        Path(path).write_bytes(data)
        self.app.status.set(f"Foto salva em {path}")

    def _clear_strip(self) -> None:
        for child in self.strip.winfo_children():
            child.destroy()
        self._refs = []
