# backend/data_paths.py
from __future__ import annotations
from pathlib import Path
import os

APP_NAME = "Luna"

def _project_root() -> Path:
    # backend/ 的上一级就是项目根
    return Path(__file__).resolve().parent.parent

def _win_localappdata() -> Path:
    # Windows 的默认用户数据目录：%LOCALAPPDATA%\Luna
    base = os.getenv("LOCALAPPDATA")
    if not base:  # 极少数情况下没有该变量，回退到家目录
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME

def resolve_data_root() -> Path:
    """
    优先级（当前以便携为最高）：
      1) 便携模式：env LUNA_PORTABLE=1 或 项目根存在 .portable → <repo>/LunaData
      2) 环境变量 LUNA_DATA_ROOT（若你想临时覆盖）
      3) Windows 默认：%LOCALAPPDATA%/Luna

    NOTE: 以后若要做“三层跨平台”（Windows/macOS/Linux），
          只需把第3层换成 platformdirs.user_data_dir(APP_NAME) 即可。
    """
    repo = _project_root()

    # 1) 便携优先
    if os.getenv("LUNA_PORTABLE") == "1" or (repo / ".portable").exists():
        return (repo / "LunaData").resolve()

    # 2) 显式覆盖
    v = os.getenv("LUNA_DATA_ROOT")
    if v:
        return Path(v).expanduser().resolve()

    # 3) Windows 默认用户目录
    return _win_localappdata().resolve()

# ====== 计算并创建目录/文件路径 ======
DATA_ROOT = resolve_data_root()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

AUDIO_DIR = DATA_ROOT / "audio"
DIARY_DIR = DATA_ROOT / "diary"   # v0.4 预留
LOG_DIR   = DATA_ROOT / "logs"    # v0.4 预留
for d in (AUDIO_DIR, DIARY_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

CFG_FILE     = DATA_ROOT / "settings.json"   # 用户设置（非密钥）
STATE_FILE   = DATA_ROOT / "state.json"      # 运行状态
PHRASES_USER = DATA_ROOT / "phrases.json"    # 私有句库（可选）

def boot_print():
    print(f"[DATA] DATA_ROOT = {DATA_ROOT}")
