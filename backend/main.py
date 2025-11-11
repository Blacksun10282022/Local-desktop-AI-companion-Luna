# backend/main.py  （隐私隔离版 + 就绪同步 + v0.5 TTS 路由）
from __future__ import annotations

from diary_worker import DiaryWorker, get_memory_hint
from dotenv import load_dotenv; load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import time, random

from data_paths import AUDIO_DIR, PHRASES_USER, boot_print

# v0.5：引入路由版 TTS
from tts_router import call_tts_routed

# 仅用于启动日志打印模块路径（可选）
import tts_client

from llm_client import call_llm, has_night_terms
from state_manager import read_state, write_state, touch_event, bump_click, is_night
from prewarm import warm_all
from phrase_bank import load_phrases, start_worker, pop_ready
from cleaner import cleanup_audio
from config_store import read_config, write_config
from llm_router import call_llm_routed


print("[BOOT] tts(client) from:", tts_client.__file__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # 允许 null/file 源
    allow_credentials=False,  # 关键：禁用凭据以避免 * 冲突
    allow_methods=["*"],
    allow_headers=["*"],
)

# 只挂 LunaData/audio
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
PHRASES_SAMPLE = Path(__file__).parent / "phrases.json"

# ====== 全局就绪标记 ======
_READY = False
_WARMUP_START_TIME = None
_DIARY_WORKER = None  # ← v0.4


class EventIn(BaseModel):
    type: str
    meta: dict | None = None
    timestamp: int | None = None  # 毫秒


class ConfigIn(BaseModel):
    # v0.3/0.4
    mute: bool | None = None
    prefer_cache_prob: float | None = None
    voice_override: str | None = None
    audio_keep_latest: int | None = None
    audio_expire_days: int | None = None
    auto_tune_cache: bool | None = None
    run_mode: str | None = None
    diary_enabled: bool | None = None
    monologue_enabled: bool | None = None
    diary_max_days: int | None = None
    privacy_mode: bool | None = None
    ui_hide_bubble: bool | None = None
    # v0.5 新增（允许前端修改）
    tts_mode: str | None = None            # cloud | local | auto
    tts_local_url: str | None = None       # 例如 http://127.0.0.1:9880
    tts_timeout_ms: int | None = None      # 本地 HTTP 超时
    # v0.6 新增（LLM 路由相关）
    llm_mode: str | None = None                     # "cloud" | "local_small" | "local_big" | "local_only" | "auto"
    llm_local_url_small: str | None = None          # 例如 http://127.0.0.1:9970
    llm_local_url_big: str | None = None            # 例如 http://127.0.0.1:9971
    llm_small_chars_max: int | None = None
    llm_big_chars_min: int | None = None
    llm_sensitive_words: list[str] | None = None


@app.on_event("startup")
def _startup():
    boot_print()
    global _READY, _WARMUP_START_TIME
    _WARMUP_START_TIME = time.time()

    print("[BOOT] startup warm.")
    cfg = read_config()

    # 私有句库优先
    phrases_path = PHRASES_USER if PHRASES_USER.exists() else PHRASES_SAMPLE
    load_phrases(phrases_path)

    start_worker(AUDIO_DIR, preload=2)
    warm_all(AUDIO_DIR)
    cleanup_audio(AUDIO_DIR, keep_latest=cfg["audio_keep_latest"], expire_days=cfg["audio_expire_days"])

    # v0.4：启动日记/独白后台
    global _DIARY_WORKER
    _DIARY_WORKER = DiaryWorker()
    _DIARY_WORKER.start()

    _READY = True  # ← 标记就绪
    warmup_time = time.time() - _WARMUP_START_TIME
    print(f"[BOOT] startup ready. (warmup took {warmup_time:.2f}s)")


@app.get("/ready")
def check_ready():
    """就绪检查端点：前端用于轮询后端是否完成预热"""
    return {
        "ready": _READY,
        "warmup_time": (time.time() - _WARMUP_START_TIME) if _WARMUP_START_TIME else 0
    }


