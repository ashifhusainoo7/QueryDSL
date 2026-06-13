# tests/test_validate.py
import pytest

from querydsl.models import (
    Aggregation,
    DSLQuery,
    Filter,
    Having,
    OrderBy,
)
from querydsl.validate import ValidationError, validate


def test_valid_simple_query_passes(model):
    validate(DSLQuery(entity="User", fields=["name"]), model)  # no raise


def test_valid_dotted_field_passes(model):
    validate(DSLQuery(entity="User", fields=["name", "company.name"]), model)  # no raise


def test_unknown_entity_rejected(model):
    with pytest.raises(ValidationError, match="entity"):
        validate(DSLQuery(entity="Ghost"), model)


def test_unknown_field_rejected(model):
    with pytest.raises(ValidationError, match="field"):
        validate(DSLQuery(entity="User", fields=["nope"]), model)


def test_unknown_relationship_rejected(model):
    with pytest.raises(ValidationError, match="relationship"):
        validate(DSLQuery(entity="User", fields=["manager.name"]), model)


def test_unknown_field_on_related_entity_rejected(model):
    with pytest.raises(ValidationError, match="field"):
        validate(DSLQuery(entity="User", fields=["company.zipcode"]), model)


def test_filter_field_validated(model):
    with pytest.raises(ValidationError, match="field"):
        validate(DSLQuery(entity="User", filters=[Filter(field="nope", op="eq", value=1)]), model)


def test_having_must_reference_known_alias(model):
    q = DSLQuery(
        entity="User",
        aggregations=[Aggregation(func="count", field="*", alias="cnt")],
        group_by=["company.name"],
        having=[Having(target="other", op="gt", value=1)],
    )
    with pytest.raises(ValidationError, match="having"):
        validate(q, model)


def test_count_star_allowed(model):
    q = DSLQuery(
        entity="User",
        aggregations=[Aggregation(func="count", field="*", alias="cnt")],
        group_by=["company.name"],
    )
    validate(q, model)  # no raise


def test_sum_star_rejected(model):
    q = DSLQuery(
        entity="User",
        aggregations=[Aggregation(func="sum", field="*", alias="bad")],
    )
    with pytest.raises(ValidationError, match=r"\*"):
        validate(q, model)


def test_order_by_alias_allowed(model):
    q = DSLQuery(
        entity="User",
        aggregations=[Aggregation(func="count", field="*", alias="cnt")],
        group_by=["company.name"],
        order_by=[OrderBy(field="cnt", dir="desc")],
    )
    validate(q, model)  # no raise


def test_limit_out_of_range_rejected(model):
    with pytest.raises(ValidationError, match="limit"):
        validate(DSLQuery(entity="User", limit=0), model)
    with pytest.raises(ValidationError, match="limit"):
        validate(DSLQuery(entity="User", limit=5000), model)
