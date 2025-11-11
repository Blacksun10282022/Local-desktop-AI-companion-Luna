# backend/state_manager.py
# 轻量运行状态：写到 data_paths.STATE_FILE（仓库外）
from data_paths import STATE_FILE
import json, time
from datetime import datetime

def read_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text("utf-8"))
    except Exception:
        pass
    return {
        "last_events": [], "counters": {}, "flags": {}, "profile": {},
        "last_ts": None, "today_clicks": 0, "late_night_clicks": 0, "day": _today_str()
    }

def write_state(state: dict):
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")
    except Exception:
        pass

def touch_event(state, ev_type: str):
    state["last_events"] = (state.get("last_events", []) + [{"type": ev_type, "ts": int(time.time())}])[-20:]
    c = state.get("counters", {}); c[ev_type] = c.get(ev_type, 0) + 1
    state["counters"] = c

def _today_str(ts: int | None = None) -> str:
    dt = datetime.fromtimestamp(ts if ts is not None else time.time())
    return dt.strftime("%Y-%m-%d")

def _hour_of(ts: int) -> int:
    return datetime.fromtimestamp(ts).hour

def is_night(ts: int | None = None) -> bool:
    h = _hour_of(int(ts if ts is not None else time.time()))
    return (h >= 22) or (h <= 6)

def bump_click(state: dict, ts: int) -> dict:
    day_now = _today_str(ts)
    if state.get("day") != day_now:
        state["today_clicks"] = 0
        state["late_night_clicks"] = 0
        state["day"] = day_now
    state["today_clicks"] = int(state.get("today_clicks", 0)) + 1
    h = _hour_of(ts)
    if 0 <= h <= 3:
        state["late_night_clicks"] = int(state.get("late_night_clicks", 0)) + 1
    state["last_ts"] = ts
    return state
