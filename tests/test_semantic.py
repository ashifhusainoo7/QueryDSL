# tests/test_semantic.py
from unittest.mock import MagicMock

from querydsl.models import (
    Catalog, TableInfo, ColumnInfo, ForeignKey,
    SemanticModel, Entity, FieldDef,
)
from querydsl.semantic import propose_semantic_model


def _catalog():
    return Catalog(tables=[
        TableInfo(name="users",
                  columns=[ColumnInfo(name="id", type="INTEGER", nullable=False),
                           ColumnInfo(name="name", type="TEXT", nullable=False)],
                  primary_key="id",
                  foreign_keys=[ForeignKey(column="company_id", ref_table="companies", ref_column="id")]),
    ])


def test_propose_returns_model_from_llm():
    expected = SemanticModel(entities=[
        Entity(name="User", table="users", primary_key="id",
               fields=[FieldDef(name="name", column="name", type="string")]),
    ])
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = expected
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured

    result = propose_semantic_model(_catalog(), fake_llm)

    assert result == expected
    fake_llm.with_structured_output.assert_called_once_with(SemanticModel)
    # The catalog must be included in the prompt the LLM receives.
    prompt_arg = fake_structured.invoke.call_args.args[0]
    assert "users" in prompt_arg
    assert "company_id" in prompt_arg
