"""端到端测试 - POST /auth/register。

测试 4 个场景：
1. 正常注册（201）
2. username 重复（409）
3. 弱密码（422 Pydantic 自动校验）
4. email 缺失（422 Pydantic 自动校验）

关键安全断言（Q4）：
- 响应体绝对不能含 'password' 或 'password_hash' 字段
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """场景 1: 正常注册返回 201 + UserRead（无 password_hash）。"""
    resp = await client.post(
        "/auth/register",
        json={
            "username": "test_alice",
            "email": "test_alice@example.com",
            "password": "Password123",
            "nickname": "Alice",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "test_alice"
    assert data["nickname"] == "Alice"
    assert "id" in data
    # 关键安全断言（Q4）：响应体不含敏感字段
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """场景 2: username 重复返回 409（业务异常自动映射）。"""
    payload = {
        "username": "test_bob",
        "email": "test_bob@example.com",
        "password": "Password123",
    }
    # 第一次注册成功
    r1 = await client.post("/auth/register", json=payload)
    assert r1.status_code == 201

    # 第二次同 username 但不同 email → 409
    payload2 = {
        "username": "test_bob",
        "email": "test_bob2@example.com",
        "password": "Password123",
    }
    r2 = await client.post("/auth/register", json=payload2)
    assert r2.status_code == 409
    assert "test_bob" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """场景 3: 弱密码（只有数字）返回 422（Pydantic 自动校验）。"""
    resp = await client.post(
        "/auth/register",
        json={
            "username": "test_charlie",
            "email": "test_charlie@example.com",
            "password": "12345678",  # 只有数字，无字母
        },
    )
    assert resp.status_code == 422
    # Pydantic 校验失败自动返回 detail 数组
    detail = resp.json()["detail"]
    assert any("字母" in str(e) for e in detail) or any("letter" in str(e).lower() for e in detail)


@pytest.mark.asyncio
async def test_register_missing_email(client: AsyncClient):
    """场景 4: 缺失 email 字段返回 422（Pydantic 自动校验）。"""
    resp = await client.post(
        "/auth/register",
        json={
            "username": "test_dave",
            "password": "Password123",
            # 故意没有 email
        },
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    # 校验错误应指明缺失 email
    assert any("email" in str(e.get("loc", [])).lower() for e in detail)