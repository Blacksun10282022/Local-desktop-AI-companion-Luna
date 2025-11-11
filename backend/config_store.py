# backend/config_store.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
from data_paths import CFG_FILE, PHRASES_USER
from datetime import datetime
import json, time

_DEFAULT: Dict[str, Any] = {
    # v0.3
    "mute": False,
    "prefer_cache_prob": 0.6,
    "voice_override": None,
    "audio_keep_latest": 80,
    "audio_expire_days": 7,
    "auto_tune_cache": False,
    # v0.4
    "run_mode": "standard",
    "diary_enabled": True,
    "monologue_enabled": True,
    "diary_max_days": 60,
    "privacy_mode": False,
    "ui_hide_bubble": False,
    # v0.5
    "tts_mode": "cloud",
    "tts_local_url": None,
    "tts_timeout_ms": 8000,
    # v0.6（LLM 双脑）
    "llm_mode": "auto",
    "llm_local_url_small": "http://127.0.0.1:9970",
    "llm_local_url_big":   "http://127.0.0.1:9971",
    "llm_small_chars_max": 120,
    "llm_big_chars_min":   160,
    "llm_sensitive_words": ["日记","独白","梦","隐私"],
    # ✅ 新增：前端窗口位置/尺寸预设
    "window_position": None,            # {"x":int,"y":int} | None
    "window_size_preset": "medium",     # small | medium | large
}

_PHRASES_FILE_FALLBACK = Path(__file__).parent / "phrases.json"

def _clamp_prob(v: Any, default: float = 0.6) -> float:
    try:
        x = float(v); x = 0.0 if x < 0 else (1.0 if x > 1 else x); return x
    except Exception:
        return default

def _pos_int(v: Any, default: int) -> int:
    try:
        x = int(v); return x if x > 0 else default
    except Exception:
        return default

def _sanitize_pos(v: Any):
    try:
        x = int(v.get("x")); y = int(v.get("y"))
        return {"x": x, "y": y}
    except Exception:
        return None

def _sanitize_preset(v: Any) -> str:
    s = str(v or "").lower()
    return s if s in ("small","medium","large") else "medium"

def _merge_defaults(x: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(_DEFAULT); out.update(x or {})
    out["prefer_cache_prob"] = _clamp_prob(out.get("prefer_cache_prob", 0.6))
    out["audio_keep_latest"] = _pos_int(out.get("audio_keep_latest", 80), 80)
    out["audio_expire_days"] = _pos_int(out.get("audio_expire_days", 7), 7)
    out["diary_max_days"]    = _pos_int(out.get("diary_max_days", 60), 60)
    out["tts_timeout_ms"]    = _pos_int(out.get("tts_timeout_ms", 8000), 8000)
    out["llm_small_chars_max"] = _pos_int(out.get("llm_small_chars_max", 120), 120)
    out["llm_big_chars_min"]   = _pos_int(out.get("llm_big_chars_min", 160), 160)
    # 新增：窗口字段
    wp = out.get("window_position", None)
    out["window_position"] = _sanitize_pos(wp) if isinstance(wp, dict) else None
    out["window_size_preset"] = _sanitize_preset(out.get("window_size_preset", "medium"))
    return out

def read_config() -> Dict[str, Any]:
    if not CFG_FILE.exists():
        CFG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CFG_FILE.write_text(json.dumps(_DEFAULT, ensure_ascii=False, indent=2), "utf-8")
        return dict(_DEFAULT)
    try:
        data = json.loads(CFG_FILE.read_text("utf-8"))
        if not isinstance(data, dict): data = {}
    except Exception:
        data = {}
    return _merge_defaults(data)

def write_config(new_cfg: Dict[str, Any]) -> Dict[str, Any]:
    cur = read_config()
    merged: Dict[str, Any] = dict(cur)
    for k, v in (new_cfg or {}).items():
        if k not in _DEFAULT:
            continue
        if k == "prefer_cache_prob":
            merged[k] = _clamp_prob(v, cur.get("prefer_cache_prob", 0.6))
        elif k in ("audio_keep_latest", "audio_expire_days", "diary_max_days",
                   "tts_timeout_ms", "llm_small_chars_max", "llm_big_chars_min"):
            merged[k] = _pos_int(v, cur.get(k, _DEFAULT[k]))
        elif k == "window_position":
            merged[k] = _sanitize_pos(v) if isinstance(v, dict) else None
        elif k == "window_size_preset":
            merged[k] = _sanitize_preset(v)
        else:
            merged[k] = v
    CFG_FILE.write_text(json.dumps(_merge_defaults(merged), ensure_ascii=False, indent=2), "utf-8")
    return _merge_defaults(merged)

def load_phrases() -> list[str]:
    try:
        p = PHRASES_USER if PHRASES_USER.exists() else _PHRASES_FILE_FALLBACK
        arr = json.loads(p.read_text("utf-8"))
        return [x for x in arr if isinstance(x, str) and x.strip()]
    except Exception:
        return []

def today_name(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time()).strftime("%Y-%m-%d")
