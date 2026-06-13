# tests/test_introspect.py
from querydsl.introspect import introspect


def test_introspect_finds_tables_and_columns(engine):
    catalog = introspect(engine)
    names = {t.name for t in catalog.tables}
    assert names == {"companies", "users"}


def test_introspect_primary_keys(engine):
    catalog = introspect(engine)
    users = next(t for t in catalog.tables if t.name == "users")
    assert users.primary_key == "id"


def test_introspect_foreign_keys(engine):
    catalog = introspect(engine)
    users = next(t for t in catalog.tables if t.name == "users")
    assert len(users.foreign_keys) == 1
    fk = users.foreign_keys[0]
    assert (fk.column, fk.ref_table, fk.ref_column) == ("company_id", "companies", "id")


def test_introspect_column_nullable(engine):
    catalog = introspect(engine)
    users = next(t for t in catalog.tables if t.name == "users")
    name_col = next(c for c in users.columns if c.name == "name")
    assert name_col.nullable is False
