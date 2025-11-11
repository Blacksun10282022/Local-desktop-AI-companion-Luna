@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul

set "ROOT=C:\Users\32707\Desktop\Luna_pre\Lunav0.6.1"
set "CONDA_BAT=C:\Users\32707\anaconda3\condabin\conda.bat"
set "ENV_XTTS=luna-xtts"
set "ENV_BACKEND=luna-core"

echo.
echo === 是否下载 XTTS v2 模型到 LunaModels\tts\xtts_v2 ? (Y/N) ===
set /p GO_TTS=输入Y或N:
if /I "%GO_TTS%"=="Y" (
  call "%CONDA_BAT%" activate %ENV_XTTS%
  set "XTTS_MODEL_DIR=%ROOT%\LunaModels\tts\xtts_v2"
  if not exist "%XTTS_MODEL_DIR%" mkdir "%XTTS_MODEL_DIR%"
  python "%ROOT%\backend\tools\fetch_xtts.py" "%XTTS_MODEL_DIR%"
) else (
  echo [SKIP] 跳过 XTTS 模型下载
)

echo.
echo === 是否下载 Qwen2 (1.5B / 7B) GGUF 到 LunaModels\llm ? (Y/N) ===
set /p GO_LLM=输入Y或N:
if /I "%GO_LLM%"=="Y" (
  call "%CONDA_BAT%" activate %ENV_BACKEND%
  python "%ROOT%\backend\tools\fetch_qwen_gguf.py" "%ROOT%\LunaModels\llm"
) else (
  echo [SKIP] 跳过 Qwen GGUF 下载
)

echo [OK] 模型拉取流程结束
pause
exit /b 0
