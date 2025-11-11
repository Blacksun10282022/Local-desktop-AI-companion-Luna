# -*- coding: utf-8 -*-
# tts_client.py
# 模块职责：通过阿里云 DashScope 的 REST 接口调用 Qwen-TTS，把一句文本合成为本地音频文件。
# 设计理念：
# 1) 端点自动选择（国际/国内/自定义直连），遇错自适应切换；
# 2) 模型候选可配置，失败降级重试；
# 3) 若完全失败，生成一段“哔声”作为兜底，保证前端交互不至于卡死。
# 注意：此处仅添加注释，不改动任何逻辑或对外行为。
from pathlib import Path
import os, time, wave, struct, math, requests
from typing import Optional, List

# 从环境读取凭证与偏好。这样便于在不同机器/网络环境下“零改代码”切换行为
API_KEY        = os.getenv("DASHSCOPE_API_KEY", "").strip()
# 可选：intl / cn（不填自动选择）；或强行指定完整 URL
TTS_PREF       = (os.getenv("TTS_PREF", "") or "").lower()     # "intl" | "cn" | ""
TTS_REST_URL   = os.getenv("TTS_REST_URL", "").strip()

# 说明：这里使用的是“multimodal-generation/generation”路径而非传统 /audio/tts
# 好处是统一了调用面；但需确保账户侧开通相应能力并按文档解析 output.audio.url
INTL_URL = "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
CN_URL   = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# 主备模型（可通过环境变量覆盖）。保持在 Qwen-TTS 家族内，避免跨模型字段差异
MODEL_CANDIDATES = [
    os.getenv("TTS_REST_MODEL", "qwen-tts-latest").strip() or "qwen-tts-latest",
]

# HTTP 超时与重试：在跨境/公司网络环境下非常重要
HTTP_TIMEOUT_S = float(os.getenv("TTS_HTTP_TIMEOUT", "18"))
RETRY_TIMES    = int(os.getenv("TTS_RETRY", "2"))

# 运行时路由记忆：记录当前端点与失败次数，避免在抖动网络中无意义来回
_current_url: Optional[str] = None
_fail_count = {}

def _basename() -> str:
    # 以毫秒时间戳生成文件基名，既避免冲突也便于根据时间顺序清理
    return f"luna_{int(time.time()*1000)}"

def _write_beep_wav(out_path: Path, secs: float = 0.35, sr: int = 24000, freq: int = 660):
    # 兜底哔声：当云端完全不可用时，至少给前端一个“可播放文件”，维持交互节奏
    n, amp = int(secs*sr), 12000
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        for i in range(n):
            s = int(amp * math.sin(2*math.pi*freq * i / sr))
            w.writeframesraw(struct.pack("<h", s))
        w.writeframes(b'')

def warm_tts() -> bool:
    # REST 本身无“加载模型”的延迟，此处返回 True 即可满足预热流程
    return True  # REST 无需预热

def _candidates() -> List[str]:
    # 端点候选优先级：
    # 1) 显式写死 URL → 使用该唯一端点
    # 2) 指定区域（cn / intl）→ 单端点
    # 3) 未指定 → 同时准备 cn 与 intl，后续根据失败次数排序选择
    if TTS_REST_URL:
        return [TTS_REST_URL]
    if TTS_PREF == "cn":
        return [CN_URL]
    if TTS_PREF == "intl":
        return [INTL_URL]
    # 没明确偏好时再两个都试
    return [CN_URL, INTL_URL]

def _choose_url() -> str:
    # 根据失败计数选择“最健康”的端点，且若当前端点稳定则保持粘性
    global _current_url
    cands = _candidates()
    if _current_url and _fail_count.get(_current_url, 0) < 2:
        return _current_url
    cands.sort(key=lambda u: _fail_count.get(u, 0))
    _current_url = cands[0]
    return _current_url

def _bump(url: str):
    # 失败计数 +1，用于下一次挑选端点时降权
    _fail_count[url] = _fail_count.get(url, 0) + 1

