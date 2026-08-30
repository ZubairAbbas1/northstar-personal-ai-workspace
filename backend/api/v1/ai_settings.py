from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.model_factory import build_chat_model, resolve_model_name
from backend.auth.dependencies import get_current_active_user
from backend.config import settings
from backend.db.session import get_db
from backend.models.ai_credential import AICredential
from backend.models.user import User
from backend.services.crypto_service import decrypt_secret, encrypt_secret, mask_secret

router = APIRouter(prefix="/ai-settings", tags=["AI Settings & BYOK"])


class AISettingsResponse(BaseModel):
    use_platform_default: bool
    provider: str
    masked_api_key: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    model_mode: str = "balanced"  # fast, balanced, quality
    allow_fallback: bool = False
    is_active: bool = True


class UpdateAISettingsRequest(BaseModel):
    provider: str = Field(description="groq, openai, anthropic, gemini, ollama, custom")
    api_key: str | None = Field(default=None, description="Plaintext API key (encrypted before storage)")
    base_url: str | None = Field(default=None, description="Custom base URL for Ollama/Custom endpoints")
    default_model: str | None = None
    model_mode: str = Field(default="balanced", description="fast, balanced, or quality")
    allow_fallback: bool = False
    use_platform_default: bool = False


class TestConnectionRequest(BaseModel):
    provider: str
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    model_used: str


@router.get("", response_model=AISettingsResponse)
async def get_ai_settings(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retrieves the current user's AI configuration with masked API keys."""
    result = await db.execute(
        select(AICredential).where(AICredential.user_id == current_user.id, AICredential.is_active.is_(True))
    )
    cred = result.scalar_one_or_none()

    if not cred or not cred.is_active:
        return AISettingsResponse(
            use_platform_default=True,
            provider="groq",
            masked_api_key=None,
            base_url=None,
            default_model=settings.DEFAULT_BALANCED_MODEL,
            model_mode="balanced",
            allow_fallback=False,
            is_active=True,
        )

    decrypted_key = None
    if cred.encrypted_api_key:
        try:
            decrypted_key = decrypt_secret(cred.encrypted_api_key)
        except Exception:
            pass

    return AISettingsResponse(
        use_platform_default=False,
        provider=cred.provider,
        masked_api_key=mask_secret(decrypted_key),
        base_url=cred.base_url,
        default_model=cred.default_model or resolve_model_name(cred.provider, cred.model_mode, "complex"),
        model_mode=cred.model_mode,
        allow_fallback=cred.allow_fallback,
        is_active=cred.is_active,
    )


@router.post("", response_model=AISettingsResponse)
async def update_ai_settings(
    data: UpdateAISettingsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Updates user AI provider settings and encrypts API keys at rest."""
    result = await db.execute(select(AICredential).where(AICredential.user_id == current_user.id))
    cred = result.scalar_one_or_none()

    if data.use_platform_default:
        if cred:
            cred.is_active = False
            await db.commit()
        return AISettingsResponse(
            use_platform_default=True,
            provider="groq",
            masked_api_key=None,
            base_url=None,
            default_model=settings.DEFAULT_BALANCED_MODEL,
            model_mode="balanced",
            allow_fallback=False,
            is_active=True,
        )

    encrypted_key = None
    if data.api_key and data.api_key.strip() and not data.api_key.startswith("••••"):
        encrypted_key = encrypt_secret(data.api_key.strip())
    elif cred and cred.encrypted_api_key:
        # Keep existing key if not modified
        encrypted_key = cred.encrypted_api_key

    if not cred:
        cred = AICredential(
            user_id=current_user.id,
            provider=data.provider.lower(),
            encrypted_api_key=encrypted_key,
            base_url=data.base_url,
            default_model=data.default_model,
            model_mode=data.model_mode,
            allow_fallback=data.allow_fallback,
            is_active=True,
        )
        db.add(cred)
    else:
        cred.provider = data.provider.lower()
        cred.encrypted_api_key = encrypted_key
        cred.base_url = data.base_url
        cred.default_model = data.default_model
        cred.model_mode = data.model_mode
        cred.allow_fallback = data.allow_fallback
        cred.is_active = True

    await db.commit()
    await db.refresh(cred)

    decrypted = decrypt_secret(cred.encrypted_api_key) if cred.encrypted_api_key else None
    return AISettingsResponse(
        use_platform_default=False,
        provider=cred.provider,
        masked_api_key=mask_secret(decrypted),
        base_url=cred.base_url,
        default_model=cred.default_model or resolve_model_name(cred.provider, cred.model_mode, "complex"),
        model_mode=cred.model_mode,
        allow_fallback=cred.allow_fallback,
        is_active=cred.is_active,
    )


@router.post("/test", response_model=TestConnectionResponse)
async def test_ai_connection(
    data: TestConnectionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tests connection to a specified AI provider without saving."""
    target_key = data.api_key
    # If the user passed a masked key or empty key, try using their saved key
    if not target_key or target_key.startswith("••••"):
        result = await db.execute(
            select(AICredential).where(
                AICredential.user_id == current_user.id,
                AICredential.provider == data.provider.lower(),
            )
        )
        saved_cred = result.scalar_one_or_none()
        if saved_cred and saved_cred.encrypted_api_key:
            target_key = decrypt_secret(saved_cred.encrypted_api_key)

    model_name = data.model or resolve_model_name(data.provider, "fast", "simple")

    try:
        chat_model = build_chat_model(
            provider=data.provider,
            api_key=target_key,
            model_name=model_name,
            base_url=data.base_url,
            temperature=0.0,
        )
        # Test quick ping
        response = await chat_model.ainvoke("Ping! Respond with 'OK'.")
        content = response.content if hasattr(response, "content") else str(response)
        return TestConnectionResponse(
            success=True,
            message=f"Connection successful! Received response: {content[:40]}...",
            model_used=model_name,
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
            model_used=model_name,
        )
