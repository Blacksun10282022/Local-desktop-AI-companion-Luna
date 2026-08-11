# Luna — Local Desktop AI Assistant

**Project period:** Nov 2025-Dec 2025

An Electron + FastAPI desktop assistant with llama.cpp-served Qwen2 models,
dual-model routing, local/cloud fallback, repeatable startup orchestration,
health checks, configuration validation and portable user-data isolation.

## 中文运行指南（v0.6.1，Windows / Anaconda）

> Electron（前端） + FastAPI（后端） + Qwen（LLM 云/本地） + XTTS v2（本地 TTS，GPU/CPU）  
> **隐私与便携**：所有真实数据只写入 `./LunaData/*`（仓库不包含任何个人隐私数据或真实密钥）  
> **说明**：本 README 只包含 **Anaconda 运行方案**；**不涉及任何 EXE 打包**。

---

## 🚀 面向小白的快速开始（Anaconda）

### 0）安装
- [Anaconda（Windows）](https://www.anaconda.com/download)  
- [Node.js LTS](https://nodejs.org/)（用于 Electron 前端开发/运行）
- NVIDIA 显卡驱动（可选；用于 XTTS GPU）

> 项目根路径可以放在任意本地工作目录；以下脚本均以仓库根目录为基准。

### 1）创建环境（一次性）
双击项目根的 **`0_Setup_Conda.bat`**  
它会创建两个 conda 环境并安装依赖：
- `luna-core`（后端）
- `luna-xtts`（本地 TTS；优先安装 CUDA 版 Torch，失败回退 CPU 版）

### 2）（可选）下载模型
双击 **`1_Fetch_Models.bat`**：
- 下载 **XTTS v2** → `LunaModels/tts/xtts_v2/`
- 下载 **Qwen2 GGUF**（1.5B/7B）→ `LunaModels/llm/`

> 可跳过：不下模型也能跑（TTS 回退云端/哔声；LLM 走云端）。

### 3）启动
双击 **`Start_Luna.bat`**：
- **首次启动**会提示粘贴 **阿里云 DashScope Key**（可留空，留空则先用本地/哔声兜底）。  
- 同时启动：XTTS（GPU:9882、CPU:9883）、后端（8000）与前端（Electron）。  
- 若存在 GGUF 模型，将自动启动本地 LLM（9970/9971）。

完成后，你会看到桌面的小圆点；点击即可播放一句话与语音。

---

## ⚙️ 配置与数据

- **密钥**：`backend/.env`（首次启动自动生成）
  ```ini
  DASHSCOPE_API_KEY=你的key
  ```
- **便携数据根**：`./LunaData/*`（自动创建）
  - `audio/` 语音缓存  
  - `diary/` 日记与独白  
  - `logs/` 运行日志  
  - `settings.json` 前端窗口位置/大小、TTS/LLM 选择等
- **模型目录**（可选）：
  - `LunaModels/tts/xtts_v2/`
  - `LunaModels/llm/Qwen2-1.5B-Instruct-GGUF/`
  - `LunaModels/llm/Qwen2-7B-Instruct-GGUF/`

> 仓库只保留 `.env.sample`；**真实 Key 与 `LunaData/*` 永不提交到 Git**。

---

## 🔌 端口与路由（默认）
- Backend（FastAPI）：`127.0.0.1:8000`  
- XTTS（本地 TTS）：GPU → `9882`，CPU → `9883`（两路都起，由路由选择）  
- Beep 兜底 TTS：`9884`（可选）  
- LLM（llama.cpp）：small → `9970`，big → `9971`  
- TTS 模式：`cloud / local / auto`（本地优先失败回云；云失败回哔声）  
- LLM 模式：`cloud / local_small / local_big / local_only / auto`

---

## 🧩 常见问题（FAQ）
- **前端没弹出来**：首次运行会自动安装前端依赖（`npm ci`），完成后会启动 UI。  
- **没有声音**：检查是否填了 Key；未下载 XTTS 模型或本地 TTS 起不来时，会回退云端/哔声。  
- **GPU XTTS 起不来**：显卡/驱动/Torch CUDA 不兼容时，GPU 窗口会报错退出，但 CPU 通道仍可用。  
- **端口被占用**：释放 8000/9882/9883/9970/9971，或在 `Start_Luna.bat` 中调整端口。  
- **数据清理**：删除 `./LunaData/*` 可“重置”本地状态（会丢失日记/缓存）。

---

## 🛡️ 隐私与便携（强约束）
- 真实数据仅落地 `./LunaData/*`，仓库不包含任何隐私内容。  
- Key 只从环境变量 / `backend/.env` 读取；仓库只保留 `.env.sample`。  
- 敏感文本（如日记、独白）默认只在本地处理，**不上传云端**。

---

# English Run Guide — Luna v0.6.1 (Anaconda only)

**Project period:** Nov 2025-Dec 2025

> Stack: **Electron** (frontend) + **FastAPI** (backend) + **Qwen** (LLM cloud/local) + **XTTS v2** (local TTS, GPU/CPU)  
> **Privacy & Portability:** all real data stays under `./LunaData/*`. No real keys or private data in the repo.  
> **Note:** This README covers **Anaconda-only workflow** — **no EXE packaging**.

---

## 🚀 Quick Start

### 0) Install
- [Anaconda for Windows](https://www.anaconda.com/download)  
- [Node.js LTS](https://nodejs.org/) (for Electron dev/run)  
- NVIDIA driver (optional; for XTTS GPU)

### 1) Create environments (one-time)
Double-click **`0_Setup_Conda.bat`** in the repo root. It creates:
- `luna-core` (backend)
- `luna-xtts` (local TTS; tries Torch CUDA, falls back to CPU wheels)

### 2) (Optional) Download models
Double-click **`1_Fetch_Models.bat`** to download:
- **XTTS v2** → `LunaModels/tts/xtts_v2/`  
- **Qwen2 GGUF** (1.5B/7B) → `LunaModels/llm/`

> You can skip this step: TTS will fall back to cloud or “beep”; LLM will route to cloud.

### 3) Run
Double-click **`Start_Luna.bat`**:
- On first run, you’ll be prompted for **DashScope API key** (can be empty).  
- It launches XTTS (GPU:9882 + CPU:9883), backend (8000), and Electron UI.  
- If GGUF models exist, local LLM (9970/9971) is started automatically.

---

## ⚙️ Config & Data
- **Key file**: `backend/.env` (auto-generated on first run)
  ```ini
  DASHSCOPE_API_KEY=your_key_here
  ```
- **Portable data root**: `./LunaData/*` (created automatically)  
- **Models** (optional): `LunaModels/tts/xtts_v2/`, `LunaModels/llm/Qwen2-1.5B-Instruct-GGUF/`, `LunaModels/llm/Qwen2-7B-Instruct-GGUF/`

---

## 🔌 Ports & Routing
- Backend: `127.0.0.1:8000`  
- XTTS: GPU → `9882`, CPU → `9883` (both started)  
- Beep TTS: `9884` (optional)  
- LLM: small → `9970`, big → `9971`  
- TTS: `cloud / local / auto` (prefer local; fallback to cloud/beep)  
- LLM: `cloud / local_small / local_big / local_only / auto`

---

## 🧩 Troubleshooting
- **No UI**: first run installs frontend deps (`npm ci`) and then starts Electron.  
- **No sound**: provide API key or download XTTS models; CPU/“beep” fallback keeps it working.  
- **Port conflicts**: free 8000/9882/9883/9970/9971 or edit `Start_Luna.bat`.

---

## 🛡️ Privacy
- All real data stays in `./LunaData/*`.  
- Keys from env or `backend/.env`; only `.env.sample` is versioned.  
- Sensitive text (diary/monologue) is processed locally by default.