def _post_generation(url: str, model: str, text: str, voice: str, lang: str) -> str:
    """
    职责：调用 generation 接口；返回音频直链 URL（非音频字节）
    协议：payload 放到 input 里，如：
      {"model":"...","input":{"text":"...","voice":"...","language_type":"..."}}
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Luna/0.2"
    }
    payload = {
        "model": model,
        "input": {
            "text": text,
            "voice": voice,
            "language_type": lang  # "Chinese" | "English" | ... | "Auto"
        }
    }
    r = requests.post(url, headers=headers, json=payload, timeout=HTTP_TIMEOUT_S)
    if r.status_code >= 400:
        # 明确抛错以触发上层“重试/切换端点”的逻辑
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")

    data = r.json()
    # 官方文档：用 output.audio.url 下载音频（通常带 24h 有效期）
    audio_url = None
    try:
        audio_url = data["output"]["audio"]["url"]
    except Exception:
        pass
    if not audio_url:
        # TODO: 不同返回版本可能结构有差异，必要时记录完整 data 以辅助排查
        raise RuntimeError(f"no audio url in response: {str(data)[:200]}")
    return audio_url

def call_tts(text: str, out_dir: Path, voice: Optional[str] = None) -> str:
    """
    职责：把文本合成为本地文件：
      成功→保存为 .wav（或根据返回的 content-type 存为 .mp3）并返回绝对路径；
      失败→返回兜底哔声 wav 的绝对路径。
    说明：voice 是 Qwen 的“音色”名称（如 'Cherry'）。未传则用默认 'Cherry'。
    """
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    base = _basename()
    if not API_KEY:
        # 没有 API Key 的情况下不抛错，直接兜底生成哔声，避免整个系统阻塞
        print("[TTS] missing DASHSCOPE_API_KEY → beep")
        wav_path = out_dir / f"{base}.wav"; _write_beep_wav(wav_path); return str(wav_path)

    # 简单的中文字符检测：含 CJK 则强制 Chinese，否则交给 Auto
    lang = "Chinese" if any("\u4e00" <= ch <= "\u9fff" for ch in text) else "Auto"
    qwen_voice = (voice or "Cherry").strip() or "Cherry"

    # 第一轮：用当前挑选的端点 + 候选模型（支持小次数重试）
    url = _choose_url()
    for model in MODEL_CANDIDATES:
        for attempt in range(1, RETRY_TIMES + 1):
            try:
                audio_url = _post_generation(url, model, text, qwen_voice, lang)
                # 二段式获取：先拿到直链 URL，再发起 GET 把音频字节落盘
                resp = requests.get(audio_url, timeout=HTTP_TIMEOUT_S)
                resp.raise_for_status()
                # 尽量根据响应类型决定扩展名，避免播放器兼容性问题
                ext = ".wav"
                ct = (resp.headers.get("content-type") or "").lower()
                if "mp3" in ct:
                    ext = ".mp3"
                file_path = out_dir / f"{base}{ext}"
                file_path.write_bytes(resp.content)
                _fail_count[url] = 0  # 当前端点恢复健康
                return str(file_path)
            except Exception as e:
                print(f"[TTS] {url} {model} attempt {attempt} error:", e)
                _bump(url)
                time.sleep(0.25)  # 小退避，给网络/服务一点恢复时间

    # 第二轮：切换到“更健康”的端点后再尝试一次候选模型
    alt = _choose_url()
    if alt != url:
        for model in MODEL_CANDIDATES:
            try:
                audio_url = _post_generation(alt, model, text, qwen_voice, lang)
                resp = requests.get(audio_url, timeout=HTTP_TIMEOUT_S)
                resp.raise_for_status()
                ext = ".wav"
                ct = (resp.headers.get("content-type") or "").lower()
                if "mp3" in ct:
                    ext = ".mp3"
                file_path = out_dir / f"{base}{ext}"
                file_path.write_bytes(resp.content)
                _fail_count[alt] = 0
                return str(file_path)
            except Exception as e:
                print(f"[TTS] alt {alt} {model} error:", e)
                _bump(alt)

    # 仍失败 → 兜底哔声（系统保证“有响应、有声音”）
    wav_path = out_dir / f"beep_{base}.wav"  # ← 加 beep_ 前缀
    _write_beep_wav(wav_path)
    print("[TTS] all attempts failed → beep")
    return str(wav_path)

