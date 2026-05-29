#!/usr/bin/env python3
"""
pairs_trading_bot.py — Statistical Arbitrage (Pairs Trading)
Bybit Futures: ETH/BTC + SOL/ETH spread mean reversion

Usage:
    python pairs_trading_bot.py          # paper mode
    python pairs_trading_bot.py --live   # live trading
    python pairs_trading_bot.py --check  # show status
"""
from __future__ import annotations
import argparse, json, logging, math, os, sys, time, urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots"); BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE   = BASE_DIR / ".env_naif"
STATE_FILE = BASE_DIR / "pairs_trading_state.json"
LOG_FILE   = BASE_DIR / "pairs_trading.log"

# ── Load env ──
def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); env[k.strip()] = v.strip()
    return env

ENV = load_env()
BYBIT_KEY    = ENV.get("BYBIT_API_KEY", "")
BYBIT_SECRET = ENV.get("BYBIT_API_SECRET", "")
TG_TOKEN     = ENV.get("TELEGRAM_TOKEN", "")
TG_CHAT      = ENV.get("TELEGRAM_CHAT_ID", "")

# ── Strategy parameters ──
PAIRS = [
    ("ETH/USDT:USDT", "BTC/USDT:USDT"),   # ETH/BTC spread
    ("SOL/USDT:USDT", "ETH/USDT:USDT"),    # SOL/ETH spread
]
TIMEFRAME      = "1h"
LOOKBACK       = 60          # periods for z-score
ZSCORE_ENTRY   = 2.0         # enter when |z| > 2.0
ZSCORE_EXIT    = 0.5         # exit  when |z| < 0.5
ZSCORE_STOP    = 3.5         # stop  when |z| > 3.5
LEG_SIZE_USD   = 15.0        # $15 per leg ($30 total per pair)
MAX_OPEN_PAIRS = 2
SCAN_INTERVAL  = 300         # 5 min
COINT_INTERVAL = 604800      # 7 days in seconds
COINT_PVALUE   = 0.10        # max p-value to consider cointegrated
DAILY_LOSS_LIM = 10.0

# ── Logging ──
logger = logging.getLogger("pairs_trading"); logger.setLevel(logging.INFO); logger.propagate = False
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception:
    pass

# ── Telegram ──
def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

# ── State ──
@dataclass
class PairPosition:
    pair_id: str                 # e.g. "ETH/USDT:USDT|BTC/USDT:USDT"
    long_symbol: str
    short_symbol: str
    long_entry: float
    short_entry: float
    size_usd: float
    entry_zscore: float
    open_time: str

@dataclass
class BotState:
    positions: list = field(default_factory=list)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    closed_count: int = 0
    day: str = ""
    halted: bool = False
    coint_cache: dict = field(default_factory=dict)   # pair_id -> {pvalue, ts}
    paused_pairs: list = field(default_factory=list)   # pair_ids that lost cointegration

def load_state() -> BotState:
    if STATE_FILE.exists():
        try:
            return BotState(**json.loads(STATE_FILE.read_text()))
        except Exception:
            pass
    return BotState()

def save_state(st: BotState):
    STATE_FILE.write_text(json.dumps(asdict(st), indent=2, default=str))

# ── Exchange helpers ──
def get_exchange(live: bool):
    import ccxt
    cfg = {
        "apiKey": BYBIT_KEY, "secret": BYBIT_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": "linear"},
    }
    ex = ccxt.bybit(cfg)
    if not live:
        ex.set_sandbox_mode(True)
    return ex

def _bybit_get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "pairs-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def fetch_price(symbol: str) -> float:
    """Fetch last price from Bybit public API (no auth needed)."""
    sym = symbol.replace("/", "").replace(":USDT", "").replace(":", "")
    # For linear contracts the symbol is like ETHUSDT
    if not sym.endswith("USDT"):
        sym = sym + "USDT" if "USDT" not in sym else sym
    try:
        data = _bybit_get(
            f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={sym}")
        return float(data["result"]["list"][0]["lastPrice"])
    except Exception as e:
        logger.warning(f"Price fetch error {symbol}: {e}")
        return 0.0

# ── Spread / Z-score ──
def fetch_ohlcv_close(symbol: str, timeframe: str = "1h", limit: int = 60) -> list[float]:
    """Fetch close prices from Bybit kline endpoint."""
    sym = symbol.replace("/", "").replace(":USDT", "").replace(":", "")
    if not sym.endswith("USDT"):
        sym = sym + "USDT" if "USDT" not in sym else sym
    interval_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}
    interval = interval_map.get(timeframe, "60")
    try:
        data = _bybit_get(
            f"https://api.bybit.com/v5/market/kline?category=linear"
            f"&symbol={sym}&interval={interval}&limit={limit}")
        rows = data["result"]["list"]
        # Bybit returns newest first; reverse for chronological order
        closes = [float(r[4]) for r in reversed(rows)]
        return closes
    except Exception as e:
        logger.warning(f"OHLCV fetch error {symbol}: {e}")
        return []

