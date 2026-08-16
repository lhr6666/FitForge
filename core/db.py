"""数据库基础设施 - SQLAlchemy 异步引擎、会话工厂。

D4 决策：SQLAlchemy 2.0 异步 + asyncmy
Q3 决策：async generator + Depends（session 生命周期与 HTTP 请求绑定）

注意：Base 类在 models/__init__.py 定义（本文件不需要，alembic env.py 才用）。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings


# ===== 异步 engine =====
# create_async_engine 是工厂函数：返回 AsyncEngine 实例
# - echo=True：MVP 阶段开 SQL 日志，方便调试
# - pool_pre_ping=True：每次连接前 ping 一下，避免"连接已失效"错误（生产必开）
engine = create_async_engine(
    settings.DATABASE_URL,#告诉路通向哪（比如 mysql+asyncmy://user:pass@localhost/db）。
    echo=True,#注意：上线前要关掉，否则日志量太大会撑爆磁盘。
    pool_pre_ping=True,
)


# ===== Session 工厂 =====
# async_sessionmaker 是工厂的工厂：调用 AsyncSessionLocal() 返回 AsyncSession
# - class_=AsyncSession：明确异步 session 类型
# - expire_on_commit=False：commit 后访问属性不重新查询 DB（async 不能 lazy load）不用await
AsyncSessionLocal = async_sessionmaker(
    bind=engine,#告诉 session 用哪个 engine（就是刚刚创建的那个）。
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # 不让系统偷偷帮你把内存数据刷到数据库，必须你自己显式控制。这样逻辑更清晰，避免产生意外的 SQL。
)


# ===== FastAPI Depends 依赖注入 =====
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 注入的数据库 session。

    使用方式：
        @router.post("/users")
        async def create_user(db: AsyncSession = Depends(get_db)):
            ...

    Lifecycle（与 HTTP 请求绑定）：
        1. 请求进入 → FastAPI 调用 get_db() → 创建新 session
        2. 路由函数执行 → 业务逻辑通过 session 操作 DB
        3. 请求结束：
           - 成功：yield 正常返回 → finally 关闭 session
           - 失败：except 触发 → rollback() 撤销未提交事务 → finally 关闭
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            # 任何异常：先回滚事务（避免部分写入）
            await session.rollback()
            raise  # 重新抛出，让 FastAPI 的 exception_handler 处理
        finally:
            # 不需要显式 close()，async with 上下文管理器自动处理
            # 但为了语义清晰，文档化一下
            pass