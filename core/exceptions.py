"""FitForge 业务异常体系。
这里是定义异常有哪些的

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


class MeasurementNotFoundError(FitForgeException):
    """测量记录不存在或非当前用户所有（HTTP 404）。

    触发场景：
        - measurement_id 不存在
        - measurement_id 存在但 user_id != current_user.id（防 ID 枚举攻击）

    关联决策：D38（跨用户访问统一返回 404 而非 403）
    由 api/exception_handlers.py 映射到 HTTP 404 Not Found。
    """

    pass


class GoalNotFoundError(FitForgeException):
    """训练目标不存在或非当前用户所有（HTTP 404）。

    触发场景：
        - goal_id 不存在
        - goal_id 存在但 user_id != current_user.id（防 ID 枚举攻击）

    关联决策：D38（跨用户访问统一返回 404 而非 403）
    由 api/exception_handlers.py 映射到 HTTP 404 Not Found。
    """

    pass


class UnauthorizedAccessError(FitForgeException):
    """未授权访问他人资源（HTTP 403）。

    预留：当前 spec §5 跨用户访问统一返回 404（D38）以防枚举，
    本异常保留供未来需要显式 403 的鉴权场景（如教练角色权限升级）。
    由 api/exception_handlers.py 映射到 HTTP 403 Forbidden。
    """

    pass