try:
    from pydantic import BaseSettings  # pydantic v1
except Exception:
    from pydantic_settings import BaseSettings  # pydantic v2 compatibility


class Settings(BaseSettings):
    RPC_HOST: str = "127.0.0.1"
    RPC_PORT: int = 8332
    RPC_USER: str | None = None
    RPC_PASSWORD: str | None = None
    RPC_COOKIE_PATH: str | None = None
    USE_SSL: bool = False
    POLL_INTERVAL: int = 2
    CORS_ORIGINS: str = "*"
    REDIS_URL: str | None = None
    WS_TOKEN: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
