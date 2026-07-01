"""配置层 - 通过 pydantic-settings 从 .env 加载配置。
所有运行时需要的配置（DB URL、JWT 密钥路径、过期时间等）都在这里集中管理。
"""
# 计划周三开始填充：
# from pydantic_settings import BaseSettings
# class Settings(BaseSettings):
#     DATABASE_URL: str
#     PRIVATE_KEY_PATH: str = "keys/private.pem"
#     PUBLIC_KEY_PATH: str = "keys/public.pem"
#     ALGORITHM: str = "RS256"
#     ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
#     ...
# settings = Settings()