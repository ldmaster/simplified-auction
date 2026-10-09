"""Provedores de IA para a analise (Anthropic, OpenAI/compativel, Gemini, CLI)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

from ..config import AIConfig

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

#: Nome do binario da CLI do Command Code (headless: ``cmd -p``).
COMMAND_CODE_BIN = "cmd"

#: Diretorios comuns de binarios. Um app aberto pelo Finder no macOS recebe um
#: PATH minimo (``/usr/bin:/bin:...``) e nao enxerga Homebrew nem ``node``.
_CANDIDATE_DIRS: tuple[str, ...] = (
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    str(Path.home() / ".local" / "bin"),
    str(Path.home() / "bin"),
    str(Path.home() / ".commandcode" / "bin"),
)


def enriched_path() -> str:
    """PATH do processo somado aos diretorios comuns de binarios."""
    parts = [part for part in os.environ.get("PATH", "").split(os.pathsep) if part]
    for directory in _CANDIDATE_DIRS:
        if directory not in parts:
            parts.append(directory)
    return os.pathsep.join(parts)


def find_command_code() -> str | None:
    """Localiza o binario ``cmd`` (PATH atual e diretorios comuns)."""
    return shutil.which(COMMAND_CODE_BIN) or shutil.which(
        COMMAND_CODE_BIN, path=enriched_path()
    )


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
    timeout: float = 300.0,
) -> str:
    """Envia o prompt a um provedor e retorna o texto da resposta.

    Args:
        config: Configuracao de IA (provedor, chave, base_url).
        prompt: Prompt completo.
        provider: Sobrescreve o provedor configurado.
        model: Sobrescreve o modelo configurado.
        timeout: Timeout da chamada em segundos.

    Returns:
        O texto da resposta do modelo.

    Raises:
        AIError: Provedor manual, sem chave, ou falha na chamada.
    """
    chosen = (provider or config.provider or "manual").lower()
    if chosen == "manual":
        raise AIError("Provedor 'manual': use o prompt gerado em um chat web.")
    if chosen == "command-code":
        return _command_code(config, model or config.model, prompt, timeout)
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


def _command_code(config: AIConfig, model: str, prompt: str, timeout: float) -> str:
    """Roda a CLI do Command Code em modo headless (usa a sua assinatura).

    O prompt vai por stdin (aguenta texto grande) e a resposta sai do stdout.
    Roda em um diretorio temporario, com PATH enriquecido (o app aberto pelo
    Finder nao herda o PATH do shell), para achar tanto ``cmd`` quanto ``node``.

    Args:
        config: Configuracao (``base_url`` pode apontar o caminho do binario).
        model: Modelo a usar; vazio usa o modelo atual do Command Code.
        prompt: Prompt completo.
        timeout: Timeout em segundos.

    Returns:
        O texto produzido pela CLI.

    Raises:
        AIError: Binario ausente, timeout ou resposta vazia.
    """
    path = enriched_path()
    binary = config.base_url or find_command_code()
    if not binary or shutil.which(binary, path=path) is None:
        raise AIError(
            "CLI 'cmd' (Command Code) nao encontrada. Se voce abriu o app pelo "
            "Finder, informe o caminho completo no campo base_url do provedor "
            "(ex.: /opt/homebrew/bin/cmd)."
        )
    args = [binary, "-p", "--skip-onboarding", "--max-turns", "4"]
    if model:
        args += ["--model", model]
    try:
        with tempfile.TemporaryDirectory(prefix="auction-cc-") as workdir:
            completed = subprocess.run(
                args,
                input=prompt,
                text=True,
                capture_output=True,
                cwd=workdir,
                timeout=timeout,
                check=False,
                env={**os.environ, "PATH": path},
            )
    except subprocess.TimeoutExpired as exc:
        raise AIError(f"Command Code excedeu {timeout:.0f}s.") from exc
    output = completed.stdout.strip()
    if not output:
        lines = (completed.stderr or "").strip().splitlines()
        detail = lines[-1] if lines else f"exit {completed.returncode}"
        raise AIError(f"Command Code nao retornou texto ({detail}).")
    return output


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
