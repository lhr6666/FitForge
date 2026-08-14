"""User ORM 模型 - users 表。

D17 决策：3 张表 schema
D17-a：CASCADE（删 user 自动删 goals/measurements）
D17-g：created_at/updated_at 全表统一

字段：
- id：主键（唯一，不为空），自增
- username：登录标识，UNIQUE 索引
- email：邮箱，UNIQUE 索引（Q6 决策：注册时强制必填）
- password_hash：Argon2id 哈希（D6 决策）
- nickname：显示名（可空）
- created_at / updated_at：UTC 时间戳

关系：
- goals → UserGoal（一对多，CASCADE）
- measurements → BodyMeasurement（一对多，CASCADE）
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from models import Base


class User(Base):
    """User 模型。

    业务意义：FitForge 的核心实体，关联所有用户级数据（goals、measurements）。
    """

    __tablename__ = "users"

    # ===== 主键 =====
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ===== 业务字段 =====
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=True)

    # ===== 时间戳（D17-g：全表统一）=====
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # 关系字段：定义了两个一对多关系，分别关联到 UserGoal 和 BodyMeasurement 模型。也设置了级联删除的规则：当 User 被删除时，所有相关的 UserGoal 和 BodyMeasurement 也会被删除。
    goals = relationship(
        "UserGoal",#告诉数据库，这个字段指向 UserGoal 模型，也就是要读取goal时去UserGoal表中找
        back_populates="user",
        cascade="all, delete-orphan",
    )
    measurements = relationship(
        "BodyMeasurement",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
#当你打印这个对象，或者在调试器里看它时，显示什么内容。
    def __repr__(self) -> str:
        return f"<User {self.username}>"


class RefreshToken(Base):
    """RefreshToken ORM 模型。

    存储每个 refresh token 的 jti + 过期时间 + 撤销状态。
    每次 login/refresh 写一行；logout/rotate 标记 revoked=True。
    """

    __tablename__ = "refresh_tokens"

    # ===== 主键 =====
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ===== 外键（D29: DB 存 jti + revoke）=====
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ===== 业务字段 =====
    jti = Column(String(36), unique=True, nullable=False, index=True)  # UUID4 字符串
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)

    # ===== 时间戳（D17-g 全表统一）=====
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ===== 关系 =====
    user = relationship("User", back_populates="refresh_tokens")

    # ===== 复合索引（D17-b 原则：跟随 WHERE 子句）=====
    __table_args__ = (
        Index("idx_refresh_tokens_user_active", "user_id", "revoked"),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken jti={self.jti[:8]}... revoked={self.revoked}>"