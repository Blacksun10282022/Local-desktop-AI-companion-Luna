# -*- coding: utf-8 -*-
# backend/local_tts_client.py
# 作用：调用“本地 TTS HTTP 服务”，把文本合成为本地音频文件。
# 兼容多种返回形式：
#   1) 直接返回 audio/* 二进制；
#   2) JSON 内含 base64 音频（字段：audio_base64 / audio）；
#   3) JSON 内含可下载的音频 URL（字段：audio_url，相对/绝对均可）。
# 关键点：
# - 保存文件时按 Content-Type 决定扩展名，避免“后缀与实际格式不一致”。
# - 新增 XTTS 情感参数透传（lang/style/speed/energy/ref_wav_b64），保持向后兼容。

from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import base64
import time
import os
import requests

# 环境“期望”参数（本地服务可参考或忽略；真实落盘后缀以 Content-Type 为准）
DEFAULT_FORMAT = os.getenv("TTS_FORMAT", "mp3")
DEFAULT_SR     = int(os.getenv("TTS_SAMPLE_RATE", "24000"))

# 常见接口路径优先级
_TTS_PATH_CANDIDATES = ("/v1/tts", "/api/tts", "/tts")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _now_millis() -> int:
    return int(time.time() * 1000)


def _ext_from_content_type(ctype: str | None, fallback: str = "wav") -> str:
    """根据 Content-Type 推断扩展名；未识别时回退到 fallback。"""
    if not ctype:
        return fallback
    c = ctype.lower().split(";")[0].strip()
    mapping = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/wave": "wav",
        "audio/vnd.wave": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/flac": "flac",
        "audio/ogg": "ogg",
        "audio/webm": "webm",
        "audio/x-m4a": "m4a",
        "audio/aac": "aac",
        "audio/opus": "opus",
    }
    return mapping.get(c, fallback)


def _compose_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def _gen_outpath(out_dir: Path, ext: str) -> Path:
    base = f"luna_{_now_millis()}"
    return out_dir / f"{base}.{ext.lstrip('.')}"


def _save_bytes(out_dir: Path, data: bytes, ext: str) -> str:
    _ensure_dir(out_dir)
    file_path = _gen_outpath(out_dir, ext)
    file_path.write_bytes(data)
    return str(file_path)


def _download_url(url: str, out_dir: Path, timeout: int = 15) -> Tuple[str, str | None]:
    """下载一个音频 URL 到本地；返回 (本地路径, Content-Type)"""
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        ctype = r.headers.get("Content-Type")
        ext = _ext_from_content_type(ctype, DEFAULT_FORMAT)
        data = r.content
    path = _save_bytes(out_dir, data, ext)
    return path, ctype


def ping_local_tts(base_url: str, timeout_ms: int = 2000) -> bool:
    """轻量探活：尝试 GET /health → /status → /"""
    if not base_url:
        return False
    timeout = max(int(timeout_ms / 1000), 1)
    for path in ("/health", "/status", "/"):
        try:
            r = requests.get(_compose_url(base_url, path), timeout=timeout)
            if r.status_code < 500:
                return True
        except Exception:
            continue
    return False


def _post_tts(base_url: str, payload: dict, timeout: int) -> requests.Response:
    last_err = None
    for path in _TTS_PATH_CANDIDATES:
        url = _compose_url(base_url, path)
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            if r.status_code // 100 == 2:  # 2xx
                return r
            last_err = RuntimeError(f"HTTP {r.status_code} at {url}: {r.text[:200]}")
        except Exception as e:
            last_err = e
    raise last_err or RuntimeError("No reachable local TTS endpoint")


def call_local_tts(
    text: str,
    out_dir: Path,
    base_url: Optional[str] = None,
    voice_override: Optional[str] = None,   # 新接口
    voice: Optional[str] = None,            # 兼容旧调用（忽略也不报错）
    timeout_ms: int = 8000,
    xtts_params: Optional[Dict[str, Any]] = None,
) -> str:
    """
    调用本地 TTS，将文本合成为本地音频文件并返回文件路径字符串。
    - 兼容老参数 `voice`；若同时提供，以 `voice_override` 为准。
    """
    if not base_url:
        raise ValueError("base_url is required for local TTS")

    # 兼容处理：老代码传了 voice，就当成 voice_override 用
    if voice_override is None and voice is not None:
        voice_override = voice

    timeout_s = max(int(timeout_ms / 1000), 1)

    payload: Dict[str, Any] = {
        "text": text,
        "voice": voice_override,  # 兼容我们服务端的 voice
        "speaker": voice_override,  # ★ 新增：兼容 XTTS 必填 speaker
        "sample_rate": DEFAULT_SR,
        "format": DEFAULT_FORMAT,
    }

    # 透传 XTTS 情感参数（若提供）
    if xtts_params:
        if "lang" in xtts_params:   payload["lang"]   = xtts_params["lang"]
        if "style" in xtts_params:  payload["style"]  = xtts_params["style"]
        if "speed" in xtts_params:  payload["speed"]  = float(xtts_params["speed"])
        if "energy" in xtts_params: payload["energy"] = float(xtts_params["energy"])
        if "ref_wav_b64" in xtts_params and xtts_params["ref_wav_b64"]:
            payload["ref_wav_b64"] = xtts_params["ref_wav_b64"]

    r = _post_tts(base_url, payload, timeout_s)

    # === 情况 1：直接返回二进制 audio/* ===
    ctype = r.headers.get("Content-Type", "")
    if ctype.lower().startswith("audio/"):
        ext = _ext_from_content_type(ctype, DEFAULT_FORMAT)
        return _save_bytes(out_dir, r.content, ext)

    # === 情况 2/3：JSON ===
    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"Local TTS unexpected response: {e}")

    # base64 内嵌音频
    b64 = data.get("audio_base64") or data.get("audio")
    if isinstance(b64, str) and b64.strip():
        try:
            raw = base64.b64decode(b64.strip(), validate=True)
        except Exception as e:
            raise RuntimeError(f"Invalid base64 audio: {e}")
        ext = data.get("ext") or data.get("format") or DEFAULT_FORMAT or "wav"
        return _save_bytes(out_dir, raw, str(ext))

    # 外链音频
    url = data.get("audio_url")
    if isinstance(url, str) and url.strip():
        if url.startswith("/"):
            url = _compose_url(base_url, url)
        path, _ = _download_url(url, out_dir, timeout=timeout_s)
        return path

    raise RuntimeError("Local TTS response missing audio data (audio_base64/audio/audio_url)")
