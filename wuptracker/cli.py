"""wuptracker — captura e gera writeups de sessões de trabalho / pentest.

    wuptracker capture ["Nome da sessão"] [--profile thm|generico]
    wuptracker show [--writeups]
    wuptracker generate [SESSÃO] [--style ...] [--profile ...] [--export DIR] [--open]
    wuptracker styles
    wuptracker config [show | set <k> <v> | unset <k> | get <k> | api-key <chave>]
    wuptracker config helper      # assistente interativo (primeira vez? comece aqui)

SESSÃO pode ser: o número mostrado no `show`, o nome da pasta, um caminho, ou
vazio (usa a mais recente). `--style` aceita vários: --style tecnico,linkedin
"""

import argparse
import os
import sys

from . import common
from . import config
from . import profiles


def _fmt_dur(d):
    return d or "em andamento"


def cmd_show(a):
    sessions = common.list_sessions()
    if not sessions:
        print("Nenhuma sessão em " + config.SESSIONS_DIR + "/")
        return
    w = max(len(s["room"]) for s in sessions)
    print(common.c_cyan(
        f"  #  {'SESSÃO'.ljust(w)}  DATA/HORA         CAPS  PERFIL     STATUS"))
    for i, s in enumerate(sessions, 1):
        when = s["started_at"].replace("T", " ")[:16]
        caps = str(s["captures"])
        if s["pending"]:
            caps += common.c_yellow(f"(+{s['pending']}?)")
        status = []
        if s["ongoing"]:
            status.append(common.c_yellow("ativa"))
        elif s.get("crashed"):
            status.append(common.c_red("interrompida"))
        if s["has_writeup"]:
            status.append(common.c_green("writeup"))
        line = (f"  {i:>2}  {s['room'].ljust(w)}  {when}  "
                f"{caps:>4}  {s['profile'].ljust(9)}  {' '.join(status)}")
        print(line)
    print(common.c_dim(f"\n  {len(sessions)} sessão(ões). "
                       f"wuptracker generate <#>  para gerar o writeup."))


def cmd_styles(a):
    print(common.c_cyan("Estilos de writeup (--style):"))
    desc = {
        "tecnico": "denso e preciso, seções fixas, horários (padrão)",
        "corrido": "narrativa fluida em texto corrido",
        "resumo": "resumo executivo curto (~250 palavras)",
        "blog": "artigo técnico didático (dev.to / Medium)",
        "linkedin": "post pronto para o LinkedIn (texto puro, hashtags)",
    }
    for k, v in desc.items():
        mark = common.c_dim(" [com imagens]") if k in profiles.STYLES_WITH_IMAGES else ""
        print(f"  {common.c_green(k.ljust(9))} {v}{mark}")
    print(common.c_dim("\n  Perfis (--profile): thm | generico"))


def _resolve_session(token):
    sessions = common.list_sessions()
    if token is None:
        if not sessions:
            sys.exit("[!] Nenhuma sessão. Rode 'wuptracker capture' primeiro.")
        return sessions[0]["dir"]
    if token.isdigit():
        idx = int(token) - 1
        if not (0 <= idx < len(sessions)):
            sys.exit(f"[!] Sessão #{token} não existe. Veja 'wuptracker show'.")
        return sessions[idx]["dir"]
    if os.path.isdir(token):
        return token
    cand = os.path.join(config.SESSIONS_DIR, token)
    if os.path.isdir(cand):
        return cand
    sys.exit(f"[!] Sessão não encontrada: {token}")


def cmd_capture(a):
    from . import capture as capture_mod

    capture_mod.capture(a.name, a.profile)


def cmd_generate(a):
    from . import generate as generate_mod

    session_dir = _resolve_session(a.session)
    generate_mod.generate(session_dir, a.style, a.profile, a.export, a.open)


def cmd_config(a):
    from . import configtool

    act, rest = a.action or "show", a.rest
    if act == "show":
        configtool.show()
    elif act == "set":
        if len(rest) < 2:
            sys.exit("uso: wuptracker config set <chave> <valor>")
        configtool.set_(rest[0], " ".join(rest[1:]))
    elif act == "get":
        if not rest:
            sys.exit("uso: wuptracker config get <chave>")
        k = configtool._resolve_key(rest[0])
        print(configtool._fmt(getattr(config, k, None)))
    elif act == "unset":
        if not rest:
            sys.exit("uso: wuptracker config unset <chave>")
        configtool.unset_(rest[0])
    elif act in ("api-key", "apikey"):
        if not rest:
            sys.exit("uso: wuptracker config api-key <chave>")
        configtool.set_api_key(rest[0])
    elif act == "backend":
        if not rest:
            sys.exit("uso: wuptracker config backend "
                     "<claude_cli|anthropic|ollama|openai|gemini>")
        configtool.set_("backend", rest[0])
    elif act in ("helper", "wizard", "setup"):
        configtool.wizard()
    else:
        sys.exit(f"[!] ação de config desconhecida: {act}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="wuptracker", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("capture", help="inicia o modo de captura")
    c.add_argument("name", nargs="?", help="nome da sessão")
    c.add_argument("--profile", help="thm | generico (padrão: config.DEFAULT_PROFILE)")
    c.set_defaults(func=cmd_capture)

    s = sub.add_parser("show", help="lista as sessões")
    s.add_argument("--writeups", action="store_true",
                   help="(reservado) só sessões já com writeup")
    s.set_defaults(func=cmd_show)

    g = sub.add_parser("generate", help="gera o writeup de uma sessão")
    g.add_argument("session", nargs="?",
                   help="número do 'show', nome, caminho, ou vazio p/ a mais recente")
    g.add_argument("--style", help="tecnico|corrido|resumo|blog|linkedin (vírgula p/ vários)")
    g.add_argument("--profile", help="força thm | generico")
    g.add_argument("--export", metavar="DIR", help="copia o(s) writeup(s) e assets para DIR")
    g.add_argument("--open", action="store_true", help="abre o resultado no editor")
    g.set_defaults(func=cmd_generate)

    sub.add_parser("styles", help="lista estilos e perfis").set_defaults(func=cmd_styles)

    cfg = sub.add_parser("config", help="ver/alterar configurações e integrações")
    cfg.add_argument("action", nargs="?", default="show",
                     choices=["show", "set", "get", "unset", "api-key", "backend",
                              "helper"])
    cfg.add_argument("rest", nargs="*", metavar="ARG")
    cfg.set_defaults(func=cmd_config)

    setup = sub.add_parser(
        "setup", help="assistente interativo de configuração (atalho p/ config helper)")
    setup.set_defaults(func=cmd_setup)
    return p


def cmd_setup(a):
    from . import configtool

    configtool.wizard()


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
