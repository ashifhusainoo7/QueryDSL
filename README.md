# 🧭 QueryDSL — Reliable Natural-Language Database Querying

Ask your SQL database questions in plain English — **without** letting an LLM write raw SQL against your data.

QueryDSL replaces the unreliable "LLM writes SQL" pattern with a **constrained, validated Query DSL** that compiles deterministically to safe SQL. The LLM's job shrinks from "write any SQL against any table" to "fill in a small, validated shape" — so it physically **cannot** hallucinate a column, run a `DELETE`, or skip the row limit.

---

## Why

The common approach — give an LLM a SQL toolkit and a prompt that says *"please don't run DML, please limit rows, please don't touch sensitive columns"* — is unreliable because **a prompt is a suggestion, not a constraint.** It leads to:

- **Confidently wrong answers** — valid SQL with the wrong join/filter, undetectable by users.
- **Broken SQL** — hallucinated table/column names.
- **Unsafe operations** — nothing in code actually prevents destructive statements.
- **Inconsistency** — the same question yields different SQL on different runs.

QueryDSL moves the guarantee from the prompt into **code**: every query is validated against a schema you control, then compiled with SQLAlchemy Core expression objects (never string concatenation).

---

## How it works

```
                        ┌─────────────── Phase A: Modeling (once per connection) ───────────────┐
  Connect DB  ─▶  Introspect catalog  ─▶  LLM proposes semantic model  ─▶  Review & lock (you)
                  (deterministic, ground truth)                            (editable JSON screen)
                        └──────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────── Phase B: Querying (repeated) ─────────────────────┐
  English question  ─▶  LLM emits DSL  ─▶  Validate against locked model  ─▶  Compile to SQL  ─▶  Run (read-only)
                        (structured)       (rejects anything not in model)   (SQLAlchemy Core)     ▶ results + SQL
                        └──────────────────────────────────────────────────────────────────────┘
```

### The four safety properties (enforced by code, not prompting)

| Property | Enforced by |
|---|---|
| No hallucinated tables/columns | `validate._resolve_field` + `Compiler._reflected_column` |
| No DML / DDL / injection | DSL grammar has only `SELECT`-shaped nodes; SQL built from bound SQLAlchemy Core objects |
| Row limit always applied | clamped in `validate`, unconditional `.limit()` in the compiler |
| Sensitive fields excluded by default | default projection drops `sensitive=True` fields |

---

## Project structure

```
querydsl/
  models.py       # Catalog, SemanticModel, DSLQuery (Pydantic)
  introspect.py   # DB → deterministic catalog
  semantic.py     # catalog + LLM → proposed semantic model
  validate.py     # DSL checked against the locked model (the gate)
  compiler.py     # DSL → safe SQL via SQLAlchemy Core (the reliability core)
  nl_to_dsl.py    # English → validated DSL, with one retry
  db.py / llm.py  # connection + multi-provider LLM (OpenAI/Anthropic/Google/Groq)
app.py            # Streamlit UI: connect → review/lock model → query
tests/            # 43 tests; deterministic core fully covered, LLM steps mocked
docs/superpowers/ # design spec and implementation plan
```

---

## Quickstart

### 1. Install

```bash
git clone https://github.com/ashifhusainoo7/QueryDSL.git
cd QueryDSL
uv venv
uv pip install -e ".[dev]"
```

(Or `python -m venv .venv && pip install -e ".[dev]"` if you don't use [uv](https://github.com/astral-sh/uv).)

### 2. Run the tests

```bash
python -m pytest -v
```

### 3. Launch the app

```bash
streamlit run app.py
```

Then in the browser:

1. **Database** — for a quick try, check *"Use SQLite file"* and point it at a local SQLite file; or enter your SQL Server details. Click **Connect database**.
2. **LLM** — pick a provider (OpenAI / Anthropic / Google / Groq), enter the model name and API key, click **Initialize LLM**.
3. **Review the model** — click **Propose model from schema**, check/edit the proposed entities, relationships, and `sensitive` flags, then **✅ Lock model**.
4. **Ask** — type a question like *"how many users per company?"* and click **Run**. You get the results table plus the generated DSL and SQL.

---

## What it supports today (Level 2)

- Lookups and filters (`eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in`, `like`, `is_null`)
- Single-hop joins across declared relationships
- Aggregations (`COUNT` / `SUM` / `AVG` / `MIN` / `MAX`), `GROUP BY`, `HAVING`
- Sorting and an always-applied row limit

### Not yet (future work)

- Time-series bucketing / trend analysis
- Subqueries, window functions, ranking ("top N per group")
- Multi-hop / chained joins

---

## Production note

The DSL structurally cannot emit writes, but when pointing at a real database use a **read-only database login** as a defense-in-depth second layer.

---

## License

MIT
