import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.models import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


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
        # Biztonsági háló: séma-módosítás SOHA ne várjon korlátlanul egy
        # táblazárolásra. A migráció a konténer indulásakor fut, amikor a RÉGI
        # példány még kiszolgál - egy futó lekérdezés mögé beállva a DDL
        # némán várna, és mögé beállna minden további olvasó is, tehát nemcsak
        # a deploy állna meg, hanem a régi alkalmazás is hibázni kezdene azon a
        # táblán. Enélkül ez a deployt percekig "csak fut" állapotban tartotta,
        # hibaüzenet nélkül.
        #
        # Ez csak a végső korlát: az egyes DDL-eket ezen felül újrapróbálkozó
        # segéddel érdemes futtatni (lásd app/core/migracio.zarasbiztos_ddl),
        # ami egy pillanatnyi forgalom miatt nem bukik el.
        if connection.dialect.name == "postgresql":
            connection.exec_driver_sql("SET lock_timeout = '30s'")
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
