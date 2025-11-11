# C:\Users\32707\Desktop\Luna\backend\tools\check_xtts.py
import os
from TTS.api import TTS

MODEL_DIR = r"C:\Users\32707\Desktop\Luna\LunaModels\tts\xtts_v2"
CFG = os.path.join(MODEL_DIR, "config.json")

tts = TTS(model_path=MODEL_DIR, config_path=CFG, progress_bar=False)  # 显式传 config
tts.to("cuda")  # GPU；要 CPU 就写 "cpu"

# 列出现有 speaker（关键）
spm = tts.synthesizer.tts_model.speaker_manager
spks = list(getattr(spm, "speakers", {}).keys())
print("num speakers:", len(spks), "examples:", spks[:10])

# 用一个真实 speaker 合成
speaker = spks[0] if spks else None
if speaker:
    tts.tts_to_file(text="你好，我在呢。", language="zh", speaker=speaker, file_path="ok.wav")
    print("ok.wav saved with speaker:", speaker)
else:
    print("no speaker list in model; provide speaker_wav instead")

# 参考音色（可选，自己换成存在的 wav）
# tts.tts_to_file(text="你好，我是参考音色。", language="zh",
#                 speaker_wav=r"C:\ref.wav", file_path="clone.wav")
