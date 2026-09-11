"""Caminhos padrão do sistema (XDG Base Directory), com fallback sensato.

- Config (config.json, .env): $XDG_CONFIG_HOME/wuptracker  (~/.config/wuptracker)
- Dados (sessions/):          $XDG_DATA_HOME/wuptracker    (~/.local/share/wuptracker)
- Writeups:                   ./writeups no diretório onde o comando é chamado
  (o writeup é um artefato do seu trabalho ali, não um dado global da ferramenta)
"""

import os

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "wuptracker")
DATA_DIR = os.path.join(
    os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
    "wuptracker")

CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
ENV_FILE = os.path.join(CONFIG_DIR, ".env")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")


def ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
