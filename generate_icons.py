"""
generate_icons.py
Generates all icon files Tauri needs from a single drawn source:
  - PNGs: 32x32, 128x128, 128x128@2x, icon.png (512)
  - Windows: icon.ico
  - macOS:   icon.icns
Run once; output goes to ui/src-tauri/icons/
"""
from PIL import Image, ImageDraw
from pathlib import Path

ICONS = Path("ui/src-tauri/icons")
ICONS.mkdir(parents=True, exist_ok=True)

BG     = (8, 12, 16, 255)      # near-black
ACCENT = (0, 229, 255, 255)    # cyan


def draw_master(size: int) -> Image.Image:
    """Draw the NEXUS 'NX' mark at the given size, scaled proportionally."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad    = max(1, size // 16)
    radius = max(2, size // 8)

    # Rounded dark tile
    d.rounded_rectangle([pad, pad, size - pad, size - pad],
                        radius=radius, fill=BG)
    # Cyan border
    bw = max(1, size // 32)
    d.rounded_rectangle([pad, pad, size - pad, size - pad],
                        radius=radius, outline=ACCENT, width=bw)

    # "NX" — draw as geometric strokes so it scales crisply at all sizes
    sw = max(1, size // 16)          # stroke width
    cx = size // 2
    top = size * 0.32
    bot = size * 0.68

    # N (left of center)
    nx0 = size * 0.24
    nx1 = size * 0.44
    d.line([(nx0, bot), (nx0, top)], fill=ACCENT, width=sw)          # left vertical
    d.line([(nx0, top), (nx1, bot)], fill=ACCENT, width=sw)          # diagonal
    d.line([(nx1, bot), (nx1, top)], fill=ACCENT, width=sw)          # right vertical

    # X (right of center)
    xx0 = size * 0.54
    xx1 = size * 0.76
    d.line([(xx0, top), (xx1, bot)], fill=ACCENT, width=sw)
    d.line([(xx1, top), (xx0, bot)], fill=ACCENT, width=sw)

    return img


# 1. PNG sizes Tauri's default config references
master = draw_master(512)

png_targets = {
    "32x32.png":      32,
    "128x128.png":    128,
    "128x128@2x.png": 256,
    "icon.png":       512,
    # Windows Store / extra sizes (harmless to include)
    "Square30x30Logo.png":   30,
    "Square44x44Logo.png":   44,
    "Square71x71Logo.png":   71,
    "Square89x89Logo.png":   89,
    "Square107x107Logo.png": 107,
    "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150,
    "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310,
    "StoreLogo.png":         50,
}
for name, sz in png_targets.items():
    draw_master(sz).save(ICONS / name)

# 2. Windows .ico (multi-resolution)
ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
master.save(ICONS / "icon.ico", format="ICO", sizes=ico_sizes)

# 3. macOS .icns
try:
    master.save(ICONS / "icon.icns", format="ICNS")
except Exception as e:
    # PIL ICNS needs square power-of-two; 512 works. If it fails, note it.
    print(f"  (icns note: {e})")

print("Generated icons:")
for f in sorted(ICONS.iterdir()):
    print(f"  {f.name:<24} {f.stat().st_size:>7} bytes")
