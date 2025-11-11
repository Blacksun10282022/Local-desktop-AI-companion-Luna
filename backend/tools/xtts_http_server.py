# -*- coding: utf-8 -*-
"""
XTTS v2 本地 HTTP 服务（离线、GPU/CPU 二合一）
POST /v1/tts -> audio/wav（二进制）
GET  /health -> {"ok":true,"device":"cuda|cpu","model_dir":"..."}
GET  /speakers -> {"speakers":[...]}
依赖:
  pip install TTS fastapi uvicorn soundfile librosa
  # GPU: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
"""
from __future__ import annotations
import os, io, base64, tempfile, glob
from typing import Optional, Tuple, List
import numpy as np
import soundfile as sf
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from TTS.api import TTS

# ========= 路径与设备 =========
XTTS_MODEL_DIR = os.getenv(
    "XTTS_MODEL_DIR",
    r"C:\Users\32707\Desktop\Luna\LunaModels\tts\xtts_v2"
)
DEVICE = os.getenv("XTTS_DEVICE", "cuda")  # "cuda" / "cpu"

# ========= 加载（显式传 config.json，避免 NoneType） =========
def _find_cfg(model_dir: str) -> str:
    md = os.path.normpath(str(model_dir)).strip().strip('\'"')
    if not os.path.isdir(md):
        raise FileNotFoundError(f"[XTTS] 模型目录不存在：{md}")
    hits = []
    for pat in ("config.json", "*config*.json"):
        hits += glob.glob(os.path.join(md, pat))
    if hits:
        return hits[0]
    try:
        listing = ", ".join(os.listdir(md)[:10])
    except Exception:
        listing = "N/A"
    raise FileNotFoundError(f"[XTTS] 未找到 config.json，目录：{md}；列举：{listing}")

def load_tts(model_dir: str, device: str):
    md = os.path.normpath(str(model_dir)).strip().strip('\'"')
    cfg = _find_cfg(md)
    tts = TTS(model_path=md, config_path=cfg, progress_bar=False)
    try:
        tts.to(device); used = device
    except Exception:
        tts.to("cpu"); used = "cpu"
    return tts, used

tts, USED_DEVICE = load_tts(XTTS_MODEL_DIR, DEVICE)

# ========= 枚举 speakers =========
def list_speakers(tts_obj) -> List[str]:
    try:
        sm = getattr(getattr(getattr(tts_obj, "synthesizer", None), "tts_model", None), "speaker_manager", None)
        sp = getattr(sm, "speakers", None)
        if isinstance(sp, dict) and sp:
            return list(sp.keys())
    except Exception:
        pass
    try:
        sp2 = getattr(tts_obj, "speakers", None)
        if isinstance(sp2, (list, tuple)) and sp2:
            return list(sp2)
    except Exception:
        pass
    return []

SPEAKERS = list_speakers(tts)

# ========= 情感/风格 =========
STYLE = {
    "neutral": {"speed": 1.00, "energy": 1.00},
    "gentle":  {"speed": 0.95, "energy": 0.85},
    "soothe":  {"speed": 0.90, "energy": 0.80},
    "cheer":   {"speed": 1.10, "energy": 1.10},
}

class In(BaseModel):
    text: str
    lang: str = "zh"
    style: Optional[str] = "neutral"
    speed: Optional[float] = 1.0
    energy: Optional[float] = 1.0
    ref_wav_b64: Optional[str] = None
    speaker: Optional[str] = None
    voice: Optional[str] = None

# ========= FastAPI =========
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False
)

@app.get("/health")
def health():
    return {"ok": True, "device": USED_DEVICE, "model_dir": XTTS_MODEL_DIR}

@app.get("/speakers")
def get_speakers():
    return {"speakers": SPEAKERS}

def _time_stretch(wav: np.ndarray, sr: int, rate: float) -> Tuple[np.ndarray, int]:
    if abs(rate - 1.0) < 1e-3:
        return wav, sr
    import librosa
    y = wav.astype(np.float32)
    y = librosa.effects.time_stretch(y, rate=rate)
    return y, sr

def _synthesize_to_file(text: str, lang: str, spk: Optional[str], ref_path: Optional[str]) -> str:
    fd, tmp_wav = tempfile.mkstemp(suffix=".wav"); os.close(fd)
    if ref_path:
        tts.tts_to_file(text=text, speaker_wav=ref_path, language=lang, file_path=tmp_wav)
    else:
        if not spk:
            raise ValueError("No available speaker found; provide `speaker` or `ref_wav_b64`.")
        tts.tts_to_file(text=text, speaker=spk, language=lang, file_path=tmp_wav)
    return tmp_wav

@app.post("/v1/tts")
def tts_api(inp: In):
    # 1) 风格融合
    preset = STYLE.get((inp.style or "neutral").lower(), STYLE["neutral"])
    speed  = float(inp.speed  if inp.speed  is not None else 1.0) * preset["speed"]
    energy = float(inp.energy if inp.energy is not None else 1.0) * preset["energy"]

    # 2) 参考音色（可选）
    ref_path = None
    if inp.ref_wav_b64:
        raw = base64.b64decode(inp.ref_wav_b64)
        fd, ref_path = tempfile.mkstemp(suffix=".wav"); os.write(fd, raw); os.close(fd)

    # 3) 决定 speaker
    default_speaker = SPEAKERS[0] if SPEAKERS else None
    chosen_speaker = (inp.speaker or inp.voice or default_speaker)
    lang = (inp.lang or "zh").lower()

    # 4) 合成：主路+两次兜底
    tmp_wav = None
    try:
        try:
            tmp_wav = _synthesize_to_file(inp.text, lang, chosen_speaker, ref_path)
        except Exception:
            # 兜底 1：强制中文
            try:
                tmp_wav = _synthesize_to_file(inp.text, "zh", chosen_speaker, ref_path)
            except Exception:
                # 兜底 2：换默认 speaker
                if default_speaker and default_speaker != chosen_speaker:
                    tmp_wav = _synthesize_to_file(inp.text, "zh", default_speaker, ref_path)
                else:
                    raise

        # 读回 + 归一化
        wav, sr = sf.read(tmp_wav, dtype="float32", always_2d=False)
        if wav is None or (isinstance(wav, np.ndarray) and wav.size == 0):
            wav = np.zeros(int(24000 * 0.3), dtype=np.float32); sr = 24000
        wav = np.asarray(wav, dtype=np.float32)
        if wav.ndim > 1: wav = wav.reshape(-1)
        peak = float(np.max(np.abs(wav))) if wav.size else 0.0
        if peak > 0: wav = np.clip(wav * min(1.0, 0.9/peak), -1.0, 1.0)
        else:        wav = np.zeros(int((sr or 24000) * 0.3), dtype=np.float32)

        # 速度/能量
        if abs(speed - 1.0) > 1e-3: wav, sr = _time_stretch(wav, sr, rate=speed)
        if abs(energy - 1.0) > 1e-3: wav = np.clip(wav * energy, -1.0, 1.0)

        buf = io.BytesIO(); sf.write(buf, wav, int(sr or 24000), format="WAV")
        return Response(buf.getvalue(), media_type="audio/wav")

    finally:
        try:
            if ref_path and os.path.exists(ref_path): os.remove(ref_path)
        except: pass
        try:
            if tmp_wav and os.path.exists(tmp_wav): os.remove(tmp_wav)
        except: pass
