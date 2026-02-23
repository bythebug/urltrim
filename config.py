from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "urltrim"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://urltrim:urltrim@localhost:5432/urltrim"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    # short codes: 6 chars = 56B+ combos with [a-zA-Z0-9]
    short_code_length: int = 6
    # redirect cache TTL (seconds)
    cache_ttl: int = 3600
    # rate limit: N requests per window
    rate_limit_per_minute: int = 60
    # alias: only allow alphanumeric + hyphen
    alias_max_length: int = 64

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
