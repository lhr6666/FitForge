"""pytest 配置和共享 fixture。

httpx.AsyncClient + ASGITransport 是 FastAPI 端到端测试的标准模式：
- ASGITransport 直接把 ASGI app 传给 httpx（不走网络）
- AsyncClient 模拟 HTTP 客户端
- pytest-asyncio 让 async 测试函数能跑

测试幂等性：
- 每个测试前清空 users 表（autouse fixture）
- 避免多次跑测试时用户名冲突
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from core.db import AsyncSessionLocal
from main import app
from models.user import User


@pytest_asyncio.fixture(autouse=True)
async def clean_users_table():
    """每个测试前后清空 users 表（幂等性）。

    autouse=True 自动应用到所有测试
    yield 前的代码 = setup
    yield 后的代码 = teardown
    """
    # Setup：清空测试数据
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.username.like("test_%")))
        await session.commit()

    yield  # 测试运行

    # Teardown：清空测试数据（避免污染下次测试）
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.username.like("test_%")))
        await session.commit()


@pytest_asyncio.fixture
async def client():
    """异步 HTTP 客户端 fixture。

    Yields:
        AsyncClient: 配置 base_url="http://test" 的 httpx 客户端
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac