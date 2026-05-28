"""
market_data_loader.py — Historical market data loader for Polymarket bots
Integrates Jon-Becker/prediction-market-analysis Parquet dataset with bot ecosystem.
Usage: from market_data_loader import get_market_history
"""
from __future__ import annotations
import json, logging, os, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── optional heavy deps ──────────────────────────────────────────
try:
    import pyarrow.parquet as pq; HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False

try:
    import pandas as pd; HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ── paths & config ───────────────────────────────────────────────
if os.name == "nt":
    _DEFAULT_DATA = r"C:\Users\xman9\Desktop\market_data"
else:
    _DEFAULT_DATA = "/root/bots/market_data"

MARKET_DATA_DIR = os.environ.get("MARKET_DATA_DIR", _DEFAULT_DATA)
CLOB_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

logger = logging.getLogger("market_data_loader")

# ── HTTP helper ──────────────────────────────────────────────────
def _http_get(url: str, timeout: int = 15):
    """GET JSON with proxy support.  Returns parsed dict/list or None."""
    try:
        proxy = os.environ.get("HTTPS_PROXY", "")
        if proxy:
            handler = urllib.request.ProxyHandler({"https": proxy, "http": proxy})
            opener = urllib.request.build_opener(handler)
        else:
            opener = urllib.request.build_opener()
        req = urllib.request.Request(url, headers={"User-Agent": "market-data-loader/1.0"})
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.debug("HTTP error %s — %s", url[:80], e)
        return None


# ── 1. Parquet loader ────────────────────────────────────────────
def load_parquet_history(market_id: str, data_dir: str = None) -> list[dict]:
    """Load OHLCV bars from local Parquet files for a given market_id.

    Searches ``{data_dir}/polymarket/`` for files whose name contains the
    market_id.  Returns a sorted list of dicts with keys:
        timestamp, open, high, low, close, volume
    Returns [] if no data found or libraries unavailable.
    """
    data_dir = data_dir or MARKET_DATA_DIR
    parquet_dir = Path(data_dir) / "polymarket"
    if not parquet_dir.is_dir():
        return []

    # find matching files
    candidates = [f for f in parquet_dir.iterdir()
                  if f.suffix == ".parquet" and market_id in f.stem]
    if not candidates:
        return []

    rows: list[dict] = []
    for fpath in candidates:
        try:
            if HAS_PANDAS:
                df = pd.read_parquet(fpath)
                for _, r in df.iterrows():
                    rows.append(_row_to_ohlcv(r))
            elif HAS_PARQUET:
                table = pq.read_table(fpath)
                for batch in table.to_batches():
                    for i in range(batch.num_rows):
                        row = {col: batch.column(col)[i].as_py() for col in batch.schema.names}
                        rows.append(_row_to_ohlcv(row))
            else:
                logger.info("Parquet file found but pyarrow/pandas not installed — skipping")
                return []
        except Exception as e:
            logger.warning("Error reading %s: %s", fpath.name, e)
            continue

    rows.sort(key=lambda r: r["timestamp"])
    return rows


def _row_to_ohlcv(row) -> dict:
    """Normalise a raw row (dict-like) into a standard OHLCV dict."""
    def _f(val, default=0.0):
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    # handle various column-name conventions in the dataset
    get = row.get if isinstance(row, dict) else lambda k, d=None: getattr(row, k, d)
    price = _f(get("price", get("p", 0)))
    return {
        "timestamp": str(get("timestamp", get("t", ""))),
        "open":   _f(get("open",  price)),
        "high":   _f(get("high",  price)),
        "low":    _f(get("low",   price)),
        "close":  _f(get("close", price)),
        "volume": _f(get("volume", get("size", 0))),
    }


