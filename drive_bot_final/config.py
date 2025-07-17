# drive_bot_final/config.py
from __future__ import annotations

import json
from typing import List, Final, Optional, Any

from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    bot_token: str = Field(..., alias="BOT_TOKEN")
    allowed_user_ids: list[int] = Field(default_factory=list, alias="ALLOWED_USER_IDS")
    admin_user_id: Optional[int] = Field(default=None, alias="ADMIN_USER_ID")

    # Google Drive
    service_account_path: str = Field(..., alias="GOOGLE_SERVICE_ACCOUNT_PATH")
    root_folder_id: str = Field(..., alias="GOOGLE_DRIVE_ROOT_FOLDER")

    # Infrastructure
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    database_url: str = Field("sqlite:///bot.db", alias="DATABASE_URL")

    # Limits
    max_file_size_mb: int = Field(50, alias="MAX_FILE_SIZE_MB")
    daily_upload_limit: int = Field(100, alias="DAILY_UPLOAD_LIMIT")

    # AI / OCR
    ai_analysis_enabled: bool = Field(True, alias="AI_ANALYSIS_ENABLED")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # лишние переменные в .env не вызывают ошибку
        case_sensitive=False,
    )

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v):
        if not v or not isinstance(v, str) or ":" not in v:
            raise ValueError("BOT_TOKEN должен быть строкой и содержать двоеточие (формат Telegram)")
        return v

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, v: Any):
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    arr = json.loads(v)
                    return [int(x) for x in arr]
                except Exception:
                    raise ValueError("ALLOWED_USER_IDS: не удалось распарсить JSON-массив")
            # Строка с id через запятую
            return [int(x) for x in v.split(",") if x.strip().isdigit()]
        raise ValueError("ALLOWED_USER_IDS: некорректный формат (ожидается список, JSON или строка через запятую)")


# глобальный singleton-объект
try:
    settings = Settings()  # type: ignore  # Все параметры должны приходить из .env или переменных окружения
except ValidationError as e:  # выводим понятную ошибку при старте
    import sys, pprint
    pprint.pp(e.errors(), stream=sys.stderr)
    sys.exit("❌  Invalid .env configuration")