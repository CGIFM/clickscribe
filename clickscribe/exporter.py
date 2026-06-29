"""把会话导出为 Markdown / HTML / JSON。

- HTML：干净原图 + CSS 脉冲动效圈叠加（深橙线 / 浅橙填充 / 灰橙小圈），不烧进像素
- Markdown：带静态烧录标注的图（MD 不支持 CSS 叠加）
"""
from __future__ import annotations

import base64
import json
import os

from . import annotator, store


def _b64(buf) -> str:
    return base64.b64encode(buf.getvalue()).decode()


def to_markdown(session: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    img_dir = os.path.join(out_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    sid = session["id"]
    lines = [f"# {session['title']}", ""]
    for i, step in enumerate(session["steps"], 1):
        title = step.get("title") or f"第 {i} 步"
        desc = step.get("description") or ""
        lines.append(f"## {i}. {title}")
        lines.append("")
        src = store.image_path(sid, step["screenshot"])
        if os.path.exists(src):
            out_name = f"step_{i:03d}.jpg"
            buf = annotator.render(src, step["x"], step["y"],
                                   scale=step.get("scale", 1.0), mode="full")
            with open(os.path.join(img_dir, out_name), "wb") as fh:
                fh.write(buf.getvalue())
            lines.append(f"![第{i}步](images/{out_name})")
            lines.append("")
        if desc:
            lines.append(desc)
            lines.append("")
    md = "\n".join(lines)
    path = os.path.join(out_dir, "guide.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(md)
    return path


def to_html(session: dict, out_path: str) -> str:
    from PIL import Image

    sid = session["id"]
    parts = [
        "<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>",
        f"<title>{session['title']}</title>",
        "<style>",
        "body{font-family:-apple-system,'PingFang SC',sans-serif;max-width:820px;",
        "margin:40px auto;padding:0 20px;color:#222;background:#fafafa}",
        "h1{border-bottom:3px solid #ff9200;padding-bottom:10px;color:#1a1a1a}",
        ".step{margin:26px 0;padding:22px;border:1px solid #e3e8ef;border-radius:14px;background:#fff;",
        "box-shadow:0 1px 3px rgba(0,0,0,.04)}",
        ".step h2{margin-top:0;color:#cc6a00;font-size:18px}",
        ".desc{color:#444;line-height:1.7;margin-top:12px}",
        ".num{display:inline-block;background:#ff9200;color:#fff;width:26px;height:26px;border-radius:50%;",
        "text-align:center;line-height:26px;margin-right:8px;font-size:14px}",
        # 干净原图 + 鼠标光标 + 脉冲圈
        ".shot{position:relative;display:block;width:100%;margin:6px 0}",
        ".shot img{display:block;width:100%;border-radius:8px;border:1px solid #e3e8ef}",
        ".marker{position:absolute;width:0;height:0}",
        ".marker .pulse{position:absolute;transform:translate(-50%,-50%);width:62px;height:62px;",
        "border-radius:50%;border:4px solid #dc5f00;background:rgba(255,170,90,.28);box-sizing:border-box;",
        "animation:cs-pulse 1.6s ease-out infinite}",
        ".marker .pulse::after{content:'';position:absolute;inset:31%;border-radius:50%;",
        "border:3px solid rgba(190,145,105,.92)}",
        ".marker .cur{position:absolute;left:0;top:0;width:18px;height:28px;",
        "filter:drop-shadow(0 1px 2px rgba(0,0,0,.35));pointer-events:none}",
        "@keyframes cs-pulse{0%{box-shadow:0 0 0 0 rgba(220,95,0,.55)}",
        "70%{box-shadow:0 0 0 26px rgba(220,95,0,0)}100%{box-shadow:0 0 0 0 rgba(220,95,0,0)}}",
        "</style></head><body>",
        f"<h1>{session['title']}</h1>",
    ]
    for i, step in enumerate(session["steps"], 1):
        title = step.get("title") or f"第 {i} 步"
        desc = step.get("description") or ""
        src = store.image_path(sid, step["screenshot"])
        shot_html = ""
        if os.path.exists(src):
            W, H = Image.open(src).size
            sc = step.get("scale", 1.0)
            px = step["x"] * sc / W * 100 if W else 50
            py = step["y"] * sc / H * 100 if H else 50
            b64 = _b64(annotator.raw_jpeg(src))
            shot_html = (
                f"<div class='shot'>"
                f"<img src='data:image/jpeg;base64,{b64}' alt='第{i}步截图'>"
                f"<div class='marker' style='left:{px:.2f}%;top:{py:.2f}%'>"
                f"<span class='pulse'></span>"
                f"<svg class='cur' viewBox='0 0 12 20' xmlns='http://www.w3.org/2000/svg'>"
                f"<path d='M0,0 L0,17 L4,13 L7,19 L9,18 L6,11 L11,11 Z' "
                f"fill='#ffffff' stroke='#111' stroke-width='1' stroke-linejoin='round'/></svg>"
                f"</div></div>"
            )
        parts.append(
            f"<div class='step'><h2><span class='num'>{i}</span>{title}</h2>"
            f"{shot_html}<p class='desc'>{desc}</p></div>"
        )
    parts.append("</body></html>")
    html = "\n".join(parts)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out_path


def to_json(session: dict, out_path: str) -> str:
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(session, fh, ensure_ascii=False, indent=2)
    return out_path
