"""LangChain emite spans y uso de tokens reales a LangSmith."""
import os


def configure(config):
    from dotenv import load_dotenv
    load_dotenv(override=False)
    os.environ['LANGSMITH_TRACING'] = str(config.langsmith_tracing).lower()
    os.environ['LANGSMITH_PROJECT'] = config.langsmith_project
    if config.langsmith_tracing:
        if not config.langsmith_api_key:
            raise ValueError('LANGSMITH_API_KEY requerida para tracing')
        os.environ['LANGSMITH_API_KEY'] = config.langsmith_api_key.get_secret_value()


def model(config):
    if config.agent_mode == 'offline':
        return None
    if config.llm_provider == 'anthropic':
        from langchain_anthropic import ChatAnthropic
        if not config.anthropic_api_key or not config.anthropic_model:
            raise ValueError('ANTHROPIC_API_KEY y ANTHROPIC_MODEL requeridos')
        return ChatAnthropic(model=config.anthropic_model,
                             api_key=config.anthropic_api_key.get_secret_value(),
                             max_tokens=2048, timeout=30, max_retries=1)
    from langchain_openai import ChatOpenAI
    if not config.openai_api_key or not config.openai_model:
        raise ValueError('OPENAI_API_KEY y OPENAI_MODEL requeridos')
    return ChatOpenAI(model=config.openai_model,
                      api_key=config.openai_api_key.get_secret_value(),
                      timeout=30, max_retries=1)
