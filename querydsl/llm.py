# querydsl/llm.py
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel


@dataclass
class LLMConfig:
    provider: str           # "OpenAI" | "Anthropic" | "Google" | "Groq"
    model: str
    api_key: str
    temperature: float = 0.0


def make_llm(config: LLMConfig) -> BaseChatModel:
    """Return a LangChain chat model for the chosen provider.

    Imports are local so the app starts even if a provider package is missing.
    """
    if config.provider == "OpenAI":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=config.model, temperature=config.temperature, api_key=config.api_key)
    if config.provider == "Anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=config.model, temperature=config.temperature, api_key=config.api_key)
    if config.provider == "Google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=config.model, temperature=config.temperature, google_api_key=config.api_key)
    if config.provider == "Groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model_name=config.model, temperature=config.temperature, api_key=config.api_key)
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