def fetch_spread_history(pair1: str, pair2: str,
                         timeframe: str = "1h", limit: int = 60) -> list[float]:
    """Return price-ratio series: pair1_close / pair2_close."""
    c1 = fetch_ohlcv_close(pair1, timeframe, limit)
    c2 = fetch_ohlcv_close(pair2, timeframe, limit)
    if not c1 or not c2:
        return []
    n = min(len(c1), len(c2))
    ratios = []
    for i in range(n):
        if c2[i] != 0:
            ratios.append(c1[i] / c2[i])
    return ratios

def calc_zscore(spread: list[float]) -> float | None:
    """Compute z-score of the latest spread value vs rolling window."""
    if len(spread) < 20:
        return None
    mean = sum(spread) / len(spread)
    var = sum((x - mean) ** 2 for x in spread) / len(spread)
    std = math.sqrt(var) if var > 0 else 0
    if std == 0:
        return 0.0
    return (spread[-1] - mean) / std

# ── Cointegration test ──
def check_cointegration(pair1: str, pair2: str) -> tuple[bool, float]:
    """
    Engle-Granger cointegration test.
    Uses statsmodels ADF if available, otherwise a simple approximation.
    Returns (is_cointegrated, p_value).
    """
    closes1 = fetch_ohlcv_close(pair1, "1h", 168)  # 7 days of hourly data
    closes2 = fetch_ohlcv_close(pair2, "1h", 168)
    if len(closes1) < 50 or len(closes2) < 50:
        logger.warning("Not enough data for cointegration test")
        return False, 1.0

    n = min(len(closes1), len(closes2))
    closes1, closes2 = closes1[:n], closes2[:n]

    # OLS regression: closes1 = beta * closes2 + alpha + residuals
    x_mean = sum(closes2) / n
    y_mean = sum(closes1) / n
    num = sum((closes2[i] - x_mean) * (closes1[i] - y_mean) for i in range(n))
    den = sum((closes2[i] - x_mean) ** 2 for i in range(n))
    beta = num / den if den != 0 else 1.0
    alpha = y_mean - beta * x_mean
    residuals = [closes1[i] - beta * closes2[i] - alpha for i in range(n)]

    try:
        from statsmodels.tsa.stattools import adfuller
        result = adfuller(residuals, maxlag=int(n ** (1 / 3)), autolag=None)
        p_value = result[1]
        logger.info(f"ADF test (statsmodels): stat={result[0]:.4f} p={p_value:.4f}")
    except ImportError:
        # Simple ADF approximation: Dickey-Fuller on residuals
        p_value = _simple_adf(residuals)
        logger.info(f"ADF test (approx): p={p_value:.4f}")

    cointegrated = p_value < COINT_PVALUE
    return cointegrated, round(p_value, 6)

def _simple_adf(series: list[float]) -> float:
    """
    Simplified Dickey-Fuller: regress diff(y) on y_lag.
    Returns approximate p-value using critical value heuristics.
    """
    n = len(series)
    if n < 30:
        return 1.0
    dy = [series[i] - series[i - 1] for i in range(1, n)]
    y_lag = series[:-1]
    # OLS: dy = gamma * y_lag + error
    ym = sum(y_lag) / len(y_lag)
    dm = sum(dy) / len(dy)
    num = sum((y_lag[i] - ym) * (dy[i] - dm) for i in range(len(dy)))
    den = sum((y_lag[i] - ym) ** 2 for i in range(len(dy)))
    gamma = num / den if den != 0 else 0
    # t-statistic
    resid = [dy[i] - gamma * y_lag[i] for i in range(len(dy))]
    sse = sum(r ** 2 for r in resid) / max(len(resid) - 1, 1)
    se = math.sqrt(sse / den) if den > 0 and sse > 0 else 1.0
    t_stat = gamma / se if se != 0 else 0
    # Approximate p-value from DF critical values (n~100)
    # 1%: -3.51, 5%: -2.89, 10%: -2.58
    if t_stat < -3.51:
        return 0.005
    elif t_stat < -2.89:
        return 0.03
    elif t_stat < -2.58:
        return 0.07
    elif t_stat < -1.95:
        return 0.15
    else:
        return 0.50

# ── Position management ──
def pair_id(p1: str, p2: str) -> str:
    return f"{p1}|{p2}"

