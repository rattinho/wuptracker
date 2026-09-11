"""`wuptracker config` — inspeciona e altera configurações e integrações."""

import os
import shutil

from . import common
from . import config
from . import paths
from . import profiles

ENV_PATH = paths.ENV_FILE

# chave -> (tipo, opções|None, ajuda)
SETTABLE = {
    "BACKEND": ("choice",
                ["claude_cli", "anthropic", "ollama", "openai", "gemini"],
                "motor do LLM"),
    "CLAUDE_MODEL": ("str", None, "modelo do backend 'anthropic'"),
    "CLAUDE_CLI_MODEL": ("str_or_none", None,
                         "modelo p/ 'claude_cli' (vazio = padrão do CLI)"),
    "OLLAMA_HOST": ("str", None, "URL do Ollama (backend 'ollama')"),
    "OLLAMA_MODEL": ("str", None, "modelo com visão no Ollama (llava, llama3.2-vision…)"),
    "OPENAI_BASE_URL": ("str", None, "endpoint compatível OpenAI (backend 'openai')"),
    "OPENAI_MODEL": ("str", None, "modelo do backend 'openai'"),
    "GEMINI_MODEL": ("str", None, "modelo do backend 'gemini' (gemini-2.0-flash…)"),
    "DEFAULT_PROFILE": ("domain", None, "perfil padrão: thm | generico"),
    "DEFAULT_STYLE": ("style", None,
                      "estilo(s) padrão do writeup, vírgula p/ vários"),
    "CAPTURE_ACTIVE_MONITOR_ONLY": ("bool", None,
                                    "capturar só o monitor sob o cursor"),
    "CROP_IMAGES": ("bool", None, "recortar imagens para a região relevante"),
    "CROP_PADDING": ("float", None, "margem do recorte (fração, ex: 0.03)"),
    "EMBED_IMAGES": ("bool", None, "embutir imagens no writeup"),
    "WEBP_IMAGES": ("bool", None, "converter imagens do writeup para WebP"),
    "WEBP_QUALITY": ("int", None, "qualidade do WebP (0-100)"),
    "IMAGE_MAX_WIDTH": ("int", None, "largura máx. das imagens do writeup (0 = livre)"),
    "SCREENSHOT_QUALITY": ("int", None, "qualidade JPEG no envio à API (1-100)"),
    "PLAY_SOUND": ("bool", None, "bip ao capturar"),
    "SHOW_NOTIFICATION": ("bool", None, "notificação de desktop ao capturar"),
    "OPEN_AFTER_GENERATE": ("bool", None, "abrir o writeup no editor após gerar"),
    "SESSIONS_DIR": ("str", None, "pasta das sessões"),
    "WRITEUPS_DIR": ("str", None, "pasta dos writeups"),
}

ALIASES = {
    "backend": "BACKEND", "model": "CLAUDE_MODEL", "cli-model": "CLAUDE_CLI_MODEL",
    "ollama-host": "OLLAMA_HOST", "ollama-model": "OLLAMA_MODEL",
    "openai-url": "OPENAI_BASE_URL", "openai-model": "OPENAI_MODEL",
    "gemini-model": "GEMINI_MODEL",
    "profile": "DEFAULT_PROFILE", "style": "DEFAULT_STYLE",
    "monitor": "CAPTURE_ACTIVE_MONITOR_ONLY", "crop": "CROP_IMAGES",
    "images": "EMBED_IMAGES", "sound": "PLAY_SOUND", "notify": "SHOW_NOTIFICATION",
    "open": "OPEN_AFTER_GENERATE", "webp": "WEBP_IMAGES",
    "webp-quality": "WEBP_QUALITY", "max-width": "IMAGE_MAX_WIDTH",
}


def _resolve_key(key):
    k = ALIASES.get(key.lower(), key.upper())
    if k not in SETTABLE:
        raise SystemExit(
            f"[!] Chave desconhecida: {key!r}. Veja 'wuptracker config'.\n"
            f"    Disponíveis: {', '.join(sorted(SETTABLE))}")
    return k


