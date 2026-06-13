# tests/test_models.py
import pytest
from pydantic import ValidationError as PydanticValidationError

from querydsl.models import (
    AggFunc,
    Aggregation,
    Catalog,
    ColumnInfo,
    DSLQuery,
    Entity,
    FieldDef,
    Filter,
    FilterOp,
    ForeignKey,
    Having,
    SemanticModel,
    TableInfo,
)


def test_dslquery_defaults():
    q = DSLQuery(entity="User")
    assert q.fields == []
    assert q.filters == []
    assert q.aggregations == []
    assert q.group_by == []
    assert q.having == []
    assert q.order_by == []
    assert q.limit == 100


def test_dslquery_rejects_unknown_field_key():
    with pytest.raises(PydanticValidationError):
        DSLQuery(entity="User", bogus_key=1)


def test_filter_op_enum():
    f = Filter(field="state", op="eq", value="TX")
    assert f.op is FilterOp.eq


def test_aggregation_and_having():
    a = Aggregation(func="count", field="*", alias="user_count")
    assert a.func is AggFunc.count
    h = Having(target="user_count", op="gt", value=5)
    assert h.target == "user_count"


def test_semantic_model_entity_lookup():
    m = SemanticModel(entities=[
        Entity(name="Company", table="companies", primary_key="id",
               fields=[FieldDef(name="name", column="name", type="string")]),
    ])
    assert m.entity("Company").table == "companies"
    assert m.entity("Missing") is None


def test_catalog_roundtrip():
    c = Catalog(tables=[
        TableInfo(name="users",
                  columns=[ColumnInfo(name="id", type="INTEGER", nullable=False)],
                  primary_key="id",
                  foreign_keys=[ForeignKey(column="company_id", ref_table="companies", ref_column="id")]),
    ])
    assert c.tables[0].foreign_keys[0].ref_table == "companies"
