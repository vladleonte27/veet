"""Veet - hold Alt+Shift to voice-type into any app."""
import os
import sys
import math
import re
import time
import queue
import threading
import wave
import winsound
from pathlib import Path


# ---- packaging-aware paths ----
def resource_path(*parts: str) -> Path:
    """Path to a bundled resource. Works in dev and in PyInstaller (onedir
    next to exe; onefile via _MEIPASS)."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            p = Path(meipass).joinpath(*parts)
            if p.exists():
                return p
        return Path(sys.executable).resolve().parent.joinpath(*parts)
    return Path(__file__).resolve().parent.joinpath(*parts)


def data_dir() -> Path:
    """User-writable data directory (logs, runtime cache)."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    d = Path(base) / "Veet"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Register bundled CUDA DLLs before importing faster_whisper. Looks first in
# the dev venv (.venv) and then in the bundled `nvidia/` folder shipped next
# to the exe (GPU build).
def _cuda_path() -> None:
    if not hasattr(os, "add_dll_directory"):
        return
    candidates = []
    dev = Path(__file__).resolve().parent / ".venv/Lib/site-packages/nvidia"
    if dev.is_dir():
        candidates.append(dev)
    if getattr(sys, "frozen", False):
        for root in (
            Path(sys.executable).resolve().parent,
            Path(getattr(sys, "_MEIPASS", str(Path(sys.executable).parent))),
        ):
            cand = root / "nvidia"
            if cand.is_dir():
                candidates.append(cand)
    if not candidates:
        return
    dirs = []
    for base in candidates:
        for sub in ("cuda_runtime/bin", "cublas/bin", "cudnn/bin", "cuda_nvrtc/bin"):
            p = base / sub
            if p.is_dir():
                dirs.append(str(p))
                try:
                    os.add_dll_directory(str(p))
                except OSError:
                    pass
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")


_cuda_path()

import ctypes
import tkinter as tk
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
import pystray
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageGrab, ImageFilter, ImageChops


# ---------- config ----------
# Model selection: distil-large-v3 on GPU (best quality, ~28x realtime),
# distil-small.en on CPU (~470MB, usable speed on most laptops). VEET_MODEL
# overrides both regardless of device.
MODEL_GPU = os.environ.get("VEET_MODEL_GPU", "distil-large-v3")
MODEL_CPU = os.environ.get("VEET_MODEL_CPU", "distil-small.en")
MODEL_OVERRIDE = os.environ.get("VEET_MODEL")
LANGUAGE = os.environ.get("VEET_LANG", "en")
DEVICE = os.environ.get("VEET_DEVICE", "auto")            # auto: cuda if available, else cpu
COMPUTE = os.environ.get("VEET_COMPUTE", "auto")          # auto: float16 on cuda, int8 on cpu
MIN_SECONDS = 0.3
POLISH = os.environ.get("VEET_POLISH", "1") != "0"   # filler-word cleanup
PROMPT = (
    "Vlad, VL Media, Veet, ChatGPT, Claude, Anthropic, OpenAI, "
    "Facebook, OLX, Romania, Bucharest, PowerShell, Windows, Python."
)
LOG_PATH = data_dir() / "veet.log"


# ---------- text polish ----------
# Self-correction: discard everything from the last sentence boundary up
# through a "no, no, ..." (or "oh no") sequence. Whatever follows is kept.
_CORRECTION_RE = re.compile(
    r"(?:^|(?<=[.!?]\s))[^.!?]*?,\s*(?:oh[,\s]+)?(?:no[,\s]+){2,}",
    flags=re.IGNORECASE,
)

