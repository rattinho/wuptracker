"""Utilidades compartilhadas entre capture.py e generate.py."""

import base64
import io
import os
import platform
import re
import subprocess
import sys

from dotenv import load_dotenv

from . import config
from . import paths

load_dotenv(paths.ENV_FILE)
load_dotenv()  # também o .env do diretório atual, se houver (dev/legado)

PHASES = [
    "reconhecimento", "enumeracao", "acesso_inicial", "pos_exploracao",
    "privesc", "web", "crypto", "stego", "misc",
]


def slugify(text):
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or "sessao"


def list_sessions():
    """Lista as sessões em SESSIONS_DIR, mais recentes primeiro.

    Cada item: name, dir, room, profile, started_at, duration, captures (int),
    pending (int, capturas sem .json), ongoing (bool), has_writeup (bool).
    """
    import json

    base = config.SESSIONS_DIR
    out = []
    if not os.path.isdir(base):
        return out
    for name in os.listdir(base):
        sdir = os.path.join(base, name)
        meta_path = os.path.join(sdir, "meta.json")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            meta = {}
        caps_dir = os.path.join(sdir, "captures")
        pngs = [f for f in os.listdir(caps_dir)] if os.path.isdir(caps_dir) else []
        shots = sorted(f[:-4] for f in pngs if f.endswith(".png")
                       and not f.endswith("_crop.png"))
        analysed = {f[:-5] for f in pngs if f.endswith(".json")}
        alive = False
        try:
            with open(os.path.join(sdir, "capture.pid")) as f:
                os.kill(int(f.read().strip()), 0)
                alive = True
        except (OSError, ValueError):
            alive = False
        wbase = os.path.join(config.WRITEUPS_DIR, name)
        has_writeup = os.path.isdir(wbase) or any(
            f == f"{name}.md" or f.startswith(f"{name}-")
            for f in (os.listdir(config.WRITEUPS_DIR)
                      if os.path.isdir(config.WRITEUPS_DIR) else []))
        out.append({
            "name": name,
            "dir": sdir,
            "room": meta.get("room", name),
            "profile": meta.get("profile", "?"),
            "started_at": meta.get("started_at", ""),
            "duration": meta.get("duration"),
            "captures": len(shots),
            "pending": sum(1 for s in shots if s not in analysed),
            "ongoing": alive,
            "crashed": "ended_at" not in meta and not alive,
            "has_writeup": has_writeup,
        })
    out.sort(key=lambda s: s["started_at"], reverse=True)
    return out


def fmt_elapsed(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def png_to_jpeg_b64(png_path, quality=None):
    """Converte um PNG para JPEG base64 para reduzir o payload da API."""
    from PIL import Image

    quality = quality or config.SCREENSHOT_QUALITY
    with Image.open(png_path) as im:
        im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def cursor_pos():
    """Posição (x, y) global do cursor, ou None se não for possível obter."""
    try:
        from pynput.mouse import Controller

        x, y = Controller().position
        return int(x), int(y)
    except Exception:
        return None


def grab_screen(png_path, active_only=None):
    """Captura a tela para png_path.

    active_only=True  -> só o monitor onde o cursor está (fallback: tela toda)
    active_only=False -> todos os monitores
    active_only=None  -> usa config.CAPTURE_ACTIVE_MONITOR_ONLY
    """
    if active_only is None:
        active_only = getattr(config, "CAPTURE_ACTIVE_MONITOR_ONLY", True)

    errors = []
    wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or \
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"

    # Em Wayland o mss/X11 não capturam o compositor real.
    if wayland:
        from shutil import which

        # spectacle: -m = monitor atual (sob o cursor); -f = tela cheia
        spectacle_mode = "-m" if active_only else "-f"
        wl = [
            ("spectacle", ["spectacle", "-b", "-n", spectacle_mode, "-o", png_path]),
            ("grim", ["grim", png_path]),                                # wlroots
            ("gnome-screenshot", ["gnome-screenshot", "-f", png_path]),  # GNOME
        ]
        for name, cmd in wl:
            if not which(name):
                continue
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=25)
                if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
                    return name
                errors.append(f"{name}: não gerou arquivo")
            except Exception as e:
                errors.append(f"{name}: {e}")
        raise RuntimeError(
            "Falha ao capturar tela no Wayland — " + " | ".join(errors) +
            ". Instale 'spectacle' (KDE), 'grim' (wlroots) ou 'gnome-screenshot'.")

    # X11: mss — captura por monitor (o retângulo-união falha em multi-monitor).
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            mons = sct.monitors[1:] or [sct.monitors[0]]

            target = None
            if active_only:
                pos = cursor_pos()
                if pos:
                    for m in mons:
                        if (m["left"] <= pos[0] < m["left"] + m["width"] and
                                m["top"] <= pos[1] < m["top"] + m["height"]):
                            target = m
                            break
                if target is None and len(mons) == 1:
                    target = mons[0]

            if target is not None:
                s = sct.grab(target)
                Image.frombytes("RGB", s.size, s.rgb).save(png_path)
            elif len(mons) == 1:
                s = sct.grab(mons[0])
                Image.frombytes("RGB", s.size, s.rgb).save(png_path)
            else:
                imgs = [(m, sct.grab(m)) for m in mons]
                left = min(m["left"] for m, _ in imgs)
                top = min(m["top"] for m, _ in imgs)
                width = max(m["left"] + m["width"] for m, _ in imgs) - left
                height = max(m["top"] + m["height"] for m, _ in imgs) - top
                canvas = Image.new("RGB", (width, height), "black")
                for m, s in imgs:
                    canvas.paste(Image.frombytes("RGB", s.size, s.rgb),
                                 (m["left"] - left, m["top"] - top))
                canvas.save(png_path)
        return "mss"
    except Exception as e:
        errors.append(f"mss: {e}")

    # X11: ferramentas de linha de comando (captura a tela toda)
    from shutil import which

    candidates = [
        ("scrot", ["scrot", "-o", png_path]),
        ("maim", ["maim", png_path]),
        ("import", ["import", "-window", "root", png_path]),
        ("spectacle", ["spectacle", "-b", "-n", "-f", "-o", png_path]),
        ("gnome-screenshot", ["gnome-screenshot", "-f", png_path]),
    ]
    for name, cmd in candidates:
        if not which(name):
            continue
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=20)
            if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
                return name
            errors.append(f"{name}: não gerou arquivo")
        except Exception as e:
            errors.append(f"{name}: {e}")

    raise RuntimeError("Falha ao capturar tela — " + " | ".join(errors))


