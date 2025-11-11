@echo off
setlocal ENABLEEXTENSIONS
chcp 65001 >nul

REM ===== 可配置 =====
set "CONDA_BAT=C:\Users\32707\anaconda3\condabin\conda.bat"
set "ENV_BACKEND=luna-core"
set "ENV_XTTS=luna-xtts"

set "BACKEND_PORT=8000"
set "XTTS_GPU_PORT=9882"
set "XTTS_CPU_PORT=9883"
set "XTTS_MODEL_DIR=%~dp0LunaModels\tts\xtts_v2"

REM --- v0.6: LLM 本地参数 ---
set "LLAMA_EXE=%~dp0backend\tools\llama.cpp\llama-server.exe"
set "LLM_SMALL_PATH=%~dp0LunaModels\llm\Qwen2-1.5B-Instruct-GGUF\qwen2-1_5b-instruct-q4_k_m.gguf"
if not exist "%LLM_SMALL_PATH%" set "LLM_SMALL_PATH=%~dp0LunaModels\llm\Qwen2-1.5B-Instruct-GGUF\Qwen2-1.5B-Instruct-Q4_K_M.gguf"
set "LLM_BIG_PATH=%~dp0LunaModels\llm\Qwen2-7B-Instruct-GGUF\qwen2-7b-instruct-q4_k_m.gguf"
if not exist "%LLM_BIG_PATH%" set "LLM_BIG_PATH=%~dp0LunaModels\llm\Qwen2-7B-Instruct-GGUF\Qwen2-7B-Instruct-Q4_K_M.gguf"

set "LUNA_PORTABLE=1"
set "LUNA_API=http://127.0.0.1:%BACKEND_PORT%"
set "PYTHONUTF8=1"

REM ===== 路径校验 =====
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if not exist "%CONDA_BAT%" (echo [ERR] conda.bat 不存在: %CONDA_BAT% & pause & exit /b 1)
if not exist "%ROOT%\backend\main.py" (echo [ERR] 必须在项目根运行本脚本 & pause & exit /b 1)

REM ===== 首启：写 Key =====
set "ENV_FILE=%ROOT%\backend\.env"
set "SENTINEL=%ROOT%\LunaData\.firstrun_ok"
if not exist "%ROOT%\LunaData" mkdir "%ROOT%\LunaData"
if not exist "%SENTINEL%" (
  echo.
  echo === Luna 首次启动 ===
  echo 请输入阿里云 DashScope Key（可留空，回车跳过）：
  set /p USERKEY=Key:
  > "%ENV_FILE%" echo DASHSCOPE_API_KEY=%USERKEY%
  > "%SENTINEL%" echo ok
  echo [OK] 已写入 backend\.env
)

echo [ROOT] %ROOT%
echo [ENV] XTTS_MODEL_DIR=%XTTS_MODEL_DIR%
echo [ENV] LLM_SMALL=%LLM_SMALL_PATH%
echo [ENV] LLM_BIG=%LLM_BIG_PATH%

REM ===== 0) 本地 LLM =====
if exist "%LLAMA_EXE%" if exist "%LLM_SMALL_PATH%" (
  start "LLM-1.5B (9970)" "%LLAMA_EXE%" -m "%LLM_SMALL_PATH%" --alias local --host 127.0.0.1 --port 9970 -ngl 35 -c 4096 --no-webui --chat-template chatml
)
if exist "%LLAMA_EXE%" if exist "%LLM_BIG_PATH%" (
  start "LLM-7B (9971)" "%LLAMA_EXE%" -m "%LLM_BIG_PATH%" --alias local --host 127.0.0.1 --port 9971 -ngl 40 -c 4096 --no-webui --chat-template chatml
)

REM ===== 1) XTTS-GPU : 9882 =====
start "XTTS-HTTP (cuda %XTTS_GPU_PORT%)" cmd /K ^
  call "%CONDA_BAT%" activate %ENV_XTTS% ^&^& ^
  set XTTS_MODEL_DIR=%XTTS_MODEL_DIR% ^&^& ^
  set XTTS_DEVICE=cuda ^&^& ^
  cd /d "%ROOT%" ^&^& ^
  python -m uvicorn backend.tools.xtts_http_server:app --host 0.0.0.0 --port %XTTS_GPU_PORT%

REM ===== 2) XTTS-CPU : 9883 =====
start "XTTS-HTTP (cpu %XTTS_CPU_PORT%)" cmd /K ^
  call "%CONDA_BAT%" activate %ENV_XTTS% ^&^& ^
  set XTTS_MODEL_DIR=%XTTS_MODEL_DIR% ^&^& ^
  set XTTS_DEVICE=cpu ^&^& ^
  cd /d "%ROOT%" ^&^& ^
  python -m uvicorn backend.tools.xtts_http_server:app --host 0.0.0.0 --port %XTTS_CPU_PORT%

REM ===== 2.5) 哔声兜底（可选）: 9884 =====
start "BEEP-TTS (9884)" cmd /K ^
  call "%CONDA_BAT%" activate %ENV_BACKEND% ^&^& ^
  cd /d "%ROOT%" ^&^& ^
  python -m uvicorn backend.tools.local_beep_tts_server:app --host 127.0.0.1 --port 9884

REM ===== 3) 后端（建议用 serve.py，不用 --reload 提升稳定性）=====
start "Luna-Backend" cmd /K ^
  call "%CONDA_BAT%" activate %ENV_BACKEND% ^&^& ^
  cd /d "%ROOT%\backend" ^&^& ^
  python -m backend.serve

REM ===== 4) 等后端就绪→应用 TTS 预设（auto + 9882 优先 + 18s 超时）=====
call "%CONDA_BAT%" activate %ENV_BACKEND%
cd /d "%ROOT%\backend"
for /l %%i in (1,1,30) do (
  >nul 2>nul powershell -Command "try{$r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:%BACKEND_PORT%/ping; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
  if %ERRORLEVEL%==0 goto :DO_PRESET
  echo ... backend not ready, retry %%i/30
  timeout /t 1 >nul
)
goto :START_UI
:DO_PRESET
python tools\apply_tts_preset.py %BACKEND_PORT%
:START_UI

REM ===== 5) 前端（首次自动装依赖）=====
if not exist "%ROOT%\frontend\node_modules" (
  echo [INFO] 正在安装前端依赖（一次性）...
  cd /d "%ROOT%\frontend" & call npm ci
)
start "Luna-UI" cmd /K ^
  cd /d "%ROOT%\frontend" ^&^& ^
  set LUNA_API=%LUNA_API% ^&^& ^
  npm start

endlocal
exit /b
