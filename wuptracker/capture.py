"""Captura de tela em background durante uma sessão de trabalho.

Uso:
    python capture.py "Skynet"
    python capture.py "Refatorar API" --profile generico
    python capture.py            # pede o nome interativamente

Perfis (--profile): "thm" (pentest/CTF) | "generico" (qualquer trabalho).
Padrão em config.DEFAULT_PROFILE.

Durante a sessão:
    F9  -> captura a tela, analisa com o Claude e salva
    F10 / Ctrl+C -> encerra a sessão
    (Wayland) pkill -USR1/-USR2 -f capture.py
"""

import datetime as dt
import json
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from pynput import keyboard

from . import common
from . import config
from . import llm
from . import profiles


class Session:
    def __init__(self, room, profile="thm"):
        self.room = room
        self.profile = profiles.resolve(profile)
        self.analyze_prompt = profiles.get(self.profile)["analyze_prompt"]
        self.start = dt.datetime.now()
        stamp = self.start.strftime("%Y-%m-%d_%H-%M")
        self.name = f"{stamp}_{common.slugify(room)}"
        self.dir = os.path.join(config.SESSIONS_DIR, self.name)
        self.captures_dir = os.path.join(self.dir, "captures")
        os.makedirs(self.captures_dir, exist_ok=True)
        self.captures = []          # entradas do session.json
        self.lock = threading.Lock()
        self.count = 0              # nº de capturas que começaram a processar
        self.submitted = 0         # nº de F9/sinais disparados
        self.completed = 0         # nº de capturas que terminaram (ok ou erro)
        self._write_meta()
        self._write_session()

    @property
    def pending(self):
        return self.submitted - self.completed

    def submit(self, pool):
        with self.lock:
            self.submitted += 1
        pool.submit(self._run)

    def _run(self):
        try:
            self.do_capture()
        except Exception as e:
            print(common.c_red(f"[!] erro na captura: {e}"))
        finally:
            with self.lock:
                self.completed += 1

    # ---------- persistência ----------
    def _write_meta(self, ended=None):
        meta = {
            "room": self.room,
            "profile": self.profile,
            "started_at": self.start.isoformat(timespec="seconds"),
            "system": common.system_name(),
        }
        if ended:
            meta["ended_at"] = ended.isoformat(timespec="seconds")
            meta["duration"] = common.fmt_elapsed(
                (ended - self.start).total_seconds())
        with open(os.path.join(self.dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    def _write_session(self):
        ordered = sorted(self.captures, key=lambda c: c["filename"])
        with open(os.path.join(self.dir, "session.json"), "w", encoding="utf-8") as f:
            json.dump({"captures": ordered}, f, indent=2, ensure_ascii=False)

    def add_capture(self, entry):
        with self.lock:
            self.captures.append(entry)
            self._write_session()

    # ---------- captura ----------
    def elapsed_label(self):
        secs = (dt.datetime.now() - self.start).total_seconds()
        return common.fmt_elapsed(secs)

    def do_capture(self):
        label = self.elapsed_label()
        fname = label.replace(":", "-")
        png_path = os.path.join(self.captures_dir, f"{fname}.png")
        json_path = os.path.join(self.captures_dir, f"{fname}.json")

        with self.lock:
            self.count += 1
            n = self.count
        queued = self.pending - 1
        q = f"  ({queued} na fila)" if queued > 0 else ""
        print(common.c_yellow(f"[{label}] capturando… (#{n}){q}"))

        try:
            common.grab_screen(png_path)
        except Exception as e:
            print(common.c_red(f"[{label}] falha na captura de tela: {e}"))
            return

        common.beep()

        analysis = self._analyze(png_path, label)

        # imagem a exibir no writeup: recorte quando o modelo indicar uma região
        image = f"{fname}.png"
        crop_note = "sem recorte"
        if getattr(config, "CROP_IMAGES", True) and isinstance(analysis.get("crop"), dict):
            crop_path = os.path.join(self.captures_dir, f"{fname}_crop.png")
            try:
                if common.crop_image(png_path, crop_path, analysis["crop"]):
                    image = f"{fname}_crop.png"
                    ow, oh = common.image_size(png_path)
                    cw, ch = common.image_size(crop_path)
                    pct = round(100 * (cw * ch) / (ow * oh)) if ow and oh else 0
                    crop_note = f"recorte {cw}×{ch} ({pct}% de {ow}×{oh})"
            except Exception as e:
                print(common.c_yellow(f"[{label}] recorte falhou: {e}"))
        analysis["image"] = image

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)

        title = analysis.get("title") or "[análise pendente]"
        # "phase" (thm) ou "category" (generico) — guarda o que houver
        bucket = analysis.get("phase") or analysis.get("category") or "misc"
        self.add_capture({
            "timestamp": label,
            "filename": fname,
            "title": title,
            "phase": bucket,
            "image": image,
            "is_key_moment": bool(analysis.get("is_key_moment")),
        })

        star = " ★" if analysis.get("is_key_moment") else ""
        print(common.c_green(f"[{label}] ✓ {title}{star}") +
              common.c_dim(f"  · {crop_note}"))
        common.notify("Writeup Capture", f"[{label}] {title}")

    def _analyze(self, png_path, label):
        try:
            text = llm.analyze_image(png_path, self.analyze_prompt)
            return _parse_json(text)
        except Exception as e:
            print(common.c_red(f"[{label}] análise falhou: {e}"))
            return {
                "error": str(e),
                "description": "[análise pendente]",
                "phase": "misc",
                "title": f"Captura {label} (análise pendente)",
                "commands": [], "findings": [], "tool": None,
                "is_key_moment": False, "key_moment_reason": None,
            }

    def finish(self):
        end = dt.datetime.now()
        self._write_meta(ended=end)
        try:
            os.remove(os.path.join(self.dir, "capture.pid"))
        except OSError:
            pass
        dur = common.fmt_elapsed((end - self.start).total_seconds())
        done = len(self.captures)
        print()
        print(common.c_cyan(f"Sessão encerrada. {done} capturas em {dur}"))
        if done != self.count:
            print(common.c_yellow(
                f"({self.count - done} captura(s) não finalizaram a análise)"))
        print(common.c_dim(f"Gerar o writeup:  wuptracker generate {self.name}"))


def _parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    return {
        "error": "resposta não-JSON",
        "raw": text,
        "description": "[análise pendente]",
        "phase": "misc", "title": "[análise pendente]",
        "commands": [], "findings": [], "tool": None,
        "is_key_moment": False, "key_moment_reason": None,
    }


def capture(room=None, profile=None):
    """Inicia o modo de captura e bloqueia até o encerramento da sessão."""
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    backend = common.check_capture_backend()
    if not backend:
        sys.exit("[!] Nenhum backend de captura disponível. Instale 'mss' "
                 "(pip install -r requirements.txt) ou 'scrot'.")
    # valida o backend do LLM cedo
    llm.preflight()

    profile = profiles.resolve_domain(
        profile or getattr(config, "DEFAULT_PROFILE", "thm"))

    room = room or input("Nome da sessão: ").strip()
    if not room:
        sys.exit("[!] Nome da sessão vazio.")

    session = Session(room, profile)
    pool = ThreadPoolExecutor(max_workers=4)
    stop = threading.Event()

    # SIGUSR1 = capturar | SIGUSR2 = encerrar (para atalhos globais no Wayland).
    signal.signal(signal.SIGUSR1, lambda *_: session.submit(pool))
    signal.signal(signal.SIGUSR2, lambda *_: stop.set())

    pid = os.getpid()
    prog = os.path.basename(sys.argv[0]) or "wuptracker.py"
    pidfile = os.path.join(session.dir, "capture.pid")
    try:
        with open(pidfile, "w") as f:
            f.write(str(pid))
    except OSError:
        pass

    print(common.c_green(f"[✓] Sessão iniciada: {session.name}"))
    print(f"    Perfil: {session.profile}  |  Captura: {backend}  |  PID: {pid}")

    wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or \
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"

    listener = None
    if wayland:
        print(common.c_yellow(
            "    Wayland: teclas globais (F9) podem não funcionar. Use sinais —\n"
            f"      capturar:  kill -USR1 {pid}   (ou  pkill -USR1 -f {prog})\n"
            f"      encerrar:  kill -USR2 {pid}   (ou  pkill -USR2 -f {prog})\n"
            "    Dica: crie um atalho global (KDE/GNOME) apontando para esse comando.\n"
            "    (ou mantenha este terminal focado para o F9 funcionar)"))

    try:
        capture_key = getattr(keyboard.Key, config.CAPTURE_KEY)
        exit_key = getattr(keyboard.Key, config.EXIT_KEY)

        def on_press(key):
            if key == capture_key:
                session.submit(pool)
            elif key == exit_key:
                stop.set()
                return False

        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        print(f"    F9 = capturar | F10 ou Ctrl+C = encerrar")
    except Exception as e:
        print(common.c_yellow(f"    Listener de teclado indisponível ({e}). "
                              "Use os sinais acima ou Ctrl+C."))

    last_note = 0.0
    try:
        while not stop.is_set():
            time.sleep(0.2)
            now = time.time()
            if session.pending and now - last_note > 8:
                print(common.c_dim(
                    f"    … {session.pending} análise(s) em processamento"))
                last_note = now
    except KeyboardInterrupt:
        print()
    finally:
        if listener is not None:
            listener.stop()
        _drain(session, pool)
        session.finish()


def _drain(session, pool):
    """Espera as análises pendentes terminarem, com progresso e proteção contra
    um segundo Ctrl+C que deixaria arquivos pela metade."""
    if session.pending <= 0:
        pool.shutdown(wait=True)
        return

    print(common.c_yellow(
        f"⏳ {session.pending} análise(s) ainda processando — "
        "NÃO feche o terminal."))
    forced = False
    try:
        while session.completed < session.submitted:
            done, total = session.completed, session.submitted
            print(f"\r   {done}/{total} concluídas…   ", end="", flush=True)
            time.sleep(0.3)
        print(f"\r   {session.submitted}/{session.submitted} concluídas.      ")
    except KeyboardInterrupt:
        forced = True
        left = session.submitted - session.completed
        print(common.c_red(
            f"\n[!] Interrompido à força com {left} análise(s) incompleta(s). "
            "Os screenshots (.png) foram salvos; as análises faltantes ficarão "
            "sem .json. O generate.py ainda funciona com o que houver."))
    pool.shutdown(wait=not forced, cancel_futures=forced)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    profile = None
    if "--profile" in args:
        i = args.index("--profile")
        try:
            profile = args[i + 1]
        except IndexError:
            sys.exit("[!] --profile requer um valor (thm | generico).")
        del args[i:i + 2]
    capture(args[0] if args else None, profile)


if __name__ == "__main__":
    main()
