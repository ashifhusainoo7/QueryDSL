# querydsl/compiler.py
from __future__ import annotations

from sqlalchemy import MetaData, Table, and_, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.selectable import Select

from .models import (
    AggFunc,
    Aggregation,
    DSLQuery,
    Entity,
    FilterOp,
    SemanticModel,
)
from .validate import validate

_AGG_FUNCS = {
    AggFunc.count: func.count,
    AggFunc.sum: func.sum,
    AggFunc.avg: func.avg,
    AggFunc.min: func.min,
    AggFunc.max: func.max,
}


class CompileError(Exception):
    """Raised when a (validated) query cannot be compiled against reflected tables."""


def _label_for(ref: str) -> str:
    """DSL ref -> result column label. 'name' -> 'name', 'company.name' -> 'company_name'."""
    return ref.replace(".", "_")


class Compiler:
    """Compiles a validated DSLQuery into a SQLAlchemy Core SELECT against reflected tables."""

    def __init__(self, model: SemanticModel, engine: Engine):
        self.model = model
        self.engine = engine
        self.md = MetaData()
        self.md.reflect(bind=engine)

    # ----- helpers -----

    def _table(self, entity: Entity) -> Table:
        if entity.table not in self.md.tables:
            raise CompileError(f"Table '{entity.table}' for entity '{entity.name}' not found in DB")
        return self.md.tables[entity.table]

    def _column(self, base: Entity, ref: str) -> ColumnElement:
        """Resolve a (validated) plain or dotted field ref to a reflected column."""
        if "." in ref:
            rel_name, field_name = ref.split(".", 1)
            rel = base.relationship(rel_name)
            target = self.model.entity(rel.target)
            fdef = target.field(field_name)
            return self._reflected_column(target, fdef.column)
        fdef = base.field(ref)
        return self._reflected_column(base, fdef.column)

    def _reflected_column(self, entity: Entity, column_name: str) -> ColumnElement:
        table = self._table(entity)
        if column_name not in table.c:
            raise CompileError(
                f"Column '{column_name}' (entity '{entity.name}') not found in table '{table.name}'"
            )
        return table.c[column_name]

    def _condition(self, col: ColumnElement, op: FilterOp, value) -> ColumnElement:
        if op is FilterOp.eq:
            return col == value
        if op is FilterOp.ne:
            return col != value
        if op is FilterOp.lt:
            return col < value
        if op is FilterOp.lte:
            return col <= value
        if op is FilterOp.gt:
            return col > value
        if op is FilterOp.gte:
            return col >= value
        if op is FilterOp.in_:
            return col.in_(value if isinstance(value, (list, tuple)) else [value])
        if op is FilterOp.like:
            return col.like(value)
        if op is FilterOp.is_null:
            return col.is_(None)
        raise CompileError(f"Unsupported operator '{op}'")

    def _agg_element(self, base: Entity, agg: Aggregation) -> ColumnElement:
        fn = _AGG_FUNCS[agg.func]
        if agg.field == "*":
            return fn().label(agg.alias)
        return fn(self._column(base, agg.field)).label(agg.alias)

    def _refs(self, query: DSLQuery) -> list[str]:
        """All field refs that might require a join, so we can build select_from up front."""
        refs: list[str] = []
        refs += query.fields
        refs += query.group_by
        refs += [f.field for f in query.filters]
        refs += [a.field for a in query.aggregations if a.field != "*"]
        refs += [o.field for o in query.order_by]
        return refs

    # ----- build -----

    def build(self, query: DSLQuery) -> Select:
        validate(query, self.model)  # structural + model guarantees, before any SQL exists
        base = self.model.entity(query.entity)
        base_table = self._table(base)

        # Projection.
        labeled_aggs: dict[str, ColumnElement] = {}
        columns: list[ColumnElement] = []
        if query.aggregations:
            for ref in query.group_by:
                columns.append(self._column(base, ref).label(_label_for(ref)))
            for agg in query.aggregations:
                element = self._agg_element(base, agg)
                labeled_aggs[agg.alias] = element
                columns.append(element)
        else:
            field_refs = query.fields or [f.name for f in base.fields if not f.sensitive]
            for ref in field_refs:
                columns.append(self._column(base, ref).label(_label_for(ref)))

        stmt = select(*columns)

        # Joins (deduplicated by relationship name), built from declared relationships.
        joined = base_table
        seen: set[str] = set()
        for ref in self._refs(query):
            if "." not in ref:
                continue
            rel_name = ref.split(".", 1)[0]
            if rel_name in seen:
                continue
            seen.add(rel_name)
            rel = base.relationship(rel_name)
            target = self.model.entity(rel.target)
            target_table = self._table(target)
            joined = joined.join(
                target_table,
                base_table.c[rel.local_key] == target_table.c[rel.foreign_key],
            )
        stmt = stmt.select_from(joined)

        # WHERE.
        conditions = [
            self._condition(self._column(base, flt.field), flt.op, flt.value)
            for flt in query.filters
        ]
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # GROUP BY.
        for ref in query.group_by:
            stmt = stmt.group_by(self._column(base, ref))

        # HAVING (target references an aggregation alias).
        for hav in query.having:
            element = labeled_aggs[hav.target]
            stmt = stmt.having(self._condition(element.element, hav.op, hav.value))

        # ORDER BY (alias of an aggregation, or a field).
        for ob in query.order_by:
            target = labeled_aggs.get(ob.field)
            if target is None:
                target = self._column(base, ob.field)
            stmt = stmt.order_by(target.desc() if ob.dir == "desc" else target.asc())

        # LIMIT — always applied.
        stmt = stmt.limit(query.limit)
        return stmt

    def to_sql(self, query: DSLQuery) -> str:
        stmt = self.build(query)
        return str(stmt.compile(self.engine, compile_kwargs={"literal_binds": True}))

    def run(self, query: DSLQuery) -> tuple[list[dict], str]:
        """Execute the query read-only. Returns (rows-as-dicts, generated-SQL)."""
        stmt = self.build(query)
        sql = str(stmt.compile(self.engine, compile_kwargs={"literal_binds": True}))
        with self.engine.connect() as conn:
            result = conn.execute(stmt)
            rows = [dict(m) for m in result.mappings().all()]
        return rows, sql
