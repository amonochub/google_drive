"""
Enhanced configuration module with proper validation and error handling.
Replaces the original config.py with better practices.
"""

from functools import lru_cache
from typing import List, Optional, Union
import os
import structlog
from pydantic import Field, ValidationError, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = structlog.get_logger(__name__)

# Type aliases for better readability
IDList = Optional[List[int]]
ScopeList = Union[List[str], str]


class Settings(BaseSettings):
    """
    Enhanced application settings with comprehensive validation.
    
    All configuration is loaded from environment variables with proper fallbacks
    and validation to ensure the application starts correctly.
    """

    # =============== Telegram Bot Configuration =============== #
    bot_token: str = Field(
        ..., 
        alias='BOT_TOKEN',
        description='Telegram Bot API token from @BotFather'
    )

    # =============== Google Drive Configuration =============== #
    gdrive_root_folder: str = Field(
        ..., 
        alias='GOOGLE_DRIVE_ROOT_FOLDER',
        description='Root folder ID in Google Drive for uploads'
    )
    
    gdrive_client_id: str = Field(
        ..., 
        alias='GOOGLE_CLIENT_ID',
        description='Google OAuth2 Client ID'
    )
    
    gdrive_client_secret: str = Field(
        ..., 
        alias='GOOGLE_CLIENT_SECRET',
        description='Google OAuth2 Client Secret'
    )
    
    gdrive_refresh_token: str = Field(
        ..., 
        alias='GOOGLE_REFRESH_TOKEN',
        description='Google OAuth2 Refresh Token'
    )
    
    drive_scopes: ScopeList = Field(
        default=['https://www.googleapis.com/auth/drive'],
        alias='DRIVE_SCOPES',
        description='Google Drive API scopes (comma-separated string or list)',
    )

    # =============== File Processing Configuration =============== #
    max_file_size_mb: int = Field(
        default=50, 
        alias='MAX_FILE_SIZE_MB',
        ge=1,
        le=2000,
        description='Maximum file size for upload in MB'
    )
    
    heavy_pdf_mb: float = Field(
        default=20.0, 
        alias='HEAVY_PDF_MB',
        ge=1.0,
        le=500.0,
        description='Threshold for heavy PDF processing in MB'
    )

    # =============== Access Control =============== #
    allowed_user_ids: IDList = Field(
        default=None,
        alias='ALLOWED_USER_IDS',
        description='Comma-separated list of allowed Telegram user IDs',
    )

    # =============== Feature Flags =============== #
    ai_analysis_enabled: bool = Field(
        default=False, 
        alias='AI_ANALYSIS_ENABLED',
        description='Enable AI-powered document analysis'
    )

    # =============== Redis Configuration =============== #
    redis_dsn: str = Field(
        default='redis://localhost:6379/0',
        alias='REDIS_DSN',
        description='Redis connection string'
    )
    
    cache_ttl: int = Field(
        default=3600, 
        alias='CACHE_TTL',
        ge=60,
        le=86400,
        description='Cache TTL in seconds (1 minute to 24 hours)'
    )

    # =============== Logging Configuration =============== #
    log_level: str = Field(
        default='INFO',
        alias='LOG_LEVEL',
        description='Logging level'
    )
    
    structured_logging: bool = Field(
        default=True,
        alias='STRUCTURED_LOGGING',
        description='Enable structured JSON logging'
    )

    # =============== Performance Configuration =============== #
    max_workers: int = Field(
        default=4,
        alias='MAX_WORKERS',
        ge=1,
        le=20,
        description='Maximum number of worker threads for processing'
    )
    
    batch_size: int = Field(
        default=10,
        alias='BATCH_SIZE',
        ge=1,
        le=50,
        description='Maximum files per batch operation'
    )

    # =============== Security Configuration =============== #
    rate_limit_requests: int = Field(
        default=10,
        alias='RATE_LIMIT_REQUESTS',
        ge=1,
        le=100,
        description='Maximum requests per user per minute'
    )
    
    rate_limit_window: int = Field(
        default=60,
        alias='RATE_LIMIT_WINDOW',
        ge=10,
        le=3600,
        description='Rate limit window in seconds'
    )

    # =============== Pydantic Configuration =============== #
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False,
        validate_assignment=True,
    )

    # =============== Validators =============== #
    @validator('allowed_user_ids', pre=True)
    def parse_user_ids(cls, v):
        """Parse comma-separated user IDs into list of integers."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                return [int(uid.strip()) for uid in v.split(',') if uid.strip()]
            except ValueError as e:
                raise ValueError(f"Invalid user ID format: {e}")
        return v

    @validator('drive_scopes', pre=True)
    def parse_scopes(cls, v):
        """Parse comma-separated scopes into list of strings."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(',') if s.strip()]
        return v

    @validator('bot_token')
    def validate_bot_token(cls, v):
        """Validate Telegram bot token format."""
        if not v or len(v) < 40:
            raise ValueError("Invalid bot token format")
        if ':' not in v:
            raise ValueError("Bot token must contain ':'")
        return v

    @validator('redis_dsn')
    def validate_redis_dsn(cls, v):
        """Validate Redis connection string."""
        if not v.startswith(('redis://', 'rediss://')):
            raise ValueError("Redis DSN must start with redis:// or rediss://")
        return v

    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate logging level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    # =============== Properties =============== #
    @property
    def is_docker_environment(self) -> bool:
        """Check if running in Docker environment."""
        return os.getenv('DOCKER_ENV', '').lower() == 'true'

    @property
    def redis_url(self) -> str:
        """Get Redis URL with Docker host adjustment."""
        if self.is_docker_environment:
            return self.redis_dsn.replace('localhost', 'redis').replace('127.0.0.1', 'redis')
        return self.redis_dsn

    @property
    def max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def heavy_pdf_bytes(self) -> int:
        """Get heavy PDF threshold in bytes."""
        return int(self.heavy_pdf_mb * 1024 * 1024)

    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        if self.allowed_user_ids is None:
            return True  # Allow all users if no restriction set
        return user_id in self.allowed_user_ids

    def to_dict(self) -> dict:
        """Convert settings to dictionary (hiding sensitive data)."""
        data = self.model_dump()
        # Hide sensitive fields
        sensitive_fields = ['bot_token', 'gdrive_client_secret', 'gdrive_refresh_token']
        for field in sensitive_fields:
            if field in data and data[field]:
                data[field] = '***HIDDEN***'
        return data


