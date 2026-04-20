from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # Alpaca
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"

    # Polygon
    polygon_api_key: str

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o"

    # Database
    database_url: str

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Trading config
    watchlist: str = "AAPL,MSFT,NVDA,TSLA,AMZN"
    max_position_size_pct: float = 0.10
    max_daily_loss_pct: float = 0.02
    min_confidence_threshold: float = 0.70
    max_agent_iterations: int = 7
    exit_monitor_interval_seconds: int = 30

    # Notifications (all optional — system works without them)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_email: str = ""

    @property
    def watchlist_symbols(self) -> List[str]:
        return [s.strip() for s in self.watchlist.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
