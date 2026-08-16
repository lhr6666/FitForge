"""body_measurements 路由 e2e 测试。

覆盖 6 个端点（POST / POST batch / GET / GET id / PATCH / DELETE）+ 鉴权 + 422 校验。
共 10 个核心 case。

fixtures: conftest.py 提供 client (httpx AsyncClient) + auth_headers (Bearer token)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_body_measurement_201(client: AsyncClient, auth_headers):
    """POST /body-measurements 正常 -> 201 + BodyMeasurementRead。"""
    body = {"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"}
    r = await client.post("/body-measurements", json=body, headers=auth_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["weight"] == 70.0
    assert "id" in data


@pytest.mark.asyncio
async def test_post_body_measurement_401_no_auth(client: AsyncClient):
    """POST /body-measurements 无 token -> 401。"""
    r = await client.post(
        "/body-measurements",
        json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_post_body_measurement_422_invalid_weight(client: AsyncClient, auth_headers):
    """POST /body-measurements weight < 20 -> 422（Pydantic Field ge=20 校验）。"""
    r = await client.post(
        "/body-measurements",
        json={"weight": 1.0, "recorded_at": "2026-08-16T08:30:00"},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_batch_201(client: AsyncClient, auth_headers):
    """POST /body-measurements/batch 批量 2 条 -> 201 + count=2。"""
    body = {"items": [
        {"weight": 70.0, "recorded_at": "2026-08-15T08:30:00"},
        {"weight": 71.0, "recorded_at": "2026-08-16T08:30:00"},
    ]}
    r = await client.post("/body-measurements/batch", json=body, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["count"] == 2


@pytest.mark.asyncio
async def test_get_body_measurements_with_filters(client: AsyncClient, auth_headers):
    """GET /body-measurements?from=&to= 带过滤 -> 200 + 至少 1 条。"""
    base = "2026-08-16T08:30:00"
    await client.post(
        "/body-measurements",
        json={"weight": 70.0, "recorded_at": base},
        headers=auth_headers,
    )
    r = await client.get(
        "/body-measurements?from=2026-08-15&to=2026-08-17",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_get_measurement_by_id(client: AsyncClient, auth_headers):
    """GET /body-measurements/{id} 本人 -> 200 + id 一致。"""
    created = (
        await client.post(
            "/body-measurements",
            json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"},
            headers=auth_headers,
        )
    ).json()
    r = await client.get(f"/body-measurements/{created['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_measurement_404(client: AsyncClient, auth_headers):
    """GET /body-measurements/{id} 不存在 -> 404。"""
    r = await client.get("/body-measurements/99999", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_measurement_notes(client: AsyncClient, auth_headers):
    """PATCH /body-measurements/{id} 改 notes -> 200 + notes 更新。"""
    created = (
        await client.post(
            "/body-measurements",
            json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"},
            headers=auth_headers,
        )
    ).json()
    r = await client.patch(
        f"/body-measurements/{created['id']}",
        json={"notes": "morning"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "morning"


@pytest.mark.asyncio
async def test_patch_measurement_422_extra_field(client: AsyncClient, auth_headers):
    """W3 验证：PATCH 传 weight（schema extra='forbid'） -> 422。

    关键：BodyMeasurementPatch 用 extra='forbid' 拒额外字段 —— 保护关键测量值不被误覆盖。
    """
    created = (
        await client.post(
            "/body-measurements",
            json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"},
            headers=auth_headers,
        )
    ).json()
    r = await client.patch(
        f"/body-measurements/{created['id']}",
        json={"weight": 999.0, "notes": "x"},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_measurement_204(client: AsyncClient, auth_headers):
    """DELETE /body-measurements/{id} 成功 -> 204 + 后续 GET 404。"""
    created = (
        await client.post(
            "/body-measurements",
            json={"weight": 70.0, "recorded_at": "2026-08-16T08:30:00"},
            headers=auth_headers,
        )
    ).json()
    r = await client.delete(f"/body-measurements/{created['id']}", headers=auth_headers)
    assert r.status_code == 204
    r2 = await client.get(f"/body-measurements/{created['id']}", headers=auth_headers)
    assert r2.status_code == 404