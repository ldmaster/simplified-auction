"""Provedores de IA para a analise (Anthropic, OpenAI/compativel, Gemini)."""

from __future__ import annotations

import httpx

from ..config import AIConfig

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4o-mini",
    "compatible": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
}


class AIError(RuntimeError):
    """Falha ao chamar o provedor de IA."""


def _default_model(provider: str) -> str:
    return _DEFAULT_MODELS.get(provider, "gpt-4o-mini")


def run_api(
    config: AIConfig,
    prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    timeout: float = 120.0,
) -> str:
    """Envia o prompt a um provedor remoto e retorna o texto da resposta.

    Args:
        config: Configuracao de IA (chave, provedor, base_url).
        prompt: Prompt completo.
        provider: Sobrescreve o provedor configurado.
        model: Sobrescreve o modelo configurado.
        timeout: Timeout da chamada em segundos.

    Returns:
        O texto da resposta do modelo.

    Raises:
        AIError: Sem chave configurada ou falha na chamada.
    """
    chosen = (provider or config.provider or "manual").lower()
    if chosen == "manual":
        raise AIError("Provedor 'manual': use o prompt gerado em um chat web.")
    if not config.api_key:
        raise AIError("Nenhuma chave de API configurada (defina AUCTION_AI_KEY).")
    model_name = model or config.model or _default_model(chosen)
    try:
        if chosen == "anthropic":
            return _anthropic(config, model_name, prompt, timeout)
        if chosen == "gemini":
            return _gemini(config, model_name, prompt, timeout)
        return _openai(config, model_name, prompt, timeout)
    except httpx.HTTPError as exc:
        raise AIError(f"Falha na chamada de IA: {exc}") from exc


def _anthropic(config: AIConfig, model: str, prompt: str, timeout: float) -> str:
    response = httpx.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": config.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    blocks = response.json().get("content", [])
    return "".join(block.get("text", "") for block in blocks if isinstance(block, dict))


def _openai(config: AIConfig, model: str, prompt: str, timeout: float) -> str:
    url = config.base_url or OPENAI_URL
    response = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {config.api_key or ''}",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    choices = response.json().get("choices", [])
    if not choices:
        return ""
    return str(choices[0].get("message", {}).get("content", ""))


def _gemini(config: AIConfig, model: str, prompt: str, timeout: float) -> str:
    url = GEMINI_URL.format(model=model)
    response = httpx.post(
        url,
        params={"key": config.api_key or ""},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=timeout,
    )
    response.raise_for_status()
    candidates = response.json().get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
