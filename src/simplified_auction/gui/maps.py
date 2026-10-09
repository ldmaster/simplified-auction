"""Localizacao do imovel: mapa embutido (OSM) e imagem do Google no app."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from collections.abc import Callable
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from .. import uistate
from ..config import external_http_config
from ..geocoding import (
    address_line,
    geocode,
    google_maps_route_url,
    google_maps_url,
    search_candidates,
)
from ..maps import MAP_TYPES, static_map_url
from .images import PILLOW_AVAILABLE, thumbnail, to_photoimage

if TYPE_CHECKING:
    from .app import AuctionApp

try:
    from tkintermapview import TkinterMapView

    MAPS_AVAILABLE = True
except ImportError:  # pragma: no cover - extra 'maps' ausente
    MAPS_AVAILABLE = False

_MAP_TYPE_LABELS = {
    "roadmap": "Mapa",
    "satellite": "Satelite",
    "hybrid": "Hibrido",
    "terrain": "Relevo",
}


class MapPanel:
    """Mostra o endereco, o mapa embutido e a imagem do Google Maps."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.LabelFrame(parent, text="Localizacao")
        self._row: dict[str, Any] = {}
        self._detail: dict[str, Any] = {}
        self._map: Any = None
        self._image_label: tk.Label | None = None
        self._image_ref: Any = None
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=4)
        self.address = tk.StringVar(value="sem endereco")
        ttk.Label(
            bar, textvariable=self.address, wraplength=460, justify="left"
        ).pack(side="left", anchor="w")

        ttk.Button(bar, text="Google (no app)", command=self.google_static).pack(side="right")
        self.maptype = tk.StringVar(value=_label_of(uistate.map_type()))
        combo = ttk.Combobox(
            bar, textvariable=self.maptype, values=[_MAP_TYPE_LABELS[k] for k in MAP_TYPES],
            width=9, state="readonly",
        )
        combo.pack(side="right", padx=4)
        combo.bind("<<ComboboxSelected>>", lambda _e: self._save_maptype())
        ttk.Button(bar, text="Mapa interativo", command=self.locate).pack(side="right")

        row2 = ttk.Frame(self.frame)
        row2.pack(fill="x", padx=4)
        ttk.Button(row2, text="Abrir no Google Maps", command=self._open_maps).pack(side="left")
        ttk.Button(row2, text="Rota (navegador)", command=self._open_route).pack(side="left", padx=4)

        self.hint = ttk.Label(
            self.frame,
            text="",
            foreground="#888",
            wraplength=620,
            justify="left",
        )
        self.hint.pack(anchor="w", padx=4, pady=(2, 0))
        self.map_frame = ttk.Frame(self.frame)
        self.map_frame.pack(fill="both", expand=True, pady=(4, 4))

    # ------------------------------------------------------------------ estado

    def set_property(self, row: dict[str, Any] | None, detail: dict[str, Any] | None) -> None:
        """Define o imovel exibido (limpa o mapa anterior)."""
        self._row = row or {}
        self._detail = detail or {}
        self.address.set(address_line(self._row, self._detail) or "sem endereco")
        self._reset()
        self._update_hint()

    def _update_hint(self) -> None:
        if not MAPS_AVAILABLE:
            self.hint.configure(
                text="Mapa interativo indisponivel (extra 'maps'). O Google no app segue funcionando."
            )
            return
        if not uistate.google_maps_key():
            self.hint.configure(
                text=(
                    "Para o Google dentro do app, informe a chave da API em Config "
                    "(Maps Static). Sem chave, use o mapa interativo (OpenStreetMap)."
                )
            )
        else:
            self.hint.configure(text="")

    def _save_maptype(self) -> None:
        for kind, label in _MAP_TYPE_LABELS.items():
            if label == self.maptype.get():
                uistate.set_map_type(kind)
                return

    def _reset(self) -> None:
        if self._map is not None:
            self._map.destroy()
            self._map = None
        if self._image_label is not None:
            self._image_label.destroy()
            self._image_label = None
        self._image_ref = None

    # ------------------------------------------------------------------ acoes

    def _open_maps(self) -> None:
        address = address_line(self._row, self._detail)
        if not address:
            messagebox.showinfo("Mapa", "Sem endereco para abrir.")
            return
        webbrowser.open(google_maps_url(address))

    def _open_route(self) -> None:
        address = address_line(self._row, self._detail)
        if not address:
            messagebox.showinfo("Mapa", "Sem endereco para a rota.")
            return
        webbrowser.open(google_maps_route_url(address))

    def _ensure_coords(self, then: Callable[[float, float], None], label: str) -> None:
        """Resolve as coordenadas (cache -> geocodificacao) e chama ``then``."""
        imovel_id = str(self._row.get("imovel_id") or "")
        if imovel_id:
            cached = self.app.store.get_geocode(imovel_id)
            if cached is not None:
                then(float(cached["lat"]), float(cached["lon"]))
                return
        candidates = search_candidates(self._row, self._detail)
        if not candidates:
            messagebox.showinfo("Mapa", "Sem endereco para localizar.")
            return
        cfg = self.app.cfg
        store = self.app.store

        def work() -> Any:
            from ..http import HttpClient

            with HttpClient(cfg.http) as client:
                return geocode(client, candidates)

        def done(result: Any) -> None:
            if isinstance(result, Exception):
                self.app.status.set(f"Falha ao localizar: {result}")
                messagebox.showerror("Mapa", str(result))
                return
            if result is None:
                self.hint.configure(
                    text="Endereco nao encontrado nas fontes (OpenStreetMap) — use 'Abrir no Google Maps'.",
                    foreground="#b60",
                )
                return
            if imovel_id:
                store.save_geocode(imovel_id, result.lat, result.lon, result.query)
            then(result.lat, result.lon)

        self.app.run_async(work, done, label=label)

    def locate(self) -> None:
        """Plota o imovel no mapa interativo (OpenStreetMap, sem chave)."""
        if not MAPS_AVAILABLE:
            messagebox.showinfo(
                "Mapa",
                "Mapa interativo indisponivel. Instale o extra 'maps' ou use 'Google (no app)'.",
            )
            return
        self._ensure_coords(self._place_osm, "Localizando no mapa")

    def google_static(self) -> None:
        """Busca a imagem do Google Maps e mostra dentro do app."""
        key = uistate.google_maps_key()
        if not key:
            messagebox.showinfo(
                "Google Maps",
                "Informe a chave da API do Google Maps em Config (Preferencias > Google Maps). "
                "E preciso habilitar 'Maps Static API' e o billing no projeto do Google Cloud.",
            )
            return
        if not PILLOW_AVAILABLE:
            messagebox.showwarning("Google Maps", "Pillow nao instalado (pip install .[gui]).")
            return
        self._ensure_coords(self._fetch_static, "Buscando mapa do Google")

    def _place_osm(self, lat: float, lon: float) -> None:
        if self._map is None:
            self._reset()
            self._map = TkinterMapView(self.map_frame, width=640, height=320, corner_radius=0)
            self._map.pack(fill="both", expand=True)
        self._map.set_position(lat, lon)
        self._map.set_zoom(16)
        self._map.delete_all_marker()
        self._map.set_marker(lat, lon, text="imovel")
        self.hint.configure(text="OpenStreetMap (interativo)", foreground="#666")
        self.app.status.set("Localizado no mapa.")

    def _fetch_static(self, lat: float, lon: float) -> None:
        key = uistate.google_maps_key()
        maptype = uistate.map_type()
        url = static_map_url(key, lat, lon, maptype=maptype)
        cfg = self.app.cfg

        def work() -> Any:
            from ..http import HttpClient

            with HttpClient(external_http_config(cfg.http)) as client:
                return client.get_bytes(url)

        def done(result: Any) -> None:
            if isinstance(result, Exception):
                texto = str(result)
                if "403" in texto or "400" in texto:
                    texto += (
                        "\n\nVerifique: a chave esta correta, a 'Maps Static API' esta "
                        "habilitada e o billing esta ativo no projeto do Google Cloud."
                    )
                self.app.status.set("Falhou ao buscar o mapa do Google.")
                messagebox.showerror("Google Maps", texto)
                return
            image = thumbnail(result, (640, 400))
            if image is None:
                messagebox.showerror("Google Maps", "Resposta nao era uma imagem valida.")
                return
            self._show_image(image)

        self.app.run_async(work, done, label="Buscando mapa do Google")

    def _show_image(self, image: Any) -> None:
        photo = to_photoimage(image)
        if photo is None:
            return
        self._reset()
        self._image_ref = photo
        self._image_label = tk.Label(self.map_frame, image=photo)
        self._image_label.pack()
        self.hint.configure(text="Google Maps (imagem, dentro do app)", foreground="#666")
        self.app.status.set("Mapa do Google carregado.")


def _label_of(kind: str) -> str:
    """Rotulo do tipo de mapa a partir do codigo."""
    return _MAP_TYPE_LABELS.get(kind, _MAP_TYPE_LABELS["roadmap"])
