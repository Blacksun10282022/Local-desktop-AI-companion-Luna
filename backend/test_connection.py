#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# backend/test_connection.py
"""快速测试后端各模块是否正常（含 v0.5 本地 TTS 探活）"""

import os
import sys
from pathlib import Path

print("=" * 56)
print("Luna 后端连接测试")
print("=" * 56)

# 0. 载入 .env
print("\n[0] 载入 .env ...")
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ .env 已尝试载入（若存在）")
except Exception as e:
    print(f"! 警告：dotenv 载入失败：{e}")

# 1. 测试环境变量
print("\n[1/6] 测试环境变量（DASHSCOPE_API_KEY）...")
api = os.getenv("DASHSCOPE_API_KEY", "")
if api:
    print("✓ 检测到 DASHSCOPE_API_KEY（长度已隐藏）")
else:
    print("✗ 未检测到 DASHSCOPE_API_KEY（仅云端 LLM/TTS 会受影响）")

# 2. 打印数据目录
print("\n[2/6] 数据目录与路径...")
try:
    from data_paths import DATA_ROOT, AUDIO_DIR, boot_print
    boot_print()
    print(f"✓ AUDIO_DIR = {AUDIO_DIR}")
except Exception as e:
    print(f"✗ data_paths 错误: {e}")

# 3. 试跑一次 LLM（可选）
print("\n[3/6] 测试 LLM 生成（可选）...")
try:
    from llm_client import call_llm
    text = call_llm({"memory_hint": ""})
    print(f"✓ LLM 返回: {text}")
except Exception as e:
    print(f"! LLM 调用失败（不影响 TTS 测试）: {e}")

# 4. 预热（轻量）
print("\n[4/6] 预热 TTS（REST 无需预热，仅返回 True）...")
try:
    from tts_client import warm_tts
    ok = warm_tts()
    print(f"✓ TTS warm: {ok}")
except Exception as e:
    print(f"✗ TTS warm 错误: {e}")

# 5. 云端 TTS 简测
print("\n[5/6] 云端 TTS 简测（仅检查模块是否可调用）...")
try:
    from tts_client import call_tts
    from data_paths import AUDIO_DIR
    p = call_tts("这是一次测试。", AUDIO_DIR, voice=None)
    print(f"✓ 云端 TTS 输出文件: {Path(p).name}")
except Exception as e:
    print(f"! 云端 TTS 失败（若无 Key 或网络限制可忽略）: {e}")

# 6. 本地 TTS 探活（v0.5 新增）
print("\n[6/6] 本地 TTS 探活（仅当配置了 LUNA_TTS_LOCAL_URL 或 settings.json 中 tts_local_url 时）...")
try:
    from config_store import read_config
    from local_tts_client import ping_local_tts, call_local_tts
    from data_paths import AUDIO_DIR

    cfg = read_config()
    url = (os.getenv("LUNA_TTS_LOCAL_URL") or cfg.get("tts_local_url") or "").strip()
    if not url:
        print("• 未配置本地 TTS（跳过）")
    else:
        ok = ping_local_tts(url)
        print(f"• ping {url} → {ok}")
        if ok:
            try:
                p = call_local_tts("本地 TTS 探活测试。", AUDIO_DIR, base_url=url, voice=cfg.get("voice_override"), timeout_ms=int(cfg.get("tts_timeout_ms") or 8000))
                print(f"✓ 本地 TTS 输出文件: {Path(p).name}")
            except Exception as e:
                print(f"! 本地 TTS 调用失败（将回落云端）: {e}")
except Exception as e:
    print(f"✗ 本地 TTS 探活步骤异常: {e}")

print("\n" + "=" * 56)
print("测试结束：若无致命报错，说明后端就绪。")
print("=" * 56)
