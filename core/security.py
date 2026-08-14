"""安全基础设施 - 密码哈希。

D6 决策：Argon2id（passlib + argon2-cffi）
D5 决策：PyJWT（用于后续 /auth/login 的 token 签发，本文件暂未涉及）
D7 决策：RS256（暂未涉及 JWT，本文件先做密码哈希）

OWASP 2023+ 推荐 Argon2id 作为 PHC（Password Hashing Competition）算法：
- memory-hard：抗 GPU/ASIC 硬件加速攻击
- 时间硬性：抗侧信道攻击
- 内置 salt：自动生成随机盐，相同密码哈希不同
"""

from passlib.context import CryptContext


# ===== 密码哈希上下文 =====
# schemes=["argon2"]：声明只用 Argon2id 算法（passlib 也支持 bcrypt/scrypt/pbkdf2_sha256）
# deprecated="auto"：未来可加新算法时，旧哈希自动迁移（生产环境用得到）
#
# Argon2id 默认参数（passlib 默认值）：
#   - time_cost = 3（迭代 3 次）
#   - memory_cost = 65536 KiB（64 MB）
#   - parallelism = 4（4 个并行线程）
#   - hash_len = 32
#   - salt_len = 16
#   - type = ID（Argon2id，hybrid 模式，结合 Argon2i 和 Argon2d）
#
# 生产环境推荐调高 time_cost（如 4-6）+ memory_cost（如 131072 KiB）抗 GPU 攻击。
# 调参标准：单次 hash 耗时 250-500ms（用户体验 + 安全性的平衡）

#基础配置
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

#密码注册
def hash_password(plain: str) -> str:
    """对明文密码进行 Argon2id 哈希。

    Args:
        plain: 用户输入的明文密码

    Returns:
        Argon2id 哈希字符串（包含算法、盐、成本参数）：
        示例：$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>

    安全特性：
        - 自动生成 16 字节随机 salt（相同密码每次哈希结果不同）
        - 哈希字符串自带参数，verify 时无需额外配置
        - timing-safe 比较（避免时序攻击）
    """
    return pwd_context.hash(plain)

# 密码验证
def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希字符串是否匹配。

    Args:
        plain: 用户输入的明文密码
        hashed: 数据库存储的 Argon2id 哈希字符串

    Returns:
        True: 密码正确
        False: 密码错误

    安全特性：
        - 自动从 hashed 字符串解析 salt 和 cost 参数
        - timing-safe 比较（passlib 内部用恒定时间算法）
        - 错误时不抛异常（返回 False），便于上层业务处理
    """
    return pwd_context.verify(plain, hashed)


# ===== JWT 密钥加载（启动时一次）=====
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from core.config import settings
from core.exceptions import InvalidTokenError


_PRIVATE_KEY: str = ""
_PUBLIC_KEY: str = ""


def _load_keys() -> None:
    """启动时加载 RSA 密钥对（仅一次）。"""
    global _PRIVATE_KEY, _PUBLIC_KEY
    with open(settings.JWT_PRIVATE_KEY_PATH) as f:
        _PRIVATE_KEY = f.read()
    with open(settings.JWT_PUBLIC_KEY_PATH) as f:
        _PUBLIC_KEY = f.read()


_load_keys()


# ===== Token 寿命常量 =====
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 14


def create_access_token(user_id: int) -> str:
    """签发 access token（30 分钟）。

    Payload: {sub: user_id, iat, exp, type: "access"}
    算法: RS256 (D7 决策) + RSA 2048
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, _PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """签发 refresh token（14 天）+ 返回 jti。

    Returns: (token, jti)
    Payload: {sub, jti, iat, exp, type: "refresh"}

    用途: login + refresh 时签发；logout + refresh 时撤销（D30 决策）
    """
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()),
        "type": "refresh",
    }
    token = jwt.encode(payload, _PRIVATE_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_access_token(token: str) -> dict[str, Any]:
    """解码 + 验证 access token。失败抛 InvalidTokenError。

    验证 3 件事:
        1. 签名正确（RS256 + 公钥）
        2. 未过期（exp > now）
        3. 类型正确（type == "access"，防 refresh token 误用）
    """
    try:
        payload = jwt.decode(token, _PUBLIC_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("token 已过期")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("token 无效")
    if payload.get("type") != "access":
        raise InvalidTokenError("token 类型错误（不是 access）")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """解码 + 验证 refresh token。失败抛 InvalidTokenError。

    验证 3 件事:
        1. 签名正确
        2. 未过期
        3. 类型正确（type == "refresh"）
    """
    try:
        payload = jwt.decode(token, _PUBLIC_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("refresh token 已过期")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("refresh token 无效")
    if payload.get("type") != "refresh":
        raise InvalidTokenError("token 类型错误（不是 refresh）")
    return payload