from huggingface_hub import snapshot_download
target = r"C:\Users\32707\Desktop\Luna\LunaModels\tts\xtts_v2"
print("downloading to:", target)
snapshot_download(
    repo_id="coqui/XTTS-v2",
    local_dir=target,
    local_dir_use_symlinks=False,
)
print("done")
