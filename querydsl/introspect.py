# querydsl/introspect.py
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from .models import Catalog, ColumnInfo, ForeignKey, TableInfo


def introspect(engine: Engine) -> Catalog:
    """Build a deterministic Catalog from a live database connection.

    Pure introspection of INFORMATION_SCHEMA-equivalent metadata via SQLAlchemy's
    inspector. No LLM, no guessing — this is ground truth.
    """
    insp = inspect(engine)
    tables: list[TableInfo] = []

    for table_name in insp.get_table_names():
        columns = [
            ColumnInfo(name=col["name"], type=str(col["type"]), nullable=bool(col["nullable"]))
            for col in insp.get_columns(table_name)
        ]

        pk_cols = insp.get_pk_constraint(table_name).get("constrained_columns") or []
        primary_key = pk_cols[0] if pk_cols else None

        foreign_keys: list[ForeignKey] = []
        for fk in insp.get_foreign_keys(table_name):
            referred_table = fk["referred_table"]
            for local_col, remote_col in zip(
                fk["constrained_columns"], fk["referred_columns"], strict=True
            ):
                foreign_keys.append(
                    ForeignKey(column=local_col, ref_table=referred_table, ref_column=remote_col)
                )

        tables.append(
            TableInfo(name=table_name, columns=columns,
                      primary_key=primary_key, foreign_keys=foreign_keys)
        )

    return Catalog(tables=tables)
