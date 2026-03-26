from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "change-me-in-production-use-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 jours

    database_url: str = "sqlite+aiosqlite:///./musicapp.db"

    class Config:
        env_file = ".env"


settings = Settings()
