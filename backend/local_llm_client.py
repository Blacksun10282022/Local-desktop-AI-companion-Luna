# -*- coding: utf-8 -*-
# backend/local_llm_client.py
"""
本地 LLM HTTP 客户端：优先 /v1/chat/completions，失败回退 /completion。
返回：单条字符串。
"""
from __future__ import annotations
from typing import Optional, Dict, Any
import requests

def _join(base: str, path: str) -> str:
    return f"{(base or '').rstrip('/')}/{(path or '').lstrip('/')}"

def _post_json(url: str, payload: Dict[str, Any], timeout_s: int):
    try:
        r = requests.post(url, json=payload, timeout=timeout_s)
        ct = (r.headers.get("content-type") or "").lower()
        data = r.json() if "application/json" in ct else None
        return r.status_code, data, r.text
    except Exception as e:
        return -1, None, str(e)

def _extract_openai_chat(data: Dict[str, Any] | None) -> Optional[str]:
    try:
        ch0 = (data or {})["choices"][0]
        msg = ch0.get("message") or {}
        return (msg.get("content") or "").strip()
    except Exception:
        return None

def _extract_llamacpp_completion(data: Dict[str, Any] | None) -> Optional[str]:
    if not isinstance(data, dict): return None
    txt = data.get("content") or data.get("generation")
    if not txt and "choices" in data:
        try: txt = data["choices"][0]["text"]
        except Exception: txt = None
    return txt.strip() if isinstance(txt, str) else None

def call_local_llm(
    ctx: Dict[str, Any],
    base_url: str,
    timeout_ms: int = 6000,
    system_prompt: Optional[str] = None,
    max_tokens: int = 48,
    temperature: float = 0.7,
) -> str:
    """
    ctx：与 llm_client.build_user_prompt() 一致；若 system_prompt 为空，会在用户端组装“短句风格限制”。
    返回：字符串（失败抛错，由路由兜底）。
    """
    from llm_client import build_user_prompt  # 复用现有模板（保持人格一致）
    user_prompt = build_user_prompt(ctx)

    sys_prompt = system_prompt or (
        "你是 Luna，一个安静敏感的桌面伴生体。"
        "只输出一句 5~15 字的中文短句，温柔且不打扰；不要解释或表情；避免复述上一句。"
    )
    timeout_s = max(int(timeout_ms/1000), 2)

    # 路径 1：OpenAI 兼容 /v1/chat/completions
    url1 = _join(base_url, "/v1/chat/completions")
    payload1 = {
        "model": "local",
        "messages": [
            {"role":"system","content": sys_prompt},
            {"role":"user","content": user_prompt}
        ],
        "temperature": float(temperature),
        "max_tokens": int(max_tokens)
    }
    c,d,_ = _post_json(url1, payload1, timeout_s)
    if 200 <= c < 300:
        out = _extract_openai_chat(d)
        if out: return out

    # 路径 2：llama.cpp /completion
    url2 = _join(base_url, "/completion")
    prompt2 = f"<|system|>\n{sys_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>\n"
    payload2 = {
        "prompt": prompt2,
        "temperature": float(temperature),
        "n_predict": int(max_tokens),
        "stop": ["</s>", "<|user|>", "<|assistant|>"]
    }
    c2,d2,_ = _post_json(url2, payload2, timeout_s)
    if 200 <= c2 < 300:
        out2 = _extract_llamacpp_completion(d2)
        if out2: return out2

    raise RuntimeError(f"Local LLM failed: chat={c} completion={c2}")
