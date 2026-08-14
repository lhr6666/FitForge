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
        min_length=3,#限制字符串最短是3
        max_length=50,#限制字符串最长是50
        pattern=r"^[a-zA-Z0-9_]+$",#调用re.search()来验证字符串是否符合正则表达式
        #正则表达式：^[a-zA-Z0-9_]+$，表示字符串必须以字母、数字或下划线开头，后面可以接任意数量的字母、数字或下划线。不符合这个规则的，会抛出ValueError异常
        description="用户名（3-50 字符，字母数字下划线）",#描述字段的作用，方便API文档生成
    )
    email: EmailStr = Field(#EmailStr是Pydantic提供的特殊字符串类型，专门用于验证电子邮件格式的合法性。它不是简单的正则检查，而是通常依赖底层的 email-validator 库，遵循 RFC 5322 标准，能处理极其复杂的邮箱格式边缘情况。
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

    @field_validator("password")#绑定字段，就是你在 `UserCreate` 类里定义的变量名。它告诉 Pydantic：“**这个校验器只负责盯着这个字段看**。”
    @classmethod#类方法，让这个方法属于“**类**”本身，而不是属于“**对象（实例）”。它**不能**操作具体某个用户的数据，但可以帮类“生产”或“检查”数据。因为pydantic的校验是发生在创建对象之前，所以需要使用类方法。
    def password_must_contain_letter_and_digit(cls, v: str) -> str:#cls:类方法，v:字符串，cls是class的缩写，表示当前类
        """Q5 中等密码强度校验。

        - 必须含字母（大小写均可）
        - 必须含数字
        - 拦典型弱密码如 '12345678'
        """
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须包含字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        return v# 代表 Value（值）。它就是用户传进来的那个字段的具体内容。


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
        from_attributes=True,  # 允许 Pydantic 模型不仅仅从字典（dict）构造，还可以从任意具有属性的对象（如 ORM 对象、Dataclass 对象）读取数据。同时也是 分离数据库模型与 API 响应的关键。通过使用pydantic作为中间人，将想要看到的字段呈现出来给响应模型发给前端。
    )


# ============ /auth/login + refresh + logout 新增 schema ============

class LoginRequest(BaseModel):
    """登录请求体（email + password）。

    Q4: 不含 password_hash 字段——只接明文 password
    Q6: email 必填
    """

    email: EmailStr = Field(description="邮箱（Q6 必填）")
    password: str = Field(min_length=8, max_length=128, description="明文密码（路由层转 service.verify_password）")


class RefreshRequest(BaseModel):
    """刷新 token 请求体（只用 refresh_token）。"""

    refresh_token: str = Field(
        min_length=10,
        description="14 天有效 refresh token（D28 双 token 机制）",
    )


class TokenResponse(BaseModel):
    """登录 / 刷新响应体（双 token + 元信息）。

    Q4: 不含 password_hash
    """

    access_token: str = Field(description="Access token（30 分钟有效，Authorization Bearer 用）")
    refresh_token: str = Field(description="Refresh token（14 天有效，/auth/refresh 用）")
    token_type: str = Field(default="bearer", description="固定 'bearer'（OAuth 2.0 标准）")
    expires_in: int = Field(description="Access token 寿命（秒），默认 1800 = 30 分钟")