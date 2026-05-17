# PyInstaller spec for Veet.
# Build:
#   CPU:  pyinstaller --clean --noconfirm veet.spec
#   GPU:  set VEET_BUILD_GPU=1 && pyinstaller --clean --noconfirm veet.spec
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path.cwd()
INCLUDE_GPU = os.environ.get("VEET_BUILD_GPU", "0") == "1"
APP_NAME = "Veet"
ICON_PATH = ROOT / "assets" / "icon.ico"

# ---- bundled assets (next to the exe) ----
datas = [
    (str(ROOT / "assets" / "Inter.ttf"),         "assets"),
    (str(ROOT / "assets" / "chime-start.wav"),   "assets"),
    (str(ROOT / "assets" / "chime-stop.wav"),    "assets"),
]
binaries = []
hiddenimports = []

# Pull in everything for ML + audio libs.
for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "av", "tokenizers"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += collect_submodules("sounddevice")
hiddenimports += collect_submodules("keyboard")
hiddenimports += collect_submodules("pystray")
hiddenimports += collect_submodules("PIL")
hiddenimports += ["licensing"]

if INCLUDE_GPU:
    # GPU build: bundle CUDA libs (~1.2 GB extra).
    for pkg in ("nvidia.cuda_runtime", "nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_nvrtc"):
        try:
            d, b, h = collect_all(pkg)
            datas += d
            binaries += b
            hiddenimports += h
        except Exception:
            pass
    excludes = []
else:
    # CPU build: omit CUDA libs (~1.2 GB savings).
    excludes = [
        "nvidia",
        "nvidia.cublas",
        "nvidia.cudnn",
        "nvidia.cuda_runtime",
        "nvidia.cuda_nvrtc",
    ]

a = Analysis(
    ["veet.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    strip=False,
    upx=False,                # UPX can corrupt some Python C-extensions
    console=False,            # windowed app (no console flash)
    icon=str(ICON_PATH) if ICON_PATH.exists() else None,
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