# Common discourse fillers. Conservative on "like" (only between commas / at
# clause boundaries) to avoid wrecking legitimate uses like "I like coffee".
_FILLER_RE = re.compile(
    r"\b(?:um+|uh+|er+|erm+|ehm+|hmm+|ahh+)\b[,.\s]*"
    r"|,?\s*\byou know\b\s*,?\s*"
    r"|,?\s*\bi mean\b\s*,?\s*"
    r"|,?\s*\bet[\s-]?cetera\b\.?\s*"
    r"|\b(?:basically|literally|honestly)\b\s+"
    r"|,\s*like\s*,\s*"                          # ", like,"
    r"|(?:^|(?<=[.!?]\s))[Ll]ike\s*,\s*"         # "Like, ..." at clause start
    r"|\blike\s*,\s*"                            # "X like, Y" — common filler
    r"|,?\s*\b(?:kind of|sort of)\b\s*,?\s*",    # "kind of" / "sort of"
    flags=re.IGNORECASE,
)


def _dedupe(text: str) -> str:
    """Collapse consecutive repeated words and 2–4-word phrases."""
    # Single-word stutters: "the the the" → "the"
    text = re.sub(r"\b(\w+)(?:\s+\1\b)+", r"\1", text, flags=re.IGNORECASE)
    # Repeated short phrases (longest first to avoid double-collapse)
    for n in (4, 3, 2):
        pat = re.compile(
            r"((?:\b\w+\b\s*){" + str(n) + r"})\s*[,.]?\s*\1",
            flags=re.IGNORECASE,
        )
        prev = None
        while prev != text:
            prev = text
            text = pat.sub(r"\1", text)
    return text


_LIST_TRIGGER_RE = re.compile(
    r"\b(?:the |a |my |our |this is the |here['’]s the |this is a |"
    r"these are the |here are the )?"
    r"(?:grocery|shopping|to[\s-]?do|task|reading|wish|packing|"
    r"todo|to do)?\s*list[: ]+"
    r"|\b(?:items?|things|groceries|tasks|steps)\s*[:.]?\s+",
    flags=re.IGNORECASE,
)
_LIST_SPLIT_RE = re.compile(r",\s*|\s+(?:and|or|then|plus)\s+", flags=re.IGNORECASE)


def make_bullets(text: str) -> str:
    """If the user dictated a list (triggered by a phrase like 'the grocery
    list', 'shopping list', 'to-do list', 'items:'), reformat the items as
    bullets. Otherwise return text unchanged."""
    m = _LIST_TRIGGER_RE.search(text)
    if not m:
        return text
    intro = text[:m.end()].rstrip(": ").rstrip() + ":"
    tail = text[m.end():]
    # Stop at the next sentence boundary.
    end_match = re.search(r"[.!?](?:\s|$)", tail)
    list_body = tail[:end_match.start()] if end_match else tail
    rest = tail[end_match.start() + 1:].strip() if end_match else ""
    items = [p.strip(" .,;") for p in _LIST_SPLIT_RE.split(list_body)]
    items = [p[0].upper() + p[1:] if p else "" for p in items if p]
    if len(items) < 2:
        return text
    bullets = "\n".join(f"• {it}" for it in items)
    result = f"{intro}\n{bullets}"
    if rest:
        result += f"\n\n{rest}"
    return result


def polish(text: str) -> str:
    """Strip fillers, drop self-corrected clauses, collapse stutters, tidy
    punctuation. Conservative — only patterns that almost always signal
    noise; keeps the speaker's intent."""
    s = _CORRECTION_RE.sub(" ", text)
    s = _FILLER_RE.sub(" ", s)
    s = _dedupe(s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.!?;:])", r"\1", s)
    s = re.sub(r"([,.!?;:])[\s,]*\1+", r"\1", s)
    s = re.sub(r",\s*\.", ".", s)
    s = re.sub(r"(^|[.!?]\s+)([a-z])",
               lambda m: m.group(1) + m.group(2).upper(), s)
    return s


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------- input (persistent stream for zero-cost record toggle) ----------
class AudioIn:
    """Always-on input stream. `start()` flips a flag — capture is instant."""

    SR = 16000

    def __init__(self) -> None:
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._lock = threading.Lock()
        self._stream = sd.InputStream(
            samplerate=self.SR, channels=1, dtype="float32",
            callback=self._cb, blocksize=160, latency="low",
        )
        self._stream.start()

    def _cb(self, indata, _frames, _t, _s) -> None:
        if self._recording:
            self._frames.append(indata.copy())

    def start(self) -> None:
        with self._lock:
            self._frames = []
            self._recording = True

    def stop(self) -> list[np.ndarray]:
        with self._lock:
            self._recording = False
            f, self._frames = self._frames, []
        return f


