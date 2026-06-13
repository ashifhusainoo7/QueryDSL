# tests/test_nl_to_dsl.py
from unittest.mock import MagicMock

import pytest

from querydsl.models import DSLQuery
from querydsl.nl_to_dsl import nl_to_dsl, NlToDslError


def test_returns_valid_dsl(model):
    good = DSLQuery(entity="User", fields=["name"])
    structured = MagicMock()
    structured.invoke.return_value = good
    llm = MagicMock()
    llm.with_structured_output.return_value = structured

    result = nl_to_dsl("list user names", model, llm)

    assert result == good
    llm.with_structured_output.assert_called_once_with(DSLQuery)


def test_retries_once_on_invalid_then_succeeds(model):
    bad = DSLQuery(entity="User", fields=["nope"])     # unknown field -> invalid
    good = DSLQuery(entity="User", fields=["name"])
    structured = MagicMock()
    structured.invoke.side_effect = [bad, good]
    llm = MagicMock()
    llm.with_structured_output.return_value = structured

    result = nl_to_dsl("list user names", model, llm)

    assert result == good
    assert structured.invoke.call_count == 2
    # The retry prompt must include the validation error feedback.
    retry_prompt = structured.invoke.call_args_list[1].args[0]
    assert "nope" in retry_prompt


def test_raises_after_retry_still_invalid(model):
    bad = DSLQuery(entity="User", fields=["nope"])
    structured = MagicMock()
    structured.invoke.side_effect = [bad, bad]
    llm = MagicMock()
    llm.with_structured_output.return_value = structured

    with pytest.raises(NlToDslError):
        nl_to_dsl("nonsense", model, llm)
    assert structured.invoke.call_count == 2
