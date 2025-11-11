# backend/cleaner.py
from pathlib import Path
import time

def cleanup_audio(dir_path: Path, keep_latest: int = 80, expire_days: int = 7):
    p = Path(dir_path)
    if not p.exists(): return
    files = sorted([f for f in p.iterdir() if f.is_file()], key=lambda x: x.stat().st_mtime, reverse=True)
    # 1) 超出数量清理
    for f in files[keep_latest:]:
        try: f.unlink()
        except Exception: pass
    # 2) 过期清理
    now = time.time()
    for f in files:
        try:
            if (now - f.stat().st_mtime) > expire_days*86400:
                f.unlink()
        except Exception: pass
