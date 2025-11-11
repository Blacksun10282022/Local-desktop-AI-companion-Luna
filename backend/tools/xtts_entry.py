# backend/tools/xtts_entry.py
# 作用：统一 XTTS 服务的启动入口，XTTS_DEVICE=cuda/cpu 控制设备，
# 端口来自 argv[1] 或环境变量 PORT。让 bat 可以一行起 GPU / CPU 两路。
import os, sys
import uvicorn
from xtts_http_server import app  # 你已有的服务实现

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("PORT", "9883"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
