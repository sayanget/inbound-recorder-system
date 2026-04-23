"""
Generate a multi-resolution .ico for 流向分布工具.

Usage:  python gen_icon.py  →  produces icon.ico in the same folder.

Called by build.bat before PyInstaller so the resulting exe has a proper icon.
You can replace icon.ico with your own file at any time; build.bat will not
overwrite an icon.ico that's already there and has non-zero size, unless you
delete it first.
"""
from __future__ import annotations

import math
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[!] 缺少 Pillow。先执行: pip install Pillow")
    sys.exit(1)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
SIZES = [16, 24, 32, 48, 64, 128, 256]

# Modern flat badge: blue gradient circle with a stacked-bar glyph + "流".
BG_TOP = (37, 99, 235)        # --accent
BG_BOT = (29, 78, 216)
BAR_COLORS = [                # route distribution bars
    (239, 68, 68),   # red
    (251, 146, 60),  # orange
    (250, 204, 21),  # yellow
    (34, 197, 94),   # green
    (56, 189, 248),  # sky
]


def find_cjk_font() -> str | None:
    """Find a CJK-capable font on Windows for the 流 glyph."""
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\Deng.ttf",
        r"C:\Windows\Fonts\Dengb.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def render(size: int, font_path: str | None) -> Image.Image:
    """Render one icon layer at the given pixel size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")

    # 1) Vertical gradient background (rounded rect for larger sizes, circle for 16-24)
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg, "RGBA")
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(BG_TOP[0] * (1 - t) + BG_BOT[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOT[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOT[2] * t)
        bgd.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Mask: rounded rect for larger, circle for small
    mask = Image.new("L", (size, size), 0)
    m = ImageDraw.Draw(mask)
    if size <= 24:
        m.ellipse([0, 0, size - 1, size - 1], fill=255)
    else:
        radius = int(size * 0.22)
        m.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)

    img = Image.composite(bg, img, mask)
    d = ImageDraw.Draw(img, "RGBA")

    # 2) Stacked-bar glyph in the lower portion — suggests a bar chart.
    bar_count = 5
    pad = max(1, size // 8)
    bar_area_w = size - 2 * pad
    bar_w = max(1, bar_area_w // (bar_count * 2))
    gap = max(1, (bar_area_w - bar_w * bar_count) // max(1, (bar_count - 1)))
    base_y = size - pad - max(1, size // 12)
    max_h = int(size * 0.45)

    # Heights that look like a distribution
    heights = [0.55, 0.85, 0.70, 1.00, 0.60]

    x = pad + max(0, (bar_area_w - (bar_w * bar_count + gap * (bar_count - 1))) // 2)
    for i in range(bar_count):
        h = int(max_h * heights[i])
        color = BAR_COLORS[i % len(BAR_COLORS)] + (235,)
        d.rectangle([x, base_y - h, x + bar_w, base_y], fill=color)
        x += bar_w + gap

    # 3) Overlay a bold 流 character in the upper-left if font available.
    #    Skip for very small sizes — too blurry.
    if font_path and size >= 32:
        try:
            font = ImageFont.truetype(font_path, int(size * 0.48))
            text = "流"
            tx = int(size * 0.10)
            ty = int(size * 0.05)
            # Soft drop-shadow
            d.text((tx + 1, ty + 1), text, font=font, fill=(0, 0, 0, 90))
            d.text((tx, ty), text, font=font, fill=(255, 255, 255, 250))
        except Exception as e:
            print(f"[warn] text overlay failed: {e}")

    return img


def main():
    font_path = find_cjk_font()
    if not font_path:
        print("[warn] 未找到中文字体，跳过文字叠加层")

    # Render from largest to smallest; Pillow's ICO writer stores each layer
    # by downsampling the base image, but we prefer crisp per-size renders,
    # so we explicitly attach each layer via append_images.
    sizes_desc = sorted(SIZES, reverse=True)
    imgs = [render(s, font_path) for s in sizes_desc]
    base = imgs[0]
    base.save(
        OUT,
        format="ICO",
        sizes=[(s, s) for s in sizes_desc],
        append_images=imgs[1:],
    )
    final_size = os.path.getsize(OUT)
    print(f"[ok] 生成图标: {OUT}  ({final_size} bytes)")
    print(f"     尺寸: {', '.join(str(s) for s in sizes_desc)}")
    if final_size < 2000:
        print("[warn] 文件过小，可能只写入了单层；请检查 Pillow 版本是否 >= 9.1")


if __name__ == "__main__":
    main()
