"""UserGoal ORM 模型 - user_goals 表。

D17 决策：3 张表 schema
D17-a：CASCADE（删 user 自动删 goals）
D17-b：复合索引 (user_id, status)
D17-d：ENUM 约束在 DB 层

字段：
- id：主键，自增
- user_id：FK → users.id，ON DELETE CASCADE
- type：ENUM('cut','bulk','maintain','strength')
- target_value：FLOAT 可空（如 75.0 kg）
- status：ENUM('active','completed','abandoned')，default 'active'
- deadline：DATE 可空（预留字段）
- notes：TEXT 可空（预留字段）
- created_at / updated_at：UTC 时间戳

复合索引：
- idx_user_goals_user_status：(user_id, status) — 查"某用户当前 active 目标"用
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.orm import relationship

from models import Base


class UserGoal(Base):
    """UserGoal 模型。

    业务意义：用户的训练目标（如"3 个月内减脂到 75kg"），一个用户可以有多个目标（active/completed/abandoned）。
    """

    __tablename__ = "user_goals"

    # ===== 主键 =====
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 这个就是定位究竟这个goal是哪个user定义的，从而达到关联数据的目的
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),#这条代码会使得数据库建立索引：在 user_goals.user_id 列上建索引；注册触发器：在 users 表上注册删除监听器
        # 触发器：当 users 表中的某行被删除时，user_goals 表中所有与该用户相关的行也会被删除。
        #因为user_goals表中的user_id列是外键，指向users表中的id列，并不是他这个表本身的列（也就是主键）
        nullable=False,
        index=True,
    )

    # ===== 业务字段（D17-d：ENUM 约束在 DB 层）=====
    type = Column(
        Enum("cut", "bulk", "maintain", "strength", name="goal_type"),
        nullable=False,
    )
    target_value = Column(Float, nullable=True)  # 如 75.0（kg）
    status = Column(
        Enum("active", "completed", "abandoned", name="goal_status"),
        default="active",
        nullable=False,
        index=True,
    )

    # ===== 预留字段（未来扩展用）=====
    deadline = Column(Date, nullable=True)
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
    user = relationship("User", back_populates="goals")

    # ===== 复合索引（D17-b）=====
    __table_args__ = (
        Index("idx_user_goals_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<UserGoal {self.id} {self.type} {self.status}>"