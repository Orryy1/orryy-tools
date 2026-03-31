from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    PORT: int = 8000

    # Replicate
    REPLICATE_API_TOKEN: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # YouTube Data API
    YOUTUBE_API_KEY: str = ""

    # AcoustID
    ACOUSTID_API_KEY: str = ""

    # Buttondown newsletter
    BUTTONDOWN_API_KEY: str = ""

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_MONTHLY_PRICE_ID: str = "price_1TH6baLCOyO4XufRmH9KELqa"
    STRIPE_PRO_ANNUAL_PRICE_ID: str = "price_1TH6cKLCOyO4XufRbNaLq4zj"
    STRIPE_STEM_SINGLE_PRICE_ID: str = "price_1TH6boLCOyO4XufRhbEvnozn"
    STRIPE_TRACKID_SINGLE_PRICE_ID: str = "price_1TH6bpLCOyO4XufR5PTHfF1m"

    # Cloudflare R2
    R2_ENDPOINT: str = ""
    R2_ACCESS_KEY: str = ""
    R2_SECRET_KEY: str = ""
    R2_BUCKET_NAME: str = "orryy-tools"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,https://tools.orryy.com"

    # Modal
    MODAL_TOKEN_ID: str = ""
    MODAL_TOKEN_SECRET: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
