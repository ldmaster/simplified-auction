"""Modo navegador opcional: resolve o desafio JS (Radware) com Playwright.

As paginas ``/sistema/`` da Caixa usam o Radware Bot Manager (CAPTCHA/JS). Um
navegador real executa esse desafio. Este modulo e **opcional** e so e acionado
quando habilitado — a lista oficial (``/listaweb/*.csv``) e os assets estaticos
(``/editais/``, ``/fotos/``) nao precisam dele.

Uso consciente: e um acesso automatizado a paginas publicas; respeite os termos
do site e mantenha o ritmo baixo.
"""

from __future__ import annotations

import importlib.util
import logging

logger = logging.getLogger(__name__)


class BrowserUnavailable(RuntimeError):
    """Playwright nao esta instalado."""


def available() -> bool:
    """Retorna ``True`` se o Playwright estiver instalado."""
    return importlib.util.find_spec("playwright") is not None


def fetch_html(url: str, *, timeout_ms: int = 45000, settle_ms: int = 4000) -> str:
    """Abre a URL em um Chromium headless e devolve o HTML apos o desafio.

    Args:
        url: URL alvo.
        timeout_ms: Timeout de navegacao em milissegundos.
        settle_ms: Espera extra (ms) para o desafio JS resolver.

    Returns:
        O HTML final da pagina.

    Raises:
        BrowserUnavailable: Se o Playwright nao estiver instalado.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable(
            "Playwright nao instalado. Rode: "
            "uv pip install -e '.[browser]' && .venv/bin/playwright install chromium"
        ) from exc
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            context = browser.new_context(locale="pt-BR")
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(settle_ms)
            return str(page.content())
        finally:
            browser.close()


_POST_JS = """
async ([action, data]) => {
  const body = new URLSearchParams(data).toString();
  const r = await fetch(action, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body,
  });
  return await r.text();
}
"""


def post_form(
    page_url: str,
    action: str,
    data: dict[str, str],
    *,
    timeout_ms: int = 45000,
    settle_ms: int = 4000,
) -> str:
    """Navega ate ``page_url`` e faz um POST AJAX de dentro da pagina.

    A pagina ja carrega o token do desafio anti-bot; o ``fetch`` feito no
    contexto dela aproveita esse token.

    Args:
        page_url: Pagina a visitar primeiro (ex.: ``busca-documentos.asp``).
        action: Endpoint do POST (ex.: ``carregaPesquisaDocumentos.asp``).
        data: Campos do formulario.
        timeout_ms: Timeout de navegacao.
        settle_ms: Espera extra (ms) apos carregar a pagina.

    Returns:
        O corpo da resposta.

    Raises:
        BrowserUnavailable: Se o Playwright nao estiver instalado.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserUnavailable(
            "Playwright nao instalado. Rode: "
            "uv pip install -e '.[browser]' && .venv/bin/playwright install chromium"
        ) from exc
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            context = browser.new_context(locale="pt-BR")
            page = context.new_page()
            page.goto(page_url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(settle_ms)
            return str(page.evaluate(_POST_JS, [action, data]))
        finally:
            browser.close()
