"""FitForge 配置管理（D11 决策）。

使用 pydantic-settings 从 .env 文件加载配置。
所有配置字段集中在此，其他模块统一通过 `from core.config import settings` 引用。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """FitForge 全局配置。

    字段命名规范：
    - 数据库：DATABASE_URL（运行时异步）、SYNC_DATABASE_URL（Alembic 用）
    - JWT：JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH / JWT_ALGORITHM / JWT_EXPIRE_MINUTES
    """

    # ===== 数据库 =====
    # 运行时用（FastAPI + asyncmy）fastAPI需要对数据库进行操作，因此要用到异步对数据库进行访问；这是fastAPI的url地址
    DATABASE_URL: str = "mysql+asyncmy://fitforge:fitforge_dev_password_2026@localhost:3306/fitforge"
    # Alembic autogenerate 用（pymysql 同步）alembic需要对数据库进行操作，因此要用到同步对数据库进行访问；这是alembic的url地址
    SYNC_DATABASE_URL: str = "mysql+pymysql://fitforge:fitforge_dev_password_2026@localhost:3306/fitforge"

    # ===== JWT（RS256 非对称签名）=====
    # 私钥路径（签发 token 用）
    JWT_PRIVATE_KEY_PATH: str = "./keys/private.pem"
    # 公钥路径（验证 token 用）
    JWT_PUBLIC_KEY_PATH: str = "./keys/public.pem"
    # 签名算法（D7 决策：RS256）
    JWT_ALGORITHM: str = "RS256"
    # Token 过期时间（分钟）—— MVP 默认 1 天
    JWT_EXPIRE_MINUTES: int = 60 * 24

    # ===== 应用元信息 =====
    APP_NAME: str = "FitForge"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ===== 日志 =====
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/fitforge.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,  # 大小写敏感，避免 DATABASE_URL 和 database_url 混淆
        extra="ignore",  # .env 多余字段忽略，不报错
    )


# 全局单例：整个项目共享一个 settings 实例
settings = Settings()