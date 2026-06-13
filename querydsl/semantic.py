# querydsl/semantic.py
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from .models import Catalog, SemanticModel

_SYSTEM = """You are a database modeling assistant. Given the raw catalog of a SQL database
(tables, columns, types, primary keys, foreign keys), propose a clean semantic model:

- One entity per meaningful table. Give each a clear, singular PascalCase name (e.g. "User").
- For each entity, expose useful fields with friendly camelCase names mapped to real columns.
  Set "sensitive": true on fields like passwords, tokens, secrets, emails, and personal identifiers.
- Create a relationship for every foreign key (name it after the referenced concept, e.g. "company"),
  with local_key (the FK column on this table) and foreign_key (the referenced column).
- primary_key must be the real primary key column name.

Only reference tables and columns that exist in the catalog below.
"""


def _render_catalog(catalog: Catalog) -> str:
    lines: list[str] = []
    for table in catalog.tables:
        lines.append(f"TABLE {table.name} (primary_key={table.primary_key}):")
        for col in table.columns:
            null = "NULL" if col.nullable else "NOT NULL"
            lines.append(f"  - {col.name} {col.type} {null}")
        for fk in table.foreign_keys:
            lines.append(f"  FK {fk.column} -> {fk.ref_table}.{fk.ref_column}")
    return "\n".join(lines)


def propose_semantic_model(catalog: Catalog, llm: BaseChatModel) -> SemanticModel:
    """Ask the LLM to propose a SemanticModel over the catalog. The result is structurally
    valid (forced via with_structured_output) but should still be reviewed by a human."""
    structured = llm.with_structured_output(SemanticModel)
    prompt = f"{_SYSTEM}\n\nCATALOG:\n{_render_catalog(catalog)}"
    return structured.invoke(prompt)
