"""user_goals 路由 e2e 测试。

覆盖 4 个端点（POST / GET / GET id / PATCH）+ 鉴权 + 405 verify DELETE not implemented。
共 7 个核心 case。

fixtures: conftest.py 提供 client (httpx AsyncClient) + auth_headers (Bearer token)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_goal_201(client: AsyncClient, auth_headers):
    """POST /user-goals 正常 -> 201 + status='active'（默认）。"""
    r = await client.post(
        "/user-goals",
        json={"type": "cut", "target_value": 75.0},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_post_goal_401_no_auth(client: AsyncClient):
    """POST /user-goals 无 token -> 401。"""
    r = await client.post("/user-goals", json={"type": "cut"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_goals_with_status_filter(client: AsyncClient, auth_headers):
    """GET /user-goals?status=active 只返回 active（Q4 状态机）。

    创建 2 个，patch 1 个为 completed，验证 active 过滤生效。
    """
    g1 = (
        await client.post("/user-goals", json={"type": "cut"}, headers=auth_headers)
    ).json()
    await client.post("/user-goals", json={"type": "bulk"}, headers=auth_headers)
    await client.patch(
        f"/user-goals/{g1['id']}", json={"status": "completed"}, headers=auth_headers,
    )
    r = await client.get("/user-goals?status=active", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert all(g["status"] == "active" for g in data)
    assert len(data) == 1


@pytest.mark.asyncio
async def test_get_goal_by_id(client: AsyncClient, auth_headers):
    """GET /user-goals/{id} 本人 -> 200 + id 一致。"""
    created = (
        await client.post("/user-goals", json={"type": "cut"}, headers=auth_headers)
    ).json()
    r = await client.get(f"/user-goals/{created['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_patch_goal_status_to_completed(client: AsyncClient, auth_headers):
    """PATCH /user-goals/{id} 改 status -> 200 + target_value 不变（W4）。"""
    created = (
        await client.post(
            "/user-goals",
            json={"type": "cut", "target_value": 75.0},
            headers=auth_headers,
        )
    ).json()
    r = await client.patch(
        f"/user-goals/{created['id']}",
        json={"status": "completed", "notes": "done"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["target_value"] == 75.0  # W4 exclude_unset 不动未传字段


@pytest.mark.asyncio
async def test_delete_goal_does_not_exist(client: AsyncClient, auth_headers):
    """Q5 verify：DELETE /user-goals/{id} 不实现 -> 405 Method Not Allowed。

    FastAPI 路由层对未注册 method 自动返回 405。
    这反向验证 Q5 决策：不实现 DELETE，goal 是历史轨迹走 PATCH status=abandoned。
    """
    r = await client.delete("/user-goals/1", headers=auth_headers)
    assert r.status_code == 405


@pytest.mark.asyncio
async def test_patch_goal_422_extra_field(client: AsyncClient, auth_headers):
    """W3 verify：PATCH 传 user_id（schema extra='forbid'） -> 422。

    关键：UserGoalUpdate 用 extra='forbid' 拒额外字段 —— 防止 user_id 被前端误改。
    """
    created = (
        await client.post("/user-goals", json={"type": "cut"}, headers=auth_headers)
    ).json()
    r = await client.patch(
        f"/user-goals/{created['id']}",
        json={"user_id": 999},
        headers=auth_headers,
    )
    assert r.status_code == 422