"""调用 CC Switch 跟随代理，为截图生成步骤说明。

CC Switch（15721）按路径分流，OpenAI 格式直连会走 Codex 通道失败。
所以走「跟随代理」7999——它实时读 CC Switch 当前 Claude 供应商
（jlc 中转 / glm-5.1，支持视觉），转发并强制 model 跟随。

重要：jlc/glm-5.1 经该代理**只支持流式请求**（非流式返回 E015），
因此 describe() 使用 stream=True 并解析 SSE。
"""
from __future__ import annotations

import base64
import io
import json
import os
import time

import requests

# 跟随代理（见 ~/Projects/simplemindmap/ai-proxy/proxy.py）
CC_SWITCH_BASE = os.environ.get("CCSWITCH_BASE", "http://127.0.0.1:7999")
CC_SWITCH_URL = os.environ.get("CCSWITCH_URL", f"{CC_SWITCH_BASE}/v1/chat/completions")
DEFAULT_MODEL = os.environ.get("CCSWITCH_MODEL", "glm-5.1")

PROMPT = (
    "这是一张电脑操作的截图，红框标注了用户刚刚点击的位置。"
    "请用一句简洁的中文描述这一步做了什么，例如「点击右上角的『分享』按钮」"
    "或「在搜索框输入关键词后回车」。只输出动作描述本身："
    "不要序号、不要引号、不超过 30 个字。"
)


def list_models(base: str = CC_SWITCH_BASE) -> list[str]:
    try:
        resp = requests.get(f"{base}/v1/models", timeout=5)
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", [])]
    except Exception:
        return []


def pick_model() -> str:
    """跟随代理会强制覆盖 model，这里只是取一个合理名。"""
    models = list_models()
    for keyword in ("glm", "gpt-4o", "claude", "gemini", "vl"):
        for m in models:
            if keyword in m.lower():
                return m
    if models:
        return models[0]
    return DEFAULT_MODEL


def _encode_optimized(path: str, max_side: int = 1440, quality: int = 80) -> str:
    """缩放 + JPEG 压缩后 base64，降低 token 消耗与限流概率。"""
    from PIL import Image

    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    scale = max_side / max(w, h)
    if scale < 1:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def _stream_chat(payload: dict) -> str:
    """发流式请求，拼接 SSE delta.content 返回完整文本。"""
    pieces: list[str] = []
    with requests.post(CC_SWITCH_URL, json=payload, stream=True, timeout=120) as resp:
        if resp.status_code == 429 or resp.status_code >= 500:
            raise RuntimeError(
                f"上游限流/错误 {resp.status_code}: {resp.text[:160]}"
            )
        resp.raise_for_status()
        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            try:
                delta = obj["choices"][0]["delta"]
            except (KeyError, IndexError):
                continue
            if delta.get("content"):
                pieces.append(delta["content"])
    return "".join(pieces)


def describe(image_path: str, model: str | None = None) -> str:
    """让 AI 看图，返回一句话描述。流式 + 限流重试。"""
    model = model or pick_model()
    b64 = _encode_optimized(image_path)
    payload = {
        "model": model,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 120,
        "temperature": 0.3,
    }
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            return _stream_chat(payload).strip()
        except (requests.RequestException, RuntimeError) as exc:
            last_err = exc
            time.sleep(3 * (attempt + 1))
    raise last_err or RuntimeError("AI 请求失败")
