# backend/phrase_bank.py
from __future__ import annotations
from pathlib import Path
import json, threading, queue, random, time
from typing import Optional

# v0.5：改为路由版 TTS（本地失败自动回落云端）
from tts_router import call_tts_routed

_PHRASES: list[str] = []
_READY: "queue.Queue[tuple[str,str]]" = queue.Queue()
_WORKER: Optional[threading.Thread] = None
_LAST_TEXT: Optional[str] = None

def load_phrases(phrases_path: Path):
    """加载短句 JSON（list[str]），过滤空白。"""
    global _PHRASES
    if phrases_path.exists():
        try:
            arr = json.loads(phrases_path.read_text("utf-8"))
            _PHRASES = [p for p in arr if isinstance(p, str) and p.strip()]
            print(f"[PHRASE] loaded {len(_PHRASES)} phrases from {phrases_path.name}")
        except Exception as e:
            print("[PHRASE] load error:", e)
            _PHRASES = []
    else:
        _PHRASES = []
        print(f"[PHRASE] not found: {phrases_path}")

def _pick_phrase() -> Optional[str]:
    """尽量避免与上一句重复，最多尝试 6 次；失败返回任意一句。"""
    global _LAST_TEXT
    if not _PHRASES:
        return None
    for _ in range(6):
        p = random.choice(_PHRASES)
        if p != _LAST_TEXT:
            return p
    return random.choice(_PHRASES)

def start_worker(audio_dir: Path, preload: int = 6):
    """后台线程：把短句预合成到一个小池里（text, file_path）。"""
    global _WORKER, _LAST_TEXT
    if _WORKER and _WORKER.is_alive():
        return

    audio_dir.mkdir(parents=True, exist_ok=True)

    def _run():
        global _LAST_TEXT
        random.seed(time.time())
        while True:
            try:
                # 池子不够就补，够了就小憩
                while _READY.qsize() < preload and _PHRASES:
                    phrase = _pick_phrase()
                    if not phrase:
                        break
                    try:
                        # v0.5：统一走路由（本地→失败回落云端）
                        out_path = call_tts_routed(phrase, audio_dir, voice=None)
                        _READY.put_nowait((phrase, str(out_path)))
                        _LAST_TEXT = phrase
                        # 轻微节流，避免集中生成
                        time.sleep(random.uniform(0.25, 0.45))
                    except Exception as e:
                        print("[PHRASE] synth fail:", e)
                        time.sleep(random.uniform(0.4, 0.8))

                # 间隔检查
                time.sleep(random.uniform(1.2, 1.6))

            except Exception as e:
                print("[PHRASE] worker error:", e)
                time.sleep(1.0)

    _WORKER = threading.Thread(target=_run, daemon=True)
    _WORKER.start()

def pop_ready() -> Optional[tuple[str,str]]:
    """取出一条已合成的 (text, abs_file_path)。"""
    try:
        return _READY.get_nowait()
    except Exception:
        return None
