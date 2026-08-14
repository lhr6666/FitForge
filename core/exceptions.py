"""FitForge 业务异常体系。

Q2 决策：业务异常体系（service 抛自定义异常，路由层 exception_handler 映射）

设计原则：
1. 所有业务异常继承 FitForgeException 基类 → 路由层 catch FitForgeException 兜底
2. 具体异常（UsernameExistsError 等）继承 FitForgeException → 路由层 catch 具体异常映射特定状态码
3. 异常与 HTTP 状态码解耦 → service 层不知道有 HTTP，业务可复用
"""

from typing import Any


class FitForgeException(Exception):
    """FitForge 业务异常基类。

    所有 FitForge 业务异常都应继承此类，而不是直接继承 Exception。
    这样路由层的 exception_handler 可以：
    - 捕获具体子类（UsernameExistsError）→ 映射特定状态码（如 409）
    - 兜底捕获 FitForgeException → 映射 400（业务错误）

    使用建议：
        raise UsernameExistsError("用户名 'alice' 已被占用")
        raise EmailExistsError(f"邮箱 '{email}' 已被注册")
    """

    def __init__(self, message: str, *args: Any) -> None:
        """初始化业务异常。

        Args:
            message: 异常描述信息（会作为 detail 返回给客户端）
            *args: 传递给父类 Exception 的额外参数（保留扩展性）
        """
        super().__init__(message, *args)
        self.message = message

    def __str__(self) -> str:
        return self.message


class UsernameExistsError(FitForgeException):
    """用户名已被占用（HTTP 409）。

    触发场景：
        - service.register() 检测到 username 已存在
        - 并发注册同时请求同 username 导致 DB UNIQUE 冲突（兜底）

    由 api/exception_handlers.py 映射到 HTTP 409 Conflict。
    """

    pass


class EmailExistsError(FitForgeException):
    """邮箱已被注册（HTTP 409）。

    触发场景：
        - service.register() 检测到 email 已存在
        - 并发注册同时请求同 email 导致 DB UNIQUE 冲突（兜底）

    由 api/exception_handlers.py 映射到 HTTP 409 Conflict。
    """

    pass


class InvalidCredentialsError(FitForgeException):
    """登录凭证错误（HTTP 401）。

    触发场景：
        - email 不存在
        - password 错误

    注意：两个场景返回**统一消息**（防枚举攻击）
    """

    pass


class InvalidTokenError(FitForgeException):
    """JWT token 无效（HTTP 401）。

    触发场景：
        - token 签名错
        - token 已过期
        - token 类型错（拿 refresh 当 access 用）
        - token 被撤销（refresh 表 revoked=true）
    """

    pass