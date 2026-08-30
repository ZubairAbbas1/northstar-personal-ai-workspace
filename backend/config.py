from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "AI Productivity Workspace"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Database & Cache
    # Default to async SQLite for zero-config local dev, easily switched to PostgreSQL
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./workspace.db",
        description="Async database connection string (PostgreSQL or SQLite)",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and queues",
    )

    # Security & Authentication
    JWT_SECRET: str = Field(
        default="dev-super-secret-jwt-key-replace-in-production-min-32-chars",
        description="Secret key for JWT token encoding/decoding",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Secret Encryption Vault (AES-256-GCM / Fernet Key for BYOK and OAuth tokens)
    # Generated via Fernet.generate_key() or 32-char secret
    ENCRYPTION_KEY: str = Field(
        default="e1lvdXIxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTA=",
        description="Base64 Fernet / 32-byte secret key for encrypting BYOK API keys and OAuth tokens at rest",
    )

    # Platform Default AI Settings
    USE_PLATFORM_AI: bool = True
    GROQ_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Default model parameters
    DEFAULT_FAST_MODEL: str = "openai/gpt-oss-20b"
    DEFAULT_BALANCED_MODEL: str = "openai/gpt-oss-120b"
    DEFAULT_QUALITY_MODEL: str = "openai/gpt-oss-120b"

    # Observability
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str | None = None
    LANGSMITH_PROJECT: str = "ai-productivity-workspace"

    # Third Party OAuth Client Defaults
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    SLACK_CLIENT_ID: str | None = None
    SLACK_CLIENT_SECRET: str | None = None

    def validate_production(self) -> None:
        """Fail fast when a production process is using known development secrets."""
        if self.ENVIRONMENT.lower() != "production":
            return

        insecure_values = {
            "JWT_SECRET": {
                "dev-super-secret-jwt-key-replace-in-production-min-32-chars",
                "dev-jwt-secret-replace-in-production",
                "generate-a-secure-random-secret-key-at-least-32-characters",
            },
            "ENCRYPTION_KEY": {
                "e1lvdXIxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTA=",
            },
        }
        invalid = [name for name, values in insecure_values.items() if getattr(self, name) in values]
        if len(self.JWT_SECRET) < 32:
            invalid.append("JWT_SECRET")
        if invalid:
            names = ", ".join(sorted(set(invalid)))
            raise RuntimeError(f"Unsafe production configuration: replace {names}.")


settings = Settings()
