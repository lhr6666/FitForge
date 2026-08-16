"""端到端测试 - POST /auth/register。

你的终端：会显示文字报告，告诉你“通过”还是“失败”。
测试服务器：会在后台默默运行，处理请求，但它不会像正式上线那样把日志打印到你的屏幕上（除非你专门配置过）。
跟服务器：它是在启动一个“模拟服务器”（Test Server）来运行你的代码，而不是凭空想象。测试结束后，这个迷你服务器通常会销毁或者重置状态。

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


# ============================================================
# /auth/login + refresh + logout + me 测试
# ============================================================

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """场景：login 成功返回 access + refresh。"""
    # 先注册（确保有用户）
    await client.post("/auth/register", json={
        "username": "login_alice", "email": "login_alice@example.com", "password": "Password123",
    })
    # 登录
    resp = await client.post("/auth/login", json={
        "email": "login_alice@example.com", "password": "Password123",
    })
    #assert（断言）：这是测试的核心。它的意思是：“我坚信后面跟着的内容是真的”。
    assert resp.status_code == 200  # 判决：服务器必须返回 200（成功），否则报错
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800
    assert len(data["access_token"]) > 50
    assert len(data["refresh_token"]) > 50


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """场景：错误密码 → 401。"""
    resp = await client.post("/auth/login", json={
        "email": "login_alice@example.com", "password": "WrongPass1",
    })
    assert resp.status_code == 401
    # 统一错误消息（防枚举攻击）
    detail = resp.json()["detail"]
    assert "邮箱" in detail or "密码" in detail or "invalid" in detail.lower()


@pytest.mark.asyncio
async def test_refresh_rotate_and_revoke(client: AsyncClient):
    """场景：refresh rotate 成功 + 旧 refresh 撤销。"""
    # 注册 + 登录
    await client.post("/auth/register", json={
        "username": "refresh_alice", "email": "refresh_alice@example.com", "password": "Password123",
    })
    login_resp = await client.post("/auth/login", json={
        "email": "refresh_alice@example.com", "password": "Password123",
    })
    old_refresh = login_resp.json()["refresh_token"]

    # refresh 成功（新 token）
    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_resp.status_code == 200
    new_refresh = refresh_resp.json()["refresh_token"]
    assert new_refresh != old_refresh  # D28 关键：refresh 必须 rotate

    # 旧 refresh 再用 → 401（已 revoke）
    retry_resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert retry_resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient):
    """场景：/auth/me 用 Bearer token 拿当前用户。"""
    # 注册 + 登录
    await client.post("/auth/register", json={
        "username": "me_alice", "email": "me_alice@example.com", "password": "Password123",
    })
    login_resp = await client.post("/auth/login", json={
        "email": "me_alice@example.com", "password": "Password123",
    })
    access_token = login_resp.json()["access_token"]

    # /auth/me 带 Bearer
    resp = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "me_alice"
    # 关键安全断言：响应体不含敏感字段
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    """场景：/auth/me 没 Bearer → 401。"""
    resp = await client.get("/auth/me")
    assert resp.status_code == 401  # HTTPBearer auto-error → 401