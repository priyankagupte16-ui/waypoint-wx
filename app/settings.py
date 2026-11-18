from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Waypoint Wx"
    author_name: str = "Priya"
    database_url: str = "sqlite:///./waypoint.db"
    youtube_api_key: str = ""
    google_maps_api_key: str = ""
    openai_api_key: str = ""
    max_range_days: int = 366
    forecast_horizon_days: int = 16


settings = Settings()
