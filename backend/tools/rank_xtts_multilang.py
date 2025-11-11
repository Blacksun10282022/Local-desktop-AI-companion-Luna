# -*- coding: utf-8 -*-
r"""
XTTS v2 多音色四语种评测（GPU 端口 9882，仅测本地 HTTP 服务）
语言: 中文/英文/日文/韩文
指标: zh/ja/ko -> CER(字符级)，en -> WER(词级)
结果: C:\Users\32707\Desktop\Luna\LunaData\metrics\xtts_rank.csv

用法：
  conda activate luna-xtts
  set FW_MODEL_SIZE=medium        # 可选: medium / large-v3（你要全量就设 large-v3）
  python C:\Users\32707\Desktop\Luna\backend\tools\rank_xtts_multilang.py
"""

import os, csv, time, pathlib, statistics, requests, unicodedata, re, math
from typing import List, Dict
import numpy as np

# ===== 仅测 GPU 端口 =====
XTTS_BASE = "http://127.0.0.1:9882"
OUT_DIR   = pathlib.Path(r"C:\Users\32707\Desktop\Luna\LunaData\metrics")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH  = OUT_DIR / "xtts_rank.csv"
HTTP_TIMEOUT = 30  # s

LANG_TESTS = {
    "zh": ["你好，我在呢。", "今晚风很轻。", "喝口温水，会好些。"],
    "en": ["hello there", "take a deep breath", "you are doing great"],
    "ja": ["こんにちは、ここにいます。", "夜風がやさしいです。", "少し休みましょう。"],
    "ko": ["안녕, 여기 있어.", "밤바람이 상쾌해요.", "잠깐 쉬어가요."],
}
TOPN_PRINT = 8

# ===== Whisper (GPU) =====
from faster_whisper import WhisperModel
size = os.getenv("FW_MODEL_SIZE", "medium")
WHISPER = WhisperModel(size, device="cuda", compute_type="float16")  # 你的 4080 OK

# ---------- 文本规范化 ----------
def _strip_punct_space_cjk(s: str) -> str:
    """CJK: NFKC + 去所有标点(P*)与空白(Z*)"""
    s = unicodedata.normalize("NFKC", s)
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "Z") or ch in "\t\r\n":
            continue
        out.append(ch)
    return "".join(out)

def _normalize_en_words(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[^a-z0-9\s']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _cer(ref: str, hyp: str) -> float:
    r, h = list(ref), list(hyp)
    if not r:
        return 0.0 if not h else 1.0
    dp = np.zeros((len(r)+1, len(h)+1), dtype=np.int32)
    for i in range(len(r)+1): dp[i,0] = i
    for j in range(len(h)+1): dp[0,j] = j
    for i in range(1, len(r)+1):
        ri = r[i-1]
        for j in range(1, len(h)+1):
            cost = 0 if ri == h[j-1] else 1
            a = dp[i-1, j] + 1
            b = dp[i, j-1] + 1
            c = dp[i-1, j-1] + cost
            dp[i, j] = a if a < b and a < c else (b if b < c else c)
    return dp[len(r), len(h)] / max(1, len(r))

from jiwer import wer as _wer
def _wer_en(ref: str, hyp: str) -> float:
    return _wer(_normalize_en_words(ref), _normalize_en_words(hyp))

# ---------- HTTP 合成 & 识别 ----------
def _speakers_http() -> List[str]:
    r = requests.get(f"{XTTS_BASE}/speakers", timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data["speakers"] if isinstance(data, dict) else data

def _tts_http(text: str, lang: str, spk: str) -> bytes:
    r = requests.post(f"{XTTS_BASE}/v1/tts",
                      json={"text": text, "lang": lang, "speaker": spk},
                      timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.content

def _asr_text(wav_bytes: bytes, lang: str) -> str:
    import tempfile, soundfile as sf  # soundfile 只为确认读取可用
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
        f.write(wav_bytes); f.flush()
        segs, info = WHISPER.transcribe(f.name, language=lang, beam_size=5, vad_filter=True)
        return "".join(s.text for s in segs).strip()

def _score_one(lang: str, ref: str, hyp: str) -> float:
    if lang == "en":
        return _wer_en(ref, hyp)
    return _cer(_strip_punct_space_cjk(ref), _strip_punct_space_cjk(hyp))

# ---------- 主流程 ----------
def main():
    try:
        r = requests.get(f"{XTTS_BASE}/health", timeout=5); r.raise_for_status()
    except Exception as e:
        raise SystemExit(f"[ERR] XTTS(9882) 未就绪：{e}")
    spks = _speakers_http()
    if not spks:
        raise SystemExit("[ERR] /speakers 返回空；请确认模型已加载出 speakers")

    rows = []
    t0 = time.time()
    for i, spk in enumerate(spks, 1):
        res: Dict[str, float] = {}
        for lang, tests in LANG_TESTS.items():
            vals = []
            for sent in tests:
                try:
                    wav = _tts_http(sent, lang, spk)
                    hyp = _asr_text(wav, lang)
                    vals.append(_score_one(lang, sent, hyp))
                except Exception:
                    vals.append(float("nan"))  # 不把失败算 1.0
            clean = [v for v in vals if not math.isnan(v)]
            res[lang] = round(float(statistics.mean(clean)) if clean else 1.0, 4)
        avg = round((res["zh"]+res["en"]+res["ja"]+res["ko"])/4, 4)
        row = [spk, res["zh"], res["en"], res["ja"], res["ko"], avg]
        rows.append(row)
        print(f"[{i}/{len(spks)}]", row)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["speaker","zh_CER","en_WER","ja_CER","ko_CER","avg"])
        w.writerows(rows)

    def topn(col, title):
        ok = [r for r in rows if not math.isnan(r[col])]
        ok.sort(key=lambda x: x[col])
        print(f"\n== Top {min(TOPN_PRINT, len(ok))} {title} ==")
        for r in ok[:TOPN_PRINT]:
            print(r[0], r[col])
    topn(1,"ZH"); topn(2,"EN"); topn(3,"JA"); topn(4,"KO")

    print("\nCSV ->", CSV_PATH)
    print("done in", round(time.time()-t0, 1), "s")

if __name__ == "__main__":
    main()
