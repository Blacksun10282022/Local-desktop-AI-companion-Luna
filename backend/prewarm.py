# backend/prewarm.py
"""
职责：
- 启动阶段“热身” LLM 与 TTS；
- v0.5 起：优先探活本地 TTS，统一走路由 `call_tts_routed` 进行一次极短合成，
  确保本地链路/回落链路真实可用；若生成了 beep_* 则丢弃避免进入缓存池。
"""

from __future__ import annotations
import os
import time
from pathlib import Path

from llm_client import call_llm
from config_store import read_config
from local_tts_client import ping_local_tts
from tts_router import call_tts_routed  # 统一路由（cloud/local/auto）

def warm_all(audio_dir: Path):
    t0 = time.time()

    # 1) 预热 LLM（允许失败，不打断启动）
    try:
        _ = call_llm({"event_type": "warmup", "counters": {}, "flags": {}})
    except Exception as e:
        print(f"[WARM] LLM warmup skip: {e}")

    # 2) 本地 TTS 探活 + 路由一次极短合成
    cfg = read_config()
    local_url = (os.getenv("LUNA_TTS_LOCAL_URL") or cfg.get("tts_local_url") or "").strip()
    timeout_ms = int(cfg.get("tts_timeout_ms") or 8000)

    local_alive = ping_local_tts(local_url, timeout_ms=timeout_ms) if local_url else False

    tts_ok = False
    try:
        p = Path(call_tts_routed("我在呢，放心点我。", audio_dir, voice=cfg.get("voice_override")))
        # 若是 beep_ 兜底，删除避免进入缓存池
        if p.name.startswith("beep_"):
            try:
                p.unlink()
            except Exception:
                pass
        else:
            tts_ok = True
    except Exception as e:
        print(f"[WARM] TTS warmup failed: {e}")
        tts_ok = False

    dt = time.time() - t0
    print(f"[WARM] LLM+TTS done in {dt:.2f}s, local_alive={local_alive}, tts_ok={tts_ok}")