def _tone(freq: float, dur: float, gain: float = 0.085, sr: int = 22050) -> np.ndarray:
    """Pure sine with a Hann-shaped envelope.
    - 8ms leading silence absorbs driver pop on play-start.
    - 250ms trailing silence pushes the session-close click far past the
      perceived end of the chime, so the brain treats it as background."""
    n = int(sr * dur)
    t = np.arange(n) / sr
    body = (np.sin(2 * np.pi * freq * t) * np.sin(np.pi * t / dur) ** 1.3 * gain).astype(np.float32)
    pad_lead = np.zeros(int(sr * 0.008), dtype=np.float32)
    pad_tail = np.zeros(int(sr * 0.250), dtype=np.float32)
    return np.concatenate([pad_lead, body, pad_tail])


def _save_wav(path: Path, buf: np.ndarray, sr: int = 22050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())


def _load_wav(path: Path, sr: int = 22050) -> np.ndarray | None:
    try:
        with wave.open(str(path), "rb") as f:
            if f.getnchannels() != 1 or f.getframerate() != sr or f.getsampwidth() != 2:
                return None
            data = f.readframes(f.getnframes())
        return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32767.0
    except Exception:
        return None


def _ensure_chime(name: str, generator) -> Path:
    """Return a path to the chime WAV. Prefers the bundled copy (read-only).
    If missing, generates and saves to data_dir (user-writable)."""
    bundled = resource_path("assets", f"{name}.wav")
    if bundled.is_file():
        return bundled
    user = data_dir() / "assets" / f"{name}.wav"
    if not user.is_file():
        try:
            _save_wav(user, generator())
        except Exception as e:
            log(f"chime save error ({name}): {e}")
    return user


# Solfeggio "healing" frequencies — 528 Hz ("love") on press, 396 Hz ("release") on stop
START_CHIME_PATH = _ensure_chime("chime-start", lambda: _tone(528.0, dur=0.13))
END_CHIME_PATH = _ensure_chime("chime-stop", lambda: _tone(396.0, dur=0.16))


