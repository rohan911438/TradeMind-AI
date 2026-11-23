"""Central configuration. Every value can be overridden with an environment variable (12-factor style)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Minimal .env loader (backend/.env), real environment variables take priority
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes")


# Blue-chip universe: the Nifty 50 constituents (Yahoo Finance tickers without the ".NS" suffix).
NIFTY50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "BHARTIARTL", "SBIN", "HINDUNILVR", "ITC", "LT",
    "BAJFINANCE", "HCLTECH", "KOTAKBANK", "AXISBANK", "SUNPHARMA", "MARUTI", "M&M", "ULTRACEMCO", "NTPC", "TITAN",
    "ONGC", "ADANIPORTS", "POWERGRID", "WIPRO", "BAJAJFINSV", "NESTLEIND", "COALINDIA", "ASIANPAINT", "JSWSTEEL",
    "TATASTEEL", "BAJAJ-AUTO", "ADANIENT", "GRASIM", "HINDALCO", "TECHM", "SBILIFE", "EICHERMOT", "HDFCLIFE",
    "SHRIRAMFIN", "TRENT", "BEL", "APOLLOHOSP", "CIPLA", "DRREDDY", "TATACONSUM", "JIOFIN", "ETERNAL",
    "HEROMOTOCO", "INDIGO", "MAXHEALTH", "TMPV",
]
# The model was trained and evaluated (thesis Chapter 8) on these four stocks; kept fixed for reproducibility.
MODEL_SYMBOLS_DEFAULT = "RELIANCE,TCS,INFY,HDFCBANK"


def _list(name: str, default: str) -> list[str]:
    return [s.strip().upper() for s in os.getenv(name, default).split(",") if s.strip()]


class Settings:
    def __init__(self) -> None:
        self.SYMBOLS = _list("SYMBOLS", ",".join(NIFTY50))          # tradable universe (live feed)
        self.MODEL_SYMBOLS = _list("MODEL_SYMBOLS", MODEL_SYMBOLS_DEFAULT)  # training / benchmark universe

        # StreamX
        self.EVENTS_PER_SEC = int(os.getenv("EVENTS_PER_SEC", "200"))
        # Accelerated simulation: one live candle (= one simulated 5-minute bar) every BAR_SECONDS of real time
        self.BAR_SECONDS = float(os.getenv("BAR_SECONDS", "10"))
        self.RECORD_EVENTS = _bool("RECORD_EVENTS", "true")
        self.RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

        # PredictX
        self.HORIZON = int(os.getenv("HORIZON", "6"))  # bars ahead (6 x 5 min = 30 min)
        self.LABEL_THRESHOLD = float(os.getenv("LABEL_THRESHOLD", "0.0025"))  # +/-0.25 %

        # Paper trading / RiskGuard
        self.STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "1000000"))
        self.RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))
        self.MAX_SYMBOL_EXPOSURE = float(os.getenv("MAX_SYMBOL_EXPOSURE", "0.20"))
        self.MAX_TOTAL_EXPOSURE = float(os.getenv("MAX_TOTAL_EXPOSURE", "0.60"))
        self.MIN_RR = float(os.getenv("MIN_RR", "1.2"))
        self.DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", "0.03"))
        self.STOP_ATR_MULT = float(os.getenv("STOP_ATR_MULT", "1.5"))

        # Paths
        self.DATA_DIR = BASE_DIR / "data"
        self.RAW_DIR = self.DATA_DIR / "raw"
        self.EVENTS_DIR = self.DATA_DIR / "events"
        self.MODEL_DIR = BASE_DIR / "models"
        self.STATIC_DIR = BASE_DIR / "static"
        for d in (self.RAW_DIR, self.EVENTS_DIR, self.MODEL_DIR):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()

DISCLAIMER = "Educational prototype. Confidence is not a probability of profit. Not financial advice."
