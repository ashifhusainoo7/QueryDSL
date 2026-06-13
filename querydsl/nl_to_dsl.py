# querydsl/nl_to_dsl.py
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from .models import DSLQuery, SemanticModel
from .validate import ValidationError, validate

_SYSTEM = """You translate a user's natural-language question into a DSLQuery JSON object
that queries the database described by the semantic model below.

Rules:
- Only use entity names, field names, and relationship names that appear in the model.
- Reference fields on related entities with dotted names, e.g. "company.name".
- Use aggregations + group_by for counts/sums/averages "per" something. For counts use
  field "*". HAVING targets must match an aggregation alias.
- Always prefer a sensible limit (default 100).
"""


def _render_model(model: SemanticModel) -> str:
    lines: list[str] = []
    for entity in model.entities:
        field_names = ", ".join(f.name for f in entity.fields)
        lines.append(f"ENTITY {entity.name}: fields=[{field_names}]")
        for rel in entity.relationships:
            lines.append(f"  relationship '{rel.name}' -> {rel.target}")
    return "\n".join(lines)


class NlToDslError(Exception):
    """Raised when the LLM cannot produce a valid DSLQuery within the retry budget."""


def nl_to_dsl(
    question: str,
    model: SemanticModel,
    llm: BaseChatModel,
    max_retries: int = 1,
) -> DSLQuery:
    """English -> validated DSLQuery. Retries once with the validation error fed back."""
    structured = llm.with_structured_output(DSLQuery)
    base_prompt = f"{_SYSTEM}\n\nMODEL:\n{_render_model(model)}\n\nQUESTION: {question}"

    last_error: str | None = None
    for attempt in range(max_retries + 1):
        prompt = base_prompt
        if last_error is not None:
            prompt = f"{base_prompt}\n\nYour previous answer was invalid: {last_error}\nFix it."
        candidate = structured.invoke(prompt)
        try:
            validate(candidate, model)
            return candidate
        except ValidationError as exc:
            last_error = str(exc)

    raise NlToDslError(f"Could not produce a valid query: {last_error}")
