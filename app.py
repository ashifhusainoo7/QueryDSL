# app.py
import json

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

from querydsl.compiler import Compiler
from querydsl.db import DatabaseConfig, make_engine
from querydsl.introspect import introspect
from querydsl.llm import LLMConfig, make_llm
from querydsl.models import SemanticModel
from querydsl.nl_to_dsl import NlToDslError, nl_to_dsl
from querydsl.semantic import propose_semantic_model

st.set_page_config(page_title="QueryDSL", page_icon="🧭", layout="wide")
st.title("🧭 QueryDSL — Reliable NL Database Querying")

# ----- session state -----
for key, default in {
    "engine": None, "llm": None, "catalog": None,
    "proposed_model": None, "locked_model": None, "history": [],
}.items():
    st.session_state.setdefault(key, default)

# ----- sidebar: connect DB + LLM -----
with st.sidebar:
    st.header("1) Connect")

    with st.expander("Database", expanded=True):
        use_sqlite = st.checkbox("Use SQLite file (for testing)")
        if use_sqlite:
            sqlite_path = st.text_input("SQLite path", value="demo.db")
        else:
            server = st.text_input("Server")
            database = st.text_input("Database")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            driver = st.selectbox("Driver",
                ["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server", "FreeTDS"])
        if st.button("Connect database"):
            try:
                if use_sqlite:
                    st.session_state.engine = create_engine(f"sqlite:///{sqlite_path}")
                else:
                    st.session_state.engine = make_engine(DatabaseConfig(
                        server=server, database=database, username=username,
                        password=password, driver=driver))
                st.session_state.catalog = introspect(st.session_state.engine)
                st.success(f"Connected. Found {len(st.session_state.catalog.tables)} tables.")
            except Exception as exc:
                st.error(f"Connection failed: {exc}")

    with st.expander("LLM", expanded=True):
        provider = st.selectbox("Provider", ["OpenAI", "Anthropic", "Google", "Groq"])
        model_name = st.text_input("Model", value="gpt-4o")
        api_key = st.text_input("API key", type="password")
        if st.button("Initialize LLM"):
            try:
                st.session_state.llm = make_llm(LLMConfig(
                    provider=provider, model=model_name, api_key=api_key))
                st.success("LLM ready.")
            except Exception as exc:
                st.error(f"LLM init failed: {exc}")

# ----- Phase A: propose + review semantic model -----
st.header("2) Review the semantic model")

if st.session_state.catalog and st.session_state.llm and st.session_state.proposed_model is None:
    if st.button("Propose model from schema"):
        with st.spinner("Analyzing schema..."):
            try:
                st.session_state.proposed_model = propose_semantic_model(
                    st.session_state.catalog, st.session_state.llm)
            except Exception as exc:
                st.error(f"Proposal failed: {exc}")

if st.session_state.proposed_model is not None and st.session_state.locked_model is None:
    st.caption("Edit the proposed model if needed, then lock it. The DSL can only reference what's here.")
    edited = st.text_area(
        "Semantic model (JSON)",
        value=st.session_state.proposed_model.model_dump_json(indent=2),
        height=400,
    )
    if st.button("✅ Lock model"):
        try:
            st.session_state.locked_model = SemanticModel.model_validate_json(edited)
            st.success("Model locked. You can now ask questions.")
        except Exception as exc:
            st.error(f"Invalid model JSON: {exc}")

if st.session_state.locked_model is not None:
    st.success("Model is locked.")
    with st.expander("View locked model"):
        st.json(json.loads(st.session_state.locked_model.model_dump_json()))
    if st.button("Re-edit model"):
        st.session_state.locked_model = None

# ----- Phase B: ask questions -----
st.header("3) Ask a question")

if st.session_state.locked_model and st.session_state.llm and st.session_state.engine:
    question = st.text_area("Your question",
                            placeholder="e.g. how many users per company in Texas?")
    if st.button("Run", type="primary") and question:
        try:
            with st.spinner("Translating to DSL..."):
                dsl = nl_to_dsl(question, st.session_state.locked_model, st.session_state.llm)
            compiler = Compiler(st.session_state.locked_model, st.session_state.engine)
            rows, sql = compiler.run(dsl)
            st.session_state.history.insert(0, {"question": question, "sql": sql})

            st.subheader("Results")
            st.dataframe(pd.DataFrame(rows))
            with st.expander("Generated DSL"):
                st.json(json.loads(dsl.model_dump_json()))
            with st.expander("Generated SQL"):
                st.code(sql, language="sql")
        except NlToDslError as exc:
            st.warning(f"Couldn't translate that question. Try rephrasing. ({exc})")
        except Exception as exc:
            st.error(f"Query failed: {exc}")
else:
    st.info("Connect a database, initialize the LLM, and lock a semantic model first.")

if st.session_state.history:
    st.header("History")
    for item in st.session_state.history[:10]:
        with st.expander(item["question"]):
            st.code(item["sql"], language="sql")
