#!/usr/bin/env python3
"""
smart_dca_bot.py — Sentiment-weighted DCA accumulator (Bybit Spot)

Buy MORE when fearful/oversold, sell portions when greedy/overbought.
Cycle: buy fear → sell greed → buy fear.

Usage:
    python smart_dca_bot.py          # paper mode
    python smart_dca_bot.py --live   # real orders on Bybit
    python smart_dca_bot.py --check  # show state
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time, urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots"); BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE   = BASE_DIR / ".env_dca"
STATE_FILE = BASE_DIR / "smart_dca_state.json"
LOG_FILE   = BASE_DIR / "smart_dca.log"

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

# ── Strategy parameters (overridable via .env) ──
COINS          = ["BTC", "ETH", "SOL"]
QUOTE          = "USDT"
CHECK_SEC      = 8 * 3600
BASE_BUY_USDT  = float(ENV.get("DCA_BASE_BUY", "5.5"))
MAX_BUY_USDT   = float(ENV.get("DCA_MAX_BUY", "15.0"))
MIN_ORDER      = 5.0
MIN_SCORE      = float(ENV.get("DCA_MIN_SCORE", "55"))
DAILY_CAP_USDT = float(ENV.get("DCA_DAILY_CAP", "10.0"))
RSI_PERIOD     = 14
RSI_TIMEFRAME  = "1w"
W_FNG          = 0.5
W_RSI          = 0.5
FNG_URL        = "https://api.alternative.me/fng/?limit=1&format=json"

# ── Sell thresholds (F&G based) ──
SELL_TIER_1    = float(ENV.get("DCA_SELL_T1", "75"))    # F&G >= 75 → sell 25%
SELL_TIER_2    = float(ENV.get("DCA_SELL_T2", "80"))    # F&G >= 80 → sell 50%
SELL_PCT_1     = 0.25
SELL_PCT_2     = 0.50
MIN_SELL_USDT  = 5.0
SELL_COOLDOWN  = 48 * 3600

# ── Logging ──
logger = logging.getLogger("smart_dca"); logger.setLevel(logging.INFO); logger.propagate = False
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
if sys.stdin and sys.stdin.isatty():
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

# ── HTTP helper ──
def http_get(url: str, timeout: int = 15) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "smart-dca/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.warning("HTTP GET %s: %s", url, e)
        return None

# ── State ──
@dataclass
class BotState:
    spend_today: float = 0.0
    spend_day: str = ""
    total_spent: float = 0.0
    total_sold: float = 0.0
    total_profit: float = 0.0
    accumulated: dict = field(default_factory=dict)   # coin → USDT spent
    holdings: dict = field(default_factory=dict)       # coin → qty held
    avg_price: dict = field(default_factory=dict)      # coin → avg buy price
    buys: int = 0
    sells: int = 0
    cycles: int = 0
    last_fng: float = -1.0
    last_scores: dict = field(default_factory=dict)
    last_sell_ts: dict = field(default_factory=dict)   # coin → epoch of last sell

def load_state() -> BotState:
    if STATE_FILE.exists():
        try:
            raw = json.loads(STATE_FILE.read_text())
            st = BotState()
            for k, v in raw.items():
                if hasattr(st, k):
                    setattr(st, k, v)
            return st
        except Exception:
            pass
    return BotState()

def save_state(st: BotState):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(asdict(st), indent=2))

def roll_day(st: BotState):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if st.spend_day != today:
        if st.spend_day and (st.spend_today > 0 or st.total_sold > 0):
            tg(f"📊 DCA Daily | bought ${st.spend_today:.2f} | "
               f"profit ${st.total_profit:.2f}")
        st.spend_day = today
        st.spend_today = 0.0

# ── Signals ──
def fetch_fear_greed() -> float | None:
    data = http_get(FNG_URL)
    if data and "data" in data and data["data"]:
        try:
            return float(data["data"][0]["value"])
        except (KeyError, ValueError):
            pass
    logger.warning("Fear&Greed fetch failed")
    return None

def fetch_ohlcv(symbol: str, timeframe: str = "1w", limit: int = 50) -> list | None:
    sym = symbol.replace("/", "")
    url = (f"https://api.bybit.com/v5/market/kline?"
           f"category=spot&symbol={sym}&interval=W&limit={limit}")
    data = http_get(url)
    if not data or data.get("retCode") != 0:
        logger.warning("OHLCV fetch failed for %s", symbol)
        return None
    rows = data.get("result", {}).get("list", [])
    if not rows:
        return None
    closes = [float(r[4]) for r in reversed(rows)]
    return closes

def compute_rsi(closes: list[float], period: int = RSI_PERIOD) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def blended_score(fng: float, rsi: float) -> float:
    return W_FNG * (100.0 - fng) + W_RSI * (100.0 - rsi)

def size_multiplier(score: float) -> float:
    if score < MIN_SCORE:
        return 0.0
    frac = (score - MIN_SCORE) / (100.0 - MIN_SCORE)
    max_mult = MAX_BUY_USDT / BASE_BUY_USDT
    return 1.0 + frac * (max_mult - 1.0)

# ── Execution ──
def fetch_price(symbol: str) -> float | None:
    sym = symbol.replace("/", "")
    data = http_get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={sym}")
    if data and data.get("retCode") == 0:
        tickers = data.get("result", {}).get("list", [])
        if tickers:
            return float(tickers[0].get("lastPrice", 0))
    return None

def bybit_signed_request(params: dict) -> dict | None:
    import hmac, hashlib
    ts = str(int(time.time() * 1000))
    recv = "5000"
    body = json.dumps(params)
    sign_str = f"{ts}{BYBIT_KEY}{recv}{body}"
    sig = hmac.new(BYBIT_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-BAPI-API-KEY": BYBIT_KEY,
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": recv,
        "X-BAPI-SIGN": sig,
    }
    url = "https://api.bybit.com/v5/order/create"
    try:
        req = urllib.request.Request(url, data=body.encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.error("Bybit API error: %s", e)
        return None

def bybit_signed_get(path: str, params: str) -> dict | None:
    import hmac, hashlib
    ts = str(int(time.time() * 1000))
    recv = "5000"
    sign_str = f"{ts}{BYBIT_KEY}{recv}{params}"
    sig = hmac.new(BYBIT_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.bybit.com{path}?{params}"
    try:
        req = urllib.request.Request(url, headers={
            "X-BAPI-API-KEY": BYBIT_KEY,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv,
            "X-BAPI-SIGN": sig,
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.error("Bybit GET error: %s", e)
        return None

def get_order_fill(symbol: str, order_id: str) -> tuple[float, float] | None:
    time.sleep(1)
    sym = symbol.replace("/", "")
    params = f"category=spot&symbol={sym}&orderId={order_id}"
    resp = bybit_signed_get("/v5/order/realtime", params)
    if resp and resp.get("retCode") == 0:
        orders = resp.get("result", {}).get("list", [])
        if orders:
            qty = float(orders[0].get("cumExecQty", 0))
            price = float(orders[0].get("avgPrice", 0))
            if qty > 0 and price > 0:
                return qty, price
    return None

def place_buy_live(symbol: str, usdt: float) -> tuple[bool, str]:
    params = {
        "category": "spot", "symbol": symbol.replace("/", ""),
        "side": "Buy", "orderType": "Market",
        "marketUnit": "quoteCoin", "qty": f"{usdt:.2f}",
    }
    resp = bybit_signed_request(params)
    if resp and resp.get("retCode") == 0:
        oid = resp.get("result", {}).get("orderId", "")
        logger.info("[LIVE] BUY %s $%.2f OK (order=%s)", symbol, usdt, oid)
        return True, oid
    logger.error("[LIVE] BUY %s failed: %s", symbol, resp.get("retMsg") if resp else "no response")
    return False, ""

def place_sell_live(symbol: str, qty: float) -> bool:
    sym = symbol.replace("/", "")
    precision = 6
    if "BTC" in sym:
        precision = 6
    elif "ETH" in sym:
        precision = 5
    elif "SOL" in sym:
        precision = 3
    qty_str = f"{qty:.{precision}f}"
    params = {
        "category": "spot", "symbol": sym,
        "side": "Sell", "orderType": "Market",
        "qty": qty_str,
    }
    resp = bybit_signed_request(params)
    if resp and resp.get("retCode") == 0:
        logger.info("[LIVE] SELL %s qty=%s OK", symbol, qty_str)
        return True
    logger.error("[LIVE] SELL %s failed: %s", symbol, resp.get("retMsg") if resp else "no response")
    return False

def place_buy(symbol: str, usdt: float, live: bool, st: BotState, coin: str) -> bool:
    if usdt < MIN_ORDER:
        logger.info("skip %s: $%.2f < min $%.2f", symbol, usdt, MIN_ORDER)
        return False
    price = fetch_price(symbol) or 0
    if price <= 0:
        logger.warning("no price for %s", symbol)
        return False
    if not live:
        qty = usdt / price
        logger.info("[PAPER] BUY %s $%.2f (≈%.6f @ $%.2f)", symbol, usdt, qty, price)
    else:
        ok, oid = place_buy_live(symbol, usdt)
        if not ok:
            return False
        fill = get_order_fill(symbol, oid) if oid else None
        if fill:
            qty, price = fill
            logger.info("[LIVE] Fill: %s qty=%.8f @ $%.2f", coin, qty, price)
        else:
            qty = usdt / price
            logger.warning("Could not get fill for %s, using estimate", coin)
    old_qty = st.holdings.get(coin, 0.0)
    old_avg = st.avg_price.get(coin, 0.0)
    new_qty = old_qty + qty
    st.avg_price[coin] = ((old_avg * old_qty) + (price * qty)) / new_qty if new_qty > 0 else price
    st.holdings[coin] = new_qty
    return True

def place_sell(symbol: str, qty: float, live: bool, st: BotState, coin: str) -> bool:
    price = fetch_price(symbol) or 0
    if price <= 0:
        return False
    sell_value = qty * price
    if sell_value < MIN_SELL_USDT:
        logger.info("skip sell %s: $%.2f < min $%.2f", symbol, sell_value, MIN_SELL_USDT)
        return False
    if not live:
        logger.info("[PAPER] SELL %s qty=%.6f ($%.2f @ $%.2f)", symbol, qty, sell_value, price)
    else:
        if not place_sell_live(symbol, qty):
            return False
    avg = st.avg_price.get(coin, price)
    profit = (price - avg) * qty
    st.holdings[coin] = st.holdings.get(coin, 0.0) - qty
    st.total_sold += sell_value
    st.total_profit += profit
    st.sells += 1
    return True

# ── Main cycle ──
def run_cycle(st: BotState, live: bool):
    roll_day(st)
    st.cycles += 1

    fng = fetch_fear_greed()
    if fng is None:
        logger.warning("No F&G signal — skipping cycle")
        return
    st.last_fng = fng
    logger.info("Fear&Greed=%d", int(fng))

    # ── SELL mode: F&G >= SELL_TIER_1 ──
    if fng >= SELL_TIER_1:
        sell_pct = SELL_PCT_2 if fng >= SELL_TIER_2 else SELL_PCT_1
        logger.info("GREED mode (F&G=%d) → sell %.0f%% of holdings", int(fng), sell_pct * 100)
        sold_any = False
        now = time.time()
        for coin in COINS:
            last_sell = st.last_sell_ts.get(coin, 0)
            if now - last_sell < SELL_COOLDOWN:
                hrs_left = (SELL_COOLDOWN - (now - last_sell)) / 3600
                logger.info("  %s: cooldown (%.0fh left)", coin, hrs_left)
                continue
            held = st.holdings.get(coin, 0.0)
            if held <= 0:
                continue
            symbol = f"{coin}/{QUOTE}"
            sell_qty = held * sell_pct
            price = fetch_price(symbol) or 0
            if price > 0 and sell_qty * price >= MIN_SELL_USDT:
                avg = st.avg_price.get(coin, 0)
                pnl = (price - avg) / avg * 100 if avg > 0 else 0
                logger.info("  %s: held=%.6f sell=%.6f avg=$%.2f now=$%.2f (%.1f%%)",
                            coin, held, sell_qty, avg, price, pnl)
                if place_sell(symbol, sell_qty, live, st, coin):
                    sold_any = True
                    st.last_sell_ts[coin] = now
        if sold_any:
            tg(f"💰 DCA Sell | F&G={int(fng)} (greed)\n"
               f"Profit: ${st.total_profit:.2f}")
        save_state(st)
        logger.info("Cycle #%d done (SELL) | profit $%.2f",
                    st.cycles, st.total_profit)
        return

    # ── BUY mode: fear score >= MIN_SCORE ──
    bought_any = False
    for coin in COINS:
        if st.spend_today >= DAILY_CAP_USDT:
            logger.info("Daily cap reached ($%.2f)", st.spend_today)
            break

        symbol = f"{coin}/{QUOTE}"
        closes = fetch_ohlcv(symbol)
        if not closes:
            continue
        rsi = compute_rsi(closes)
        if rsi is None:
            logger.warning("RSI unavailable for %s", coin)
            continue

        score = blended_score(fng, rsi)
        mult = size_multiplier(score)
        st.last_scores[coin] = {"rsi": round(rsi, 1), "score": round(score, 1), "mult": round(mult, 2)}
        logger.info("  %s: RSI(w)=%.1f score=%.1f mult=%.2f", coin, rsi, score, mult)

        if mult == 0.0:
            continue

        usdt = min(BASE_BUY_USDT * mult, MAX_BUY_USDT)
        usdt = min(usdt, DAILY_CAP_USDT - st.spend_today)

        if place_buy(symbol, usdt, live, st, coin):
            st.spend_today += usdt
            st.total_spent += usdt
            st.accumulated[coin] = st.accumulated.get(coin, 0.0) + usdt
            st.buys += 1
            bought_any = True

    if bought_any:
        parts = [f"{c}: ${st.accumulated.get(c, 0):.2f}" for c in COINS]
        tg(f"🛒 DCA Buy | F&G={int(fng)} | spent today ${st.spend_today:.2f}\n" +
           " | ".join(parts))

    save_state(st)
    logger.info("Cycle #%d done | spent today $%.2f/$%.2f | total $%.2f",
                st.cycles, st.spend_today, DAILY_CAP_USDT, st.total_spent)

def show_status(st: BotState):
    print(f"Smart DCA Status")
    print(f"  Cycles:      {st.cycles}")
    print(f"  Buys:        {st.buys}  |  Sells: {st.sells}")
    print(f"  Total spent: ${st.total_spent:.2f}")
    print(f"  Total sold:  ${st.total_sold:.2f}")
    print(f"  Profit:      ${st.total_profit:.2f}")
    print(f"  Today spent: ${st.spend_today:.2f} / ${DAILY_CAP_USDT:.2f}")
    print(f"  Last F&G:    {st.last_fng:.0f}")
    print(f"  Holdings:")
    for coin in COINS:
        qty = st.holdings.get(coin, 0.0)
        avg = st.avg_price.get(coin, 0.0)
        spent = st.accumulated.get(coin, 0.0)
        print(f"    {coin}: {qty:.6f} (avg ${avg:.2f}) spent ${spent:.2f}")
    if st.last_scores:
        print(f"  Last scores:")
        for coin, s in st.last_scores.items():
            print(f"    {coin}: RSI={s.get('rsi','?')} score={s.get('score','?')} mult={s.get('mult','?')}")

# ── Entry ──
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="Execute real orders")
    ap.add_argument("--check", action="store_true", help="Show state and exit")
    args = ap.parse_args()

    st = load_state()

    if args.check:
        show_status(st)
        return

    mode = "LIVE" if args.live else "Paper"
    logger.info("%s mode — coins=%s every %dh", mode, COINS, CHECK_SEC // 3600)
    logger.info("Buy: F&G<%.0f | Sell: F&G>%.0f (25%%) / F&G>%.0f (50%%)",
                MIN_SCORE, SELL_TIER_1, SELL_TIER_2)
    tg(f"🟢 Smart DCA started ({mode}) — buy fear / sell greed")

    try:
        while True:
            try:
                run_cycle(st, args.live)
            except Exception as e:
                logger.exception("Cycle error: %s", e)
            logger.info("Sleeping %ds...", CHECK_SEC)
            time.sleep(CHECK_SEC)
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        tg(f"🔴 Smart DCA stopped | profit ${st.total_profit:.2f}")
        save_state(st)

if __name__ == "__main__":
    main()
