
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError

# --------------------------------------------------------------------------- #
#  ‣  Полезные тайп-алиасы
IDList = list[int] | None
ScopeList = list[str] | str  # допускаем CSV-строку из .env
# --------------------------------------------------------------------------- #

class Settings(BaseSettings):
    """Все настройки проекта берутся из .env.

    ⚠️ Названия атрибутов – в *snake_case*, а через `alias` мы
    «маппим» их на VARIABLE_NAMES ИЗ .env.
    """

    # -------------------  Telegram  ------------------- #
    bot_token: str = Field(..., alias='BOT_TOKEN')

    # -------------------  Google Drive  ------------------- #
    gdrive_root_folder: str = Field(..., alias='GOOGLE_DRIVE_ROOT_FOLDER')
    gdrive_client_id: str = Field(..., alias='GOOGLE_CLIENT_ID')
    gdrive_client_secret: str = Field(..., alias='GOOGLE_CLIENT_SECRET')
    gdrive_refresh_token: str = Field(..., alias='GOOGLE_REFRESH_TOKEN')
    drive_scopes: ScopeList = Field(
        'https://www.googleapis.com/auth/drive',
        alias='DRIVE_SCOPES',
        description='Скоуп(ы) для Google Drive API',
    )

    # -------------------  Прочее  ------------------- #
    max_file_size_mb: int = Field(50, alias='MAX_FILE_SIZE_MB')
    allowed_user_ids: IDList = Field(
        default=None,
        alias='ALLOWED_USER_IDS',
        description='Разрешённые Telegram user_id, CSV',
    )
    ai_analysis_enabled: bool = Field(False, alias='AI_ANALYSIS_ENABLED')
    REDIS_DSN: str = Field(..., alias='REDIS_DSN')
    HEAVY_PDF_MB: float = Field(..., alias='HEAVY_PDF_MB')
    GOOGLE_CREDENTIALS_FILE: str = Field(..., alias="GOOGLE_CREDENTIALS_FILE")

    # -------------------  Pydantic v2 meta  ------------------- #
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',          # игнорируем ЛИШНИЕ переменные .env, но не падаем
    )

    # -------------------  Post-init «косметика» -------------- #
    def __post_init__(self):
        # allowed_user_ids → List[int]  (если передан CSV-строкой)
        if isinstance(self.allowed_user_ids, str):
            self.allowed_user_ids = [
                int(uid.strip()) for uid in self.allowed_user_ids.split(',') if uid.strip()
            ]
        # drive_scopes → List[str]
        if isinstance(self.drive_scopes, str):
            self.drive_scopes = [s.strip() for s in self.drive_scopes.split(',') if s.strip()]

# -------------------  Singleton - чтобы импортировать везде ---------------- #
try:
    settings = Settings()   # noqa:  S105  (pydantic валидирует сам)
except ValidationError as err:
    print('❌  Ошибка валидации настроек\n', err.json(indent=2))
    raise SystemExit(1)

@lru_cache
def get_settings() -> Settings:
    return Settings()
