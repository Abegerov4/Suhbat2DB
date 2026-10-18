import pytest
from pydantic import SecretStr

from app.agent.factory import create_agent, has_llm_key, make_embedder
from app.agent.llm import LangChainLLM, supports_temperature
from app.agent.prompts import Prompt, PromptRegistry
from app.agent.retrieval.embeddings import HashEmbedder, OpenAIEmbedder
from app.core.config import Settings, get_settings


def settings(**update: object) -> Settings:
    return get_settings().model_copy(update=update)


def test_providers_and_models() -> None:
    llm = LangChainLLM(settings(openai_api_key=SecretStr("sk-test")))
    assert llm.providers == ["openai"]  # у Anthropic нет ключа — резервного нет
    assert llm.model_name("generate_sql") == "gpt-4.1"
    assert llm.model_name("guard") == "gpt-4.1-mini"
    chat = llm._chat("openai", "generate_sql")
    assert chat.temperature == 0.0  # type: ignore[attr-defined]

    both = LangChainLLM(
        settings(openai_api_key=SecretStr("sk-a"), anthropic_api_key=SecretStr("sk-b"))
    )
    assert both.providers == ["openai", "anthropic"]
    assert both._model_id("anthropic", "explain") == "claude-haiku-4-5"
    assert both._chat("anthropic", "explain") is not None


def test_overrides_and_reasoning_models() -> None:
    llm = LangChainLLM(
        settings(openai_api_key=SecretStr("sk-test")), overrides={"generate_sql": "gpt-5.4-mini"}
    )
    assert llm.model_name("generate_sql") == "gpt-5.4-mini"
    assert llm._chat("openai", "generate_sql").temperature is None  # type: ignore[attr-defined]
    assert not supports_temperature("o3") and supports_temperature("gpt-4.1")


def test_no_keys() -> None:
    with pytest.raises(RuntimeError):
        LangChainLLM(settings(openai_api_key=None, anthropic_api_key=None))
    assert not has_llm_key(settings(openai_api_key=None, anthropic_api_key=None))


def test_embedder_choice() -> None:
    assert isinstance(make_embedder(settings(openai_api_key=None)), HashEmbedder)
    embedder = make_embedder(settings(openai_api_key=SecretStr("sk-test")))
    assert isinstance(embedder, OpenAIEmbedder) and embedder.dimension == 3072


async def test_agent_stays_fake_without_keys() -> None:
    assert await create_agent(settings(agent_mode="fake")) is None
    assert await create_agent(settings(openai_api_key=None, anthropic_api_key=None)) is None


def test_prompts_local_and_langfuse(monkeypatch: pytest.MonkeyPatch) -> None:
    local = PromptRegistry(get_settings()).get("generate_sql")
    text = local.compile(today="2026-10-19", timezone="Asia/Almaty")
    assert "Сегодня: 2026-10-19" in text and "{{" not in text
    assert local.metadata() == {}

    class FakePrompt:
        prompt = "Версия из Langfuse {{today}}"

    class FakeClient:
        def get_prompt(self, name: str, **kwargs: object) -> FakePrompt:
            assert name == "suhbat2db-guard" and kwargs["label"] == "production"
            return FakePrompt()

    monkeypatch.setattr("langfuse.get_client", lambda: FakeClient())
    registry = PromptRegistry(
        settings(
            prompts_from_langfuse=True,
            langfuse_public_key="pk",
            langfuse_secret_key=SecretStr("sk"),
        )
    )
    prompt: Prompt = registry.get("guard")
    assert prompt.compile(today="x") == "Версия из Langfuse x"
    assert "langfuse_prompt" in prompt.metadata()
