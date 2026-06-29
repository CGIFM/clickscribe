"""把会话导出为 Markdown / HTML / JSON。

导出的图片带橙色光圈 + 鼠标光标标注（与编辑器一致）。
"""
from __future__ import annotations

import base64
import json
import os

from . import annotator, store


def _annotated_b64(path: str, x: int, y: int, mode: str = "full") -> str:
    buf = annotator.render(path, x, y, mode=mode)
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
            buf = annotator.render(src, step["x"], step["y"], mode="full")
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
    sid = session["id"]
    parts = [
        "<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>",
        f"<title>{session['title']}</title>",
        "<style>",
        "body{font-family:-apple-system,'PingFang SC',sans-serif;max-width:780px;",
        "margin:40px auto;padding:0 20px;color:#222;background:#fafafa}",
        "h1{border-bottom:3px solid #ff9200;padding-bottom:10px;color:#1a1a1a}",
        ".step{margin:28px 0;padding:22px;border:1px solid #e3e8ef;border-radius:14px;background:#fff;",
        "box-shadow:0 1px 3px rgba(0,0,0,.04)}",
        ".step h2{margin-top:0;color:#cc6a00;font-size:18px}",
        ".step img{max-width:100%;border-radius:8px;border:1px solid #e3e8ef;display:block}",
        ".desc{color:#444;line-height:1.7;margin-top:12px}",
        ".num{display:inline-block;background:#ff9200;color:#fff;width:26px;height:26px;border-radius:50%;",
        "text-align:center;line-height:26px;margin-right:8px;font-size:14px}",
        "</style></head><body>",
        f"<h1>{session['title']}</h1>",
    ]
    for i, step in enumerate(session["steps"], 1):
        title = step.get("title") or f"第 {i} 步"
        desc = step.get("description") or ""
        src = store.image_path(sid, step["screenshot"])
        img_tag = ""
        if os.path.exists(src):
            b64 = _annotated_b64(src, step["x"], step["y"], mode="full")
            img_tag = f"<img src='data:image/jpeg;base64,{b64}' alt='第{i}步截图'>"
        parts.append(
            f"<div class='step'><h2><span class='num'>{i}</span>{title}</h2>"
            f"{img_tag}<p class='desc'>{desc}</p></div>"
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