def _coerce(key, raw):
    kind, opts, _ = SETTABLE[key]
    if kind == "bool":
        if raw.lower() in ("1", "true", "on", "yes", "sim", "y"):
            return True
        if raw.lower() in ("0", "false", "off", "no", "nao", "não", "n"):
            return False
        raise SystemExit(f"[!] {key} espera on/off (recebido {raw!r})")
    if kind == "int":
        return int(raw)
    if kind == "float":
        return float(raw)
    if kind == "str_or_none":
        return None if raw.strip().lower() in ("", "none", "-") else raw
    if kind == "choice":
        if raw not in opts:
            raise SystemExit(f"[!] {key} deve ser um de: {', '.join(opts)}")
        return raw
    if kind == "domain":
        return profiles.resolve_domain(raw)
    if kind == "style":
        return ",".join(profiles.resolve_style(s) for s in raw.split(","))
    return raw


def _fmt(v):
    if isinstance(v, bool):
        return "on" if v else "off"
    if v is None:
        return "—"
    return str(v)


# --------------------------------------------------------------------------
# .env / API keys
# --------------------------------------------------------------------------
BACKEND_ENV_KEY = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
                   "gemini": "GEMINI_API_KEY"}


def read_env_key(name):
    try:
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{name}="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return os.environ.get(name, "")


def set_env_key(name, value):
    lines, found = [], False
    try:
        with open(ENV_PATH, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        pass
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{name}="):
            lines[i] = f"{name}={value}"
            found = True
            break
    if not found:
        lines.append(f"{name}={value}")
    paths.ensure_dirs()
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(ENV_PATH, 0o600)
    print(common.c_green(f"✓ {name} gravada em {ENV_PATH} (chmod 600)"))


def set_api_key(value, name=None):
    """`config api-key <valor>` — grava a chave do backend ativo (ou de `name`)."""
    if name is None:
        from . import llm

        b = llm.resolve_backend(config.BACKEND)
        name = BACKEND_ENV_KEY.get(b)
        if not name:
            raise SystemExit(
                f"[!] o backend '{b}' não usa API key. "
                "Troque para 'anthropic' ou 'openai' primeiro, ou use "
                "'wuptracker config set <NOME_API_KEY> <valor>'.")
    set_env_key(name, value)


# --------------------------------------------------------------------------
# ações
# --------------------------------------------------------------------------
def _yes(b):
    return common.c_green("ok") if b else common.c_red("faltando")


def show():
    from . import llm

    local = config.load_local()
    b = llm.resolve_backend(config.BACKEND)

    print(common.c_cyan("Integrações"))
    if b == "claude_cli":
        print(f"  LLM          claude_cli  · comando `claude`: "
              f"{_yes(bool(shutil.which('claude')))}  (grátis, usa sua assinatura)")
    elif b == "anthropic":
        k = read_env_key("ANTHROPIC_API_KEY")
        print(f"  LLM          anthropic  · {config.CLAUDE_MODEL}  · "
              f"ANTHROPIC_API_KEY: {_yes(bool(k))}")
    elif b == "ollama":
        host = config.OLLAMA_HOST
        up = False
        try:
            import urllib.request
            urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=3)
            up = True
        except Exception:
            up = False
        print(f"  LLM          ollama  · {config.OLLAMA_MODEL}  · {host}: "
              f"{_yes(up)}  (local, offline, grátis)")
    elif b == "openai":
        base = config.OPENAI_BASE_URL
        local_srv = "localhost" in base or "127.0.0.1" in base
        k = read_env_key("OPENAI_API_KEY")
        print(f"  LLM          openai  · {config.OPENAI_MODEL}  · {base}  · "
              f"OPENAI_API_KEY: {_yes(bool(k) or local_srv)}")
    elif b == "gemini":
        k = read_env_key("GEMINI_API_KEY") or read_env_key("GOOGLE_API_KEY")
        print(f"  LLM          gemini  · {config.GEMINI_MODEL}  · "
              f"GEMINI_API_KEY: {_yes(bool(k))}  (tier grátis no Google AI Studio)")

    cap = common.check_capture_backend() or common.c_red("nenhum!")
    print(f"  Captura      {cap}  · monitor ativo: "
          f"{_fmt(config.CAPTURE_ACTIVE_MONITOR_ONLY)}")
    ns = "notify-send" if shutil.which("notify-send") else "plyer (fallback)"
    print(f"  Notificação  {ns}  · som: {_fmt(config.PLAY_SOUND)} · "
          f"desktop: {_fmt(config.SHOW_NOTIFICATION)}")

    print(common.c_cyan("\nConfiguração") +
          common.c_dim("  (local sobrepõe o padrão)"))
    for k in SETTABLE:
        cur = getattr(config, k, None)
        src = common.c_yellow("local") if k in local else common.c_dim("padrão")
        line = f"  {k.lower().replace('_', '-'):<28} {_fmt(cur):<14} {src}"
        if k in local and config.default_of(k) is not None:
            line += common.c_dim(f"  (padrão: {_fmt(config.default_of(k))})")
        print(line)
    print(common.c_dim("\n  wuptracker config set <chave> <valor>   ·   "
                       "config unset <chave>   ·   config api-key <chave>"))
    print(common.c_dim("  wuptracker config helper   → assistente interativo "
                       "(passo a passo, com explicações)"))


