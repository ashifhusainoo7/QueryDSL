# QueryDSL — Reliable Natural-Language Database Querying

**Date:** 2026-06-13
**Status:** Approved design, pending implementation plan
**Replaces:** [SQLToNLP](https://github.com/ashifhusainoo7/SQLToNLP) (LLM-writes-raw-SQL approach)

---

## Problem

The existing project (`SQLToNLP`) is a Streamlit app where a LangChain ReAct agent
(`create_react_agent` + `SQLDatabaseToolkit`) is given free rein to introspect the
database, write arbitrary SQL, and execute it against a live SQL Server. The **only**
guardrail is a system-prompt instruction ("never run DML", "limit to 100 rows", "exclude
sensitive columns").

A prompt is a suggestion, not a constraint. This produces the reliability failures the
project suffers from:

- **Confidently wrong answers** — valid SQL with the wrong join/filter, undetectable by users.
- **Broken SQL** — hallucinated table/column names.
- **Unsafe operations** — nothing in code prevents DML; the model is only *asked* not to.
- **Inconsistency** — the same question yields different SQL/results across runs.

## Goal

Replace the unsafe "LLM writes raw SQL" core with a **constrained Query DSL pipeline**:

> Natural language → LLM emits a structured DSL query (not raw SQL) → the DSL is validated
> against a schema we control → a deterministic compiler turns it into safe, correct SQL.

The reliability guarantee comes from **validating the DSL against an introspected catalog and
compiling it deterministically** — not from prompting. Whatever the LLM produces is checked
before any SQL exists.

## Non-Goals (this version)

- Subqueries, window functions, ranking ("top N per group"), running totals (deferred — Level 4).
- Time-series bucketing / trend analysis (deferred — Level 3).
- Write operations of any kind (out of scope permanently — this is a read-only analytics tool).
- Fully zero-touch modeling (rejected — a human review step is required for reliability).

## Scope of supported questions (Level 2)

- Lookups and filters: "users who haven't logged in today", "companies in Texas".
- Joins across related entities (via declared relationships).
- Aggregations: `COUNT` / `SUM` / `AVG`, `GROUP BY`, `HAVING`.
- Sorting and row limits.

---

## Architecture — two phases

### Phase A — Modeling (once per database connection)

```
Connect → Introspect catalog (INFORMATION_SCHEMA) → LLM proposes semantic model
        → Review screen (user confirms / edits) → Lock model
```

### Phase B — Querying (repeated)

```
English question + locked model → LLM emits DSL (JSON) → Validate DSL against model
        → Compile to SQL (SQLAlchemy Core) → Execute (read-only) → Show results + generated SQL
```

The safety/validity guarantee lives in the **validate** and **compile** steps. If the LLM emits
garbage, validation rejects it before any SQL is built.

---

## Data structures

### 1. Catalog (deterministic — ground truth from introspection)

Queried from `INFORMATION_SCHEMA`. No LLM involved; this cannot hallucinate.

```
Catalog:
  tables: [
    { name, columns: [{ name, type, nullable }],
      primary_key, foreign_keys: [{ column, ref_table, ref_column }] }
  ]
```

### 2. Semantic model (LLM-proposed, user-confirmed)

The set of entities/fields/relationships the DSL is allowed to reference. The LLM proposes
friendly names, descriptions, sensitivity flags, and likely relationships over the catalog;
the user confirms/edits on the review screen; then it is locked.

```
SemanticModel:
  entities: [
    { name: "User", table: "tbl_users", primary_key: "id",
      fields: [
        { name: "lastLogin", column: "last_login_dt", type: "datetime", sensitive: false },
        { name: "email",     column: "email",         type: "string",   sensitive: true }
      ],
      relationships: [
        { name: "company", target: "Company", local_key: "company_id", foreign_key: "id" }
      ] }
  ]
```

- `sensitive: true` fields are excluded from results by default, enforced in code.
- Relationships are seeded from catalog foreign keys, plus any the user adds for implicit
  (non-FK) joins the database does not declare.

### 3. The DSL (per-question, Pydantic model)

The LLM's only output in Phase B. Pydantic validation rejects malformed shapes automatically.

```json
{
  "entity": "User",
  "fields": ["name", "company.name"],
  "filters": [
    { "field": "lastLogin", "op": "lt", "value": "2026-06-13" },
    { "field": "company.state", "op": "eq", "value": "TX" }
  ],
  "aggregations": [ { "func": "count", "field": "id", "alias": "user_count" } ],
  "group_by": ["company.name"],
  "having": [ { "target": "user_count", "op": "gt", "value": 5 } ],
  "order_by": [ { "field": "user_count", "dir": "desc" } ],
  "limit": 100
}
```

Dotted field references (`company.name`) resolve through declared relationships.

Supported filter ops (initial): `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in`, `like`, `is_null`.
Supported aggregation funcs: `count`, `sum`, `avg`, `min`, `max`.

---

## The compiler — where safety is structural

`compiler.py` walks the validated `DSLQuery` and builds SQL with **SQLAlchemy Core expression
objects** — never string concatenation. Properties that follow for free:

- **No hallucinated columns** — every `field` must resolve to a real entity/column in the
  locked model, or compilation fails.
- **No DML / no injection** — the DSL grammar has only SELECT-shaped nodes; there is no way to
  express DELETE/DROP/UPDATE. Values become bound parameters.
- **Correct joins by construction** — `company.name` resolves via the model's declared
  relationship; SQLAlchemy emits the JOIN. The LLM never writes join logic.
- **Row limit always applied** — defaults to 100 if the LLM omits `limit`.
- **Sensitive fields filtered** — `sensitive: true` columns are dropped from the projection
  unless explicitly overridden.

---

## Module layout (in the `QueryDSL/` project)

```
querydsl/
  introspect.py    # DB connection -> Catalog (deterministic)
  semantic.py      # Catalog + LLM -> proposed SemanticModel
  models.py        # Pydantic: Catalog, SemanticModel, DSLQuery
  nl_to_dsl.py     # English + SemanticModel -> DSLQuery (the only LLM call in Phase B)
  validate.py      # DSLQuery checked against SemanticModel
  compiler.py      # DSLQuery -> SQLAlchemy SELECT -> SQL string + execution
  db.py            # connection layer (reused/adapted from SQLToNLP)
  llm.py           # multi-provider LLM setup (reused/adapted from SQLToNLP)
app.py             # Streamlit UI: connect -> review screen -> query interface
```

Reused from the old app: SQL Server connection layer, multi-provider LLM setup
(OpenAI/Groq/Google/Anthropic), Streamlit UI shell. Replaced entirely: the ReAct-agent core.

---

## Error handling

- **Bad DSL from LLM** → validation error caught → one automatic retry feeding the error back
  to the LLM → if still invalid, show "couldn't translate that question"; never run anything.
- **Empty / ambiguous question** → LLM returns a `needs_clarification` marker → UI asks the
  user to rephrase.
- **SQL execution error** → shown plainly alongside the generated SQL, so it is debuggable.
- **Read-only enforcement** → the DB session is opened read-only as a second backstop beyond
  the DSL's structural guarantee.

---

## Testing strategy

- **Compiler tests (core effort):** a table of `DSLQuery → expected SQL`, run against a local
  SQLite fixture so no server is needed.
- **Validation tests:** malformed DSL (unknown field, attempted DML, bad op) must be rejected.
- **Introspection test:** against a fixture DB, assert the produced catalog is correct.
- **LLM steps (semantic proposal, NL→DSL):** light smoke tests with mocked responses; assert
  output *shape*, not exact content (non-deterministic).

---

## Build sequence (high level — detailed plan to follow)

1. `models.py` — Pydantic definitions for Catalog, SemanticModel, DSLQuery.
2. `introspect.py` + tests — catalog from a fixture DB.
3. `compiler.py` + tests — DSLQuery → SQL against SQLite fixture (the reliability core).
4. `validate.py` + tests — reject malformed/unsafe DSL.
5. `semantic.py` — LLM proposes a model from a catalog.
6. `nl_to_dsl.py` — English → DSL with one validation-retry.
7. `app.py` — wire connect → review screen → query interface; reuse `db.py` / `llm.py`.
