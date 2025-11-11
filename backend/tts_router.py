# -*- coding: utf-8 -*-
# 作用：在 cloud / local / auto 三种模式之间路由 TTS 调用；本地失败自动回落到云端。
from __future__ import annotations
from pathlib import Path
from typing import Optional
import os
import re

from config_store import read_config
from tts_client import call_tts as call_cloud_tts
from local_tts_client import call_local_tts


def _to_int(v, default: int) -> int:
    try:
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return default


def _detect_lang(text: str) -> str:
    """极简语言检测：含 CJK → zh，否则 en（XTTS 也可接收 ja/ko）。"""
    if re.search(r"[\u4e00-\u9fff]", text or ""):
        return "zh"
    return "en"


# 你要求 Cloud 默认 Cherry，这里就只白名单 Cherry；不在表里的声线一律用 Cherry
QWEN_VOICES = {"Cherry"}


def call_tts_routed(text: str, out_dir: Path, voice: Optional[str] = None) -> str:
    """
    路由策略：
      - cloud: 直接云端
      - local: 只打本地；失败则回落云端
      - auto : 先打本地，失败自动回落云端
    返回：落盘后的音频“绝对文件路径字符串”
    """
    cfg = read_config()
    mode = (os.getenv("TTS_MODE") or cfg.get("tts_mode") or "cloud").strip().lower()
    local_url = (os.getenv("LUNA_TTS_LOCAL_URL") or cfg.get("tts_local_url") or "").strip()
    timeout_ms = _to_int(os.getenv("TTS_HTTP_TIMEOUT") or cfg.get("tts_timeout_ms") or 8000, 8000)

    # —— XTTS 情感参数（从 env > settings 读取；不存在时不影响其他本地服务）——
    style   = (os.getenv("XTTS_STYLE")   or cfg.get("tts_style")   or "neutral").strip().lower()
    speed   = float(os.getenv("XTTS_SPEED")   or cfg.get("tts_speed")   or 1.0)
    energy  = float(os.getenv("XTTS_ENERGY")  or cfg.get("tts_energy")  or 1.0)
    lang    = (os.getenv("XTTS_LANG")    or cfg.get("tts_lang")    or _detect_lang(text)).strip().lower()
    ref_b64 =  os.getenv("XTTS_REF_B64") or cfg.get("tts_ref_b64") or None

    xtts_params = {
        "lang":   lang,
        "style":  style,
        "speed":  speed,
        "energy": energy,
    }
    if ref_b64:
        xtts_params["ref_wav_b64"] = ref_b64

    def _try_local() -> str:
        if not local_url:
            raise RuntimeError("LUNA_TTS_LOCAL_URL not set")
        return call_local_tts(
            text=text,
            out_dir=out_dir,
            base_url=local_url,
            voice_override=voice,     # 本地 XTTS 会把它当作 speaker
            timeout_ms=timeout_ms,
            xtts_params=xtts_params,  # 透传给 /v1/tts
        )

    # —— 云端调用：只传白名单，否则强制 Cherry（你要求的默认 Cloud 声音）——
    def _call_cloud() -> str:
        safe_voice = voice if (voice in QWEN_VOICES) else "Cherry"
        return call_cloud_tts(text=text, out_dir=out_dir, voice=safe_voice)

    if mode == "cloud":
        return _call_cloud()

    if mode == "local":
        try:
            p = _try_local()
            print(f"[TTS] local ok: {Path(p).name}")
            return p
        except Exception as e:
            print(f"[TTS] local failed: {e}; fallback=cloud")
            return _call_cloud()

    # auto
    try:
        p = _try_local()
        print(f"[TTS] auto→local ok: {Path(p).name}")
        return p
    except Exception as e:
        print(f"[TTS] auto→local failed: {e}; fallback=cloud")
        return _call_cloud()
