"""Gera o writeup final em Markdown a partir de uma sessão capturada.

Uso:
    python generate.py sessions/2026-09-10_14-32_skynet/
    python generate.py sessions/... --profile generico
    python generate.py sessions/... --style corrido
    python generate.py sessions/... --style tecnico,linkedin,resumo
    python generate.py          # lista sessões disponíveis e pede escolha

--profile (thm|generico): domínio; padrão vem de meta.json.
--style (tecnico|corrido|resumo|blog|linkedin, separados por vírgula): formato;
        padrão em config.DEFAULT_STYLE.
"""

import datetime as dt
import json
import os
import sys

from . import common
from . import config
from . import llm
from . import profiles


def pick_session():
    base = config.SESSIONS_DIR
    if not os.path.isdir(base):
        sys.exit(f"[!] Pasta '{base}' não existe. Rode capture.py primeiro.")
    dirs = sorted(d for d in os.listdir(base)
                  if os.path.isdir(os.path.join(base, d)))
    if not dirs:
        sys.exit(f"[!] Nenhuma sessão em '{base}'.")
    print("Sessões disponíveis:")
    for i, d in enumerate(dirs, 1):
        print(f"  {i}. {d}")
    choice = input("Escolha o número: ").strip()
    try:
        return os.path.join(base, dirs[int(choice) - 1])
    except (ValueError, IndexError):
        sys.exit("[!] Escolha inválida.")