def play_chime(path: Path) -> None:
    """Play a chime via Windows' native WinMM (winsound). Survives audio
    engine idle/suspend; replaces any currently playing sound automatically."""
    try:
        winsound.PlaySound(
            str(path),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
    except Exception as e:
        log(f"chime error: {e}")


audio_in = AudioIn()


# ---------- shared state ----------
class App:
    def __init__(self) -> None:
        self.paused = False
        self.model = None
        self.model_ready = threading.Event()
        self.ui_queue: queue.Queue = queue.Queue()

    def post_ui(self, fn) -> None:
        self.ui_queue.put(fn)


app = App()
root: tk.Tk | None = None
overlay: "Overlay | None" = None


# ---------- press / release handlers ----------
def on_press() -> None:
    if app.paused:
        return
    if not app.model_ready.is_set():
        app.post_ui(lambda: overlay.show_loading())
        return
    audio_in.start()                                  # flag flip, instant
    play_chime(START_CHIME_PATH)                      # native WinMM, no glitch
    log("recording")
    app.post_ui(lambda: overlay.show_recording())


def on_release() -> None:
    threading.Thread(target=_handle_release, daemon=True).start()


def _handle_release() -> None:
    frames = audio_in.stop()
    if not frames:
        app.post_ui(lambda: overlay.hide())
        return
    play_chime(END_CHIME_PATH)

    audio = np.concatenate(frames, axis=0).flatten().astype(np.float32)
    duration = len(audio) / AudioIn.SR
    if duration < MIN_SECONDS:
        log(f"too short ({duration:.2f}s)")
        app.post_ui(lambda: overlay.hide())
        return

    app.post_ui(lambda: overlay.show_transcribing())
    log(f"transcribing {duration:.1f}s")
    t0 = time.time()
    try:
        segments, _ = app.model.transcribe(
            audio, language=LANGUAGE, vad_filter=True, beam_size=5,
            condition_on_previous_text=False, initial_prompt=PROMPT,
        )
        text = "".join(s.text for s in segments).strip()
    except Exception as e:
        log(f"transcribe error: {e}")
        app.post_ui(lambda: overlay.hide())
        return
    elapsed = time.time() - t0
    app.post_ui(lambda: overlay.hide())

    if not text:
        log(f"silence ({elapsed:.1f}s)")
        return
    if POLISH:
        text = polish(text)
        if not text:
            log(f"all-filler ({elapsed:.1f}s)")
            return
        text = make_bullets(text)
    log(f"-> {text}  ({elapsed:.1f}s)")
    pyperclip.copy(text)
    for k in ("alt", "shift"):
        try:
            keyboard.release(k)
        except Exception:
            pass
    time.sleep(0.05)
    keyboard.send("ctrl+v")


# ---------- hotkey via low-level hook (no polling) ----------
_SHIFT = {"shift", "left shift", "right shift"}
_ALT = {"alt", "left alt", "right alt", "alt gr"}


class HotkeyHook:
    def __init__(self) -> None:
        self.shift = False
        self.alt = False
        self.active = False
        keyboard.hook(self._on)

    def _on(self, e) -> None:
        if e.name in _SHIFT:
            self.shift = e.event_type == "down"
        elif e.name in _ALT:
            self.alt = e.event_type == "down"
        else:
            return
        both = self.shift and self.alt
        if both and not self.active:
            self.active = True
            on_press()
        elif not both and self.active:
            self.active = False
            on_release()


# ---------- overlay (capture-and-blur "glass" pill, animated width) ----------
class Overlay:
    WINDOW_W = 152             # fixed outer window width (must fit all states)
    PILL_H = 44
    SS = 2
    BLUR_RADIUS = 22
    TINT = (16, 18, 24, 105)
    # Per-state pill widths (visible portion); window stays at WINDOW_W.
    WIDTHS = {"recording": 112, "transcribing": 148, "loading": 132}
    ANIM_DURATION = 0.22
    LABELS = {
        "recording": "Listening",
        "transcribing": "Transcribing",
        "loading": "Loading model",
    }

    def __init__(self, root_: tk.Tk) -> None:
        self.root = root_
        self.state = "hidden"
        self.start_t = 0.0
        self._photo: ImageTk.PhotoImage | None = None
        self._orig: Image.Image | None = None
        self._tinted: Image.Image | None = None
        self._cache: dict[str, Image.Image] = {}

        # Width animation state
        self.target_w = self.WIDTHS["recording"]
        self.pill_w = self.target_w
        self.anim_from = self.target_w
        self.anim_start = 0.0
        # Text + indicator crossfade state
        self.prev_label: str | None = None
        self.prev_state: str | None = None
        self.prev_start_t = 0.0                       # keeps old indicator's animation phase
        self.label_swap_t = 0.0

        root_.overrideredirect(True)
        root_.attributes("-topmost", True)
        root_.configure(bg="#000000")
        root_.geometry(f"{self.WINDOW_W}x{self.PILL_H}")
        root_.withdraw()

        self.img_label = tk.Label(root_, bd=0, highlightthickness=0, bg="#000000")
        self.img_label.place(x=0, y=0, width=self.WINDOW_W, height=self.PILL_H)

        self.font = self._load_font(14 * self.SS)

        # Pre-build pill_mask + glass_overlay for every even width in range.
        # Animation snaps to nearest 2px which is imperceptible.
        self._mask_cache: dict[int, Image.Image] = {}
        self._glass_cache: dict[int, Image.Image] = {}
        lo = min(self.WIDTHS.values())
        hi = max(self.WIDTHS.values())
        for w in range(lo, hi + 1, 2):
            self._build_mask(w)
            self._build_glass(w)
        for w in self.WIDTHS.values():
            self._build_mask(w)
            self._build_glass(w)

        # Window styles: no-activate, no taskbar, click-through
        root_.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetAncestor(root_.winfo_id(), 2)  # GA_ROOT
            GWL_EXSTYLE = -20
            STYLES = 0x08000000 | 0x00000080 | 0x00000020  # NOACTIVATE | TOOLWINDOW | TRANSPARENT
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | STYLES)
        except Exception as e:
            log(f"window style error: {e}")

    # ---------- per-width caches ----------
    def _build_mask(self, width: int) -> Image.Image:
        if width in self._mask_cache:
            return self._mask_cache[width]
        SS = self.SS
        H2 = self.PILL_H * SS
        W2 = self.WINDOW_W * SS
        pw2 = width * SS
        pad = (W2 - pw2) // 2
        m = Image.new("L", (W2, H2), 0)
        ImageDraw.Draw(m).rounded_rectangle(
            (pad, 0, pad + pw2 - 1, H2 - 1), radius=H2 // 2, fill=255,
        )
        mask = m.resize((self.WINDOW_W, self.PILL_H), Image.LANCZOS)
        self._mask_cache[width] = mask
        return mask

    def _build_glass(self, width: int) -> Image.Image:
        """Top specular highlight + bottom inner shadow, drawn only inside the
        pill of the given width and clipped to its shape."""
        if width in self._glass_cache:
            return self._glass_cache[width]
        W, H = self.WINDOW_W, self.PILL_H
        pad = (W - width) // 2
        r = (H - 2) // 2

        def stroke(color):
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(img).rounded_rectangle(
                (pad + 1, 1, pad + width - 2, H - 2),
                radius=r, outline=color, width=1,
            )
            return img

        def vgrad(curve):
            col = Image.linear_gradient("L").resize((1, H))
            return Image.eval(col, curve).resize((W, H))

        top = stroke((255, 255, 255, 130))
        top_mask = vgrad(lambda v: max(0, 255 - int(v * 2.2)))
        tr, tg, tb, ta = top.split()
        top = Image.merge("RGBA", (tr, tg, tb, ImageChops.multiply(ta, top_mask)))

        bot = stroke((0, 0, 0, 95))
        bot_mask = vgrad(lambda v: max(0, int(v * 2.2) - 255))
        br, bg, bb, ba = bot.split()
        bot = Image.merge("RGBA", (br, bg, bb, ImageChops.multiply(ba, bot_mask)))

        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.alpha_composite(top)
        out.alpha_composite(bot)
        r2, g2, b2, a2 = out.split()
        glass = Image.merge("RGBA", (r2, g2, b2, ImageChops.multiply(a2, self._build_mask(width))))
        self._glass_cache[width] = glass
        return glass

    def _current_width(self) -> int:
        """Eased interpolation between anim_from and target_w, snapped to even px."""
        if self.pill_w == self.target_w:
            return self.target_w
        elapsed = time.perf_counter() - self.anim_start
        t = min(elapsed / self.ANIM_DURATION, 1.0)
        eased = 0.5 - 0.5 * math.cos(math.pi * t)
        w = self.anim_from + (self.target_w - self.anim_from) * eased
        w_int = int(round(w / 2) * 2)
        if t >= 1.0:
            self.pill_w = self.target_w
            return self.target_w
        return w_int

    @staticmethod
    def _load_font(size_px: int) -> ImageFont.ImageFont:
        ttf = resource_path("assets", "Inter.ttf")
        if ttf.is_file():
            try:
                f = ImageFont.truetype(str(ttf), size=size_px)
                try:
                    f.set_variation_by_axes([size_px, 500])  # Medium weight
                except (AttributeError, OSError, ValueError):
                    pass
                return f
            except Exception:
                pass
        try:
            return ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", size_px)
        except Exception:
            return ImageFont.load_default()

    def _capture_backdrop(self, x: int, y: int) -> None:
        """Grab original screen at the window position once. Pre-compute a
        blurred+tinted version. Per-frame compositing combines them with the
        current width's pill_mask and glass overlay."""
        orig = ImageGrab.grab(bbox=(x, y, x + self.WINDOW_W, y + self.PILL_H),
                              all_screens=True).convert("RGBA")
        blurred = orig.filter(ImageFilter.GaussianBlur(radius=self.BLUR_RADIUS))
        self._orig = orig
        self._tinted = Image.alpha_composite(
            blurred, Image.new("RGBA", orig.size, self.TINT)
        )

    def _text_image(self, label: str) -> Image.Image:
        if label in self._cache:
            return self._cache[label]
        SS = self.SS
        w = int(self.font.getlength(label)) + 2 * SS
        h = 28 * SS
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(img).text(
            (SS, h // 2), label, font=self.font, anchor="lm",
            fill=(245, 245, 250, 255),
        )
        img = img.resize((w // SS, h // SS), Image.LANCZOS)
        self._cache[label] = img
        return img

    def _show(self, state: str) -> None:
        first = self.state == "hidden"
        new_target = self.WIDTHS[state]
        new_label = self.LABELS[state]
        prev_label = self.LABELS.get(self.state) if not first else None
        if first:
            self.target_w = new_target
            self.pill_w = new_target
            self.anim_from = new_target
            self.prev_label = None
        elif new_target != self.target_w:
            # Start a width transition from current visual width
            self.anim_from = self._current_width()
            self.target_w = new_target
            self.pill_w = self.anim_from
            self.anim_start = time.perf_counter()
        if not first and prev_label != new_label:
            self.prev_label = prev_label
            self.prev_state = self.state              # state we're leaving
            self.prev_start_t = self.start_t          # preserve its animation phase
            self.label_swap_t = time.perf_counter()
        self.state = state
        self.start_t = time.perf_counter()
        if first:
            # Use the Windows work area (excludes taskbar) so we can sit
            # tight against the taskbar regardless of its size/position.
            try:
                class _RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long),
                    ]
                r = _RECT()
                ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
                sw, work_bottom = r.right - r.left, r.bottom
            except Exception:
                sw = self.root.winfo_screenwidth()
                work_bottom = self.root.winfo_screenheight() - 48  # taskbar guess
            x = (sw - self.WINDOW_W) // 2
            y = work_bottom - self.PILL_H - 12              # 12px above taskbar
            self.root.geometry(f"{self.WINDOW_W}x{self.PILL_H}+{x}+{y}")
            try:
                self._capture_backdrop(x, y)
            except Exception as e:
                log(f"backdrop capture failed: {e}")
                fallback = Image.new("RGBA", (self.WINDOW_W, self.PILL_H), (0, 0, 0, 0))
                self._orig = fallback
                self._tinted = Image.new("RGBA", (self.WINDOW_W, self.PILL_H), (24, 26, 32, 230))
            self.root.deiconify()
            self._tick()

    def show_recording(self) -> None: self._show("recording")
    def show_transcribing(self) -> None: self._show("transcribing")
    def show_loading(self) -> None: self._show("loading")

    def hide(self) -> None:
        self.state = "hidden"
        self.root.withdraw()

    def _draw_indicator(
        self,
        target: Image.Image,
        cx: int,
        cy: int,
        size: int,
        state: str,
        start_t: float,
        alpha: float = 1.0,
        y_offset: int = 0,
    ) -> None:
        if alpha <= 0.01:
            return
        SS = self.SS
        s = (size + 8) * SS
        tmp = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        elapsed = time.perf_counter() - start_t
        cc = s // 2

        if state == "recording":
            phase = (elapsed * 1.1) % 1.0
            t = 0.5 - 0.5 * math.cos(phase * 2 * math.pi)
            r = (5 + 2.2 * t) * SS
            for hr, ha in ((r + 5 * SS, 22), (r + 3 * SS, 50), (r + 1 * SS, 110)):
                td.ellipse((cc - hr, cc - hr, cc + hr, cc + hr), fill=(255, 255, 255, ha))
            td.ellipse((cc - r, cc - r, cc + r, cc + r), fill=(255, 255, 255, 250))
        else:
            ring_w = 2 * SS
            r = (size // 2) * SS
            box = (cc - r, cc - r, cc + r, cc + r)
            td.ellipse(box, outline=(255, 255, 255, 40), width=ring_w)
            speed = 360 if state == "transcribing" else 220
            extent = 100 if state == "transcribing" else 90
            angle = (elapsed * speed) % 360
            td.arc(box, start=angle, end=angle + extent,
                   fill=(255, 255, 255, 240), width=ring_w)

        tmp = tmp.resize((s // SS, s // SS), Image.LANCZOS)
        if alpha < 1.0:
            tmp = self._faded(tmp, alpha)
        target.alpha_composite(tmp, (cx - tmp.width // 2, cy - tmp.height // 2 + y_offset))

    @staticmethod
    def _faded(img: Image.Image, alpha: float) -> Image.Image:
        if alpha >= 1.0:
            return img
        r, g, b, a = img.split()
        return Image.merge("RGBA", (r, g, b, Image.eval(a, lambda v: int(v * alpha))))

    def _render(self) -> Image.Image:
        now = time.perf_counter()
        w = self._current_width()
        img = self._orig.copy()
        img.paste(self._tinted, (0, 0), self._build_mask(w))
        img.alpha_composite(self._build_glass(w))

        # ---- text fade choreography ----
        # Phase 1 (0..100ms):    old text slides down + fades out
        # Phase 2 (100..220ms):  pill widens, no text
        # Phase 3 (220..370ms):  new text fades in
        FADE_OUT = 0.10
        FADE_IN_START = 0.22
        FADE_IN = 0.15
        elapsed = now - self.label_swap_t
        new_label = self.LABELS[self.state]
        new_img = self._text_image(new_label)

        out_alpha = 0.0
        out_y_off = 0
        in_alpha = 1.0
        if self.prev_label and elapsed < FADE_IN_START + FADE_IN:
            if elapsed < FADE_OUT:
                p = elapsed / FADE_OUT
                p_eased = 1 - (1 - p) ** 3            # ease-out
                out_alpha = 1.0 - p_eased
                out_y_off = int(p_eased * 8)
            in_alpha = 0.0
            if elapsed > FADE_IN_START:
                p = min((elapsed - FADE_IN_START) / FADE_IN, 1.0)
                in_alpha = 1 - (1 - p) ** 3           # ease-out
        elif self.prev_label and elapsed >= FADE_IN_START + FADE_IN:
            self.prev_label = None                    # transition done

        ind = 16
        gap = 9
        center_x = self.WINDOW_W // 2
        cy = self.PILL_H // 2

        # NEW group geometry
        total_new = ind + gap + new_img.width
        start_x_new = center_x - total_new // 2
        new_ind_cx = start_x_new + ind // 2
        new_text_x = start_x_new + ind + gap

        # Outgoing group (indicator + text), each in their OLD positions
        if out_alpha > 0.01 and self.prev_label and self.prev_state:
            old_img = self._text_image(self.prev_label)
            total_old = ind + gap + old_img.width
            start_x_old = center_x - total_old // 2
            old_ind_cx = start_x_old + ind // 2
            old_text_x = start_x_old + ind + gap
            self._draw_indicator(
                img, old_ind_cx, cy, ind,
                state=self.prev_state, start_t=self.prev_start_t,
                alpha=out_alpha, y_offset=out_y_off,
            )
            img.alpha_composite(
                self._faded(old_img, out_alpha),
                (old_text_x, (self.PILL_H - old_img.height) // 2 + out_y_off),
            )

        # Incoming group at NEW positions
        if in_alpha > 0.01:
            self._draw_indicator(
                img, new_ind_cx, cy, ind,
                state=self.state, start_t=self.start_t, alpha=in_alpha,
            )
            img.alpha_composite(
                self._faded(new_img, in_alpha),
                (new_text_x, (self.PILL_H - new_img.height) // 2),
            )
        return img

    def _tick(self) -> None:
        if self.state == "hidden":
            return
        try:
            self._photo = ImageTk.PhotoImage(self._render())
            self.img_label.config(image=self._photo)
        except Exception as e:
            log(f"render error: {e}")
        self.root.after(16, self._tick)


def pump_ui() -> None:
    while True:
        try:
            fn = app.ui_queue.get_nowait()
        except queue.Empty:
            break
        try:
            fn()
        except Exception as e:
            log(f"ui error: {e}")
    root.after(20, pump_ui)


# ---------- tray ----------
_TRAY_MARK_CACHE: dict[bool, Image.Image] = {}


def _tray_icon(active: bool) -> Image.Image:
    """Render the Veet waveform mark for the system tray. Loaded once from
    the bundled icon-mark.png and tinted gray when paused."""
    if active in _TRAY_MARK_CACHE:
        return _TRAY_MARK_CACHE[active]
    src = resource_path("assets", "icon-mark.png")
    try:
        img = Image.open(str(src)).convert("RGBA").resize((64, 64), Image.LANCZOS)
    except Exception:
        # Fallback: empty cell. Should never hit in normal builds.
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    if not active:
        r, g, b, a = img.split()
        dim = lambda v: int(v * 0.55)
        r, g, b = r.point(dim), g.point(dim), b.point(dim)
        img = Image.merge("RGBA", (r, g, b, a))
    _TRAY_MARK_CACHE[active] = img
    return img


def build_tray() -> pystray.Icon:
    def toggle(icon, _):
        app.paused = not app.paused
        icon.icon = _tray_icon(not app.paused)
        icon.title = "Veet · paused" if app.paused else "Veet · Alt+Shift to talk"
        icon.update_menu()
        log("paused" if app.paused else "resumed")

    def quit_(icon, _):
        icon.stop()
        try:
            app.post_ui(root.destroy)
        except Exception:
            os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem(lambda _: "Resume" if app.paused else "Pause", toggle),
        pystray.MenuItem("Quit Veet", quit_),
    )
    return pystray.Icon("veet", _tray_icon(True), "Veet · Alt+Shift to talk", menu)


# ---------- boot ----------
def _cuda_loadable() -> bool:
    """ctranslate2's device='auto' picks CUDA if it *could* exist, even when
    cuBLAS isn't actually loadable. Probe it ourselves so we fail to CPU
    cleanly when libs aren't bundled."""
    try:
        ctypes.WinDLL("cublas64_12.dll")
        return True
    except (OSError, AttributeError):
        return False


def load_model_thread() -> None:
    from faster_whisper import WhisperModel  # lazy: keeps main-thread import fast
    device = DEVICE
    compute = COMPUTE
    if device == "auto":
        device = "cuda" if _cuda_loadable() else "cpu"
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    model_name = MODEL_OVERRIDE or (MODEL_GPU if device == "cuda" else MODEL_CPU)
    log(f"loading {model_name} on {device}/{compute}")
    try:
        m = WhisperModel(model_name, device=device, compute_type=compute)
    except Exception as e:
        log(f"{device} load failed ({e}); falling back to cpu/int8")
        device, compute = "cpu", "int8"
        model_name = MODEL_OVERRIDE or MODEL_CPU
        m = WhisperModel(model_name, device=device, compute_type=compute)
    try:
        warm = np.zeros(int(AudioIn.SR * 0.5), dtype=np.float32)
        list(m.transcribe(warm, language=LANGUAGE, vad_filter=False, beam_size=1)[0])
    except Exception as e:
        log(f"warmup warning: {e}")
    app.model = m
    app.model_ready.set()
    log(f"model ready ({model_name} on {device}/{compute})")


def main() -> None:
    global root, overlay
    root = tk.Tk()
    root.withdraw()
    overlay = Overlay(root)

    threading.Thread(target=load_model_thread, daemon=True).start()
    HotkeyHook()
    tray = build_tray()
    threading.Thread(target=tray.run, daemon=True).start()

    root.after(20, pump_ui)
    log("ui up, listening for Alt+Shift")
    root.mainloop()
    log("bye")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
