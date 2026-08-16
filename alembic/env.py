from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# FitForge 自定义：D11 决策用 pydantic-settings 加载配置（不用 alembic.ini）
from core.config import settings
from models import Base  # noqa: F401（导入触发 3 个 model 注册到 Base.metadata）

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# FitForge 自定义：把 settings.SYNC_DATABASE_URL 注入 alembic config
# 避免 alembic.ini 含明文密码
#这里直接读取同步地址防止读到异步地址导致报错
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# FitForge 自定义：target_metadata 让 alembic autogenerate 能对比 ORM 和 DB schema
# from myapp import mymodel

# Base.metadata 就是一个“图纸收纳册”。因为class User(base)Python 执行到这儿时,它把 id 和 name 这些定义，自动塞进了 Base 肚子里的 metadata 收纳册里。
target_metadata = Base.metadata  # 3 张 model 表（users/user_goals/body_measurements）

#但同样还需要导入其他模型比如定义的user表，goal表等，这样base.metadata里面才会有所有的表，然后才能生成迁移文件。
#如果不导入的话就会以为base.metadata里面是空的，还会把原有的表清除掉

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
