"""
polymarket_api.py — Read-only Polymarket API client.

Provides market search, orderbook, trades, pricing, arbitrage detection,
and whale activity tracking. No trading, no private keys, no wallet ops.

Usage:
    from polymarket_api import search_markets, get_market, get_orderbook
    markets = search_markets("election")
    book = get_orderbook(token_id)

Self-test:  python polymarket_api.py
"""

import os
import time
import requests
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

_RATE_WINDOW = 60          # seconds
_RATE_MAX = 30             # requests per window
_request_times: list[float] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def _session() -> requests.Session:
    s = requests.Session()
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        s.proxies = {"https": proxy, "http": proxy}
    s.headers["Accept"] = "application/json"
    return s


def _rate_wait() -> None:
    """Block until we are within the 30-req/min budget."""
    now = time.time()
    cutoff = now - _RATE_WINDOW
    while _request_times and _request_times[0] < cutoff:
        _request_times.pop(0)
    if len(_request_times) >= _RATE_MAX:
        sleep_for = _request_times[0] - cutoff + 0.05
        if sleep_for > 0:
            log(f"rate-limit: sleeping {sleep_for:.1f}s")
            time.sleep(sleep_for)


def _get(url: str, params: dict | None = None, timeout: int = 15) -> dict | list | None:
    """GET with rate limiting; returns parsed JSON or None on any error."""
    _rate_wait()
    _request_times.append(time.time())
    try:
        r = _session().get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"GET {url} failed: {e}")
        return None


def _parse_market(m: dict) -> dict:
    """Normalise a Gamma-API market object into a slim dict."""
    outcomes_prices = m.get("outcomePrices") or "[]"
    if isinstance(outcomes_prices, str):
        import json as _json
        try:
            prices = _json.loads(outcomes_prices)
        except Exception:
            prices = []
    else:
        prices = outcomes_prices
    yes = float(prices[0]) if len(prices) > 0 else 0.0
    no = float(prices[1]) if len(prices) > 1 else 0.0
    return {
        "id": m.get("id"),
        "question": m.get("question"),
        "slug": m.get("slug"),
        "yes_price": round(yes, 4),
        "no_price": round(no, 4),
        "volume": float(m.get("volume") or 0),
        "liquidity": float(m.get("liquidity") or 0),
        "end_date": m.get("endDate"),
    }

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_markets(query: str, limit: int = 20) -> list[dict]:
    """Search open markets by keyword."""
    data = _get(f"{GAMMA_API}/markets", params={
        "closed": "false", "limit": limit, "slug_keyword": query,
    })
    if not isinstance(data, list):
        return []
    return [_parse_market(m) for m in data]


def get_market(market_id: str) -> dict | None:
    """Fetch a single market by ID."""
    data = _get(f"{GAMMA_API}/markets/{market_id}")
    if not isinstance(data, dict):
        return None
    return _parse_market(data)


def get_event(event_slug: str) -> dict | None:
    """Fetch an event (with its markets) by slug."""
    data = _get(f"{GAMMA_API}/events", params={"slug": event_slug})
    if isinstance(data, list) and data:
        ev = data[0]
    elif isinstance(data, dict):
        ev = data
    else:
        return None
    markets_raw = ev.get("markets") or []
    ev["markets"] = [_parse_market(m) for m in markets_raw]
    return ev


def get_orderbook(token_id: str) -> dict | None:
    """Fetch the CLOB order book for a token."""
    data = _get(f"{CLOB_API}/book", params={"token_id": token_id})
    if not isinstance(data, dict):
        return None
    bids = data.get("bids") or []
    asks = data.get("asks") or []
    best_bid = float(bids[0]["price"]) if bids else 0.0
    best_ask = float(asks[0]["price"]) if asks else 0.0
    spread = round(best_ask - best_bid, 6) if (best_bid and best_ask) else 0.0
    mid = round((best_bid + best_ask) / 2, 6) if (best_bid and best_ask) else 0.0
    return {"bids": bids, "asks": asks, "spread": spread, "midpoint": mid}


def get_trades(market_id: str, limit: int = 50) -> list[dict]:
    """Fetch recent trades for a market."""
    data = _get(f"{DATA_API}/trades", params={
        "market": market_id, "limit": limit,
    })
    if not isinstance(data, list):
        return []
    return data


