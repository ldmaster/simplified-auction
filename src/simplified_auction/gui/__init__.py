"""Interface grafica (Tkinter) do simplified-auction."""

from __future__ import annotations

from .. import config as config_module


def main(cfg: config_module.Config | None = None) -> int:
    """Abre a janela principal.

    Args:
        cfg: Configuracao; carregada do ambiente se omitida.

    Returns:
        O codigo de saida.
    """
    import tkinter as tk
    from tkinter import messagebox

    from .app import AuctionApp
    from .images import app_icon

    config = cfg or config_module.load()
    root = tk.Tk()
    root.title("simplified-auction — leilao de imoveis Caixa")
    root.geometry("1200x780")

    icon = app_icon()
    if icon is not None:
        root.iconphoto(True, icon)

    def _report_error(exc_type: type[BaseException], exc: BaseException, _tb: object) -> None:
        messagebox.showerror("Erro inesperado", f"{exc_type.__name__}: {exc}")

    root.report_callback_exception = _report_error

    app = AuctionApp(root, config)
    try:
        root.mainloop()
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