def set_(key, value):
    kl = key.lower().replace("-", "_")
    if kl in ("api_key", "apikey"):
        set_api_key(value)
        return
    if kl.endswith("_api_key"):                 # ex: OPENAI_API_KEY
        set_env_key(key.upper(), value)
        return

    k = _resolve_key(key)
    val = _coerce(k, value)
    config.set_local(k, val)
    print(common.c_green(f"✓ {k} = {_fmt(val)}") +
          common.c_dim(f"  → {config.CONFIG_LOCAL_PATH}"))

    if k == "BACKEND":
        from . import llm

        b = llm.resolve_backend(val)
        if b == "claude_cli" and not shutil.which("claude"):
            print(common.c_yellow("  ⚠ comando `claude` não encontrado no PATH"))
        if b == "anthropic" and not read_env_key("ANTHROPIC_API_KEY"):
            print(common.c_yellow("  ⚠ falta a chave: wuptracker config api-key <chave>"))
        if b == "openai" and not read_env_key("OPENAI_API_KEY") \
                and "localhost" not in config.OPENAI_BASE_URL:
            print(common.c_yellow("  ⚠ falta a chave: wuptracker config api-key <chave> "
                                  "(ou aponte openai-url para um servidor local)"))
        if b == "ollama":
            print(common.c_dim("  → 'wuptracker config set ollama-model <modelo-com-visão>' "
                               "· 'ollama pull <modelo>'"))
        if b == "gemini" and not (read_env_key("GEMINI_API_KEY")
                                  or read_env_key("GOOGLE_API_KEY")):
            print(common.c_yellow("  ⚠ falta a chave (grátis em "
                                  "aistudio.google.com/apikey): "
                                  "wuptracker config api-key <chave>"))


def unset_(key):
    k = _resolve_key(key)
    config.unset_local(k)
    print(common.c_green(f"✓ {k} voltou ao padrão ({_fmt(config.default_of(k))})"))


# --------------------------------------------------------------------------
# wizard interativo — `wuptracker config helper`
# --------------------------------------------------------------------------
BACKEND_MORE = """
claude_cli  Usa o CLI do Claude Code (comando `claude`). Consome a cota da sua
            assinatura Pro/Max — zero custo por token, zero API key. As imagens
            sobem para a Anthropic. É o padrão, e o mais simples de começar.

gemini      API do Google Gemini. Tem um tier gratuito generoso, sem cartão —
            pegue a chave em https://aistudio.google.com/apikey. Boa opção grátis
            se você não usa Claude Code. As imagens sobem para o Google.

ollama      Roda um modelo NA SUA máquina via Ollama. Nada sai do computador —
            ideal para engajamentos onde as telas são confidenciais. Precisa de
            um modelo com visão baixado (ex.: `ollama pull llama3.2-vision`).
            Mais lento e um pouco menos preciso que os modelos de nuvem.

openai      Qualquer endpoint no formato da API OpenAI: OpenAI, Groq (rápido,
            tem tier grátis), OpenRouter (vários modelos), LM Studio / llama.cpp
            (local). Você escolhe a URL, o modelo e a chave.

anthropic   API paga da Anthropic, cobrada por token — use se quiser os modelos
            Claude sem depender do CLI/assinatura.
"""

