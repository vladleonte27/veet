"""Generate Veet icon files from the source mark (veet-logo.jpg).

Pipeline:
  1. Read veet-logo.jpg (white waveform bars on dark backdrop).
  2. Use luminance as alpha → produce a clean transparent mark.
  3. Save icon-mark.png (transparent), icon.png (mark + brand surface
     rounded square), and icon.ico (multi-resolution Windows icon).

Usage:  .venv\\Scripts\\python.exe packaging\\gen_icons.py
"""
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "veet-logo.jpg"
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

SURFACE = (15, 17, 21, 255)   # brand dark backdrop
ACCENT = (103, 232, 249)      # cyan, no alpha — alpha set per use


def make_transparent_mark(size: int = 1024) -> Image.Image:
    """Load the source, keep the bright ink, drop the dark backdrop. Returns
    a clean white-on-transparent RGBA image at the requested size."""
    src = Image.open(SRC).convert("L")
    arr = np.asarray(src, dtype=np.int32)
    # Smooth ramp: <40 fully transparent, >90 fully opaque, linear in between.
    alpha = np.clip((arr - 40) * 6, 0, 255).astype(np.uint8)
    white = Image.new("RGBA", src.size, (255, 255, 255, 255))
    white.putalpha(Image.fromarray(alpha))
    return white.resize((size, size), Image.LANCZOS)


def make_icon(size: int, mark_transparent: Image.Image, glow: bool = False) -> Image.Image:
    """Composite the mark onto a brand rounded-square backdrop. When `glow`
    is True, bake a soft cyan highlight behind the mark inside the square."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    radius = int(size * 0.21)
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=SURFACE,
    )

    if glow:
        # Bottom-right anchored cyan halo, larger spread, softer falloff —
        # reads as a light source coming from outside the icon's lower-right.
        y, x = np.mgrid[0:size, 0:size].astype(np.float32)
        gx = size * 0.74
        gy = size * 0.74
        dist = np.sqrt((x - gx) ** 2 + (y - gy) ** 2)
        norm = dist / (size * 0.55)                  # bigger gradient radius
        intensity = np.clip(1.0 - norm, 0.0, 1.0) ** 1.4
        alpha_arr = (intensity * 130).astype(np.uint8)
        rgba = np.stack([
            np.full_like(alpha_arr, ACCENT[0]),
            np.full_like(alpha_arr, ACCENT[1]),
            np.full_like(alpha_arr, ACCENT[2]),
            alpha_arr,
        ], axis=-1)
        glow_layer = Image.fromarray(rgba, mode="RGBA")

        # Clip the glow to the rounded square so it never bleeds outside.
        rect = Image.new("L", (size, size), 0)
        ImageDraw.Draw(rect).rounded_rectangle(
            (0, 0, size - 1, size - 1), radius=radius, fill=255,
        )
        gr, gg, gb, ga = glow_layer.split()
        ga = ImageChops.multiply(ga, rect)
        img.alpha_composite(Image.merge("RGBA", (gr, gg, gb, ga)))

    img.alpha_composite(mark_transparent.resize((size, size), Image.LANCZOS))
    return img


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"missing source: {SRC}")

    mark = make_transparent_mark(1024)
    mark.save(ASSETS / "icon-mark.png", optimize=True)
    print(f"  wrote {ASSETS / 'icon-mark.png'}")

    # Big "marketing" icon with the cyan glow baked in (used on the website).
    icon_hero = make_icon(1024, mark, glow=True)
    icon_hero.save(ASSETS / "icon.png", optimize=True)
    print(f"  wrote {ASSETS / 'icon.png'} (with glow)")

    # Windows .ico stays clean — small sizes (16/24/32) look muddy with glow.
    sizes = [256, 128, 64, 48, 32, 24, 16]
    ico_imgs = [make_icon(s, mark, glow=False) for s in sizes]
    ico_imgs[0].save(ASSETS / "icon.ico", format="ICO", append_images=ico_imgs[1:])
    print(f"  wrote {ASSETS / 'icon.ico'}")


if __name__ == "__main__":
    main()