def load_analysis(captures_dir, filename):
    path = os.path.join(captures_dir, f"{filename}.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def build_context(session_dir):
    captures_dir = os.path.join(session_dir, "captures")

    with open(os.path.join(session_dir, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)

    session_path = os.path.join(session_dir, "session.json")
    if os.path.exists(session_path):
        with open(session_path, encoding="utf-8") as f:
            entries = json.load(f).get("captures", [])
    else:
        entries = []

    entries = sorted(entries, key=lambda c: c.get("filename", ""))
    embed = getattr(config, "EMBED_IMAGES", True)

    blocks, tools, phases, images = [], set(), set(), []
    for e in entries:
        a = load_analysis(captures_dir, e["filename"])
        phase = a.get("phase") or e.get("phase") or "misc"
        phases.add(phase)
        tool = a.get("tool")
        if tool:
            tools.add(str(tool).lower())
        # commands (thm) / actions (generico)
        cmds = (a.get("commands") or []) + (a.get("actions") or [])
        finds = a.get("findings") or []
        app = a.get("tool") or a.get("app")
        km = a.get("is_key_moment")
        reason = a.get("key_moment_reason")

        img_line = ""
        img_file = a.get("image") or e.get("image")
        if img_file and not os.path.exists(os.path.join(captures_dir, img_file)):
            img_file = e["filename"] + ".png"  # fallback p/ sessões antigas
        if embed and img_file and os.path.exists(os.path.join(captures_dir, img_file)):
            stem = os.path.splitext(img_file)[0]
            ext = ".webp" if getattr(config, "WEBP_IMAGES", True) else \
                os.path.splitext(img_file)[1]
            out_name = stem + ext
            images.append((img_file, out_name))       # (origem, nome no assets/)
            img_line = f"\nImagem: assets/{out_name}"

        blocks.append(
            f"[{e.get('timestamp','??:??:??')}] {str(phase).upper()}: "
            f"{a.get('title') or e.get('title','(sem título)')}\n"
            f"Descrição: {a.get('description','')}\n"
            f"App/ferramenta: {app or '—'}\n"
            f"Ações/comandos: {'; '.join(cmds) if cmds else '—'}\n"
            f"Findings: {'; '.join(finds) if finds else '—'}\n"
            f"Momento-chave: {'sim' if km else 'não'}"
            f"{' — ' + reason if km and reason else ''}"
            f"{img_line}"
        )

    return (meta, entries, "\n\n".join(blocks),
            sorted(tools), sorted(phases), images)


def _strip_fence(md):
    if md.startswith("```"):
        lines = md.split("\n")
        md = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return md.strip()


def generate(session_dir, styles=None, profile_override=None, export_dir=None,
             open_after=None):
    """Gera um ou mais writeups para a sessão. Retorna a lista de arquivos .md."""
    session_dir = session_dir.rstrip("/")
    if not os.path.isdir(session_dir):
        sys.exit(f"[!] Sessão não encontrada: {session_dir}")

    meta, entries, ctx, tools, phases, images = build_context(session_dir)
    if not entries:
        sys.exit("[!] Sessão sem capturas.")

    profile = profiles.resolve_domain(
        profile_override or meta.get("profile") or "thm")
    if isinstance(styles, str):
        styles = styles.split(",")
    styles = [profiles.resolve_style(s) for s in
              (styles or getattr(config, "DEFAULT_STYLE", "tecnico").split(","))]

    room = meta.get("room", os.path.basename(session_dir))
    duration = meta.get("duration", "desconhecida")
    base = os.path.basename(session_dir)

    common_fields = dict(
        room_name=room, duration=duration, total_captures=len(entries),
        tools_list=", ".join(tools) if tools else "não identificadas",
        captures_context=ctx, fase_tags=", ".join(phases),
        data_hoje=dt.date.today().isoformat(),
    )

    llm.preflight()
    outputs, dirs_with_assets = [], set()
    for style in styles:
        prompt = profiles.build_writeup_prompt(profile, style, **common_fields)
        embed = bool(style in profiles.STYLES_WITH_IMAGES and images)

        print(common.c_cyan(
            f"Gerando writeup [{profile}/{style}] de '{room}' "
            f"({len(entries)} capturas)…"))
        markdown = _strip_fence(llm.generate_text(prompt))

        out_dir = os.path.join(config.WRITEUPS_DIR, base) if embed \
            else config.WRITEUPS_DIR
        os.makedirs(out_dir, exist_ok=True)

        stem = "writeup" if style == "tecnico" else f"writeup-{style}"
        fname = f"{stem}.md" if embed else \
            (f"{base}.md" if style == "tecnico" else f"{base}-{style}.md")
        out = os.path.join(out_dir, fname)

        if embed:
            markdown = _embed_images(markdown, images, entries, session_dir, out_dir)
            dirs_with_assets.add(out_dir)

        with open(out, "w", encoding="utf-8") as f:
            f.write(markdown + "\n")
        outputs.append(out)
        print(common.c_green(f"✓ {out}"))
        if embed:
            print(f"  {len(set(images))} imagem(ns) em "
                  f"{os.path.join(out_dir, 'assets')}/")

    if export_dir:
        _export(outputs, dirs_with_assets, export_dir)

    if open_after if open_after is not None else config.OPEN_AFTER_GENERATE:
        if outputs:
            common.open_in_editor(outputs[0])
    return outputs


def _export(outputs, dirs_with_assets, export_dir):
    import shutil

    export_dir = os.path.expanduser(export_dir)
    os.makedirs(export_dir, exist_ok=True)
    for md in outputs:
        shutil.copy2(md, os.path.join(export_dir, os.path.basename(md)))
    for d in dirs_with_assets:
        src = os.path.join(d, "assets")
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(export_dir, "assets"),
                            dirs_exist_ok=True)
    print(common.c_green(f"↗ exportado para {export_dir}"))


def main():
    args = sys.argv[1:]
    prof_override = _take_opt(args, "--profile")
    style_arg = _take_opt(args, "--style")
    export_dir = _take_opt(args, "--export")
    open_after = True if "--open" in args else None
    args = [a for a in args if a != "--open"]

    session_dir = args[0] if args else pick_session()
    generate(session_dir, style_arg, prof_override, export_dir, open_after)


def _take_opt(args, flag):
    if flag in args:
        i = args.index(flag)
        try:
            val = args[i + 1]
        except IndexError:
            sys.exit(f"[!] {flag} requer um valor.")
        del args[i:i + 2]
        return val
    return None


def _embed_images(markdown, images, entries, session_dir, out_dir):
    """images: lista de (arquivo_origem, nome_no_assets). Otimiza cada imagem
    (WebP/resize) para writeups/<sessão>/assets/ e injeta as que o modelo não
    referenciou numa galeria no fim."""
    import shutil

    assets_dir = os.path.join(out_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    captures_dir = os.path.join(session_dir, "captures")

    saved_bytes = orig_bytes = 0
    for src_name, out_name in dict.fromkeys(images):
        src = os.path.join(captures_dir, src_name)
        if not os.path.exists(src):
            continue
        stem = os.path.join(assets_dir, os.path.splitext(out_name)[0])
        written = common.optimize_image(src, stem)
        if not written:                       # otimização falhou -> cópia crua
            written = os.path.join(assets_dir, src_name)
            shutil.copy2(src, written)
        orig_bytes += os.path.getsize(src)
        saved_bytes += os.path.getsize(written)

    if orig_bytes:
        pct = round(100 * saved_bytes / orig_bytes)
        print(common.c_dim(
            f"  imagens: {_hsize(orig_bytes)} → {_hsize(saved_bytes)} ({pct}%)"))

    out_names = [o for _, o in dict.fromkeys(images)]
    used = {o for o in out_names if f"assets/{o}" in markdown}
    missing = [o for o in out_names if o not in used]
    if missing:
        gallery = ["", "## Capturas", ""]
        # mapeia nome-no-assets -> entrada, via stem do arquivo de origem
        stem_to_entry = {os.path.splitext(e.get("image", ""))[0]: e for e in entries}
        for o in missing:
            e = stem_to_entry.get(os.path.splitext(o)[0], {})
            cap = e.get("title", o)
            ts = e.get("timestamp", "")
            gallery += [f"**[{ts}]** {cap}" if ts else f"**{cap}**", "",
                        f"![{cap}](assets/{o})", ""]
        markdown = markdown.rstrip() + "\n" + "\n".join(gallery)
    return markdown


def _hsize(n):
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


if __name__ == "__main__":
    main()
