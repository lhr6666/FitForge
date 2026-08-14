"""FastAPI 业务异常 → HTTP 状态码映射。

Q2 决策：业务异常体系（service 抛自定义异常，路由层 add_exception_handler 映射）

设计原则：
1. service 不知道 HTTP 存在 —— 抛业务异常即可
2. 路由层把业务异常映射到正确的 HTTP 状态码 + 响应体
3. 兜底 3 层：具体异常 → 业务基类 → Exception（500）
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from core.exceptions import (
    EmailExistsError,
    FitForgeException,
    InvalidCredentialsError,
    InvalidTokenError,
    UsernameExistsError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """注册所有业务异常的 HTTP 映射。

    调用方式（在 main.py）：
        from api.exception_handlers import register_exception_handlers
        app = FastAPI()
        register_exception_handlers(app)

    异常 → 状态码映射（按 spec §6）：
    - UsernameExistsError → 409 Conflict
    - EmailExistsError    → 409 Conflict
    - IntegrityError      → 409 Conflict（DB 层兜底，处理并发 UNIQUE 冲突）
    - FitForgeException   → 400 Bad Request（其他业务异常兜底）
    - Exception           → 500 Internal Server Error（FastAPI 默认）
    """
# 告诉 FastAPI：如果你抓住了 UsernameExistsError这种类型的错误，
# 就请用这个 username_exists_handler 函数来处理它。
    @app.exception_handler(UsernameExistsError)
    async def username_exists_handler(
        request: Request,  # noqa: ARG001（FastAPI 必须的参数）
        exc: UsernameExistsError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(EmailExistsError)
    async def email_exists_handler(
        request: Request,  # noqa: ARG001
        exc: EmailExistsError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(
        request: Request,  # noqa: ARG001
        exc: InvalidCredentialsError,
    ) -> JSONResponse:
        # 401 Unauthorized（登录凭证错误）
        # WWW-Authenticate: Bearer 头是 OAuth 2.0 标准
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(InvalidTokenError)
    async def invalid_token_handler(
        request: Request,  # noqa: ARG001
        exc: InvalidTokenError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request,  # noqa: ARG001
        exc: IntegrityError,  # noqa: ARG001
    ) -> JSONResponse:
        # DB 层兜底：应对并发注册同 username/email
        # 业务层 99% 拦截 + DB 层 1% 兜底 = 纵深防御
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "数据冲突，可能是 username 或 email 已被占用（DB 层兜底）",
            },
        )

    @app.exception_handler(FitForgeException)
    async def fitforge_exception_handler(
        request: Request,  # noqa: ARG001
        exc: FitForgeException,
    ) -> JSONResponse:
        # 兜底：未被子类 handler 捕获的业务异常 → 400
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )