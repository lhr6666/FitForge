"""FitForge 主入口 - FastAPI 应用实例。

挂载路由 + 注册异常处理（spec §4.2）：
- POST /auth/register（api/auth.py）
- 业务异常 → HTTP 状态码（api/exception_handlers.py）
"""
from fastapi import FastAPI

from api.auth import router as auth_router
from api.exception_handlers import register_exception_handlers

app = FastAPI(
    title="FitForge",
    description="一个给健身爱好者用的训练管理工具",
    version="0.1.0",
)


# 注册业务异常 → HTTP 状态码映射（Q2 决策）
register_exception_handlers(app)

# 挂载路由
app.include_router(auth_router)

# Phase 3: body-measurements + user-goals (Task 10)
from api.body import router as body_router
from api.goal import router as goal_router

app.include_router(body_router)
app.include_router(goal_router)


@app.get("/")
async def root() -> dict[str, str]:
    """健康检查入口 - 确认服务能起来即可。"""
    return {"status": "ok", "service": "fitforge", "version": "0.1.0"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Kubernetes 风格健康检查 - 后续部署用。"""
    return {"status": "healthy"}


# 后续会陆续挂载：
# app.include_router(body_measurement.router, prefix="/body", tags=["body"])
# app.include_router(goal.router, prefix="/goal", tags=["goal"])