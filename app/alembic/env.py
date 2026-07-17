"""
env.py minimo do Alembic (criado na LIB-002 como habilitador de validacao).
As migracoes deste repo sao escritas a mao (sem autogenerate); a URL vem de
sqlalchemy.url (alembic.ini / -x) ou da env var DATABASE_URL.
NAO esta ligado a startup da aplicacao (o runtime continua usando migrate.py).
"""
import os

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config


def get_url() -> str:
    return (
        config.get_main_option("sqlalchemy.url")
        or os.getenv("DATABASE_URL", "sqlite:///./test.db")
    )


target_metadata = None  # migracoes manuais


def run_migrations_offline() -> None:
    context.configure(url=get_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
