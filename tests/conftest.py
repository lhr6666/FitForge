"""pytest 配置和共享 fixture。

httpx.AsyncClient + ASGITransport 是 FastAPI 端到端测试的标准模式：
- ASGITransport 直接把 ASGI app 传给 httpx（不走网络）
- AsyncClient 模拟 HTTP 客户端
- pytest-asyncio 让 async 测试函数能跑

测试隔离（Phase 4 D41 决策）：
- 顶层 SQLite in-memory DB（StaticPool 共享 connection）
- engine fixture 创建所有表
- 每个测试函数有独立 db_session（teardown 不保留）
- service 测试 + route e2e 测试都通过 db_session / auth_headers fixture 拿数据

历史：Phase 4（2026-08-16）扩展 fixtures（engine/db_session/sample_user/auth_headers）。
Phase 3 的 clean_users_table 替换为 clean_test_data（清全部表，更彻底）。
Phase 3 的 client fixture 改为依赖 engine + dependency_overrides（走测试 SQLite）。
"""

# ===== 测试专属 SQLite in-memory 配置（D41 决策）=====
# 必须在 import settings 之前执行 —— BaseSettings 会读 os.environ
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.config import settings
from core.db import get_db
from core.security import hash_password
from main import app
from models import Base
from models.user import User
from services.auth_service import login


# ===== asyncio 模式（pytest-asyncio 默认 strict，需要显式 event_loop）=====
@pytest.fixture(scope="session")
def event_loop():
    """session-scoped event loop —— 让 engine fixture 跨测试共享。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ===== 测试 engine（in-memory SQLite + StaticPool）=====
# StaticPool 强制所有 connection 共享同一 in-memory DB schema
# 否则 SQLAlchemy async + 连接池会在不同 connection 间切换 -> 缺表报错
@pytest_asyncio.fixture(scope="session")
async def engine():
    """session 级 engine：所有测试函数共享同一 in-memory SQLite 实例。"""
    eng = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


# ===== 独立 session（每个测试函数新建）=====
@pytest_asyncio.fixture
async def db_session(engine):
    """每个测试函数一个独立 AsyncSession。"""
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as session:
        yield session


# ===== 测试用户（service 单元测试用，不需可登录）=====
@pytest_asyncio.fixture
async def sample_user(db_session):
    """基础 User（service 单元测试直接用此 fixture）。"""
    user = User(
        username="test_sample",
        email="sample@example.com",
        password_hash="not-a-real-hash",
    )
    db_session.add(user)
    await db_session.commit()
    return user


# ===== 鉴权 headers（route e2e 测试用）=====
# W8 关键：内部 register + login -> 返回 {"Authorization": "Bearer xxx"}
@pytest_asyncio.fixture
async def auth_headers(db_session):
    """注册并登录 alice_test，拿 Authorization headers。

    用独立的用户（不复用 sample_user）—— 因为 route e2e 测试要可登录的用户。
    """
    user = User(
        username="alice_test",
        email="alice_test@example.com",
        password_hash=hash_password("Password123"),
    )
    db_session.add(user)
    await db_session.commit()

    access, _refresh, _exp = await login(
        db_session, "alice_test@example.com", "Password123"
    )
    return {"Authorization": f"Bearer {access}"}


# ===== 幂等性：清空测试数据（D41 沿用 Phase 3 思路 + 扩范围）=====
@pytest_asyncio.fixture(autouse=True)
async def clean_test_data(engine):
    """每个测试前后清空所有测试数据（幂等性）。

    autouse=True 自动应用到所有测试
    范围：清空所有 ORM 表（用 session 直接 delete 比 truncate 在 SQLite 更稳）
    """
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _clean():
        async with async_session_maker() as session:
            # 反向清表（children -> parents 避免 FK 报错）
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(delete(table))
            await session.commit()

    await _clean()  # setup
    yield  # 测试运行
    await _clean()  # teardown


# ===== httpx AsyncClient（route e2e 测试用）=====
@pytest_asyncio.fixture
async def client(engine):
    """异步 HTTP 客户端 fixture。

    注入：FastAPI app.dependency_overrides[get_db] = 测试 engine 的 session
    Yields:
        AsyncClient: 配置 base_url="http://test" 的 httpx 客户端
    """
    async def _override_get_db():
        async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()