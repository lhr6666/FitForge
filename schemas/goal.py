"""user_goals Pydantic schemas.

D35: PATCH 允许全 5 字段（type/target_value/status/deadline/notes），不含 user_id/id/time
D36: 不实现 DELETE（走 status=abandoned + PATCH）
D37: 列表 limit ≤ 100, offset ≥ 0
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ===== Literal 类型 =====

GOAL_TYPE = Literal["cut", "bulk", "maintain", "strength"]
GOAL_STATUS = Literal["active", "completed", "abandoned"]


# ===== 入参 =====


class UserGoalCreate(BaseModel):
    """POST /user-goals 入参"""

    type: GOAL_TYPE
    target_value: float | None = Field(default=None, ge=0, le=1000)
    deadline: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    # status 默认 "active"，service 层填


class UserGoalUpdate(BaseModel):
    """PATCH /user-goals/{id} 入参（Q4：5 字段）"""

    model_config = ConfigDict(extra="forbid")
    type: GOAL_TYPE | None = None
    target_value: float | None = Field(default=None, ge=0, le=1000)
    status: GOAL_STATUS | None = None
    deadline: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class UserGoalListQuery(BaseModel):
    """GET /user-goals query 参数"""

    status: GOAL_STATUS | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# ===== 出参 =====


class UserGoalRead(BaseModel):
    """GET / POST / PATCH 响应体"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    type: str  # PyBaseModel Literal 类型 + ORM str 列，反序列化保留为 str
    target_value: float | None
    status: str
    deadline: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime