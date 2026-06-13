# querydsl/models.py
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------- Catalog: deterministic ground truth from introspection ----------

class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool


class ForeignKey(BaseModel):
    column: str
    ref_table: str
    ref_column: str


class TableInfo(BaseModel):
    name: str
    columns: list[ColumnInfo]
    primary_key: str | None = None
    foreign_keys: list[ForeignKey] = Field(default_factory=list)


class Catalog(BaseModel):
    tables: list[TableInfo]


# ---------- Semantic model: LLM-proposed, user-confirmed ----------

class FieldDef(BaseModel):
    name: str            # friendly name used in the DSL
    column: str          # real column name
    type: str
    sensitive: bool = False
    description: str = ""


class Relationship(BaseModel):
    name: str            # name used in dotted DSL refs, e.g. "company"
    target: str          # target entity name
    local_key: str       # column on this entity's table
    foreign_key: str     # column on the target entity's table


class Entity(BaseModel):
    name: str
    table: str
    primary_key: str
    fields: list[FieldDef]
    relationships: list[Relationship] = Field(default_factory=list)

    def field(self, name: str) -> FieldDef | None:
        return next((f for f in self.fields if f.name == name), None)

    def relationship(self, name: str) -> Relationship | None:
        return next((r for r in self.relationships if r.name == name), None)


class SemanticModel(BaseModel):
    entities: list[Entity]

    def entity(self, name: str) -> Entity | None:
        return next((e for e in self.entities if e.name == name), None)


# ---------- DSL: the LLM's per-question output ----------

class FilterOp(StrEnum):
    eq = "eq"
    ne = "ne"
    lt = "lt"
    lte = "lte"
    gt = "gt"
    gte = "gte"
    in_ = "in"
    like = "like"
    is_null = "is_null"


class AggFunc(StrEnum):
    count = "count"
    sum = "sum"
    avg = "avg"
    min = "min"
    max = "max"


class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    op: FilterOp
    value: Any = None


class Aggregation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    func: AggFunc
    field: str            # a field name, or "*" (only valid with func=count)
    alias: str


class Having(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str           # must match an Aggregation.alias
    op: FilterOp
    value: Any = None


class OrderBy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str            # a field name or an aggregation alias
    dir: Literal["asc", "desc"] = "asc"


class DSLQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity: str
    fields: list[str] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    aggregations: list[Aggregation] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    having: list[Having] = Field(default_factory=list)
    order_by: list[OrderBy] = Field(default_factory=list)
    limit: int = 100
