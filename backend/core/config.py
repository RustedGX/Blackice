from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./blackice.db", env="DATABASE_URL"
    )

    # Portfolio defaults
    initial_balance: float = Field(default=100000.0, env="INITIAL_BALANCE")
    max_position_pct: float = Field(default=0.20, env="MAX_POSITION_PCT")
    max_drawdown_threshold: float = Field(default=0.15, env="MAX_DRAWDOWN_THRESHOLD")

    # Rate limiting
    claude_calls_per_minute: int = Field(default=10, env="CLAUDE_CALLS_PER_MINUTE")
    price_monitor_interval: int = Field(default=15, env="PRICE_MONITOR_INTERVAL")

    # Server
    backend_port: int = Field(default=8000, env="BACKEND_PORT")
    frontend_url: str = Field(default="http://localhost:3000", env="FRONTEND_URL")

    # Trading
    slippage_pct: float = Field(default=0.0001, env="SLIPPAGE_PCT")
    backtest_signal_every_n_bars: int = Field(default=5, env="BACKTEST_SIGNAL_EVERY_N_BARS")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