def image_size(path):
    """(width, height) de uma imagem, ou (0, 0) se não der para abrir."""
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def optimize_image(src, dst_stem, max_width=None, quality=None):
    """Salva uma versão leve de `src`: redimensiona para max_width e converte
    para WebP (ou PNG otimizado se WebP indisponível). `dst_stem` é o caminho
    SEM extensão. Retorna o caminho final gravado, ou None se falhar."""
    from PIL import Image

    if max_width is None:
        max_width = getattr(config, "IMAGE_MAX_WIDTH", 1600)
    if quality is None:
        quality = getattr(config, "WEBP_QUALITY", 80)
    want_webp = getattr(config, "WEBP_IMAGES", True)

    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            if max_width and im.width > max_width:
                h = round(im.height * max_width / im.width)
                im = im.resize((max_width, h), Image.LANCZOS)
            if want_webp:
                try:
                    out = dst_stem + ".webp"
                    im.save(out, "WEBP", quality=quality, method=6)
                    return out
                except Exception:
                    pass
            out = dst_stem + ".png"
            im.save(out, optimize=True)
            return out
    except Exception:
        return None


def crop_image(src_png, dst_png, box, pad=None):
    """Recorta src_png para a região `box` (frações 0..1: x, y, w, h) e salva
    em dst_png. Retorna True se recortou, False se a região é inválida/grande
    demais (nesse caso não gera arquivo)."""
    from PIL import Image

    try:
        x, y = float(box["x"]), float(box["y"])
        w, h = float(box["w"]), float(box["h"])
    except (KeyError, TypeError, ValueError):
        return False
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1):
        return False
    # região cobre quase tudo -> não vale a pena recortar
    if w * h >= 0.9:
        return False

    if pad is None:
        pad = getattr(config, "CROP_PADDING", 0.03)
    x0 = max(0.0, x - pad)
    y0 = max(0.0, y - pad)
    x1 = min(1.0, x + w + pad)
    y1 = min(1.0, y + h + pad)

    with Image.open(src_png) as im:
        W, H = im.size
        box_px = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
        cw, ch = box_px[2] - box_px[0], box_px[3] - box_px[1]
        if cw < 60 or ch < 60:
            return False
        # recorte já com a margem cobre quase tudo -> não compensa
        if (cw * ch) / (W * H) >= 0.85:
            return False
        im.crop(box_px).save(dst_png)
    return True


def check_capture_backend():
    """Verifica no início se há algum backend de captura disponível."""
    from shutil import which

    wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or \
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"

    if wayland:
        for t in ("spectacle", "grim", "gnome-screenshot"):
            if which(t):
                return t
        return None

    try:
        import mss  # noqa: F401
        import PIL  # noqa: F401

        return "mss"
    except Exception:
        pass
    for t in ("scrot", "maim", "import", "spectacle", "gnome-screenshot"):
        if which(t):
            return t
    return None


def notify(title, message):
    if not config.SHOW_NOTIFICATION:
        return
    try:
        subprocess.run(["notify-send", title, message, "--icon=camera"],
                       check=False, capture_output=True, timeout=5)
    except Exception:
        try:
            from plyer import notification

            notification.notify(title=title, message=message, timeout=3)
        except Exception:
            pass


def beep():
    if config.PLAY_SOUND:
        print("\a", end="", flush=True)


def system_name():
    return platform.system().lower()


def open_in_editor(path):
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass


# Cores ANSI
def c_green(s):
    return f"\033[92m{s}\033[0m"


def c_yellow(s):
    return f"\033[93m{s}\033[0m"


def c_red(s):
    return f"\033[91m{s}\033[0m"


def c_cyan(s):
    return f"\033[96m{s}\033[0m"


def c_dim(s):
    return f"\033[2m{s}\033[0m"
