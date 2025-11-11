# C:\Users\32707\Desktop\Luna\backend\tools\probe_xtts_speakers.py
import os, requests, pathlib, time, json
from TTS.api import TTS

XTTS = "http://127.0.0.1:9882"
OUT = pathlib.Path("probe"); OUT.mkdir(exist_ok=True)
MODEL_DIR = r"C:\Users\32707\Desktop\Luna\LunaModels\tts\xtts_v2"

def list_speakers_http():
    try:
        r = requests.get(f"{XTTS}/speakers", timeout=5)
        print("GET /speakers:", r.status_code, r.text[:200])
        if r.ok:
            data = r.json()
            if isinstance(data, dict) and "speakers" in data:
                return list(data["speakers"])
            if isinstance(data, list):
                return list(data)
    except Exception as e:
        print("http speakers error:", e)
    return []

def list_speakers_local():
    cfg = os.path.join(MODEL_DIR, "config.json")
    tts = TTS(model_path=MODEL_DIR, config_path=cfg, progress_bar=False)
    try: tts.to("cuda")
    except Exception: tts.to("cpu")
    sm = tts.synthesizer.tts_model.speaker_manager
    return list(getattr(sm, "speakers", {}).keys())

def main():
    spks = list_speakers_http() or list_speakers_local()
    print("speakers:", len(spks))
    for i, s in enumerate(spks[:58]):   # 先探 30 个
        try:
            t0 = time.time()
            r = requests.post(f"{XTTS}/v1/tts", json={"text":"你好，我在呢。","lang":"zh","speaker":s}, timeout=60)
            if r.ok:
                (OUT/f"{i:02d}_{s}.wav").write_bytes(r.content)
                print(f"{i:02d} {s} -> {time.time()-t0:.2f}s")
            else:
                print(f"{i:02d} {s} -> HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            print(f"{i:02d} {s} -> error: {e}")
    print("done ->", OUT.resolve())

if __name__ == "__main__":
    main()
