# backend/serve.py
# 作用：给 Py + Uvicorn 一个极薄的启动入口，便于 batch 一键拉起。
# 不改 main.py 的任何对外行为。
import os
import uvicorn
from main import app  # 直接复用你已有的 FastAPI app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    # 绑定 127.0.0.1，减少防火墙弹窗；日志信息级别足够排障。
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
