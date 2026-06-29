"""截图标注渲染：半透明橙色光圈 + 鼠标光标，支持全屏 / 聚焦裁切。

- 全屏模式 (full)：整屏 + 点击处橙色光圈 + 箭头光标
- 聚焦模式 (crop)：以点击点为中心裁出一块，再画光圈 + 光标
"""
from __future__ import annotations

import io

from PIL import Image, ImageDraw

DEEP_ORANGE = (220, 95, 0)       # 外圈深橙描边线
LIGHT_ORANGE = (255, 170, 90)    # 中间浅橙半透明填充
GRAY_ORANGE = (190, 145, 105)    # 鼠标尖灰橙小圈
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# 经典箭头光标轮廓，尖端在 (0,0)，朝右下
_CURSOR = [(0, 0), (0, 17), (4, 13), (7, 19), (9, 18), (6, 11), (11, 11)]


def _cursor_at(cx: int, cy: int, s: int = 1):
    return [(cx + dx * s, cy + dy * s) for dx, dy in _CURSOR]


def _draw_cursor(d, cx: int, cy: int, s: int = 1) -> None:
    poly = _cursor_at(cx, cy, s)
    # 八方向黑色描边，让白色光标在任何背景上都清晰
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                   (-1, -1), (1, 1), (-1, 1), (1, -1)):
        d.polygon([(px + ox, py + oy) for px, py in poly], fill=BLACK + (230,))
    d.polygon(poly, fill=WHITE + (255,), outline=BLACK + (255,))


def _draw_glow(d, cx: int, cy: int, r: int) -> None:
    """Glitter 风格三层光圈：中间浅橙高透明填充 + 外圈深橙描边线 + 中心灰橙小圈。"""
    box = [cx - r, cy - r, cx + r, cy + r]
    # 1. 中间浅橙半透明填充（透明度较高，能透出底图）
    d.ellipse(box, fill=LIGHT_ORANGE + (72,))
    # 2. 外圈深橙色描边线
    d.ellipse(box, outline=DEEP_ORANGE + (255,), width=max(3, r // 8))
    # 3. 鼠标尖周围的灰橙色小圈（描边环，围绕光标尖端）
    rs = max(14, r // 2)
    d.ellipse([cx - rs, cy - rs, cx + rs, cy + rs], outline=GRAY_ORANGE + (215,),
              width=max(3, r // 12))


def render(path: str, x: int, y: int, mode: str = "full",
           max_side: int = 1700, crop_w: int = 880, crop_h: int = 560) -> io.BytesIO:
    """渲染标注后的图片，返回 JPEG BytesIO。"""
    img = Image.open(path).convert("RGBA")
    W, H = img.size

    # 大图缩放（视网膜整屏往往 3K+，缩小省内存）
    if max(W, H) > max_side:
        s = max_side / max(W, H)
        img = img.resize((int(W * s), int(H * s)), Image.LANCZOS)
        x, y = int(x * s), int(y * s)
        W, H = img.size

    if mode == "crop":
        cw, ch = min(crop_w, W), min(crop_h, H)
        left = max(0, min(x - cw // 2, W - cw))
        top = max(0, min(y - ch // 2, H - ch))
        img = img.crop((left, top, left + cw, top + ch))
        cx, cy = x - left, y - top
        side = min(cw, ch)
        r = max(30, side // 10)
        cur_s = max(1, side // 450)
    else:
        cx, cy = x, y
        side = min(W, H)
        r = max(26, side // 28)
        cur_s = max(1, side // 700)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    _draw_glow(d, cx, cy, r)
    _draw_cursor(d, cx, cy, cur_s)

    out = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=85)
    buf.seek(0)
    return buf
