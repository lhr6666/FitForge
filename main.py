"""FitForge 主入口 - FastAPI 应用实例。
周二目标：本地能跑通 `uvicorn main:app --reload`，访问 /docs 看到 Swagger UI。
"""
from fastapi import FastAPI

app = FastAPI(
    title="FitForge",
    description="一个给健身爱好者用的训练管理工具",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    """健康检查入口 - 确认服务能起来即可。"""
    return {"status": "ok", "service": "fitforge", "version": "0.1.0"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Kubernetes 风格健康检查 - 后续部署用。"""
    return {"status": "healthy"}


# 周三开始陆续挂载：
# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(body.router, prefix="/body", tags=["body"])