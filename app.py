#!/usr/bin/env python3
"""clickscribe 本地服务：录制 + 编辑器 + 导出。

启动后用浏览器打开 http://127.0.0.1:5577
"""
from __future__ import annotations

import json
import os
import threading
import time
import zipfile

from flask import (Flask, Response, abort, jsonify, render_template,
                   request, send_file, stream_with_context)

from clickscribe import ai_writer, annotator, exporter, store
from clickscribe.recorder import Recorder

app = Flask(__name__)
recorder = Recorder()
PORT = 5577

# 空闲超时自动关闭（默认不常驻：30 分钟无请求则退出）
LAST_ACTIVE = time.time()
IDLE_TIMEOUT = 1800


@app.before_request
def _touch_active():
    global LAST_ACTIVE
    LAST_ACTIVE = time.time()


def _idle_watcher():
    while True:
        time.sleep(60)
        if time.time() - LAST_ACTIVE > IDLE_TIMEOUT:
            print("[clickscribe] 空闲超时，自动关闭服务")
            os._exit(0)


threading.Thread(target=_idle_watcher, daemon=True).start()


def _load_or_404(sid: str) -> dict:
    """加载会话；不存在时返回 404，避免抛异常导致 500 + 前端破图。"""
    try:
        return store.load(sid)
    except FileNotFoundError:
        abort(404)


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
    data = _load_or_404(sid)
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


# ---------------------------------------------------------------- 图片（橙色光圈 + 鼠标，支持全屏 / 聚焦裁切）
@app.route("/api/image/<sid>/<fname>")
def image(sid, fname):
    data = _load_or_404(sid)
    step = next((s for s in data["steps"] if s["screenshot"] == fname), None)
    path = store.image_path(sid, fname)
    if not os.path.exists(path):
        abort(404)
    if request.args.get("raw") == "1" or not step:
        return send_file(path, mimetype="image/png")
    mode = request.args.get("mode", "full")
    if mode not in ("full", "crop"):
        mode = "full"
    return send_file(
        annotator.render(path, step["x"], step["y"],
                         scale=step.get("scale", 1.0), mode=mode),
        mimetype="image/jpeg",
    )


# ---------------------------------------------------------------- AI 配置
def _mask(secret: str) -> str:
    if not secret:
        return ""
    return (secret[:4] + "***" + secret[-4:]) if len(secret) > 8 else "***"


@app.route("/api/config")
def get_config():
    c = ai_writer.load_config()
    return jsonify({
        "provider": c["provider"],
        "glm_key_set": bool(c.get("glm_key")),
        "glm_key_mask": _mask(c.get("glm_key", "")),
        "custom_base": c.get("custom_base", ""),
        "custom_key_set": bool(c.get("custom_key")),
        "custom_model": c.get("custom_model", ""),
    })


@app.route("/api/config", methods=["POST"])
def set_config():
    body = request.get_json(force=True) or {}
    c = ai_writer.load_config()
    if body.get("provider"):
        c["provider"] = body["provider"]
    if body.get("glm_key"):
        c["glm_key"] = body["glm_key"]          # 空值不覆盖，保留旧 key
    if "custom_base" in body:
        c["custom_base"] = body["custom_base"]
    if body.get("custom_key"):
        c["custom_key"] = body["custom_key"]
    if "custom_model" in body:
        c["custom_model"] = body["custom_model"]
    ai_writer.save_config(c)
    return jsonify({"ok": True})


# ---------------------------------------------------------------- AI 说明（看全图，流式可中断）
def _sse(d: dict) -> str:
    return "data: " + json.dumps(d, ensure_ascii=False) + "\n\n"


@app.route("/api/ai/<sid>", methods=["POST"])
def ai_all(sid):
    """一次把所有截图发给 AI（看全图理解流程），返回每步说明；前端可中断。"""
    data = _load_or_404(sid)
    paths = [store.image_path(sid, s["screenshot"]) for s in data["steps"] if s.get("screenshot")]

    def gen():
        total = len(paths)
        yield _sse({"type": "start", "total": total, "done": 0})
        try:
            descs = ai_writer.describe_all(paths)
            for i, d in enumerate(descs):
                if i < len(data["steps"]):
                    data["steps"][i]["description"] = d
            store.save(sid, data)
            yield _sse({"type": "done", "total": total, "done": total, "descriptions": descs})
        except GeneratorExit:
            raise  # 前端中断：不保存
        except Exception as exc:
            yield _sse({"type": "error", "error": str(exc)})

    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- 导出
@app.route("/api/export/<sid>/<fmt>")
def export(sid, fmt):
    data = _load_or_404(sid)
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


# ---------------------------------------------------------------- 关闭服务
@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    def _stop():
        time.sleep(0.4)  # 让响应先返回
        print("[clickscribe] 收到关闭请求，退出服务")
        os._exit(0)

    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("=" * 56)
    print("  clickscribe 已启动 →  http://127.0.0.1:5577")
    print(
        "  辅助功能权限:",
        "✅ 已授权" if Recorder.permission_ok() else "❌ 未授权（首次需手动授予）",
    )
    print("=" * 56)
    app.run(host="127.0.0.1", port=PORT, debug=False)
