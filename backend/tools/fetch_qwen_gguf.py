from huggingface_hub import snapshot_download
from pathlib import Path

TARGET = Path(r"C:\Users\32707\Desktop\Luna\LunaModels\llm")
TARGET.mkdir(parents=True, exist_ok=True)

MODELS = [
    # 轻脑：1.5B —— 兼容 1.5B / 1_5b、大写/小写、不同连字符
    ("Qwen/Qwen2-1.5B-Instruct-GGUF",
     ["*1.5B*Q4_K_M*.gguf","*1_5b*Q4_K_M*.gguf","*qwen2-1*instruct*q4_k_m*.gguf"]),
    # 重脑：7B —— 同理
    ("Qwen/Qwen2-7B-Instruct-GGUF",
     ["*7B*Q4_K_M*.gguf","*7b*Q4_K_M*.gguf","*qwen2-7b*instruct*q4_k_m*.gguf"]),
]

for rid, patterns in MODELS:
    print(f"==> {rid}")
    snapshot_download(
        repo_id=rid,
        local_dir=TARGET / rid.split('/')[-1],
        local_dir_use_symlinks=False,
        allow_patterns=patterns
    )
print("done.")