def get_market_prices(token_id: str) -> dict | None:
    """Fetch midpoint / best bid / best ask from the CLOB."""
    mid_data = _get(f"{CLOB_API}/midpoint", params={"token_id": token_id})
    if not isinstance(mid_data, dict):
        return None
    mid = float(mid_data.get("mid") or 0)
    # Enrich with top-of-book from orderbook
    book = get_orderbook(token_id)
    best_bid = book["bids"][0]["price"] if book and book["bids"] else None
    best_ask = book["asks"][0]["price"] if book and book["asks"] else None
    return {
        "mid": round(mid, 6),
        "best_bid": float(best_bid) if best_bid else None,
        "best_ask": float(best_ask) if best_ask else None,
    }


def get_active_markets(limit: int = 100, min_volume: float = 1000) -> list[dict]:
    """Paginated fetch of open markets filtered by minimum volume."""
    collected: list[dict] = []
    offset = 0
    page_size = 100
    while len(collected) < limit:
        data = _get(f"{GAMMA_API}/markets", params={
            "closed": "false", "limit": page_size, "offset": offset,
            "order": "volume", "ascending": "false",
        })
        if not isinstance(data, list) or not data:
            break
        for m in data:
            parsed = _parse_market(m)
            if parsed["volume"] >= min_volume:
                collected.append(parsed)
            if len(collected) >= limit:
                break
        # If no market in this page meets the volume floor, stop.
        if all(_parse_market(m)["volume"] < min_volume for m in data):
            break
        offset += page_size
    collected.sort(key=lambda x: x["volume"], reverse=True)
    return collected[:limit]


def find_arb_opportunities() -> list[dict]:
    """
    Scan multi-outcome events for arbitrage: sum(YES prices) <= 0.97.
    Returns events with expected profit per dollar.
    """
    opportunities: list[dict] = []
    events = _get(f"{GAMMA_API}/events", params={
        "closed": "false", "limit": 50,
    })
    if not isinstance(events, list):
        return []
    for ev in events:
        markets_raw = ev.get("markets") or []
        if len(markets_raw) < 2:
            continue
        markets = [_parse_market(m) for m in markets_raw]
        total_yes = sum(m["yes_price"] for m in markets)
        if 0 < total_yes <= 0.97:
            profit = round(1.0 - total_yes, 4)
            opportunities.append({
                "event_id": ev.get("id"),
                "title": ev.get("title"),
                "num_markets": len(markets),
                "sum_yes": round(total_yes, 4),
                "expected_profit": profit,
                "markets": markets,
            })
    opportunities.sort(key=lambda x: x["expected_profit"], reverse=True)
    return opportunities


def get_whale_activity(min_size: float = 500, limit: int = 50) -> list[dict]:
    """Fetch large trades via /trades (no user required)."""
    data = _get(f"{DATA_API}/trades", params={"limit": limit})
    if not isinstance(data, list):
        return []
    whales: list[dict] = []
    for t in data:
        size = float(t.get("size") or t.get("amount") or 0)
        if size >= min_size:
            whales.append({
                "market": t.get("market") or t.get("title"),
                "side": t.get("side"),
                "size": size,
                "price": t.get("price"),
                "timestamp": t.get("timestamp") or t.get("createdAt"),
            })
    return whales

# ---------------------------------------------------------------------------
# Self-test / demo
# ---------------------------------------------------------------------------

def _demo() -> None:
    log("=== Polymarket API — self-test ===")

    log("1) search_markets('election', limit=3)")
    results = search_markets("election", limit=3)
    for m in results:
        log(f"   {m['question'][:60]}  YES={m['yes_price']}  vol={m['volume']:.0f}")
    if not results:
        log("   (no results)")

    log("2) get_active_markets(limit=3, min_volume=5000)")
    active = get_active_markets(limit=3, min_volume=5000)
    for m in active:
        log(f"   {m['question'][:60]}  vol={m['volume']:.0f}")
    if not active:
        log("   (no results)")

    if results:
        mid = results[0]["id"]
        log(f"3) get_market('{mid}')")
        mkt = get_market(mid)
        if mkt:
            log(f"   {mkt['question'][:60]}  YES={mkt['yes_price']}")

    log("4) find_arb_opportunities()")
    arbs = find_arb_opportunities()
    for a in arbs[:3]:
        log(f"   {a['title'][:50]}  sum_yes={a['sum_yes']}  profit={a['expected_profit']}")
    if not arbs:
        log("   (none found)")

    log("5) get_whale_activity(min_size=500, limit=10)")
    whales = get_whale_activity(min_size=500, limit=10)
    for w in whales[:3]:
        log(f"   {w['market']}  size={w['size']}  side={w['side']}")
    if not whales:
        log("   (none found)")

    log("=== done ===")


if __name__ == "__main__":
    _demo()
