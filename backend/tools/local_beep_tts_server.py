# backend/tools/local_beep_tts_server.py
from __future__ import annotations
from fastapi import FastAPI, Response
from pydantic import BaseModel
import io, math, wave, struct

app = FastAPI()

class TTSIn(BaseModel):
    text: str
    voice: str | None = None
    format: str | None = "wav"
    sample_rate: int | None = 24000
    stream: bool | None = False

@app.get("/health")
def health():
    return {"ok": True}

def sine_wav_bytes(freq: float = 880.0, sr: int = 24000, dur: float = 1.0, amp: float = 0.2) -> bytes:
    nframes = int(sr * dur)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for n in range(nframes):
            val = int(amp * 32767.0 * math.sin(2.0 * math.pi * freq * (n / sr)))
            wf.writeframes(struct.pack("<h", val))
    return buf.getvalue()

@app.post("/v1/tts")
def tts(inp: TTSIn):
    data = sine_wav_bytes(sr=inp.sample_rate or 24000)
    return Response(content=data, media_type="audio/wav")

if __name__ == "__main__":
    import uvicorn, argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9880)
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
