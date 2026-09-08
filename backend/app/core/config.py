from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "SiteAegis"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    API_PREFIX: str = "/api"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()