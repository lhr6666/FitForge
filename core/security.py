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
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


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