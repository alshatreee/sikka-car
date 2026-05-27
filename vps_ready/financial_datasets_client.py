"""
Shared Python client for the Financial Datasets MCP API.
Base URL: https://mcp.financialdatasets.ai/v1
Auth: Bearer token from env var FD_API_TOKEN
Rate limit: 100 req/min (configurable via FD_RATE_LIMIT_RPM)
"""

import os
import sys
import time
import platform
from datetime import datetime
from collections import deque
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Environment & config
# ---------------------------------------------------------------------------

def _load_env():
    """Load env from .env_finance then .env3 (first hit wins for each var)."""
    if platform.system() == "Windows":
        base = Path(r"C:\Users\xman9\Desktop")
    else:
        base = Path("/root/bots")
    for name in (".env_finance", ".env3"):
        p = base / name
        if p.exists():
            load_dotenv(p, override=False)

_load_env()

BASE_URL = os.getenv("FD_BASE_URL", "https://mcp.financialdatasets.ai/v1").rstrip("/")
API_TOKEN = os.getenv("FD_API_TOKEN", "")
RATE_LIMIT = int(os.getenv("FD_RATE_LIMIT_RPM", "100"))
PROXY = os.getenv("HTTPS_PROXY", "")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [FD-Client] {msg}", flush=True)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

_request_times: deque = deque()

def _rate_limit_wait() -> None:
    """Sleep if we have made >= (RATE_LIMIT - 5) requests in the last 60 s."""
    now = time.time()
    # Purge timestamps older than 60 s
    while _request_times and _request_times[0] < now - 60:
        _request_times.popleft()
    if len(_request_times) >= RATE_LIMIT - 5:  # threshold at 95 requests
        sleep_for = 60 - (now - _request_times[0]) + 0.1
        if sleep_for > 0:
            log(f"Rate limit: sleeping {sleep_for:.1f}s")
            time.sleep(sleep_for)
    _request_times.append(time.time())

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_session = requests.Session()
_session.headers.update({
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
})
if PROXY:
    _session.proxies.update({"https": PROXY, "http": PROXY})


def _get(path: str, params: dict | None = None, timeout: int = 15) -> dict | list | None:
    """Issue a GET request with rate limiting; return parsed JSON or None."""
    _rate_limit_wait()
    url = f"{BASE_URL}{path}"
    try:
        r = _session.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log(f"GET {url} failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------

def get_stock_price(ticker: str) -> dict | None:
    """Current price for a stock."""
    data = _get(f"/stocks/{ticker}/price")
    return data if isinstance(data, dict) else None


def get_stock_history(ticker: str, days: int = 60, interval: str = "1h") -> list[dict]:
    """OHLCV history [{open, high, low, close, volume, timestamp}, ...]."""
    data = _get(f"/stocks/{ticker}/history", params={"days": days, "interval": interval})
    return data if isinstance(data, list) else []


def get_crypto_price(symbol: str) -> dict | None:
    """Current crypto price."""
    data = _get(f"/crypto/{symbol}/price")
    return data if isinstance(data, dict) else None


def get_income_statement(ticker: str, period: str = "quarterly") -> list[dict]:
    """Income statements for the given period."""
    data = _get(f"/stocks/{ticker}/financials/income", params={"period": period})
    return data if isinstance(data, list) else []


def get_balance_sheet(ticker: str, period: str = "quarterly") -> list[dict]:
    """Balance sheet snapshots."""
    data = _get(f"/stocks/{ticker}/financials/balance-sheet", params={"period": period})
    return data if isinstance(data, list) else []


def get_cash_flow(ticker: str, period: str = "quarterly") -> list[dict]:
    """Cash flow statements."""
    data = _get(f"/stocks/{ticker}/financials/cash-flow", params={"period": period})
    return data if isinstance(data, list) else []


def get_company_news(ticker: str, limit: int = 10) -> list[dict]:
    """Recent news articles for a company."""
    data = _get(f"/stocks/{ticker}/news", params={"limit": limit})
    return data if isinstance(data, list) else []


def get_insider_trades(ticker: str, limit: int = 20) -> list[dict]:
    """Insider trades for a company."""
    data = _get(f"/stocks/{ticker}/insider-trades", params={"limit": limit})
    return data if isinstance(data, list) else []


def search_companies(query: str) -> list[dict]:
    """Search companies by name or ticker."""
    data = _get("/search", params={"q": query})
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not API_TOKEN:
        log("FD_API_TOKEN not set -- cannot run self-test")
        sys.exit(1)
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    log(f"Self-test: ticker={ticker}")

    price = get_stock_price(ticker)
    log(f"Price: {price}")

    hist = get_stock_history(ticker, days=5, interval="1d")
    log(f"History: {len(hist)} bars")

    news = get_company_news(ticker, limit=3)
    log(f"News: {len(news)} articles")

    results = search_companies(ticker)
    log(f"Search: {len(results)} results")

    log("Self-test done.")
