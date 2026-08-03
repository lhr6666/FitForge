"""User Pydantic Schema - 用户请求/响应体。

Q4 决策：2 个 schema 隔离 password（UserCreate 含明文，UserRead 无 password_hash）
Q5 决策：中等密码强度（min_length=8 + 字母数字混合）
Q6 决策：email 必填（EmailStr）

设计：
- UserCreate：用户注册请求体（含 password 明文）
- UserRead：API 响应体（不含 password_hash）
"""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """用户注册请求体。

    字段：
    - username：3-50 字符，仅字母数字下划线
    - email：必填 EmailStr（Pydantic 自动验证邮箱格式）
    - password：8-128 字符，必须含字母+数字（Q5 中等强度）
    - nickname：可选，≤50 字符
    """

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="用户名（3-50 字符，字母数字下划线）",
    )
    email: EmailStr = Field(
        description="邮箱（Q6 强制必填）",
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="密码（Q5：8-128 字符，必须含字母+数字）",
    )
    nickname: str | None = Field(
        default=None,
        max_length=50,
        description="昵称（可选，≤50 字符）",
    )

    @field_validator("password")
    @classmethod
    def password_must_contain_letter_and_digit(cls, v: str) -> str:
        """Q5 中等密码强度校验。

        - 必须含字母（大小写均可）
        - 必须含数字
        - 拦典型弱密码如 '12345678'
        """
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须包含字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        return v


class UserRead(BaseModel):
    """API 响应体（注册成功后返回）。

    关键设计：
    - 不包含 password_hash 字段（Q4 隔离密码）
    - 配置 from_attributes=True，支持从 ORM 对象构造（Pydantic v2）
    """

    id: int = Field(description="用户 ID（DB 自增）")
    username: str = Field(description="用户名")
    nickname: str | None = Field(default=None, description="昵称")

    # Pydantic v2：用 model_config 替代 v1 的 Config 类
    model_config = ConfigDict(
        from_attributes=True,  # 允许从 ORM 对象构造（orm_mode 等价）
    )