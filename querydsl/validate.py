# querydsl/validate.py
from __future__ import annotations

from .models import AggFunc, DSLQuery, Entity, SemanticModel

MAX_LIMIT = 1000


class ValidationError(Exception):
    """Raised when a DSLQuery references something not in the model or is unsafe."""


def _resolve_field(base: Entity, ref: str, model: SemanticModel) -> None:
    """Raise ValidationError if `ref` (plain or dotted) is not resolvable in the model."""
    if "." in ref:
        rel_name, field_name = ref.split(".", 1)
        rel = base.relationship(rel_name)
        if rel is None:
            raise ValidationError(
                f"Unknown relationship '{rel_name}' on entity '{base.name}'"
            )
        target = model.entity(rel.target)
        if target is None:
            raise ValidationError(
                f"Relationship '{rel_name}' points to unknown entity '{rel.target}'"
            )
        if target.field(field_name) is None:
            raise ValidationError(
                f"Unknown field '{field_name}' on entity '{target.name}'"
            )
    else:
        if base.field(ref) is None:
            raise ValidationError(f"Unknown field '{ref}' on entity '{base.name}'")


def validate(query: DSLQuery, model: SemanticModel) -> None:
    """Validate a DSLQuery against the locked SemanticModel. Raises ValidationError."""
    base = model.entity(query.entity)
    if base is None:
        raise ValidationError(f"Unknown entity '{query.entity}'")

    # Limit range.
    if query.limit <= 0 or query.limit > MAX_LIMIT:
        raise ValidationError(f"limit must be between 1 and {MAX_LIMIT}, got {query.limit}")

    # Plain field references.
    for ref in query.fields:
        _resolve_field(base, ref, model)
    for ref in query.group_by:
        _resolve_field(base, ref, model)
    for flt in query.filters:
        _resolve_field(base, flt.field, model)

    # Aggregations: '*' only valid with count; otherwise the field must resolve.
    aliases: set[str] = set()
    for agg in query.aggregations:
        if agg.alias in aliases:
            raise ValidationError(f"Duplicate aggregation alias '{agg.alias}'")
        aliases.add(agg.alias)
        if agg.field == "*":
            if agg.func is not AggFunc.count:
                raise ValidationError(
                    f"Aggregation field '*' is only valid with count, not {agg.func.value}"
                )
        else:
            _resolve_field(base, agg.field, model)

    # HAVING targets must reference an aggregation alias.
    for hav in query.having:
        if hav.target not in aliases:
            raise ValidationError(
                f"having target '{hav.target}' does not match any aggregation alias"
            )

    # ORDER BY: either an aggregation alias or a resolvable field.
    for ob in query.order_by:
        if ob.field in aliases:
            continue
        _resolve_field(base, ob.field, model)
