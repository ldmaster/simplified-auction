"""Cliente HTTP educado: rate-limit, retry com backoff e cookies."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .config import HttpConfig, browser_headers
from .normalize import decode_latin1


class HttpError(RuntimeError):
    """Falha de rede que persistiu apos todas as tentativas."""


_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

#: Hosts de protecao anti-bot que a Caixa usa nas paginas ``/sistema/``.
_CHALLENGE_HOSTS = ("perfdrive.com", "shieldsquare.com")


def _is_challenge(response: httpx.Response) -> bool:
    host = response.url.host or ""
    return any(host.endswith(bad) for bad in _CHALLENGE_HOSTS)


class HttpClient:
    """Wrapper fino sobre ``httpx.Client`` com throttle e retry."""

    def __init__(self, config: HttpConfig | None = None) -> None:
        """Inicializa o cliente.

        Args:
            config: Parametros de rede; usa os padroes se omitido.
        """
        self._config = config or HttpConfig()
        self._client = httpx.Client(
            headers=browser_headers(self._config.user_agent),
            timeout=self._config.timeout,
            follow_redirects=True,
        )
        self._last = 0.0

    def close(self) -> None:
        """Fecha a conexao subjacente."""
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _throttle(self) -> None:
        wait = self._config.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def _sleep_backoff(self, attempt: int) -> None:
        time.sleep(self._config.backoff * (2**attempt))

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Executa a requisicao com throttle e retry.

        Args:
            method: Verbo HTTP.
            url: URL absoluta.
            **kwargs: Repassados ao ``httpx``.

        Returns:
            A resposta bem-sucedida.

        Raises:
            HttpError: Se todas as tentativas falharem.
        """
        last: Exception | None = None
        for attempt in range(self._config.retries):
            self._throttle()
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                last = exc
                self._sleep_backoff(attempt)
                continue
            if response.status_code in _RETRY_STATUS:
                last = HttpError(f"HTTP {response.status_code} em {url}")
                self._sleep_backoff(attempt)
                continue
            if _is_challenge(response):
                raise HttpError(
                    f"Bloqueio anti-bot da Caixa em {url}. Isso costuma ser "
                    f"temporario (por excesso de requisicoes): aguarde alguns "
                    f"minutos e tente de novo, e/ou aumente AUCTION_MIN_INTERVAL. "
                    f"Para as paginas /sistema/ ha o modo navegador (AUCTION_BROWSER=1)."
                )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise HttpError(str(exc)) from exc
            return response
        raise HttpError(f"Falha ao acessar {url}: {last}")

    def get_bytes(self, url: str, **kwargs: Any) -> bytes:
        """GET retornando bytes crus (CSV em latin-1, PDFs)."""
        return self.request("GET", url, **kwargs).content

    def get_text(self, url: str, encoding: str = "cp1252", **kwargs: Any) -> str:
        """GET retornando texto decodificado (padrao cp1252 do site)."""
        data = self.get_bytes(url, **kwargs)
        if encoding == "cp1252":
            return decode_latin1(data)
        return data.decode(encoding, errors="replace")

    def head(self, url: str, **kwargs: Any) -> httpx.Response:
        """HEAD para checagem barata de mudanca (ETag/Last-Modified)."""
        return self.request("HEAD", url, **kwargs)

    def post_form(
        self, url: str, data: dict[str, str], *, encoding: str = "utf-8", **kwargs: Any
    ) -> str:
        """POST de formulario (endpoints AJAX ``carrega*``) retornando texto.

        Os endpoints ``/sistema/`` respondem em UTF-8 (o CSV da lista, nao).
        """
        response = self.request("POST", url, data=data, **kwargs)
        if encoding == "cp1252":
            return decode_latin1(response.content)
        return response.content.decode(encoding, errors="replace")