def open_pair_position(long_sym: str, short_sym: str, size_usd: float,
                       zscore: float, st: BotState, live: bool, ex=None) -> bool:
    """Open a pair: long one asset, short the other."""
    pid = pair_id(long_sym, short_sym)
    if any(p["pair_id"] == pid for p in st.positions):
        return False
    if len(st.positions) >= MAX_OPEN_PAIRS or st.halted:
        return False

    long_price = fetch_price(long_sym)
    short_price = fetch_price(short_sym)
    if long_price <= 0 or short_price <= 0:
        logger.warning(f"Cannot fetch prices for {long_sym}/{short_sym}")
        return False

    long_qty = round(size_usd / long_price, 6)
    short_qty = round(size_usd / short_price, 6)
    lbl = "LIVE" if live else "PAPER"

    if live and ex:
        try:
            try:
                ex.set_leverage(1, long_sym)
                ex.set_leverage(1, short_sym)
            except Exception as e:
                logger.warning(f"Set leverage: {e}")
            ex.create_order(long_sym, "market", "buy", long_qty)
            ex.create_order(short_sym, "market", "sell", short_qty)
            logger.info(f"Live orders placed: long {long_sym} / short {short_sym}")
        except Exception as e:
            logger.error(f"Failed to open pair {pid}: {e}")
            tg(f"[ERROR] Failed to open pair {long_sym}/{short_sym}: {e}")
            return False

    pos = asdict(PairPosition(
        pair_id=pid, long_symbol=long_sym, short_symbol=short_sym,
        long_entry=long_price, short_entry=short_price,
        size_usd=size_usd, entry_zscore=zscore,
        open_time=datetime.now(timezone.utc).isoformat()))
    st.positions.append(pos)

    msg = (f"[{lbl}] NEW PAIR POSITION\n"
           f"Long:  {long_sym} @ ${long_price:.4f}\n"
           f"Short: {short_sym} @ ${short_price:.4f}\n"
           f"Size:  ${size_usd:.0f} per leg\n"
           f"Z-score: {zscore:+.3f}")
    logger.info(msg.replace("\n", " | "))
    tg(msg)
    return True

def close_pair_position(pos: dict, reason: str, st: BotState,
                        live: bool, ex=None) -> float:
    """Close both legs. Returns realised PnL."""
    long_now = fetch_price(pos["long_symbol"])
    short_now = fetch_price(pos["short_symbol"])
    if long_now <= 0:
        long_now = pos["long_entry"]
    if short_now <= 0:
        short_now = pos["short_entry"]

    # PnL: long leg profit + short leg profit
    long_pnl = (long_now - pos["long_entry"]) / pos["long_entry"] * pos["size_usd"]
    short_pnl = (pos["short_entry"] - short_now) / pos["short_entry"] * pos["size_usd"]
    total_pnl = long_pnl + short_pnl
    lbl = "LIVE" if live else "PAPER"

    if live and ex:
        try:
            long_qty = round(pos["size_usd"] / long_now, 6)
            short_qty = round(pos["size_usd"] / short_now, 6)
            ex.create_order(pos["long_symbol"], "market", "sell", long_qty)
            ex.create_order(pos["short_symbol"], "market", "buy", short_qty)
        except Exception as e:
            logger.error(f"Error closing {pos['pair_id']}: {e}")

    msg = (f"[{lbl}] CLOSE PAIR | {reason}\n"
           f"Long  {pos['long_symbol']}: ${long_pnl:+.4f}\n"
           f"Short {pos['short_symbol']}: ${short_pnl:+.4f}\n"
           f"Net PnL: ${total_pnl:+.4f}")
    logger.info(msg.replace("\n", " | "))
    tg(msg)

    st.daily_pnl += total_pnl
    st.total_pnl += total_pnl
    st.closed_count += 1
    return total_pnl

# ── Cointegration cache ──
def should_recheck_coint(st: BotState, pid: str) -> bool:
    entry = st.coint_cache.get(pid)
    if not entry:
        return True
    last_ts = entry.get("ts", 0)
    return (time.time() - last_ts) > COINT_INTERVAL

def update_coint_cache(st: BotState, pid: str, p_value: float):
    st.coint_cache[pid] = {"pvalue": p_value, "ts": time.time()}