# ── 2. Unified price-history getter ─────────────────────────────
def get_market_history(market_id: str, token_id: str,
                       days: int = 60, data_dir: str = None) -> list[float]:
    """Return list of close prices (floats 0-1) via Parquet → CLOB → Gamma fallback.

    Parameters
    ----------
    market_id : str   — Polymarket condition-id
    token_id  : str   — CLOB token id (for API fallback)
    days      : int   — lookback window
    data_dir  : str   — override MARKET_DATA_DIR
    """
    # --- attempt 1: local Parquet ---
    bars = load_parquet_history(market_id, data_dir)
    if bars:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        prices = [b["close"] for b in bars if b["timestamp"] >= cutoff and 0 < b["close"] < 1]
        if len(prices) >= 24:
            logger.info("Loaded %d prices from Parquet for %s", len(prices), market_id[:16])
            return prices

    # --- attempt 2: CLOB prices-history API ---
    if token_id:
        for params in [f"interval=1h&fidelity=60",
                       f"interval=max&fidelity={days * 24}"]:
            data = _http_get(f"{CLOB_API}/prices-history?market={token_id}&{params}")
            if data and isinstance(data, dict):
                hist = data.get("history", [])
                if isinstance(hist, list) and len(hist) >= 24:
                    prices = [float(pt.get("p", 0) or pt.get("price", 0))
                              for pt in hist
                              if 0 < float(pt.get("p", 0) or pt.get("price", 0) or 0) < 1]
                    if len(prices) >= 24:
                        logger.info("Loaded %d prices from CLOB for %s", len(prices), market_id[:16])
                        return prices

    # --- attempt 3: Gamma API market snapshot ---
    if market_id:
        data = _http_get(f"{GAMMA_API}/markets/{market_id}")
        if data and isinstance(data, dict):
            price = None
            for key in ("outcomePrices", "outcome_prices"):
                raw = data.get(key)
                if raw:
                    try:
                        parsed = json.loads(raw) if isinstance(raw, str) else raw
                        price = float(parsed[0])
                    except (json.JSONDecodeError, IndexError, TypeError, ValueError):
                        pass
            if price and 0 < price < 1:
                logger.info("Gamma snapshot only: single price %.3f for %s", price, market_id[:16])
                return [price]

    return []


# ── 3. Calibration data ─────────────────────────────────────────
def get_calibration_data(data_dir: str = None) -> dict:
    """Load calibration analysis (price_bucket → actual_resolution_rate).

    Looks for ``calibration.json`` in the data directory, as produced by the
    prediction-market-analysis project.  Returns empty dict if unavailable.
    """
    data_dir = data_dir or MARKET_DATA_DIR
    for name in ("calibration.json", "polymarket/calibration.json",
                 "analysis/calibration.json"):
        fpath = Path(data_dir) / name
        if fpath.is_file():
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # normalise: ensure keys are strings of bucket boundaries
                if isinstance(raw, dict):
                    logger.info("Loaded calibration from %s", fpath)
                    return {str(k): float(v) for k, v in raw.items()}
            except Exception as e:
                logger.warning("Error reading calibration file %s: %s", fpath, e)
    return {}


# ── 4. Dataset download instructions ────────────────────────────
def download_dataset(dest_dir: str = None) -> bool:
    """Print instructions for obtaining the prediction-market-analysis dataset.

    The full dataset is ~36 GB so we do NOT auto-download.
    Returns False always (manual action required).
    """
    dest_dir = dest_dir or MARKET_DATA_DIR
    print("=" * 65)
    print("  Jon-Becker/prediction-market-analysis dataset setup")
    print("=" * 65)
    print()
    print("The dataset contains historical Polymarket trades/prices in Parquet")
    print("format (~36 GB total).  Automated download is disabled.")
    print()
    print("Steps:")
    print(f"  1. mkdir -p {dest_dir}/polymarket")
    print("  2. Visit: https://github.com/Jon-Becker/prediction-market-analysis")
    print("  3. Download the Parquet files you need (or use the provided scripts)")
    print(f"  4. Place .parquet files in: {dest_dir}/polymarket/")
    print("  5. Optionally place calibration.json in the same directory")
    print()
    print("After setup, bots will auto-detect and use the local data.")
    print("=" * 65)
    return False


# ── CLI quick-test ───────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="[%(asctime)s] %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    print(f"Data dir : {MARKET_DATA_DIR}")
    print(f"Parquet  : {'available' if HAS_PARQUET else 'not installed'}")
    print(f"Pandas   : {'available' if HAS_PANDAS else 'not installed'}")
    print()
    download_dataset()
