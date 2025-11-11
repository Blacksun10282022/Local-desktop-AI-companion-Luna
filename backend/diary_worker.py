# -*- coding: utf-8 -*-
# backend/diary_worker.py
"""
职责：
- 后台线程：每日写一条“日记”，按运行模式周期性写“inner monologue”
- 仅本地落盘到 LunaData/diary/YYYY-MM-DD.json
- 不在日志打印任何正文内容，避免隐私泄露
"""
from __future__ import annotations
import json, threading, time, random
from pathlib import Path
from datetime import datetime
from typing import Literal, Dict, Any

from data_paths import DIARY_DIR, PHRASES_USER  # DIARY_DIR/PHRASES_USER 均已在 v0.3.1 提供并创建。  # noqa
from config_store import read_config  # 读取运行模式与开关                                         # noqa
from state_manager import read_state, is_night                                                      # noqa

# 句库来源：优先用户私有 LunaData/phrases.json；否则回退 backend/phrases.json（仓库示例）。
# 注：不复用 phrase_bank 的预合成线程，避免跨模块耦合。
_PHRASES_FILE_FALLBACK = Path(__file__).parent / "phrases.json"

def _load_phrases() -> list[str]:
    try:
        p = PHRASES_USER if PHRASES_USER.exists() else _PHRASES_FILE_FALLBACK
        arr = json.loads(p.read_text("utf-8"))
        return [x for x in arr if isinstance(x, str) and x.strip()]
    except Exception:
        return []

def _today_name(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time()).strftime("%Y-%m-%d")

def _day_file(day: str) -> Path:
    return DIARY_DIR / f"{day}.json"

def _read_day(day: str) -> Dict[str, Any]:
    f = _day_file(day)
    if f.exists():
        try:
            return json.loads(f.read_text("utf-8"))
        except Exception:
            pass
    return {"date": day, "entries": []}

def _write_day(day: str, obj: Dict[str, Any]) -> None:
    f = _day_file(day)
    f.write_text(json.dumps(obj, ensure_ascii=False, indent=2), "utf-8")

def _append_entry(kind: Literal["diary", "monologue"], text: str, meta: Dict[str, Any]) -> None:
    day = _today_name()
    data = _read_day(day)
    data.setdefault("entries", []).append({
        "ts": int(time.time()),
        "type": kind,
        "text": text,
        "meta": meta
    })
    _write_day(day, data)

# —— 标签统计（仅输出若干主题词供 prompt 参考，不回传正文）——
_TAGS = {
    "呼吸": ("呼吸","慢慢","放松"),
    "休息": ("休息","闭眼","眺望","走动","放空"),
    "水":   ("喝水","温水","润喉"),
    "肩颈": ("肩","颈","伸展"),
    "光":   ("光","阳","窗"),
}
_MEMORY_FILE = (DIARY_DIR.parent / "memory.json")  # 落在 LunaData/memory.json

def _update_memory_tags(text: str):
    text = text or ""
    try:
        mem = json.loads(_MEMORY_FILE.read_text("utf-8")) if _MEMORY_FILE.exists() else {}
    except Exception:
        mem = {}
    tags = mem.get("tags", {})
    for k, kws in _TAGS.items():
        if any(w in text for w in kws):
            tags[k] = int(tags.get(k, 0)) + 1
    mem["tags"] = tags
    _MEMORY_FILE.write_text(json.dumps(mem, ensure_ascii=False, indent=2), "utf-8")

def get_memory_hint(topk: int = 3) -> str:
    try:
        mem = json.loads(_MEMORY_FILE.read_text("utf-8")) if _MEMORY_FILE.exists() else {}
        pairs = sorted((mem.get("tags", {}) or {}).items(), key=lambda x: -x[1])[:topk]
        return "、".join([k for k, _ in pairs])
    except Exception:
        return ""

# —— 文本合成（本地模板），避免在 v0.4 将私密文本送云 ——
def _compose_diary() -> str:
    phrases = _load_phrases()
    st = read_state()
    clicks = int(st.get("today_clicks", 0))
    late   = int(st.get("late_night_clicks", 0))
    seg = random.choice(phrases) if phrases else "慢慢来，已经很好。"
    parts = []
    now = datetime.now().strftime("%H:%M")
    parts.append(f"{now} 的小记。")
    if clicks > 0:
        parts.append(f"今天被轻触 {clicks} 次。")
    if late > 0:
        parts.append("今晚别太晚。")
    parts.append(seg)
    return " ".join(parts)

def _compose_monologue() -> str:
    # 内心独白尽量短小（8-20字），偏意象化
    phrases = _load_phrases()
    base = random.choice(phrases) if phrases else "把眉头松开一点。"
    return base[:20]

def _cleanup_old_days(keep_days: int):
    try:
        all_files = sorted([p for p in DIARY_DIR.glob("*.json")], key=lambda x: x.stat().st_mtime, reverse=True)
        for p in all_files[keep_days:]:
            p.unlink(missing_ok=True)
    except Exception:
        pass

def _interval_by_mode(mode: str) -> int:
    # 分级频率（分钟）
    return {
        "energy":    120,
        "standard":   60,
        "immersive":  25,
    }.get(mode, 60)

class DiaryWorker:
    def __init__(self):
        self._t = None
        self._stop = False

    def start(self):
        if self._t and self._t.is_alive(): return
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def stop(self):
        self._stop = True

    def _run(self):
        last_day = _today_name()
        last_mono_ts = 0
        # 首次进入立即尝试补一条今日日记（仅当今日未写）
        self.ensure_today_diary()

        while not self._stop:
            try:
                cfg = read_config()
                mode = str(cfg.get("run_mode", "standard") or "standard").lower()
                diary_on = bool(cfg.get("diary_enabled", True))
                mono_on  = bool(cfg.get("monologue_enabled", True))
                keep_days= int(cfg.get("diary_max_days", 60))

                # 换日检测 → 当日首条日记
                now_day = _today_name()
                if diary_on and now_day != last_day:
                    self.ensure_today_diary()
                    last_day = now_day

                # inner monologue 周期
                now = time.time()
                if mono_on and (now - last_mono_ts) >= _interval_by_mode(mode)*60:
                    txt = _compose_monologue()
                    _append_entry("monologue", txt, {
                        "is_night": is_night(),
                        "run_mode": mode
                    })
                    _update_memory_tags(txt)
                    last_mono_ts = now

                # 清理老日记
                _cleanup_old_days(keep_days)

            except Exception:
                # 不打印正文，只保证线程稳态
                pass
            finally:
                time.sleep(30)  # 主循环 30s tick

    def ensure_today_diary(self):
        day = _today_name()
        obj = _read_day(day)
        if not any(e for e in obj.get("entries", []) if e.get("type") == "diary"):
            txt = _compose_diary()
            _append_entry("diary", txt, {
                "is_night": is_night(),
                "clicks": int(read_state().get("today_clicks", 0))
            })
            _update_memory_tags(txt)