# ── Core loop logic ──
def manage_positions(st: BotState, live: bool, ex=None):
    """Check z-scores of open positions; exit or stop as needed."""
    if not st.positions:
        return
    keep = []
    for pos in st.positions:
        sym1, sym2 = pos["long_symbol"], pos["short_symbol"]
        spread = fetch_spread_history(sym1, sym2, TIMEFRAME, LOOKBACK)
        z = calc_zscore(spread) if spread else None

        if z is None:
            logger.warning(f"No z-score for {pos['pair_id']} — keeping position")
            keep.append(pos)
            continue

        logger.info(f"  {pos['pair_id']} z={z:+.3f} (entry z={pos['entry_zscore']:+.3f})")

        reason = None
        if abs(z) >= ZSCORE_STOP:
            reason = f"STOP z={z:+.3f} (limit {ZSCORE_STOP})"
        elif abs(z) <= ZSCORE_EXIT:
            reason = f"EXIT z={z:+.3f} (mean reverted)"
        elif st.daily_pnl <= -DAILY_LOSS_LIM:
            reason = f"Daily loss limit (${st.daily_pnl:.2f})"
            st.halted = True

        if reason:
            close_pair_position(pos, reason, st, live, ex)
        else:
            keep.append(pos)

    st.positions = keep

def scan_for_entries(st: BotState, live: bool, ex=None):
    """Scan configured pairs for entry signals."""
    if len(st.positions) >= MAX_OPEN_PAIRS or st.halted:
        return

    for sym1, sym2 in PAIRS:
        if len(st.positions) >= MAX_OPEN_PAIRS:
            break
        pid = pair_id(sym1, sym2)

        # Skip if already in a position for this pair
        if any(p["pair_id"] == pid or p["pair_id"] == pair_id(sym2, sym1)
               for p in st.positions):
            continue

        # Skip if pair is paused (lost cointegration)
        if pid in st.paused_pairs:
            if should_recheck_coint(st, pid):
                coint, pv = check_cointegration(sym1, sym2)
                update_coint_cache(st, pid, pv)
                if coint:
                    st.paused_pairs.remove(pid)
                    logger.info(f"Cointegration restored for {pid} (p={pv:.4f})")
                    tg(f"COINT RESTORED: {pid} (p={pv:.4f})")
                else:
                    logger.info(f"Pair {pid} still not cointegrated (p={pv:.4f})")
            continue

        # Cointegration check (weekly)
        if should_recheck_coint(st, pid):
            coint, pv = check_cointegration(sym1, sym2)
            update_coint_cache(st, pid, pv)
            if not coint:
                logger.warning(f"Pair {pid} lost cointegration (p={pv:.4f}) — pausing")
                tg(f"COINT BREAK: {pid} p-value={pv:.4f} > {COINT_PVALUE}\nPausing this pair.")
                st.paused_pairs.append(pid)
                # Close any existing positions in this pair
                for pos in list(st.positions):
                    if pos["pair_id"] in (pid, pair_id(sym2, sym1)):
                        close_pair_position(pos, "Cointegration break", st, live, ex)
                        st.positions.remove(pos)
                continue

        # Fetch spread and compute z-score
        spread = fetch_spread_history(sym1, sym2, TIMEFRAME, LOOKBACK)
        z = calc_zscore(spread) if spread else None
        if z is None:
            logger.info(f"No z-score for {pid} — skipping")
            continue

        logger.info(f"  Scan {pid}: z={z:+.3f}")

        # Entry logic: mean reversion
        if z > ZSCORE_ENTRY:
            # Spread is too high — expect reversion downward
            # Short sym1/sym2 ratio => short sym1, long sym2
            open_pair_position(sym2, sym1, LEG_SIZE_USD, z, st, live, ex)
        elif z < -ZSCORE_ENTRY:
            # Spread is too low — expect reversion upward
            # Long sym1/sym2 ratio => long sym1, short sym2
            open_pair_position(sym1, sym2, LEG_SIZE_USD, z, st, live, ex)

# ── Daily summary ──
def daily_summary(st: BotState):
    msg = (f"DAILY SUMMARY — Pairs Trading\n"
           f"Open positions: {len(st.positions)}/{MAX_OPEN_PAIRS}\n"
           f"PnL today: ${st.daily_pnl:+.4f}\n"
           f"Total PnL: ${st.total_pnl:+.4f}\n"
           f"Closed trades: {st.closed_count}\n"
           f"Paused pairs: {len(st.paused_pairs)}")
    for p in st.positions:
        msg += f"\n  {p['pair_id']} z_entry={p['entry_zscore']:+.3f}"
    logger.info(msg.replace("\n", " | "))
    tg(msg)

