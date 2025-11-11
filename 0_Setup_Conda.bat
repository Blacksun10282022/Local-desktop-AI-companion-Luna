@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul

:: === 你的根路径与 conda 路径 ===
set "ROOT=C:\Users\32707\Desktop\Luna_pre\Lunav0.6.1"
set "CONDA_BAT=C:\Users\32707\anaconda3\condabin\conda.bat"
set "ENV_BACKEND=luna-core"
set "ENV_XTTS=luna-xtts"

if not exist "%CONDA_BAT%" (echo [ERR] 找不到 conda.bat: %CONDA_BAT% & pause & exit /b 1)

:: === 后端环境 ===
call "%CONDA_BAT%" create -n %ENV_BACKEND% python=3.10 -y
call "%CONDA_BAT%" activate %ENV_BACKEND%
python -m pip install --upgrade pip
python -m pip install -r "%ROOT%\requirements.txt"

:: === XTTS 环境（本地 TTS） ===
call "%CONDA_BAT%" create -n %ENV_XTTS% python=3.10 -y
call "%CONDA_BAT%" activate %ENV_XTTS%
python -m pip install --upgrade pip
python -m pip install -r "%ROOT%\requirements_luna_xtts.txt"

:: === PyTorch（GPU 优先，失败再装 CPU 版） ===
call "%CONDA_BAT%" activate %ENV_XTTS%
python - <<PY
import subprocess, sys
def run(cmd): print("[CMD]", " ".join(cmd)); return subprocess.call(cmd)==0
ok = run([sys.executable,"-m","pip","install","--index-url","https://download.pytorch.org/whl/cu121",
          "torch==2.3.1+cu121","torchaudio==2.3.1+cu121"])
if not ok:
    print("[WARN] CUDA 轮子失败，装 CPU 版")
    run([sys.executable,"-m","pip","install","torch==2.3.1","torchaudio==2.3.1"])
PY

echo.
echo [OK] 已创建 conda 环境：%ENV_BACKEND% / %ENV_XTTS%
echo 下一步：双击 1_Fetch_Models.bat（可跳过），然后双击 Start_Luna.bat
pause
exit /b 0
