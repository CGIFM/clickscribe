#!/usr/bin/env python3
"""clickscribe 本地服务：录制 + 编辑器 + 导出。

启动后用浏览器打开 http://127.0.0.1:5577
"""
from __future__ import annotations

import io
import os
import time
import zipfile

from flask import Flask, abort, jsonify, render_template, request, send_file

from clickscribe import ai_writer, exporter, store
from clickscribe.recorder import Recorder

app = Flask(__name__)
recorder = Recorder()
PORT = 5577


# ---------------------------------------------------------------- 视图
@app.route("/")
def index():
    return render_template("editor.html")


# ---------------------------------------------------------------- 状态
@app.route("/api/state")
def state():
    sids = store.list_sessions()
    return jsonify(
        {
            "recording": recorder.running,
            "buffer": len(recorder.steps),
            "permission": Recorder.permission_ok(),
            "sessions": sids,
        }
    )


# ---------------------------------------------------------------- 录制
@app.route("/api/start", methods=["POST"])
def start():
    if not Recorder.permission_ok():
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "未授予「辅助功能」权限。请打开 系统设置 → 隐私与安全性 → "
                    "辅助功能，把运行本程序的「终端」和 Python 加进去并打开开关，再重试。",
                }
            ),
            403,
        )
    recorder.start()
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def stop():
    steps = recorder.stop()
    # 丢弃最近 1 秒内的步骤（多半是点「停止」按钮本身那张）
    now = time.time()
    filtered = [s for s in steps if now - s["ts"] > 1.0]
    if not filtered:
        filtered = steps
    if not filtered:
        return jsonify({"ok": False, "error": "没有捕获到任何点击"}), 400
    sid = store.create_from_steps(filtered)
    return jsonify({"ok": True, "sid": sid})


# ---------------------------------------------------------------- 会话
@app.route("/api/sessions")
def sessions():
    return jsonify({"sessions": store.list_sessions()})


@app.route("/api/session/<sid>")
def get_session(sid):
    try:
        return jsonify(store.load(sid))
    except FileNotFoundError:
        abort(404)


@app.route("/api/session/<sid>", methods=["POST"])
def update_session(sid):
    data = store.load(sid)
    body = request.get_json(force=True) or {}
    if "title" in body:
        data["title"] = body["title"]
    if "steps" in body:
        data["steps"] = body["steps"]
    store.save(sid, data)
    return jsonify({"ok": True})


@app.route("/api/session/<sid>", methods=["DELETE"])
def delete_session(sid):
    store.delete(sid)
    return jsonify({"ok": True})


# ---------------------------------------------------------------- 图片（带点击红圈标注）
def _annotated(path: str, x: int, y: int) -> io.BytesIO:
    from PIL import Image, ImageDraw

    img = Image.open(path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    r = max(18, min(img.size) // 38)
    w = max(4, r // 4)
    d.ellipse([x - r, y - r, x + r, y + r], outline=(245, 63, 63, 255), width=w)
    d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(245, 63, 63, 255))
    out = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=82)
    buf.seek(0)
    return buf


@app.route("/api/image/<sid>/<fname>")
def image(sid, fname):
    data = store.load(sid)
    step = next((s for s in data["steps"] if s["screenshot"] == fname), None)
    path = store.image_path(sid, fname)
    if not os.path.exists(path):
        abort(404)
    if step and request.args.get("raw") != "1":
        return send_file(_annotated(path, step["x"], step["y"]), mimetype="image/jpeg")
    return send_file(path, mimetype="image/png")


# ---------------------------------------------------------------- AI 说明
@app.route("/api/ai/<sid>", methods=["POST"])
def ai_all(sid):
    data = store.load(sid)
    only_missing = request.args.get("all") != "1"
    results = []
    for i, step in enumerate(data["steps"]):
        if only_missing and step.get("description"):
            continue
        path = store.image_path(sid, step["screenshot"])
        try:
            step["description"] = ai_writer.describe(path)
            results.append({"index": i, "ok": True})
        except Exception as exc:  # 某一步失败不阻断其余
            results.append({"index": i, "ok": False, "error": str(exc)})
    store.save(sid, data)
    return jsonify({"ok": True, "results": results})


# ---------------------------------------------------------------- 导出
@app.route("/api/export/<sid>/<fmt>")
def export(sid, fmt):
    data = store.load(sid)
    os.makedirs("exports", exist_ok=True)
    safe = "".join(c for c in data["title"] if c not in "/\\\n") or sid

    if fmt == "md":
        out_dir = os.path.join("exports", f"{sid}_md")
        exporter.to_markdown(data, out_dir)
        zip_path = os.path.join("exports", f"{safe}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(out_dir):
                for fn in files:
                    full = os.path.join(root, fn)
                    zf.write(full, os.path.relpath(full, out_dir))
        return send_file(zip_path, as_attachment=True, download_name=f"{safe}.zip")

    if fmt == "html":
        path = os.path.join("exports", f"{sid}.html")
        exporter.to_html(data, path)
        return send_file(path, as_attachment=True, download_name=f"{safe}.html")

    if fmt == "json":
        path = os.path.join("exports", f"{sid}.json")
        exporter.to_json(data, path)
        return send_file(path, as_attachment=True, download_name=f"{safe}.json")

    abort(400)


if __name__ == "__main__":
    print("=" * 56)
    print("  clickscribe 已启动 →  http://127.0.0.1:5577")
    print(
        "  辅助功能权限:",
        "✅ 已授权" if Recorder.permission_ok() else "❌ 未授权（首次需手动授予）",
    )
    print("=" * 56)
    app.run(host="127.0.0.1", port=PORT, debug=False)
