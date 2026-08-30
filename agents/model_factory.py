import logging
import os
from typing import Any, Literal
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from backend.config import settings
from backend.services.crypto_service import decrypt_secret

logger = logging.getLogger(__name__)

ComplexityType = Literal["simple", "complex"]
ProviderType = Literal["groq", "openai", "anthropic", "gemini", "ollama", "custom"]

# Model Catalog Mappings
PROVIDER_DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "groq": {
        "fast": "openai/gpt-oss-20b",
        "quality": "openai/gpt-oss-120b",
    },
    "openai": {
        "fast": "gpt-4o-mini",
        "quality": "gpt-4o",
    },
    "anthropic": {
        "fast": "claude-3-haiku-20240307",
        "quality": "claude-3-5-sonnet-20241022",
    },
    "gemini": {
        "fast": "gemini-1.5-flash",
        "quality": "gemini-1.5-pro",
    },
    "ollama": {
        "fast": "llama3.2",
        "quality": "llama3.3",
    },
    "custom": {
        "fast": "default",
        "quality": "default",
    },
}


class AIProviderResolutionError(Exception):
    """Raised when an AI provider fails or credentials are invalid."""
    pass


def resolve_model_name(
    provider: str,
    model_mode: str,
    task_complexity: ComplexityType,
    custom_model: str | None = None,
) -> str:
    """Determines the appropriate model name based on provider, mode, and task complexity."""
    if custom_model:
        return custom_model

    catalog = PROVIDER_DEFAULT_MODELS.get(provider, PROVIDER_DEFAULT_MODELS["groq"])

    if model_mode == "fast":
        return catalog["fast"]
    elif model_mode == "quality":
        return catalog["quality"]
    else:  # "balanced"
        return catalog["fast"] if task_complexity == "simple" else catalog["quality"]


def build_chat_model(
    provider: str,
    api_key: str | None,
    model_name: str,
    base_url: str | None = None,
    temperature: float = 0.0,
) -> BaseChatModel:
    """Constructs a LangChain chat model instance for the specified provider."""
    provider_clean = provider.lower()

    if provider_clean == "groq":
        key = api_key or settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        if not key:
            raise AIProviderResolutionError(
                "Groq API key not found. Please configure your key in Settings -> AI Models."
            )
        return ChatGroq(
            api_key=key,
            model_name=model_name,
            temperature=temperature,
            max_retries=2,
        )

    elif provider_clean == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise AIProviderResolutionError("langchain-openai package is required for OpenAI models.")
        key = api_key or settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not key:
            raise AIProviderResolutionError(
                "OpenAI API key not found. Please configure your key in Settings -> AI Models."
            )
        return ChatOpenAI(
            api_key=key,
            model=model_name,
            temperature=temperature,
            max_retries=2,
        )

    elif provider_clean == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise AIProviderResolutionError("langchain-anthropic package is required for Anthropic models.")
        key = api_key or settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise AIProviderResolutionError(
                "Anthropic API key not found. Please configure your key in Settings -> AI Models."
            )
        return ChatAnthropic(
            api_key=key,
            model_name=model_name,
            temperature=temperature,
            max_retries=2,
        )

    elif provider_clean == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise AIProviderResolutionError("langchain-google-genai is required for Gemini models.")
        key = api_key or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not key:
            raise AIProviderResolutionError(
                "Google Gemini API key not found. Please configure your key in Settings -> AI Models."
            )
        return ChatGoogleGenerativeAI(
            google_api_key=key,
            model=model_name,
            temperature=temperature,
            max_retries=2,
        )

    elif provider_clean in ("ollama", "custom"):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise AIProviderResolutionError("langchain-openai package is required for Ollama/Custom endpoints.")

        target_base_url = base_url or (settings.OLLAMA_BASE_URL + "/v1" if provider_clean == "ollama" else None)
        if not target_base_url:
            raise AIProviderResolutionError("Base URL is required for Ollama/Custom endpoints.")

        return ChatOpenAI(
            api_key=api_key or "ollama-no-key-required",
            base_url=target_base_url,
            model=model_name,
            temperature=temperature,
            max_retries=2,
        )

    else:
        raise AIProviderResolutionError(f"Unsupported AI provider: {provider}")


async def get_model_for_user(
    user_id: str | None = None,
    task_complexity: ComplexityType = "complex",
    temperature: float = 0.0,
    db_session: Any = None,
) -> BaseChatModel:
    """
    Centralized Model Factory:
    Determines provider, retrieves encrypted BYOK key if configured, selects model
    based on quality mode & task complexity, and returns configured ChatModel.
    """
    provider = "groq"
    api_key: str | None = None
    base_url: str | None = None
    custom_model: str | None = None
    model_mode = "balanced"

    if user_id and db_session:
        try:
            from sqlalchemy import select
            from backend.models.ai_credential import AICredential
            import uuid

            uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
            result = await db_session.execute(
                select(AICredential).where(AICredential.user_id == uid, AICredential.is_active.is_(True))
            )
            credential = result.scalar_one_or_none()

            if credential:
                provider = credential.provider
                model_mode = credential.model_mode or "balanced"
                base_url = credential.base_url
                custom_model = credential.default_model

                if credential.encrypted_api_key:
                    try:
                        api_key = decrypt_secret(credential.encrypted_api_key)
                    except Exception as e:
                        logger.warning("Failed to decrypt user BYOK key for %s: %s", user_id, e)
        except Exception as e:
            logger.warning("Error fetching AI credentials for user %s: %s", user_id, e)

    model_name = resolve_model_name(
        provider=provider,
        model_mode=model_mode,
        task_complexity=task_complexity,
        custom_model=custom_model,
    )

    try:
        return build_chat_model(
            provider=provider,
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            temperature=temperature,
        )
    except AIProviderResolutionError:
        if settings.USE_PLATFORM_AI and provider != "groq":
            logger.info("Falling back to platform default Groq model for task %s", task_complexity)
            default_model = resolve_model_name(
                provider="groq",
                model_mode="balanced",
                task_complexity=task_complexity,
            )
            return build_chat_model(
                provider="groq",
                api_key=settings.GROQ_API_KEY,
                model_name=default_model,
                temperature=temperature,
            )
        raise
