# -*- coding: utf-8 -*-
# backend/llm_router.py  (Dual-Brain)
"""
cloud / local_small / local_big / local_only / auto
- cloud       ：始终云端
- local_small ：始终本地 small
- local_big   ：始终本地 big
- local_only  ：仅本地（按阈值 small/big；small 失败→big；禁止云回退）
- auto        ：按敏感/长度走本地（small/big），任何本地失败→云端回退
"""
from __future__ import annotations
from typing import Dict, Any
import os
from config_store import read_config
from llm_client import call_llm as call_cloud_llm
from local_llm_client import call_local_llm

def _to_int(v, d:int)->int:
    try: return int(v)
    except:
        try: return int(float(v))
        except: return d

def _len_hint(ctx: Dict[str,Any]) -> int:
    try: return int(ctx.get("len_hint", 16))  # 默认短句
    except: return 16

def _is_sensitive(ctx: Dict[str,Any], kws:list[str]) -> bool:
    et = str(ctx.get("event_type","")).lower()
    if et in ("diary","monologue","private","inner"):
        return True
    text = f"{ctx.get('last_text','')} {ctx.get('theme','')} {ctx.get('topic','')}"
    return any(k and (k in text) for k in kws)

def _kws(cfg)->list[str]:
    kws = cfg.get("llm_sensitive_words") or []
    if isinstance(kws, str): kws = [x for x in kws.split(",") if x.strip()]
    return kws

def _pick_url(cfg, big: bool) -> str:
    if big:
        return (os.getenv("LUNA_LLM_LOCAL_BIG_URL") or cfg.get("llm_local_url_big") or "").strip()
    return (os.getenv("LUNA_LLM_LOCAL_SMALL_URL") or cfg.get("llm_local_url_small") or "").strip()

def _prefer_small(ctx:Dict[str,Any], cfg)->bool:
    n = _len_hint(ctx)
    small_max = _to_int(os.getenv("LLM_SMALL_CHARS_MAX") or cfg.get("llm_small_chars_max") or 120, 120)
    big_min   = _to_int(os.getenv("LLM_BIG_CHARS_MIN")   or cfg.get("llm_big_chars_min")   or 160, 160)
    if n >= big_min: return False  # 长段 → big
    return True                    # 其他默认 small

def _call_local(ctx, cfg, big:bool, timeout_ms:int)->str:
    url = _pick_url(cfg, big)
    if not url:
        raise RuntimeError("缺少本地 LLM URL")
    return call_local_llm(ctx, base_url=url, timeout_ms=timeout_ms)

def call_llm_routed(ctx: Dict[str,Any]) -> str:
    cfg  = read_config()
    mode = (os.getenv("LLM_MODE") or cfg.get("llm_mode") or "auto").strip().lower()
    kws  = _kws(cfg)
    timeout_ms = int(cfg.get("tts_timeout_ms") or 8000)  # 复用一套超时

    if mode == "cloud":       return call_cloud_llm(ctx)
    if mode == "local_small": return _call_local(ctx, cfg, big=False, timeout_ms=timeout_ms)
    if mode == "local_big":   return _call_local(ctx, cfg, big=True,  timeout_ms=timeout_ms)

    if mode == "local_only":
        small = _prefer_small(ctx, cfg)
        try:
            return _call_local(ctx, cfg, big=not small, timeout_ms=timeout_ms) if not small else \
                   _call_local(ctx, cfg, big=False, timeout_ms=timeout_ms)
        except Exception:
            # small 失败→尝试 big（或反之），仍禁止云回退
            return _call_local(ctx, cfg, big=small, timeout_ms=timeout_ms)

    # auto：敏感/短句→small；长段→big；本地失败→云
    is_sensitive = _is_sensitive(ctx, kws) or bool(ctx.get("is_sensitive"))
    prefer_small = _prefer_small(ctx, cfg)
    try:
        return _call_local(ctx, cfg, big=False, timeout_ms=timeout_ms) if (is_sensitive or prefer_small) \
               else _call_local(ctx, cfg, big=True, timeout_ms=timeout_ms)
    except Exception:
        return call_cloud_llm(ctx)