@app.get("/ping")
def ping():
    """简单健康检查：用于检测后端服务是否在线（不考虑预热状态）"""
    return {"ok": True, "ts": time.time(), "ready": _READY}


@app.get("/config")
def get_config():
    return read_config()


@app.post("/config")
def set_config(cfg: ConfigIn):
    new_cfg = {k: v for k, v in cfg.dict().items() if v is not None}
    out = write_config(new_cfg)
    return {"ok": True, "config": out}


@app.post("/event")
def handle_event(ev: EventIn):
    t0 = time.time()
    state = read_state()
    cfg = read_config()

    now_ms = int(ev.timestamp) if ev.timestamp is not None else int(time.time() * 1000)
    now_s = now_ms // 1000
    tmp_state = bump_click(dict(state), now_s)
    meta = {
        "is_night": is_night(now_s),
        "today_clicks": int(tmp_state.get("today_clicks", 0)),
        "late_night_clicks": int(tmp_state.get("late_night_clicks", 0)),
    }

    THEMES = ["护颈放松", "抬头眺望", "喝口温水", "轻轻呼吸", "调暗一点灯光", "伸展手腕",
              "走动一分钟", "眉头放松", "播放轻音乐", "善待自己", "整理桌面", "慢一点节奏"]
    theme = random.choice(THEMES)

    use_cache = (random.random() < float(cfg.get("prefer_cache_prob", 0.6)))
    pick = pop_ready() if use_cache else None

    branch = "cache"
    text = None
    audio_rel = None
    if pick is not None:
        text, audio_abs = pick
        if not meta["is_night"] and has_night_terms(text):
            print("[/event] cache-skip: day-time phrase has night terms → go online")
            pick = None
        elif audio_abs and Path(audio_abs).exists():
            audio_rel = f"/audio/{Path(audio_abs).name}"
        else:
            print("[/event] cache-stale: file missing, regenerate")
            branch = "online"

    if audio_rel is None:
        branch = "online"
        ctx = {
            "now_ts": now_s, "event_type": ev.type,
            "counters": state.get("counters", {}), "flags": state.get("flags", {}),
            "meta": meta, "theme": theme, "last_text": state.get("last_text", ""),
            "memory_hint": get_memory_hint()  # ← v0.4 仅关键词
        }
        if text is None:
            text = call_llm_routed(ctx)
        # v0.5：统一走路由（本地失败自动回落云端）
        audio_file = call_tts_routed(text, AUDIO_DIR, voice=cfg.get('voice_override'))
        audio_rel = f"/audio/{Path(audio_file).name}"

    state["last_text"] = text
    touch_event(state, ev.type)
    state = bump_click(state, now_s)
    write_state(state)

    dt_ms = int((time.time() - t0) * 1000)
    if branch == "online" and bool(cfg.get("auto_tune_cache", False)):
        if dt_ms > 2500:
            cfg["prefer_cache_prob"] = min(0.9, float(cfg.get("prefer_cache_prob", 0.6)) + 0.1)
            write_config({"prefer_cache_prob": cfg["prefer_cache_prob"]})
        elif dt_ms < 1200:
            cfg["prefer_cache_prob"] = max(0.4, float(cfg.get("prefer_cache_prob", 0.6)) - 0.05)
            write_config({"prefer_cache_prob": cfg["prefer_cache_prob"]})

    fname = Path(audio_rel).name  # 可选：避免重复 Path 解析
    if bool(cfg.get("privacy_mode", False)):
        # 隐私模式：不打印文本
        print(f"[/event] branch={branch} dt={dt_ms}ms file='{fname}'")
    else:
        # 常规模式：打印完整文本
        print(f"[/event] branch={branch} dt={dt_ms}ms text='{text}' file='{fname}'")

    if state.get("counters", {}).get("poke", 0) % 20 == 0:
        cleanup_audio(AUDIO_DIR, keep_latest=cfg["audio_keep_latest"], expire_days=cfg["audio_expire_days"])

    return {"text": text, "audio_url": audio_rel, "branch": branch, "dt": dt_ms, "meta": meta}