"""BodyMeasurement ORM 模型 - body_measurements 表。

D17 决策：3 张表 schema
D17-a：CASCADE（删 user 自动删 measurements）
D17-b：复合索引 (user_id, recorded_at)
D17-c：业务时间 vs 系统时间分离（recorded_at + created_at）
D17-f：UTC 时间戳

字段：
- id：主键，自增
- user_id：FK → users.id，ON DELETE CASCADE
- weight：体重（kg），必填
- body_fat：体脂率（%），可空
- 6 个围度：chest/waist/hip/bicep/thigh/calf（cm），可空
- 3 个力量 1RM：squat_1rm/bench_1rm/deadlift_1rm（kg），可空
- recorded_at：用户测量时间（业务时间，可补录历史）
- created_at：系统插入时间（系统时间）
- updated_at：更新时间
- notes：备注，可空

复合索引：
- idx_body_measurements_user_recorded：(user_id, recorded_at) — 查"最近测量"用
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import relationship

from models import Base


class BodyMeasurement(Base):
    """BodyMeasurement 模型。

    业务意义：用户的身体数据记录（体重、体脂、围度、力量），支撑"周期化算法"读取历史数据生成训练计划。
    """

    __tablename__ = "body_measurements"

    # ===== 主键 =====
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ===== 外键（D17-a：ON DELETE CASCADE）=====
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ===== 业务字段 =====
    # 必填：体重
    weight = Column(Float, nullable=False)

    # 可选：体脂率
    body_fat = Column(Float, nullable=True)

    # 可选：6 个围度（cm）
    chest = Column(Float, nullable=True)
    waist = Column(Float, nullable=True)
    hip = Column(Float, nullable=True)
    bicep = Column(Float, nullable=True)
    thigh = Column(Float, nullable=True)
    calf = Column(Float, nullable=True)

    # 可选：3 个力量 1RM（kg）
    squat_1rm = Column(Float, nullable=True)
    bench_1rm = Column(Float, nullable=True)
    deadlift_1rm = Column(Float, nullable=True)

    # 业务时间（D17-c：业务时间 vs 系统时间分离）
    # 允许用户补录历史测量（如"补录 7 天前的测量"）
    recorded_at = Column(DateTime, nullable=False, index=True)

    # 可选：备注
    notes = Column(Text, nullable=True)

    # ===== 时间戳（D17-g：全表统一）=====
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ===== 关系（与 User 反向）=====
    user = relationship("User", back_populates="measurements")

    # ===== 复合索引（D17-b）=====
    __table_args__ = (
        Index("idx_body_measurements_user_recorded", "user_id", "recorded_at"),
    )

    def __repr__(self) -> str:
        return f"<BodyMeasurement user={self.user_id} weight={self.weight}>"