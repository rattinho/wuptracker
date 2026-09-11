"""Configurações da ferramenta de captura de writeups.

Os valores abaixo são os padrões. Um arquivo de config em
~/.config/wuptracker/config.json (gerenciado por `wuptracker config set ...`)
sobrepõe qualquer chave MAIÚSCULA.
"""

import json as _json
import os as _os

from . import paths as _paths

# Tecla de atalho para capturar a tela (nome de pynput.keyboard.Key, ex: "f9")
CAPTURE_KEY = "f9"

# Tecla para encerrar a sessão
EXIT_KEY = "f10"

# Qualidade do screenshot ao converter para JPEG no envio à API (1-100)
SCREENSHOT_QUALITY = 85

# Capturar apenas o monitor onde o cursor do mouse está (setups multi-monitor).
# Se False, captura todos os monitores juntos.
CAPTURE_ACTIVE_MONITOR_ONLY = True

# Recortar a imagem para a região relevante indicada pelo modelo de visão.
# O screenshot original é sempre preservado; o recorte vira <nome>_crop.png.
CROP_IMAGES = True

# Margem extra em volta do recorte (fração da dimensão, 0.03 = 3%)
CROP_PADDING = 0.03

# Embutir as imagens (recortadas quando houver) no writeup gerado.
# As imagens usadas são copiadas para writeups/<sessão>/assets/
EMBED_IMAGES = True

# Otimizar as imagens do writeup: converter para WebP (bem mais leve que PNG).
# Se o WebP não estiver disponível no Pillow, cai para PNG otimizado.
WEBP_IMAGES = True

# Qualidade do WebP (0-100). 80 costuma ser indistinguível e ~5x menor.
WEBP_QUALITY = 80

# Largura máxima das imagens do writeup em pixels (redimensiona mantendo proporção).
# 0 = não redimensionar.
IMAGE_MAX_WIDTH = 1600

# Pasta base para sessões (dado da ferramenta -> XDG_DATA_HOME)
SESSIONS_DIR = _paths.SESSIONS_DIR

# Pasta para writeups gerados — relativa ao diretório onde você roda o comando
# (o writeup é um artefato do seu trabalho ali, não um dado global da ferramenta)
WRITEUPS_DIR = "writeups"

# Perfil padrão do writeup quando não passado na linha de comando:
#   "thm"      -> pentest/CTF (fases, flags, privesc)
#   "generico" -> registro cronológico de qualquer sessão de trabalho
# Pode ser sobrescrito com: python capture.py "Nome" --profile generico
DEFAULT_PROFILE = "thm"

# Estilo padrão do writeup (generate.py --style ...):
#   tecnico | corrido | resumo | blog | linkedin
# generate.py aceita vários de uma vez: --style tecnico,linkedin
DEFAULT_STYLE = "tecnico"

# Backend do LLM (wuptracker config backend ...):
#   "claude_cli" -> CLI do Claude Code (assinatura Pro/Max, sem custo por token,
#                   sem API key). Requer o comando `claude` no PATH.
#   "anthropic"  -> API da Anthropic (ANTHROPIC_API_KEY). Cobra por token.
#   "ollama"     -> modelo local via Ollama. Grátis, offline, privado.
#   "openai"     -> endpoint compatível com a API OpenAI (OpenAI, Groq,
#                   OpenRouter, LM Studio, llama.cpp server...).
BACKEND = "claude_cli"

# --- backend "anthropic" ---
CLAUDE_MODEL = "claude-sonnet-5"

# --- backend "claude_cli" --- (None = usa o modelo padrão do seu CLI)
CLAUDE_CLI_MODEL = None

# --- backend "ollama" ---
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2-vision"      # precisa ser um modelo com visão

# --- backend "openai" (compatível) ---
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"
# A chave vai em OPENAI_API_KEY (.env). Servidores locais podem dispensar.

# --- backend "gemini" (Google) --- chave em GEMINI_API_KEY (.env), tier grátis
GEMINI_MODEL = "gemini-2.0-flash"

# Máximo de tokens na resposta de geração do writeup
GENERATE_MAX_TOKENS = 8000

# Máximo de tokens na análise de cada frame
ANALYZE_MAX_TOKENS = 1024

# Som de confirmação ao capturar
PLAY_SOUND = True

# Notificação desktop ao capturar
SHOW_NOTIFICATION = True

# Abrir o writeup no editor padrão após gerar
OPEN_AFTER_GENERATE = False

# A chave da API é lida de ANTHROPIC_API_KEY (.env ou ambiente). Nunca hardcodar.

# ---------------------------------------------------------------------------
# Overlay local (~/.config/wuptracker/config.json) — não editar à mão,
# use `wuptracker config`
# ---------------------------------------------------------------------------
CONFIG_LOCAL_PATH = _paths.CONFIG_FILE
_DEFAULTS = {k: v for k, v in dict(globals()).items() if k.isupper()}


def load_local():
    try:
        with open(CONFIG_LOCAL_PATH, encoding="utf-8") as f:
            return _json.load(f)
    except (OSError, ValueError):
        return {}


def save_local(data):
    if data:
        _paths.ensure_dirs()
        with open(CONFIG_LOCAL_PATH, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
    elif _os.path.exists(CONFIG_LOCAL_PATH):
        _os.remove(CONFIG_LOCAL_PATH)


def set_local(key, value):
    data = load_local()
    data[key] = value
    save_local(data)
    globals()[key] = value


def unset_local(key):
    data = load_local()
    data.pop(key, None)
    save_local(data)
    if key in _DEFAULTS:
        globals()[key] = _DEFAULTS[key]


def default_of(key):
    return _DEFAULTS.get(key)


for _k, _v in load_local().items():
    if _k.isupper():
        globals()[_k] = _v