PROFILE_MORE = """
thm        Para pentest e CTF (TryHackMe, HTB...). Seções clássicas:
           Reconhecimento, Enumeração, Acesso Inicial, Pós-Exploração,
           Escalação de Privilégio, Flags, Lições Aprendidas. A análise de cada
           tela foca em portas, serviços, comandos, credenciais e flags.

generico   Para qualquer outra coisa: dev, debugging, pesquisa, configuração,
           estudo. O writeup é um registro cronológico: Resumo, Linha do Tempo,
           Descobertas, Problemas Encontrados, Estado Final. Não força jargão
           de pentest onde não existe.

Dá pra trocar por sessão: wuptracker capture "Nome" --profile generico
"""

STYLE_MORE = """
tecnico    O mais completo: Markdown com frontmatter, seções fixas do perfil e
           âncoras de horário [HH:MM:SS]. Bloco de código pra todo comando.
           O formato "documentação". Embute as imagens.

corrido    A mesma informação, em prosa — narrativa fluida, sem tabelas nem
           lista de fases. Bom pra publicar como relato. Embute as imagens.

resumo     Curto (~250 palavras): 1 parágrafo de contexto + bullets do que foi
           feito/descoberto + conclusão. Sem imagens. Pra colar num chat/e-mail.

blog       Artigo didático estilo dev.to/Medium: introdução que situa o leitor,
           seções temáticas, código comentado, "o que aprendi". Embute imagens.

linkedin   Post pronto pra publicar: 1ª pessoa, gancho na 1ª linha, bullets de
           aprendizado, hashtags. Texto puro (sem markdown) e GENERALIZA dados
           sensíveis (IPs, flags, nomes de cliente). Sem imagens.

Na geração dá pra pedir vários de uma vez:
  wuptracker generate 1 --style tecnico,linkedin
"""


def _hr():
    print(common.c_dim("─" * 62))


def _ask(question, default=""):
    hint = f" [{default}]" if default else ""
    try:
        r = input(common.c_cyan(f"› {question}{hint} ")).strip()
    except EOFError:
        r = ""
    return r or default


def _ask_yesno(question, default=True):
    hint = "S/n" if default else "s/N"
    r = _ask(f"{question} ({hint})").strip().lower()
    if not r:
        return default
    return r in ("s", "sim", "y", "yes", "1", "on")


def _ask_choice(question, options, more_text=None):
    """options: [(valor, descrição curta), ...]. '?' mostra more_text."""
    while True:
        print(common.c_cyan(f"\n{question}"))
        for i, (val, desc) in enumerate(options, 1):
            print(f"  {i}) {common.c_green(val)} — {desc}")
        if more_text:
            print(f"  {common.c_dim('?) saiba mais sobre cada opção')}")
        r = _ask("escolha", "1")
        if r == "?" and more_text:
            _hr()
            print(more_text.strip("\n"))
            _hr()
            continue
        if r.isdigit() and 1 <= int(r) <= len(options):
            return options[int(r) - 1][0]
        for val, _ in options:
            if r.lower() == val.lower():
                return val
        print(common.c_red("  opção inválida, tente de novo"))


def _ask_model(question, presets, current, note=None):
    """Menu de modelos sugeridos + opção de digitar outro nome.

    presets: lista de strings. `current` (se não estiver em presets) aparece
    marcado como o valor em uso. Retorna a string escolhida/digitada."""
    options = list(presets)
    if current and current not in options:
        options = [current] + options
    print(common.c_cyan(f"\n{question}"))
    if note:
        print(common.c_dim(f"  {note}"))
    for i, m in enumerate(options, 1):
        tag = common.c_dim("  (em uso)") if m == current else ""
        print(f"  {i}) {m}{tag}")
    other_idx = len(options) + 1
    print(f"  {other_idx}) outro… (digitar o nome do modelo)")

    default_idx = str(options.index(current) + 1) if current in options else "1"
    while True:
        r = _ask("escolha", default_idx)
        if r.isdigit():
            n = int(r)
            if 1 <= n <= len(options):
                return options[n - 1]
            if n == other_idx:
                return _ask("Nome do modelo", current or "")
        elif r:                       # também aceita digitar o nome direto
            return r
        print(common.c_red("  opção inválida, tente de novo"))


