"""body_measurements Pydantic schemas.

D33: 两个创建端点（单 + /batch），整体事务
D34: PATCH 仅允许 notes + recorded_at（extra="forbid" 防字段误覆盖）
D37: 列表查询 limit ≤ 100, offset ≥ 0
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ===== 入参 =====


class BodyMeasurementCreate(BaseModel):
    """POST /body-measurements 入参"""

    weight: float = Field(ge=20, le=300, description="体重 kg，必填")
    body_fat: float | None = Field(default=None, ge=3, le=60, description="体脂率 %")
    chest: float | None = Field(default=None, ge=0, le=300)
    waist: float | None = Field(default=None, ge=0, le=300)
    hip: float | None = Field(default=None, ge=0, le=300)
    bicep: float | None = Field(default=None, ge=0, le=100)
    thigh: float | None = Field(default=None, ge=0, le=100)
    calf: float | None = Field(default=None, ge=0, le=80)
    squat_1rm: float | None = Field(default=None, ge=0, le=500)
    bench_1rm: float | None = Field(default=None, ge=0, le=500)
    deadlift_1rm: float | None = Field(default=None, ge=0, le=500)
    recorded_at: datetime = Field(description="业务时间（D17-c 业务时间分离）")
    notes: str | None = Field(default=None, max_length=1000)


class BodyMeasurementBatchCreate(BaseModel):
    """POST /body-measurements/batch 入参"""

    items: list[BodyMeasurementCreate] = Field(
        min_length=1,
        max_length=50,
        description="1-50 条测量记录",
    )


class BodyMeasurementPatch(BaseModel):
    """PATCH /body-measurements/{id} 入参（Q3：仅 notes + recorded_at）"""

    model_config = ConfigDict(extra="forbid")  # 拒额外字段
    notes: str | None = Field(default=None, max_length=1000)
    recorded_at: datetime | None = None


class BodyMeasurementListQuery(BaseModel):
    """GET /body-measurements query 参数"""

    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# ===== 出参 =====


class BodyMeasurementRead(BaseModel):
    """GET / POST 响应体"""

    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    weight: float
    body_fat: float | None
    chest: float | None
    waist: float | None
    hip: float | None
    bicep: float | None
    thigh: float | None
    calf: float | None
    squat_1rm: float | None
    bench_1rm: float | None
    deadlift_1rm: float | None
    recorded_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime


class BodyMeasurementBatchRead(BaseModel):
    """POST /batch 响应体"""

    count: int
    items: list[BodyMeasurementRead]