"""Central settings, read from environment / .env (never hardcode keys)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    gemini_api_key: str = ""
    groq_api_key: str = ""
    data_gov_in_api_key: str = ""
    sarvam_api_key: str = ""
    telegram_bot_token: str = ""
    database_url: str = ""

    # Model names drift; override from env without touching code.
    gemini_model: str = "gemini-3.5-flash-lite"       # writes answers (lite: faster + more free quota)
    gemini_fast_model: str = "gemini-3.5-flash-lite"  # routing + judging (cheaper quota)
    groq_model: str = "openai/gpt-oss-120b"           # fallback when Gemini is rate-limited/overloaded
    embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Upstream URLs are settings so we can point one at http://invalid to demo robustness.
    weather_url: str = "https://api.open-meteo.com/v1/forecast"
    geocode_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    soil_url: str = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    mandi_url: str = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    nasa_power_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"

    user_agent: str = "KisanSaathi/0.1 (Forge buildathon prototype)"
    cache_dir: Path = ROOT / ".cache"
    chroma_dir: Path = ROOT / "chroma_db"

    @property
    def db_url(self) -> str:
        # Supabase in prod; local SQLite file for dev so the app always runs.
        url = self.database_url or f"sqlite:///{ROOT / 'kisansaathi.sqlite3'}"
        # Supabase gives postgres:// or postgresql:// — SQLAlchemy needs the psycopg3 driver name.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                url = "postgresql+psycopg://" + url[len(prefix):]
        return url


@lru_cache
def settings() -> Settings:
    return Settings()
