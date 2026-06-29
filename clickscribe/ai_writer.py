"""AI 步骤说明生成。支持三种接入（在编辑器「设置」里切换）：

- ccswitch：走本地跟随代理 7999（默认，免配置，跟随 CC Switch 当前供应商）
- glm：智谱官方直连，填 API key，模型 glm-4v-plus
- custom：自定义 OpenAI 兼容 base_url + key + model

生成方式：一次把所有截图发给模型（看全图理解流程上下文），返回每步说明。
jlc/glm 经代理只支持流式，故统一用 stream + SSE 解析。
"""
from __future__ import annotations

import base64
import io
import json
import os
import re

import requests

CONFIG_PATH = os.environ.get("CLICKSCRIBE_CONFIG", "config.json")

DEFAULT_CONFIG = {
    "provider": "ccswitch",      # ccswitch | glm | custom
    "glm_key": "",
    "custom_base": "",
    "custom_key": "",
    "custom_model": "",
}

CCSWITCH_URL = "http://127.0.0.1:7999/v1/chat/completions"
GLM_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
GLM_MODEL = "glm-4v-plus"

ALL_PROMPT = (
    "这是按顺序的一组电脑操作截图，共 {n} 步，每张图的红圈标注了该步的点击位置。"
    "请结合整个流程的上下文，为每一步用一句简洁中文说明「这步做了什么」"
    "（不超过 30 字，不要序号、不要引号）。"
    "只返回一个 JSON 字符串数组，例如 [\"第一步说明\",\"第二步说明\"]，不要任何其他文字。"
)


# ---------------------------------------------------------------- 配置
def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as fh:
                return {**DEFAULT_CONFIG, **json.load(fh)}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(c: dict) -> dict:
    merged = {k: c.get(k, DEFAULT_CONFIG[k]) for k in DEFAULT_CONFIG}
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
    return merged


def _normalize_chat_url(base: str) -> str:
    base = (base or "").strip().rstrip("/")
    if not base:
        return ""
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    if "/v1" in base:
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def _endpoint() -> tuple[str, str, str]:
    """根据配置返回 (url, api_key, model)。"""
    c = load_config()
    provider = c.get("provider", "ccswitch")
    if provider == "glm":
        return GLM_URL, c.get("glm_key", ""), GLM_MODEL
    if provider == "custom":
        return (_normalize_chat_url(c.get("custom_base", "")),
                c.get("custom_key", ""),
                c.get("custom_model") or "gpt-4o")
    # ccswitch（跟随代理本地无需 key，model 会被覆盖）
    return CCSWITCH_URL, "", "glm-5.1"


# ---------------------------------------------------------------- 图片编码 + 流式
def _encode_optimized(path: str, max_side: int = 1024, quality: int = 78) -> str:
    from PIL import Image

    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    s = max_side / max(w, h)
    if s < 1:
        img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def _stream_chat(url: str, key: str, payload: dict, timeout: int = 180) -> str:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    pieces: list[str] = []
    with requests.post(url, json=payload, headers=headers, stream=True, timeout=timeout) as resp:
        if resp.status_code == 429 or resp.status_code >= 500:
            raise RuntimeError(f"上游限流/错误 {resp.status_code}: {resp.text[:160]}")
        resp.raise_for_status()
        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8", "replace")
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


def _parse_descriptions(text: str, n: int) -> list[str]:
    """从模型输出解析每步说明（JSON 数组），失败则按行降级。"""
    text = text.strip()
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        text = m.group(0)
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            arr = [str(x) for x in arr]
            while len(arr) < n:
                arr.append("")
            return arr[:n]
    except Exception:
        pass
    lines = [re.sub(r"^[\d.、）)\s]+", "", ln).strip() for ln in text.split("\n") if ln.strip()]
    return (lines + [""] * n)[:n]


# ---------------------------------------------------------------- 主入口：一次看全图
def describe_all(image_paths: list[str]) -> list[str]:
    """把所有截图一次发给模型，返回每步说明列表。"""
    url, key, model = _endpoint()
    if not url:
        raise RuntimeError("未配置 AI 接入：请在「设置」里选 GLM（填 key）或自定义 API")
    if not image_paths:
        return []
    content = [{"type": "text", "text": ALL_PROMPT.format(n=len(image_paths))}]
    for p in image_paths:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{_encode_optimized(p)}"},
        })
    payload = {
        "model": model,
        "stream": True,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max(600, len(image_paths) * 80),
        "temperature": 0.3,
    }
    text = _stream_chat(url, key, payload)
    return _parse_descriptions(text, len(image_paths))
