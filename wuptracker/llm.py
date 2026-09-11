"""Camada de backend do LLM — abstrai qual IA analisa as imagens e escreve o writeup.

Backends (config.BACKEND):

  claude_cli  CLI do Claude Code (`claude -p`). Usa a cota da sua assinatura
              Pro/Max — sem cobrança por token, sem API key. Requer `claude` no PATH.
  anthropic   API da Anthropic (ANTHROPIC_API_KEY). Cobra por token.
  ollama      Modelo local via Ollama (http://localhost:11434). Grátis, offline,
              privado. Requer um modelo com visão baixado (llava, llama3.2-vision,
              qwen2.5vl, moondream, minicpm-v...).
  openai      Qualquer endpoint compatível com a API OpenAI (OpenAI, Groq,
              OpenRouter, LM Studio, llama.cpp server...). Config: OPENAI_BASE_URL,
              OPENAI_MODEL, OPENAI_API_KEY.
  gemini      API do Google Gemini (GEMINI_API_KEY). Tem um tier gratuito
              generoso. Config: GEMINI_MODEL.
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

from . import config
from . import paths

try:
    from dotenv import load_dotenv

    load_dotenv(paths.ENV_FILE)
    load_dotenv()  # também o .env do diretório atual, se houver (dev/legado)
except Exception:
    pass

BACKENDS = ("claude_cli", "anthropic", "ollama", "openai", "gemini")
_ALIASES = {
    "api": "anthropic", "claude": "claude_cli", "cli": "claude_cli",
    "openai_compat": "openai", "compat": "openai", "local": "ollama",
    "google": "gemini",
}


def resolve_backend(name):
    name = (name or "claude_cli").strip().lower()
    return _ALIASES.get(name, name)


def _backend():
    return resolve_backend(getattr(config, "BACKEND", "claude_cli"))


# ==========================================================================
# API pública
# ==========================================================================
def preflight():
    """Valida que o backend escolhido está utilizável; encerra com msg clara."""
    b = _backend()
    if b not in BACKENDS:
        sys.exit(f"[!] BACKEND inválido: {b!r}. Use: {', '.join(BACKENDS)}")

    if b == "claude_cli":
        if not shutil.which("claude"):
            sys.exit("[!] comando 'claude' não encontrado no PATH. Instale o "
                     "Claude Code ou troque o backend:\n"
                     "    wuptracker config backend ollama")
    elif b == "anthropic":
        _anthropic_client()
    elif b == "ollama":
        host = _ollama_host()
        try:
            tags = _http_json("GET", f"{host}/api/tags", timeout=5)
        except Exception as e:
            sys.exit(f"[!] Ollama inacessível em {host} ({e}).\n"
                     "    Rode 'ollama serve' ou ajuste 'wuptracker config set "
                     "ollama-host ...'")
        model = _ollama_model()
        have = {m.get("name", "").split(":")[0] for m in tags.get("models", [])}
        if model.split(":")[0] not in have:
            print(f"[i] modelo Ollama '{model}' não está baixado — rode: "
                  f"ollama pull {model}", file=sys.stderr)
    elif b == "openai":
        base = _openai_base()
        local = "localhost" in base or "127.0.0.1" in base
        if not _openai_key() and not local:
            sys.exit("[!] OPENAI_API_KEY ausente.\n"
                     "    wuptracker config api-key <sua-chave>\n"
                     "    (ou aponte OPENAI_BASE_URL para um servidor local)")
    elif b == "gemini":
        if not _gemini_key():
            sys.exit("[!] GEMINI_API_KEY ausente. Pegue uma (com tier grátis) em "
                     "https://aistudio.google.com/apikey e rode:\n"
                     "    wuptracker config api-key <sua-chave>")


def analyze_image(png_path, prompt, timeout=180):
    """Analisa um screenshot. Retorna o texto bruto da resposta do modelo."""
    b = _backend()
    if b == "claude_cli":
        return _cli_analyze_image(png_path, prompt, timeout)
    img = _jpeg_b64(png_path)
    if b == "anthropic":
        return _anthropic_msg(prompt, img)
    if b == "ollama":
        return _ollama_chat(prompt, images=[img], timeout=timeout)
    if b == "openai":
        return _openai_chat(prompt, img_b64=img, timeout=timeout)
    if b == "gemini":
        return _gemini_generate(prompt, img_b64=img, timeout=timeout)
    raise RuntimeError(f"backend não suportado: {b}")


def generate_text(prompt, timeout=600):
    """Gera texto a partir de um prompt puro. Retorna o texto bruto."""
    b = _backend()
    if b == "claude_cli":
        return _cli_generate_text(prompt, timeout)
    if b == "anthropic":
        return _anthropic_msg(prompt, None)
    if b == "ollama":
        return _ollama_chat(prompt, images=None, timeout=timeout)
    if b == "openai":
        return _openai_chat(prompt, img_b64=None, timeout=timeout)
    if b == "gemini":
        return _gemini_generate(prompt, img_b64=None, timeout=timeout)
    raise RuntimeError(f"backend não suportado: {b}")


# ==========================================================================
# Helpers HTTP / imagem
# ==========================================================================
def _jpeg_b64(png_path):
    from . import common

    return common.png_to_jpeg_b64(png_path)


def _http_json(method, url, body=None, headers=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        raise RuntimeError(f"HTTP {e.code}: {detail}")


# ==========================================================================
# Backend: claude CLI
# ==========================================================================
def _cli_base_cmd():
    cmd = ["claude", "-p", "--output-format", "text"]
    model = getattr(config, "CLAUDE_CLI_MODEL", None)
    if model:
        cmd += ["--model", model]
    return cmd


def _cli_run(cmd, stdin_text, timeout):
    proc = subprocess.run(cmd, input=stdin_text, capture_output=True,
                          text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI saiu com código {proc.returncode}: "
                           f"{(proc.stderr or proc.stdout).strip()[:500]}")
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError("claude CLI não retornou saída.")
    return out


def _cli_analyze_image(png_path, prompt, timeout):
    abs_png = os.path.abspath(png_path)
    cmd = _cli_base_cmd() + ["--add-dir", os.path.dirname(abs_png)]
    return _cli_run(cmd, f"{prompt}\n\nAnalise o screenshot no arquivo: {abs_png}",
                    timeout)


def _cli_generate_text(prompt, timeout):
    return _cli_run(_cli_base_cmd(), prompt, timeout)


# ==========================================================================
# Backend: Anthropic API
# ==========================================================================
_client = None


def _anthropic_client():
    global _client
    if _client is not None:
        return _client
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("[!] pacote 'anthropic' não instalado (backend 'anthropic'). "
                 "pip install anthropic")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("[!] ANTHROPIC_API_KEY ausente. wuptracker config api-key <chave>")
    _client = Anthropic(api_key=key)
    return _client


def _anthropic_msg(prompt, img_b64):
    content = []
    if img_b64:
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg", "data": img_b64}})
    content.append({"type": "text", "text": prompt})
    max_tokens = (config.ANALYZE_MAX_TOKENS if img_b64
                  else config.GENERATE_MAX_TOKENS)
    resp = _anthropic_client().messages.create(
        model=config.CLAUDE_MODEL, max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in resp.content if b.type == "text").strip()


# ==========================================================================
# Backend: Ollama (local)
# ==========================================================================
def _ollama_host():
    return getattr(config, "OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def _ollama_model():
    return getattr(config, "OLLAMA_MODEL", "llava")


def _ollama_chat(prompt, images, timeout):
    msg = {"role": "user", "content": prompt}
    if images:
        msg["images"] = images
    body = {"model": _ollama_model(), "messages": [msg], "stream": False,
            "options": {"temperature": 0.2}}
    out = _http_json("POST", f"{_ollama_host()}/api/chat", body, timeout=timeout)
    text = (out.get("message") or {}).get("content", "").strip()
    if not text:
        raise RuntimeError(f"Ollama não retornou conteúdo: {str(out)[:300]}")
    return text


# ==========================================================================
# Backend: OpenAI-compatible (OpenAI, Groq, OpenRouter, LM Studio, llama.cpp…)
# ==========================================================================
def _openai_base():
    return getattr(config, "OPENAI_BASE_URL",
                   "https://api.openai.com/v1").rstrip("/")


def _openai_model():
    return getattr(config, "OPENAI_MODEL", "gpt-4o-mini")


def _openai_key():
    return os.environ.get("OPENAI_API_KEY", "")


def _openai_chat(prompt, img_b64, timeout):
    if img_b64:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
        ]
    else:
        content = prompt
    body = {"model": _openai_model(),
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.2}
    headers = {}
    if _openai_key():
        headers["Authorization"] = f"Bearer {_openai_key()}"
    out = _http_json("POST", f"{_openai_base()}/chat/completions",
                     body, headers, timeout)
    try:
        return out["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"resposta inesperada do endpoint: {str(out)[:300]}")


# ==========================================================================
# Backend: Google Gemini
# ==========================================================================
def _gemini_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")


def _gemini_model():
    return getattr(config, "GEMINI_MODEL", "gemini-2.0-flash")


def _gemini_generate(prompt, img_b64, timeout):
    parts = [{"text": prompt}]
    if img_b64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_b64}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.2}}
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{_gemini_model()}:generateContent")
    out = _http_json("POST", url, body,
                     headers={"x-goog-api-key": _gemini_key()}, timeout=timeout)
    try:
        cand = out["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        if not text.strip():
            raise RuntimeError(
                f"Gemini retornou vazio (finishReason="
                f"{cand.get('finishReason')}): {str(out)[:300]}")
        return text.strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"resposta inesperada do Gemini: {str(out)[:300]}")
