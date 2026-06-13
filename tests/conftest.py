# tests/conftest.py
import pytest
from sqlalchemy import create_engine, text

from querydsl.models import Entity, FieldDef, Relationship, SemanticModel


@pytest.fixture
def engine():
    """In-memory SQLite seeded with companies + users (FK users.company_id -> companies.id)."""
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE companies (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                state TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                company_id INTEGER REFERENCES companies(id),
                last_login_dt TEXT
            )
        """))
        conn.execute(text("INSERT INTO companies (id, name, state) VALUES "
                          "(1, 'Acme', 'TX'), (2, 'Globex', 'CA'), (3, 'Initech', 'TX')"))
        conn.execute(text("INSERT INTO users (id, name, email, company_id, last_login_dt) VALUES "
                          "(1, 'Alice', 'a@x.com', 1, '2026-06-01'),"
                          "(2, 'Bob',   'b@x.com', 1, '2026-06-13'),"
                          "(3, 'Carol', 'c@x.com', 2, '2026-05-20'),"
                          "(4, 'Dave',  'd@x.com', 3, NULL)"))
    return eng


@pytest.fixture
def model():
    """SemanticModel matching the fixture DB. 'email' is marked sensitive."""
    return SemanticModel(entities=[
        Entity(
            name="User", table="users", primary_key="id",
            fields=[
                FieldDef(name="name", column="name", type="string"),
                FieldDef(name="email", column="email", type="string", sensitive=True),
                FieldDef(name="lastLogin", column="last_login_dt", type="datetime"),
            ],
            relationships=[
                Relationship(name="company", target="Company",
                             local_key="company_id", foreign_key="id"),
            ],
        ),
        Entity(
            name="Company", table="companies", primary_key="id",
            fields=[
                FieldDef(name="name", column="name", type="string"),
                FieldDef(name="state", column="state", type="string"),
            ],
        ),
    ])
