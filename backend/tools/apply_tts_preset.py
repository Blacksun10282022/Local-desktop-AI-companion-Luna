# backend/tools/apply_tts_preset.py
from __future__ import annotations
import requests, sys, time

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    api = f"http://127.0.0.1:{port}"
    payload = {
        "tts_mode": "auto",
        "tts_local_url": "http://127.0.0.1:9882",
        "tts_timeout_ms": 18000
    }
    for i in range(20):
        try:
            r = requests.post(f"{api}/config", json=payload, timeout=3)
            r.raise_for_status()
            print("✓ TTS preset applied:", r.json().get("config", {}))
            return
        except Exception:
            print(f"... backend not ready, retry {i+1}/20")
            time.sleep(0.6)
    print("! failed to apply preset")

if __name__ == "__main__":
    main()