# ── Check command ──
def cmd_check():
    st = load_state()
    print(f"\n{'=' * 55}\n  Pairs Trading Bot — Status\n{'=' * 55}")
    print(f"  Day: {st.day} | Positions: {len(st.positions)}/{MAX_OPEN_PAIRS}")
    print(f"  PnL today: ${st.daily_pnl:+.4f} | Total: ${st.total_pnl:+.4f}")
    print(f"  Closed: {st.closed_count} | Halted: {st.halted}")
    print(f"  Paused pairs: {st.paused_pairs or 'none'}")
    if st.positions:
        for p in st.positions:
            spread = fetch_spread_history(
                p["long_symbol"], p["short_symbol"], TIMEFRAME, LOOKBACK)
            z = calc_zscore(spread) if spread else None
            z_str = f"{z:+.3f}" if z is not None else "N/A"
            long_now = fetch_price(p["long_symbol"])
            short_now = fetch_price(p["short_symbol"])
            lpnl = (long_now - p["long_entry"]) / p["long_entry"] * p["size_usd"] if long_now > 0 else 0
            spnl = (p["short_entry"] - short_now) / p["short_entry"] * p["size_usd"] if short_now > 0 else 0
            print(f"  {p['pair_id']}")
            print(f"    z_now={z_str}  z_entry={p['entry_zscore']:+.3f}  pnl=${lpnl + spnl:+.4f}")
    else:
        print("  No open positions")

    print(f"\n  Current spreads:")
    for sym1, sym2 in PAIRS:
        spread = fetch_spread_history(sym1, sym2, TIMEFRAME, LOOKBACK)
        z = calc_zscore(spread) if spread else None
        z_str = f"{z:+.3f}" if z is not None else "N/A"
        ratio = f"{spread[-1]:.6f}" if spread else "N/A"
        pid = pair_id(sym1, sym2)
        paused = " [PAUSED]" if pid in st.paused_pairs else ""
        print(f"    {pid}: ratio={ratio} z={z_str}{paused}")
    print(f"{'=' * 55}")

# ── Main cycle ──
def run_cycle(st: BotState, live: bool, ex=None):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if st.day != today:
        if st.day:
            daily_summary(st)
        st.day = today
        st.daily_pnl = 0.0
        st.halted = False

    if st.halted:
        logger.warning("System halted — daily loss limit hit")
        return

    manage_positions(st, live, ex)
    scan_for_entries(st, live, ex)

# ── Entry point ──
def main():
    ap = argparse.ArgumentParser(description="Pairs Trading Bot — Bybit Futures")
    ap.add_argument("--live", action="store_true", help="Live trading mode")
    ap.add_argument("--check", action="store_true", help="Show current status")
    args = ap.parse_args()

    if args.check:
        cmd_check()
        return

    live = args.live
    mode = "LIVE" if live else "PAPER"
    pair_labels = [f"{s1.split('/')[0]}/{s2.split('/')[0]}" for s1, s2 in PAIRS]

    print(f"\n{'=' * 50}")
    print(f"  Pairs Trading Bot — {mode}")
    print(f"  Pairs: {', '.join(pair_labels)}")
    print(f"  Leg size: ${LEG_SIZE_USD:.0f} | Z-entry: {ZSCORE_ENTRY}")
    print(f"  Z-exit: {ZSCORE_EXIT} | Z-stop: {ZSCORE_STOP}")
    print(f"  Lookback: {LOOKBACK}h | Scan: {SCAN_INTERVAL}s")
    print(f"{'=' * 50}\n")

    ex = None
    if live:
        if not BYBIT_KEY:
            logger.error("BYBIT_API_KEY not found in .env_naif")
            return
        try:
            ex = get_exchange(live=True)
            ex.load_markets()
            logger.info("Connected to Bybit Futures (linear)")
        except Exception as e:
            logger.error(f"Exchange connection failed: {e}")
            return
    else:
        logger.info("Paper mode — no real orders")

    tg(f"Pairs Trading Bot started ({mode})\n"
       f"Pairs: {', '.join(pair_labels)}\n"
       f"Leg: ${LEG_SIZE_USD:.0f} | Z-entry: {ZSCORE_ENTRY}")

    st = load_state()
    cycle = 0

    try:
        while True:
            cycle += 1
            logger.info(
                f"-- Cycle #{cycle} | positions:{len(st.positions)} "
                f"PnL:${st.daily_pnl:+.4f} total:${st.total_pnl:+.4f} --")
            try:
                run_cycle(st, live, ex)
            except Exception as e:
                logger.error(f"Cycle error: {e}")
            save_state(st)
            logger.info(f"Sleeping {SCAN_INTERVAL}s...")
            time.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        save_state(st)
        daily_summary(st)
        logger.info("Stopped by user")
        tg(f"Pairs Trading Bot stopped | PnL: ${st.total_pnl:+.4f}")

if __name__ == "__main__":
    main()
