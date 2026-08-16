"""user_goals service 单元测试。

覆盖 4 个 service 函数的 200/404 路径。
共 4 个核心 case + D38 防枚举关键测试。
"""

from datetime import date

import pytest

from core.exceptions import GoalNotFoundError
from models.user import User
from schemas.goal import UserGoalCreate, UserGoalUpdate
from services.goal_service import (
    create_goal,
    get_goal,
    list_goals,
    update_goal,
)


@pytest.mark.asyncio
async def test_create_goal_default_status_active(db_session, sample_user):
    """create_goal: 默认 status='active'（Q5 决策）。"""
    obj = await create_goal(
        db_session, sample_user,
        UserGoalCreate(type="cut", target_value=75.0),
    )
    assert obj.status == "active"
    assert obj.type == "cut"
    assert obj.target_value == 75.0


@pytest.mark.asyncio
async def test_list_goals_with_status_filter(db_session, sample_user):
    """list_goals: status 过滤生效（abandoned 的不出现）。"""
    g1 = await create_goal(db_session, sample_user, UserGoalCreate(type="cut"))
    g2 = await create_goal(db_session, sample_user, UserGoalCreate(type="bulk"))
    await update_goal(
        db_session, sample_user, g1.id, UserGoalUpdate(status="abandoned"),
    )
    actives = await list_goals(db_session, sample_user, status="active")
    assert len(actives) == 1
    assert actives[0].id == g2.id


@pytest.mark.asyncio
async def test_get_goal_other_user_returns_404(db_session, sample_user):
    """get_goal: 跨用户访问 -> 404 防枚举（D38）。

    关键：与 get_measurement 同样的安全设计 —— 不暴露资源存在性。
    """
    other = User(
        username="other_goal_user",
        email="other_goal@example.com",
        password_hash="x",
    )
    db_session.add(other)
    await db_session.commit()

    g = await create_goal(
        db_session, sample_user,
        UserGoalCreate(type="cut", target_value=75.0, deadline=date(2026, 12, 31)),
    )
    with pytest.raises(GoalNotFoundError):
        await get_goal(db_session, other, g.id)


@pytest.mark.asyncio
async def test_update_goal_to_completed(db_session, sample_user):
    """update_goal: status active -> completed（Q4 状态机切换）。

    target_value 不变（W4：exclude_unset 仅改显式传的字段）。
    """
    g = await create_goal(
        db_session, sample_user,
        UserGoalCreate(type="cut", target_value=75.0),
    )
    updated = await update_goal(
        db_session, sample_user, g.id, UserGoalUpdate(status="completed"),
    )
    assert updated.status == "completed"
    assert updated.target_value == 75.0  # 不变