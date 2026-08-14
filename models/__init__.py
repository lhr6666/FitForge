"""数据模型层 - SQLAlchemy ORM 模型，对应数据库表结构。

D17 决策：3 张表 schema（users / user_goals / body_measurements）
D4 决策：SQLAlchemy 2.0 异步 ORM

设计：
- Base 是所有 ORM 类的基类（DeclarativeBase）
- Alembic env.py 用 `Base.metadata` 生成 migration
- 各 model 文件（user.py / user_goal.py / body_measurement.py）继承 Base

注意：model import 在本文件底部追加（Alembic 需要 Base.metadata 在 import 之前定义）
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类。

    所有 model 类（User / UserGoal / BodyMeasurement）都继承此类。
    Alembic env.py 通过 `Base.metadata` 读取所有 model 的 schema，生成 migration。
    """
    pass


# Alembic 需要从 models 导入所有 model 才能检测到 schema
# noqa: E402,F401 是因为 import 必须在 Base 定义之后
from models.user import User, RefreshToken  # noqa: E402,F401
from models.user_goal import UserGoal  # noqa: E402,F401
from models.body_measurement import BodyMeasurement  # noqa: E402,F401
