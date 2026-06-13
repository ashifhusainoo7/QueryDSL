# tests/test_compiler.py
import pytest

from querydsl.compiler import Compiler
from querydsl.models import (
    DSLQuery, Filter, Aggregation, Having, OrderBy,
)
from querydsl.validate import ValidationError


def rows_for(engine, model, query):
    return Compiler(model, engine).run(query)[0]


def test_select_fields(engine, model):
    rows = rows_for(engine, model, DSLQuery(entity="User", fields=["name"], order_by=[OrderBy(field="name")]))
    assert [r["name"] for r in rows] == ["Alice", "Bob", "Carol", "Dave"]


def test_default_projection_excludes_sensitive(engine, model):
    # No fields specified -> all non-sensitive fields; 'email' must NOT appear.
    rows = rows_for(engine, model, DSLQuery(entity="User", limit=1))
    assert "email" not in rows[0]
    assert "name" in rows[0]


def test_explicit_sensitive_field_allowed(engine, model):
    rows = rows_for(engine, model, DSLQuery(entity="User", fields=["email"], limit=1))
    assert "email" in rows[0]


def test_filter_eq(engine, model):
    q = DSLQuery(entity="User", fields=["name"],
                 filters=[Filter(field="company.state", op="eq", value="TX")],
                 order_by=[OrderBy(field="name")])
    assert [r["name"] for r in rows_for(engine, model, q)] == ["Alice", "Bob", "Dave"]


def test_filter_is_null(engine, model):
    q = DSLQuery(entity="User", fields=["name"],
                 filters=[Filter(field="lastLogin", op="is_null")])
    assert [r["name"] for r in rows_for(engine, model, q)] == ["Dave"]


def test_filter_lt(engine, model):
    q = DSLQuery(entity="User", fields=["name"],
                 filters=[Filter(field="lastLogin", op="lt", value="2026-06-01")],
                 order_by=[OrderBy(field="name")])
    assert [r["name"] for r in rows_for(engine, model, q)] == ["Carol"]


def test_join_via_relationship(engine, model):
    q = DSLQuery(entity="User", fields=["name", "company.name"],
                 filters=[Filter(field="company.name", op="eq", value="Acme")],
                 order_by=[OrderBy(field="name")])
    rows = rows_for(engine, model, q)
    assert rows[0]["name"] == "Alice"
    assert rows[0]["company_name"] == "Acme"


def test_aggregation_group_by(engine, model):
    q = DSLQuery(
        entity="User",
        aggregations=[Aggregation(func="count", field="*", alias="user_count")],
        group_by=["company.name"],
        order_by=[OrderBy(field="company.name")],
    )
    rows = rows_for(engine, model, q)
    counts = {r["company_name"]: r["user_count"] for r in rows}
    assert counts == {"Acme": 2, "Globex": 1, "Initech": 1}


def test_having(engine, model):
    q = DSLQuery(
        entity="User",
        aggregations=[Aggregation(func="count", field="*", alias="user_count")],
        group_by=["company.name"],
        having=[Having(target="user_count", op="gt", value=1)],
    )
    rows = rows_for(engine, model, q)
    assert [r["company_name"] for r in rows] == ["Acme"]


def test_order_by_alias_desc(engine, model):
    q = DSLQuery(
        entity="User",
        aggregations=[Aggregation(func="count", field="*", alias="user_count")],
        group_by=["company.name"],
        order_by=[OrderBy(field="user_count", dir="desc")],
    )
    rows = rows_for(engine, model, q)
    assert rows[0]["company_name"] == "Acme"  # highest count first


def test_limit_always_applied(engine, model):
    sql = Compiler(model, engine).to_sql(DSLQuery(entity="User"))
    assert "LIMIT" in sql.upper()


def test_invalid_query_raises_before_sql(engine, model):
    with pytest.raises(ValidationError):
        Compiler(model, engine).run(DSLQuery(entity="User", fields=["nope"]))