def _set_if_changed(key, value):
    if value == config.default_of(key):
        config.unset_local(key)
    else:
        config.set_local(key, value)


def wizard():
    """`wuptracker config helper` — assistente interativo de configuração."""
    print(common.c_cyan("╔══════════════════════════════════════════════╗"))
    print(common.c_cyan("║        wuptracker — assistente de setup       ║"))
    print(common.c_cyan("╚══════════════════════════════════════════════╝"))
    print("Enter aceita o valor entre [colchetes]. Digite " +
          common.c_dim("?") + " numa pergunta de múltipla escolha para saber mais.")

    cur = config

    # 1. Backend de IA -----------------------------------------------------
    backend = _ask_choice(
        "Qual IA vai analisar as telas e escrever os writeups?",
        [("claude_cli", "grátis, usa sua assinatura do Claude Code"),
         ("gemini", "Google, tier gratuito generoso (precisa de key grátis)"),
         ("ollama", "100% local e offline — nada sai da sua máquina"),
         ("openai", "OpenAI / Groq / OpenRouter / LM Studio…"),
         ("anthropic", "API paga da Anthropic")],
        BACKEND_MORE)
    _set_if_changed("BACKEND", backend)

    if backend == "claude_cli":
        if shutil.which("claude"):
            print(common.c_green("  ✓ comando 'claude' encontrado no PATH"))
        else:
            print(common.c_yellow("  ⚠ 'claude' não encontrado — instale o Claude Code"))
        model = _ask_model(
            "Modelo do CLI",
            ["padrão do CLI", "opus", "sonnet", "haiku"],
            cur.CLAUDE_CLI_MODEL or "padrão do CLI")
        _set_if_changed("CLAUDE_CLI_MODEL",
                        None if model == "padrão do CLI" else model)

    elif backend == "gemini":
        print(common.c_dim("  Chave grátis em https://aistudio.google.com/apikey"))
        k = _ask("GEMINI_API_KEY (Enter para configurar depois)")
        if k:
            set_env_key("GEMINI_API_KEY", k)
        model = _ask_model(
            "Modelo Gemini",
            ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
            cur.GEMINI_MODEL)
        _set_if_changed("GEMINI_MODEL", model)

    elif backend == "ollama":
        host = _ask("URL do Ollama", cur.OLLAMA_HOST)
        _set_if_changed("OLLAMA_HOST", host)
        model = _ask_model(
            "Modelo (precisa ter visão)",
            ["llama3.2-vision", "llava", "qwen2.5vl", "minicpm-v", "moondream"],
            cur.OLLAMA_MODEL,
            note="se ainda não tiver: ollama pull <modelo>")
        _set_if_changed("OLLAMA_MODEL", model)
        try:
            import json as _j
            import urllib.request

            with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags",
                                        timeout=3) as r:
                names = {m2.get("name", "").split(":")[0]
                        for m2 in _j.loads(r.read()).get("models", [])}
            if model.split(":")[0] in names:
                print(common.c_green(f"  ✓ Ollama respondeu e '{model}' está baixado"))
            else:
                print(common.c_yellow(f"  ⚠ Ollama respondeu, mas '{model}' não está "
                                      f"baixado — rode: ollama pull {model}"))
        except Exception:
            print(common.c_yellow(f"  ⚠ Ollama não respondeu em {host} — "
                                  "rode 'ollama serve' antes de usar"))

    elif backend == "openai":
        provider = _ask_choice(
            "Qual endpoint compatível com a API OpenAI?",
            [("openai", "api.openai.com — modelos GPT oficiais"),
             ("groq", "api.groq.com — bem rápido, tem tier grátis"),
             ("openrouter", "openrouter.ai — vários modelos, um endpoint só"),
             ("local", "LM Studio / llama.cpp / vLLM na sua máquina"),
             ("outro", "digitar a URL manualmente")])
        presets = {
            "openai": ("https://api.openai.com/v1", ["gpt-4o-mini", "gpt-4o"]),
            "groq": ("https://api.groq.com/openai/v1",
                    ["llama-3.2-90b-vision-preview",
                     "llama-3.2-11b-vision-preview"]),
            "openrouter": ("https://openrouter.ai/api/v1",
                          ["google/gemini-2.0-flash-001", "openai/gpt-4o-mini"]),
            "local": ("http://localhost:1234/v1", ["local-model"]),
        }
        if provider == "outro":
            url = _ask("URL do endpoint (OPENAI_BASE_URL)", cur.OPENAI_BASE_URL)
            model_presets = [cur.OPENAI_MODEL] if cur.OPENAI_MODEL else []
        else:
            url, model_presets = presets[provider]
        _set_if_changed("OPENAI_BASE_URL", url)
        model = _ask_model("Modelo", model_presets, cur.OPENAI_MODEL)
        _set_if_changed("OPENAI_MODEL", model)

        local_srv = "localhost" in url or "127.0.0.1" in url
        prompt = "OPENAI_API_KEY" + (" (Enter para pular — endpoint local)"
                                     if local_srv else " (Enter p/ configurar depois)")
        k = _ask(prompt)
        if k:
            set_env_key("OPENAI_API_KEY", k)

    elif backend == "anthropic":
        k = _ask("ANTHROPIC_API_KEY (Enter para configurar depois)")
        if k:
            set_env_key("ANTHROPIC_API_KEY", k)
        model = _ask_model(
            "Modelo",
            ["claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5-20251001"],
            cur.CLAUDE_MODEL)
        _set_if_changed("CLAUDE_MODEL", model)

    # 2. Perfil --------------------------------------------------------------
    profile = _ask_choice(
        "Perfil padrão dos writeups (dá pra trocar por sessão)?",
        [("thm", "pentest / CTF — fases, flags, escalação de privilégio"),
         ("generico", "qualquer trabalho no PC — linha do tempo")],
        PROFILE_MORE)
    _set_if_changed("DEFAULT_PROFILE", profile)

    # 3. Estilo ----------------------------------------------------------------
    style = _ask_choice(
        "Estilo padrão do writeup (dá pra pedir vários na hora de gerar)?",
        [("tecnico", "denso, seções fixas, com horários — o mais completo"),
         ("corrido", "narrativa em texto corrido"),
         ("resumo", "resumo executivo curto, sem imagens"),
         ("blog", "artigo didático estilo dev.to/Medium"),
         ("linkedin", "post pronto pro LinkedIn, texto puro")],
        STYLE_MORE)
    _set_if_changed("DEFAULT_STYLE", style)

    # 4. Preferências rápidas --------------------------------------------------
    print(common.c_cyan("\nUns últimos ajustes rápidos:"))
    v = _ask_yesno("  Capturar só o monitor sob o cursor? (você tem +1 monitor?)",
                   cur.CAPTURE_ACTIVE_MONITOR_ONLY)
    _set_if_changed("CAPTURE_ACTIVE_MONITOR_ONLY", v)

    v = _ask_yesno("  Otimizar as imagens do writeup pra WebP (bem mais leve)?",
                   cur.WEBP_IMAGES)
    _set_if_changed("WEBP_IMAGES", v)

    v = _ask_yesno("  Notificação de desktop a cada captura (F9)?",
                   cur.SHOW_NOTIFICATION)
    _set_if_changed("SHOW_NOTIFICATION", v)

    # 5. Resultado -------------------------------------------------------------
    print(common.c_green("\n✓ Configuração salva.\n"))
    show()
    try:
        from . import llm

        llm.preflight()
        print(common.c_green("\n✓ Tudo pronto — rode 'wuptracker capture \"Nome\"' "
                             "pra começar."))
    except SystemExit as e:
        print(common.c_yellow(f"\n{e}"))
