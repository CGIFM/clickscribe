"""录制会话的本地存储（JSON 元数据 + 截图文件）。"""
from __future__ import annotations

import json
import os
import shutil
import time

SESSIONS_DIR = "sessions"
RECORDING_DIR = os.path.join(SESSIONS_DIR, "_recording")


def _ensure() -> None:
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def list_sessions() -> list[str]:
    _ensure()
    ids = [f[:-5] for f in os.listdir(SESSIONS_DIR) if f.endswith(".json")]
    ids.sort(reverse=True)  # 最新在前
    return ids


def load(sid: str) -> dict:
    with open(os.path.join(SESSIONS_DIR, f"{sid}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def save(sid: str, data: dict) -> None:
    _ensure()
    with open(os.path.join(SESSIONS_DIR, f"{sid}.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def session_dir(sid: str) -> str:
    return os.path.join(SESSIONS_DIR, sid)


def image_path(sid: str, fname: str) -> str:
    return os.path.join(session_dir(sid), "images", fname)


def create_from_steps(steps: list[dict]) -> str:
    """录制结束后，把 _recording 目录归档为一个新会话。"""
    _ensure()
    sid = time.strftime("%Y%m%d_%H%M%S")
    img_dir = os.path.join(session_dir(sid), "images")
    os.makedirs(img_dir, exist_ok=True)
    for step in steps:
        src = os.path.join(RECORDING_DIR, step["screenshot"])
        dst = os.path.join(img_dir, step["screenshot"])
        if os.path.exists(src):
            shutil.move(src, dst)
    data = {
        "id": sid,
        "title": f"操作指南 {sid}",
        "created": time.time(),
        "steps": steps,
    }
    save(sid, data)
    return sid


def delete(sid: str) -> None:
    for path in (os.path.join(SESSIONS_DIR, f"{sid}.json"), session_dir(sid)):
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