# =============== Settings Instance and Getter =============== #
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get application settings singleton.
    
    Returns:
        Settings: Validated application settings
        
    Raises:
        SystemExit: If settings validation fails
    """
    global _settings_instance
    
    if _settings_instance is None:
        try:
            _settings_instance = Settings()
            log.info(
                "settings_loaded_successfully",
                log_level=_settings_instance.log_level,
                max_file_size_mb=_settings_instance.max_file_size_mb,
                ai_analysis_enabled=_settings_instance.ai_analysis_enabled,
                docker_env=_settings_instance.is_docker_environment
            )
        except ValidationError as err:
            log.error(
                "settings_validation_failed",
                errors=[{"field": e["loc"], "message": e["msg"]} for e in err.errors()]
            )
            print("❌ Configuration validation failed:")
            for error in err.errors():
                field_path = " -> ".join(str(loc) for loc in error["loc"])
                print(f"  • {field_path}: {error['msg']}")
            print("\n💡 Please check your .env file and environment variables.")
            raise SystemExit(1) from err
        except Exception as e:
            log.error("settings_loading_failed", error=str(e))
            print(f"❌ Failed to load configuration: {e}")
            raise SystemExit(1) from e
    
    return _settings_instance


def reload_settings() -> Settings:
    """
    Reload settings (useful for testing).
    
    Returns:
        Settings: New settings instance
    """
    global _settings_instance
    _settings_instance = None
    return get_settings()


# =============== Backward Compatibility =============== #
# For backward compatibility with existing code
settings = get_settings()


# =============== Configuration Validation =============== #
def validate_configuration() -> bool:
    """
    Validate that all required configuration is present and correct.
    
    Returns:
        bool: True if configuration is valid
        
    Raises:
        SystemExit: If critical configuration is missing
    """
    try:
        settings = get_settings()
        
        # Check critical dependencies
        critical_checks = [
            (settings.bot_token, "Telegram bot token"),
            (settings.gdrive_client_id, "Google Client ID"),
            (settings.gdrive_client_secret, "Google Client Secret"),
            (settings.gdrive_refresh_token, "Google Refresh Token"),
            (settings.gdrive_root_folder, "Google Drive root folder ID"),
        ]
        
        missing_config = []
        for value, name in critical_checks:
            if not value or value.strip() == "":
                missing_config.append(name)
        
        if missing_config:
            print("❌ Missing critical configuration:")
            for config in missing_config:
                print(f"  • {config}")
            print("\n💡 Please set all required environment variables.")
            return False
        
        log.info("configuration_validation_passed")
        return True
        
    except Exception as e:
        log.error("configuration_validation_failed", error=str(e))
        return False


if __name__ == "__main__":
    # CLI for configuration validation
    import sys
    
    print("🔧 Validating configuration...")
    
    if validate_configuration():
        settings = get_settings()
        print("✅ Configuration is valid!")
        print(f"📊 Settings summary:")
        print(f"  • Log level: {settings.log_level}")
        print(f"  • Max file size: {settings.max_file_size_mb} MB")
        print(f"  • AI analysis: {'enabled' if settings.ai_analysis_enabled else 'disabled'}")
        print(f"  • Cache TTL: {settings.cache_ttl} seconds")
        print(f"  • Docker environment: {'yes' if settings.is_docker_environment else 'no'}")
        
        if settings.allowed_user_ids:
            print(f"  • Allowed users: {len(settings.allowed_user_ids)} users")
        else:
            print("  • Access: open to all users")
            
        sys.exit(0)
    else:
        print("❌ Configuration validation failed!")
        sys.exit(1)