"""Localizacao do imovel: Google Maps (link) + mapa embutido (opcional)."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

from ..geocoding import (
    address_line,
    geocode,
    google_maps_route_url,
    google_maps_url,
    search_candidates,
)

if TYPE_CHECKING:
    from .app import AuctionApp

try:
    from tkintermapview import TkinterMapView

    MAPS_AVAILABLE = True
except ImportError:  # pragma: no cover - extra 'maps' ausente
    MAPS_AVAILABLE = False


class MapPanel:
    """Mostra o endereco, abre no Google Maps e (se possivel) plota no mapa."""

    def __init__(self, parent: Any, app: AuctionApp) -> None:
        self.app = app
        self.frame = ttk.LabelFrame(parent, text="Localizacao")
        self._row: dict[str, Any] = {}
        self._detail: dict[str, Any] = {}
        self._map: Any = None
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=4)
        self.address = tk.StringVar(value="sem endereco")
        ttk.Label(
            bar, textvariable=self.address, wraplength=520, justify="left"
        ).pack(side="left", anchor="w")
        ttk.Button(bar, text="Google Maps", command=self._open_maps).pack(side="right")
        ttk.Button(bar, text="Rota", command=self._open_route).pack(side="right", padx=4)
        ttk.Button(bar, text="Localizar no mapa", command=self.locate).pack(side="right")

        self.hint = ttk.Label(
            self.frame,
            text=""
            if MAPS_AVAILABLE
            else "Mapa embutido indisponivel (instale o extra 'maps'); use o Google Maps.",
            foreground="#666",
            wraplength=620,
            justify="left",
        )
        self.hint.pack(anchor="w", padx=4)
        self.map_frame = ttk.Frame(self.frame)
        self.map_frame.pack(fill="both", expand=True)

    def set_property(self, row: dict[str, Any] | None, detail: dict[str, Any] | None) -> None:
        """Define o imovel exibido (limpa o mapa anterior)."""
        self._row = row or {}
        self._detail = detail or {}
        self.address.set(address_line(self._row, self._detail) or "sem endereco")
        self._reset_map()

    def _reset_map(self) -> None:
        if self._map is not None:
            self._map.destroy()
            self._map = None

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

    def locate(self) -> None:
        """Geocodifica (com cache) e plota o marcador no mapa embutido."""
        if not MAPS_AVAILABLE:
            messagebox.showinfo(
                "Mapa",
                "Mapa embutido indisponivel. Instale o extra 'maps' ou use 'Google Maps'.",
            )
            return
        row = self._row
        imovel_id = str(row.get("imovel_id") or "")
        if imovel_id:
            cached = self.app.store.get_geocode(imovel_id)
            if cached is not None:
                self._place(float(cached["lat"]), float(cached["lon"]), str(cached["query"]))
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
                    text="Endereco nao encontrado no OpenStreetMap — use o Google Maps.",
                    foreground="#b60",
                )
                self.app.status.set("Nao encontrei o endereco no mapa.")
                return
            if imovel_id:
                store.save_geocode(imovel_id, result.lat, result.lon, result.query)
            self._place(result.lat, result.lon, result.query)

        self.app.run_async(work, done, label="Localizando no mapa")

    def _place(self, lat: float, lon: float, query: str) -> None:
        if self._map is None:
            self._map = TkinterMapView(
                self.map_frame, width=640, height=320, corner_radius=0
            )
            self._map.pack(fill="both", expand=True)
        self._map.set_position(lat, lon)
        self._map.set_zoom(16)
        self._map.delete_all_marker()
        self._map.set_marker(lat, lon, text=query[:60])
        self.hint.configure(text=f"OpenStreetMap: {query}", foreground="#666")
        self.app.status.set("Localizado no mapa.")
