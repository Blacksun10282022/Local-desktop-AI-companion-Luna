# -*- coding: utf-8 -*-
# backend/config.py
"""
职责：
- 统一从环境读取关键配置（.env 优先），并提供默认值；
- 不再强制断言云端 Key，允许在“无 Key”场景下走本地 TTS/路由兜底。
"""

import os
from dotenv import load_dotenv

# 载入 .env（若存在）
load_dotenv()

# === 阿里云凭证（可为空；为空时所有云端 LLM/TTS 会不可用，但本地链路可继续工作） ===
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()

# === TTS 基础参数（云/本地通用的“期望输出”参数；本地服务可选择忽略） ===
COSYVOICE_MODEL  = os.getenv("COSYVOICE_MODEL", "cosyvoice-v2")
COSYVOICE_VOICE  = os.getenv("COSYVOICE_VOICE")  # 可为 None
TTS_FORMAT       = os.getenv("TTS_FORMAT", "mp3")     # 用作“默认后缀”；真实以 Content-Type 为准
TTS_SAMPLE_RATE  = int(os.getenv("TTS_SAMPLE_RATE", "24000"))

# 仅打印一次告警，不中断进程（便于无钥场景跑本地链路）
if not DASHSCOPE_API_KEY:
    print("[CFG] WARN: DASHSCOPE_API_KEY 为空；云端 LLM/TTS 将不可用，将依赖本地或路由兜底。")
