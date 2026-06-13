# querydsl/db.py
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine


@dataclass
class DatabaseConfig:
    server: str
    database: str
    username: str
    password: str
    driver: str = "ODBC Driver 17 for SQL Server"


def make_connection_url(config: DatabaseConfig) -> URL:
    if not all([config.server, config.database, config.username, config.password]):
        raise ValueError("All database connection parameters are required")
    return URL.create(
        "mssql+pyodbc",
        username=config.username,
        password=config.password,
        host=config.server,
        database=config.database,
        query={"driver": config.driver},
    )


def make_engine(config: DatabaseConfig) -> Engine:
    """Create a read-only-intended engine. Queries are SELECT-only by construction (DSL)."""
    return create_engine(make_connection_url(config))
