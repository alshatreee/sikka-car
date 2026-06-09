#!/usr/bin/env python3
"""
daytrading_bot.py — Intraday Spot Trading Bot (Bybit)

Strategy: RSI Bounce + EMA Trend + Volume Confirmation
- Scans high-volatility altcoins every 5 minutes
- Buys on RSI oversold bounce in uptrend (EMA9 > EMA21 on 1h)
- Takes profit at 2-4%, stops at 3-5%
- Max 5 concurrent positions, max $50/trade

Based on ML analysis:
  - Average optimal delay: 150 min (don't chase pumps)
  - Average entry saving: 5.88% (wait for pullbacks)
  - Average max drawdown: -17.76% (keep stops tight)

Usage:
    python daytrading_bot.py              # paper mode
    python daytrading_bot.py --live       # real trading
    python daytrading_bot.py --status     # show positions
    python daytrading_bot.py --backtest   # test on historical data
"""
from __future__ import annotations
import argparse, json, hashlib, hmac, logging, os, sys, time, statistics
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Paths ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE   = BASE_DIR / ".env_monthly"
STATE_FILE = BASE_DIR / "daytrading_state.json"
LOG_FILE   = BASE_DIR / "daytrading.log"

# ── Load env ──
def load_env() -> dict:
    env = {}
    for f in [ENV_FILE, BASE_DIR / ".env_dca"]:
        if f.exists():
            for line in open(f):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
            break
    return env

ENV = load_env()
BYBIT_KEY    = ENV.get("BYBIT_API_KEY", "")
BYBIT_SECRET = ENV.get("BYBIT_API_SECRET", "")
TG_TOKEN     = ENV.get("TELEGRAM_TOKEN", "")
TG_CHAT      = ENV.get("TELEGRAM_CHAT_ID", "")

# ══════════════════════════════════════════════════════════════
# STRATEGY PARAMETERS (tuned from ML analysis)
# ══════════════════════════════════════════════════════════════

# Position sizing
TRADE_SIZE_USDT    = float(ENV.get("DT_TRADE_SIZE", "50.0"))
MAX_POSITIONS      = int(ENV.get("DT_MAX_POSITIONS", "5"))
MAX_DAILY_LOSS     = float(ENV.get("DT_MAX_LOSS", "50.0"))

# Cross-bot intelligence files
ML_RECS_FILE       = BASE_DIR / "ml_recommendations.json"
CHANNEL_MEM_FILE   = BASE_DIR / "channel_memory.json"
SIGNAL_TRACKER     = BASE_DIR / "signal_tracker.json"

# Entry: RSI bounce from oversold
RSI_OVERSOLD       = float(ENV.get("DT_RSI_OVERSOLD", "40"))
RSI_BOUNCE_MIN     = float(ENV.get("DT_RSI_BOUNCE", "3"))
MIN_VOLUME_SPIKE   = float(ENV.get("DT_VOL_SPIKE", "1.3"))

# Exit targets (tight for day trading)
TAKE_PROFIT_PCT    = float(ENV.get("DT_TP_PCT", "3.0"))
STOP_LOSS_PCT      = float(ENV.get("DT_SL_PCT", "4.0"))
TRAILING_ACTIVATE  = float(ENV.get("DT_TRAIL_ACT", "2.0"))
TRAILING_PCT       = float(ENV.get("DT_TRAIL_PCT", "1.5"))
MAX_HOLD_HOURS     = int(ENV.get("DT_MAX_HOLD", "12"))

# Scan settings
SCAN_INTERVAL_SEC  = int(ENV.get("DT_SCAN_SEC", "300"))
KLINE_TIMEFRAME    = "15"    # 15-minute candles
TREND_TIMEFRAME    = "60"    # 1-hour candles for trend

# Watchlist: high-volatility altcoins on Bybit
WATCHLIST = [
    "NEARUSDT", "APTUSDT", "SUIUSDT", "SOLUSDT", "AVAXUSDT",
    "INJUSDT", "TIAUSDT", "SEIUSDT", "JUPUSDT", "WIFUSDT",
    "PEPEUSDT", "ARBUSDT", "OPUSDT", "FETUSDT", "RNDRUSDT",
    "STXUSDT", "LINKUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT",
    "AAVEUSDT", "ENAUSDT", "ONDOUSDT", "PENGUUSDT", "MOVEUSDT",
    "ARUSDT", "MOVRUSDT", "ALGOUSDT", "ZENUSDT", "XLMUSDT",
]

PAPER_MODE = True

# ── Logging ──
logger = logging.getLogger("daytrading")
logger.setLevel(logging.INFO)
logger.propagate = False
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
# Only add file handler (avoid duplicate when nohup redirects stdout to same file)
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _fh.setFormatter(_fmt)
    logger.addHandler(_fh)
except Exception:
    _sh = logging.StreamHandler()
    _sh.setFormatter(_fmt)
    logger.addHandler(_sh)


# ── Telegram ──
def notify(msg: str):
    logger.info(msg)
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


# ── HTTP ──
def http_get(url: str, timeout: int = 15) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "daytrading/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.debug("HTTP error %s: %s", url[:60], e)
        return None


# ══════════════════════════════════════════════════════════════
# MARKET DATA (Bybit V5 public API)
# ══════════════════════════════════════════════════════════════

def fetch_klines(symbol: str, interval: str = "15", limit: int = 100) -> list[dict] | None:
    url = (f"https://api.bybit.com/v5/market/kline?"
           f"category=spot&symbol={symbol}&interval={interval}&limit={limit}")
    data = http_get(url)
    if not data or data.get("retCode") != 0:
        return None
    rows = data.get("result", {}).get("list", [])
    if not rows:
        return None
    candles = []
    for r in reversed(rows):
        try:
            if not r[1] or not r[4]:
                continue
            candles.append({
                "ts": int(r[0]),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]) if r[5] else 0.0,
            })
        except (ValueError, IndexError):
            continue
    return candles if candles else None


def fetch_price(symbol: str) -> float | None:
    data = http_get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}")
    if data and data.get("retCode") == 0:
        tickers = data.get("result", {}).get("list", [])
        if tickers:
            val = tickers[0].get("lastPrice", "")
            if val:
                try:
                    return float(val)
                except ValueError:
                    pass
    return None


def fetch_balance() -> float:
    if PAPER_MODE:
        return 999.0
    data = bybit_signed_get("/v5/account/wallet-balance", "accountType=UNIFIED")
    if not data or data.get("retCode") != 0:
        return 0.0
    coins = data.get("result", {}).get("list", [{}])[0].get("coin", [])
    for c in coins:
        if c.get("coin") == "USDT":
            return float(c.get("availableToWithdraw", 0))
    return 0.0


# ══════════════════════════════════════════════════════════════
# TECHNICAL INDICATORS
# ══════════════════════════════════════════════════════════════

def compute_rsi(closes: list[float], period: int = 14) -> list[float]:
    if len(closes) < period + 1:
        return []
    rsi_values = []
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period - 1):
        rsi_values.append(50.0)

    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    return rsi_values


def compute_ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    multiplier = 2 / (period + 1)
    ema = [sum(values[:period]) / period]
    for i in range(period, len(values)):
        ema.append(values[i] * multiplier + ema[-1] * (1 - multiplier))
    return ema


def compute_atr(candles: list[dict], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    tr_values = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    if not tr_values:
        return 0.0
    return sum(tr_values[-period:]) / period


def volume_ratio(candles: list[dict], lookback: int = 20) -> float:
    if len(candles) < lookback + 1:
        return 1.0
    avg_vol = sum(c["volume"] for c in candles[-(lookback + 1):-1]) / lookback
    if avg_vol == 0:
        return 1.0
    return candles[-1]["volume"] / avg_vol


# ══════════════════════════════════════════════════════════════
# CROSS-BOT INTELLIGENCE
# ══════════════════════════════════════════════════════════════

_bot_intel_cache: dict = {}
_bot_intel_ts: float = 0

def load_bot_intel() -> dict:
    global _bot_intel_cache, _bot_intel_ts
    if time.time() - _bot_intel_ts < 600:
        return _bot_intel_cache

    intel = {}

    # ML recommendations (per-symbol profit/drawdown data)
    if ML_RECS_FILE.exists():
        try:
            ml = json.loads(ML_RECS_FILE.read_text())
            for sym, data in ml.get("per_symbol", ml).items():
                sym_upper = sym.upper().replace("/USDT", "").replace("USDT", "")
                if isinstance(data, dict):
                    intel[sym_upper] = {
                        "ml_profit": float(data.get("max_profit_pct", data.get("entry_saving_pct", 0))),
                        "ml_drawdown": abs(float(data.get("max_drawdown_pct", 0))),
                    }
        except Exception:
            pass

    # Channel memory (recent mentions = interest)
    if CHANNEL_MEM_FILE.exists():
        try:
            mem = json.loads(CHANNEL_MEM_FILE.read_text())
            daily = mem.get("daily", {})
            recent_days = sorted(daily.keys())[-7:]
            mention_count: dict[str, int] = {}
            for day in recent_days:
                for coin in daily[day].get("coins", []):
                    c = coin.upper()
                    mention_count[c] = mention_count.get(c, 0) + 1
            for c, count in mention_count.items():
                if c not in intel:
                    intel[c] = {}
                intel[c]["channel_mentions"] = count
        except Exception:
            pass

    # Signal tracker (win/loss history)
    if SIGNAL_TRACKER.exists():
        try:
            tracker = json.loads(SIGNAL_TRACKER.read_text())
            signals = tracker if isinstance(tracker, list) else tracker.get("signals", [])
            win_loss: dict[str, list] = {}
            for sig in signals:
                sym = sig.get("symbol", "").upper()
                outcome = sig.get("outcome", "")
                if sym and outcome in ("WIN", "LOSS"):
                    if sym not in win_loss:
                        win_loss[sym] = [0, 0]
                    if outcome == "WIN":
                        win_loss[sym][0] += 1
                    else:
                        win_loss[sym][1] += 1
            for sym, (w, l) in win_loss.items():
                if sym not in intel:
                    intel[sym] = {}
                intel[sym]["win_rate"] = w / max(w + l, 1) * 100
        except Exception:
            pass

    _bot_intel_cache = intel
    _bot_intel_ts = time.time()
    return intel


def get_intel_boost(symbol: str) -> tuple[float, list[str]]:
    intel = load_bot_intel()
    sym = symbol.upper().replace("USDT", "")
    data = intel.get(sym, {})
    boost = 0.0
    reasons = []

    # ML profit history bonus
    ml_profit = data.get("ml_profit", 0)
    if ml_profit > 5:
        boost += 10
        reasons.append(f"ML+{ml_profit:.0f}%")
    elif ml_profit > 2:
        boost += 5
        reasons.append(f"ML+{ml_profit:.0f}%")

    # Low drawdown bonus (safer coin)
    ml_dd = data.get("ml_drawdown", 0)
    if 0 < ml_dd < 10:
        boost += 5
        reasons.append("lowDD")

    # Channel mentions bonus (popular = more likely to move)
    mentions = data.get("channel_mentions", 0)
    if mentions >= 5:
        boost += 10
        reasons.append(f"ch×{mentions}")
    elif mentions >= 3:
        boost += 5
        reasons.append(f"ch×{mentions}")

    # Historical win rate bonus
    wr = data.get("win_rate", -1)
    if wr >= 70:
        boost += 10
        reasons.append(f"WR{wr:.0f}%")
    elif wr >= 50:
        boost += 5
        reasons.append(f"WR{wr:.0f}%")
    elif 0 <= wr < 30:
        boost -= 10
        reasons.append(f"⚠WR{wr:.0f}%")

    return boost, reasons


# ══════════════════════════════════════════════════════════════
# SIGNAL DETECTION
# ══════════════════════════════════════════════════════════════

@dataclass
class Signal:
    symbol: str
    price: float
    rsi: float
    rsi_prev: float
    ema_trend: str       # "up" or "down"
    volume_ratio: float
    score: float         # 0-100
    reason: str


def analyze_symbol(symbol: str) -> Signal | None:
    candles_15m = fetch_klines(symbol, KLINE_TIMEFRAME, 100)
    if not candles_15m or len(candles_15m) < 30:
        return None

    candles_1h = fetch_klines(symbol, TREND_TIMEFRAME, 50)
    if not candles_1h or len(candles_1h) < 25:
        return None

    closes_15m = [c["close"] for c in candles_15m]
    closes_1h = [c["close"] for c in candles_1h]

    # RSI on 15m
    rsi_vals = compute_rsi(closes_15m, 14)
    if len(rsi_vals) < 3:
        return None
    rsi_now = rsi_vals[-1]
    rsi_prev = rsi_vals[-2]

    # EMA trend on 1h (EMA9 vs EMA21)
    ema9 = compute_ema(closes_1h, 9)
    ema21 = compute_ema(closes_1h, 21)
    if not ema9 or not ema21:
        return None
    trend = "up" if ema9[-1] > ema21[-1] else "down"

    # Volume ratio (current vs 20-period avg)
    vol_r = volume_ratio(candles_15m)

    # ATR for volatility filter
    atr = compute_atr(candles_15m, 14)
    price = closes_15m[-1]
    atr_pct = (atr / price * 100) if price > 0 else 0

    has_volume = vol_r >= MIN_VOLUME_SPIKE

    # EMA crossover on 15m (short-term momentum shift)
    ema9_15m = compute_ema(closes_15m, 9)
    ema21_15m = compute_ema(closes_15m, 21)
    ema_cross_up = False
    if len(ema9_15m) >= 2 and len(ema21_15m) >= 2:
        ema_cross_up = ema9_15m[-1] > ema21_15m[-1] and ema9_15m[-2] <= ema21_15m[-2]

    # Price bounce from recent low
    recent_low = min(c["low"] for c in candles_15m[-12:])
    recent_high = max(c["high"] for c in candles_15m[-12:])
    price_range = (recent_high - recent_low) / recent_low * 100 if recent_low > 0 else 0
    near_low = (price - recent_low) / recent_low * 100 < 1.0 if recent_low > 0 else False
    bouncing_from_low = near_low and price > candles_15m[-2]["close"]

    # ── 3 ENTRY STRATEGIES ──
    strategy = None
    score = 0.0
    reason_parts = []

    # Strategy 1: RSI Bounce (original — relaxed to 40)
    rsi_bounce = rsi_now > rsi_prev and rsi_prev <= RSI_OVERSOLD
    rsi_cross_up = rsi_now > RSI_OVERSOLD and rsi_prev <= RSI_OVERSOLD
    if rsi_bounce or rsi_cross_up:
        strategy = "RSI"
        score = 55.0
        rsi_depth = max(0, RSI_OVERSOLD - rsi_prev)
        score += min(rsi_depth * 2, 15)
        bounce_speed = rsi_now - rsi_prev
        score += min(bounce_speed * 2, 10)
        if rsi_bounce:
            reason_parts.append(f"RSI bounce {rsi_prev:.0f}→{rsi_now:.0f}")
        else:
            reason_parts.append(f"RSI cross {rsi_now:.0f}")

    # Strategy 2: EMA Crossover + Volume (momentum entry)
    elif ema_cross_up and has_volume:
        strategy = "EMA_CROSS"
        score = 55.0
        score += min(vol_r * 3, 10)
        reason_parts.append(f"EMA9×EMA21 cross")

    # Strategy 3: Bounce from support + uptrend
    elif bouncing_from_low and trend == "up" and price_range >= 2.0:
        strategy = "SUPPORT"
        score = 52.0
        score += min(price_range * 2, 10)
        reason_parts.append(f"support bounce ({price_range:.1f}% range)")

    # Strategy 4: Momentum Breakout (works in bullish markets)
    # Price breaks above 3h high OR 3 green candles, RSI 45-68
    elif trend == "up" and 45 <= rsi_now <= 68:
        high_3h = max(c["high"] for c in candles_15m[-12:])
        prev_high = max(c["high"] for c in candles_15m[-24:-12]) if len(candles_15m) >= 24 else high_3h
        breakout = price >= high_3h * 0.999 and high_3h > prev_high
        green_run = all(candles_15m[-(i+1)]["close"] > candles_15m[-(i+1)]["open"]
                       for i in range(3)) if len(candles_15m) >= 3 else False
        if (breakout and vol_r >= 1.0) or (green_run and trend == "up"):
            strategy = "MOMENTUM"
            score = 52.0
            score += min((vol_r - 1) * 8, 12)
            if breakout:
                reason_parts.append(f"breakout high")
            if green_run:
                reason_parts.append(f"3x green")

    # Strategy 5: Pullback in Uptrend (most common pattern in bull market)
    # Uptrend + RSI in 38-55 zone + (turning up OR last candle green)
    elif trend == "up" and 38 <= rsi_now <= 55:
        pullback_depth = 60 - rsi_now
        last_green = candles_15m[-1]["close"] > candles_15m[-1]["open"]
        rsi_turning = rsi_now > rsi_prev
        if pullback_depth >= 5 and (rsi_turning or last_green):
            strategy = "PULLBACK"
            score = 50.0
            score += min(pullback_depth * 1.5, 15)
            if rsi_turning:
                score += 3
            if last_green:
                score += 3
            if vol_r >= 1.2:
                score += 5
            reason_parts.append(f"pullback RSI {rsi_now:.0f} in uptrend"
                              + (" ↑" if rsi_turning else " 🟢candle"))

    if strategy is None:
        return None

    # Block strong downtrend for all strategies
    if trend == "down" and rsi_now < 30:
        return None

    # ── COMMON SCORING ──
    if trend == "up":
        score += 12
        reason_parts.append("uptrend")
    else:
        score -= 5

    if has_volume:
        score += min(vol_r * 4, 12)
        reason_parts.append(f"vol×{vol_r:.1f}")

    if atr_pct >= 0.3:
        score += min(atr_pct * 3, 10)

    # Cross-bot intelligence bonus
    intel_boost, intel_reasons = get_intel_boost(symbol)
    score += intel_boost
    if intel_reasons:
        reason_parts.extend(intel_reasons)

    if score < 58:
        return None

    return Signal(
        symbol=symbol,
        price=price,
        rsi=rsi_now,
        rsi_prev=rsi_prev,
        ema_trend=trend,
        volume_ratio=vol_r,
        score=min(score, 95),
        reason=" | ".join(reason_parts),
    )


# ══════════════════════════════════════════════════════════════
# BYBIT EXECUTION
# ══════════════════════════════════════════════════════════════

def bybit_signed_get(path: str, params: str) -> dict | None:
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
        logger.error("Bybit GET %s: %s", path, e)
        return None


def bybit_signed_post(params: dict) -> dict | None:
    ts = str(int(time.time() * 1000))
    recv = "5000"
    body = json.dumps(params)
    sign_str = f"{ts}{BYBIT_KEY}{recv}{body}"
    sig = hmac.new(BYBIT_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    url = "https://api.bybit.com/v5/order/create"
    try:
        req = urllib.request.Request(url, data=body.encode(), headers={
            "Content-Type": "application/json",
            "X-BAPI-API-KEY": BYBIT_KEY,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv,
            "X-BAPI-SIGN": sig,
        }, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.error("Bybit POST: %s", e)
        return None


def place_buy(symbol: str, usdt_amount: float, price: float) -> bool:
    if PAPER_MODE:
        logger.info("📝 PAPER BUY %s — $%.2f @ %.6f", symbol, usdt_amount, price)
        return True

    qty = usdt_amount / price
    # Round to appropriate precision
    if price > 100:
        qty = round(qty, 4)
    elif price > 1:
        qty = round(qty, 2)
    else:
        qty = round(qty, 0)

    result = bybit_signed_post({
        "category": "spot",
        "symbol": symbol,
        "side": "Buy",
        "orderType": "Market",
        "qty": str(qty),
        "marketUnit": "baseCoin",
    })
    if result and result.get("retCode") == 0:
        logger.info("✅ BUY %s — $%.2f @ %.6f", symbol, usdt_amount, price)
        return True
    logger.error("❌ BUY failed %s: %s", symbol, result)
    return False


def place_sell(symbol: str, qty: float) -> bool:
    if PAPER_MODE:
        logger.info("📝 PAPER SELL %s — qty %.6f", symbol, qty)
        return True

    if qty > 100:
        qty = round(qty, 2)
    elif qty > 1:
        qty = round(qty, 4)
    else:
        qty = round(qty, 6)

    result = bybit_signed_post({
        "category": "spot",
        "symbol": symbol,
        "side": "Sell",
        "orderType": "Market",
        "qty": str(qty),
        "marketUnit": "baseCoin",
    })
    if result and result.get("retCode") == 0:
        logger.info("✅ SELL %s — qty %.6f", symbol, qty)
        return True
    logger.error("❌ SELL failed %s: %s", symbol, result)
    return False


# ══════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════

@dataclass
class Position:
    symbol: str
    entry_price: float
    qty: float
    usdt_size: float
    tp_price: float
    sl_price: float
    highest_price: float
    trailing_active: bool
    opened_at: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class DayState:
    positions: dict = field(default_factory=dict)   # symbol → Position dict
    daily_trades: int = 0
    daily_pnl: float = 0.0
    daily_date: str = ""
    total_pnl: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    history: list = field(default_factory=list)
    mode: str = "PAPER"
    # Self-learning memory
    memory: dict = field(default_factory=dict)       # symbol → learning data
    hour_stats: dict = field(default_factory=dict)   # hour → {wins, losses, pnl}
    streak: dict = field(default_factory=dict)       # symbol → consecutive losses

    def to_dict(self) -> dict:
        return asdict(self)


def load_state() -> DayState:
    if STATE_FILE.exists():
        try:
            raw = json.loads(STATE_FILE.read_text())
            st = DayState()
            for k, v in raw.items():
                if hasattr(st, k):
                    setattr(st, k, v)
            return st
        except Exception:
            pass
    return DayState()


def save_state(st: DayState):
    STATE_FILE.write_text(json.dumps(st.to_dict(), indent=2, default=str))


def roll_day(st: DayState):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if st.daily_date != today:
        if st.daily_date and (st.daily_trades > 0):
            notify(f"📊 Day Trading Daily | trades: {st.daily_trades} | "
                   f"PnL: ${st.daily_pnl:+.2f} | W/L: {st.wins}/{st.losses}")
        st.daily_date = today
        st.daily_trades = 0
        st.daily_pnl = 0.0


# ══════════════════════════════════════════════════════════════
# SELF-LEARNING ENGINE
# ══════════════════════════════════════════════════════════════

def learn_from_trade(st: DayState, symbol: str, pnl_pct: float, pnl_usd: float,
                     reason: str, held_min: int):
    sym = symbol.replace("USDT", "")
    hour = datetime.now(timezone.utc).hour

    # Per-symbol memory
    if sym not in st.memory:
        st.memory[sym] = {"wins": 0, "losses": 0, "total_pnl": 0.0,
                          "avg_pnl": 0.0, "trades": 0, "best_pnl": 0.0,
                          "worst_pnl": 0.0, "avg_hold_min": 0}
    m = st.memory[sym]
    m["trades"] += 1
    m["total_pnl"] = round(m["total_pnl"] + pnl_pct, 2)
    m["avg_pnl"] = round(m["total_pnl"] / m["trades"], 2)
    m["avg_hold_min"] = int((m["avg_hold_min"] * (m["trades"] - 1) + held_min) / m["trades"])
    if pnl_pct > m["best_pnl"]:
        m["best_pnl"] = round(pnl_pct, 2)
    if pnl_pct < m["worst_pnl"]:
        m["worst_pnl"] = round(pnl_pct, 2)
    if pnl_usd >= 0:
        m["wins"] += 1
        st.streak[sym] = 0
    else:
        m["losses"] += 1
        st.streak[sym] = st.streak.get(sym, 0) + 1

    # Per-hour stats
    h = str(hour)
    if h not in st.hour_stats:
        st.hour_stats[h] = {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0}
    hs = st.hour_stats[h]
    hs["trades"] += 1
    hs["pnl"] = round(hs["pnl"] + pnl_usd, 2)
    if pnl_usd >= 0:
        hs["wins"] += 1
    else:
        hs["losses"] += 1


def get_memory_boost(st: DayState, symbol: str) -> tuple[float, list[str]]:
    sym = symbol.replace("USDT", "")
    boost = 0.0
    reasons = []

    # Per-symbol learning
    m = st.memory.get(sym)
    if m and m["trades"] >= 3:
        wr = m["wins"] / m["trades"] * 100
        if wr >= 70:
            boost += 10
            reasons.append(f"myWR{wr:.0f}%")
        elif wr >= 50:
            boost += 5
            reasons.append(f"myWR{wr:.0f}%")
        elif wr < 30:
            boost -= 15
            reasons.append(f"⚠myWR{wr:.0f}%")

        if m["avg_pnl"] > 2:
            boost += 5
            reasons.append(f"avgPnL+{m['avg_pnl']:.1f}%")
        elif m["avg_pnl"] < -2:
            boost -= 10
            reasons.append(f"⚠avgPnL{m['avg_pnl']:.1f}%")

    # Streak penalty (3+ consecutive losses = avoid)
    streak = st.streak.get(sym, 0)
    if streak >= 3:
        boost -= 20
        reasons.append(f"⛔streak{streak}")
    elif streak >= 2:
        boost -= 10
        reasons.append(f"⚠streak{streak}")

    # Hour-based learning
    hour = str(datetime.now(timezone.utc).hour)
    hs = st.hour_stats.get(hour)
    if hs and hs["trades"] >= 5:
        hour_wr = hs["wins"] / hs["trades"] * 100
        if hour_wr >= 70:
            boost += 5
            reasons.append(f"goodHour")
        elif hour_wr < 30:
            boost -= 10
            reasons.append(f"⚠badHour")

    return boost, reasons


# ══════════════════════════════════════════════════════════════
# POSITION MANAGEMENT
# ══════════════════════════════════════════════════════════════

def check_exits(st: DayState):
    to_close = []
    now = datetime.now(timezone.utc)

    for sym, pos_dict in list(st.positions.items()):
        pos = Position.from_dict(pos_dict)
        price = fetch_price(sym)
        if price is None:
            continue

        pnl_pct = (price - pos.entry_price) / pos.entry_price * 100
        pnl_usd = pos.usdt_size * pnl_pct / 100

        # Update highest price for trailing
        if price > pos.highest_price:
            pos.highest_price = price
            pos.trailing_active = pnl_pct >= TRAILING_ACTIVATE
            st.positions[sym] = pos.to_dict()

        exit_reason = None

        # Take profit
        if price >= pos.tp_price:
            exit_reason = "TP"

        # Trailing stop (activated after TRAILING_ACTIVATE%)
        elif pos.trailing_active:
            trail_price = pos.highest_price * (1 - TRAILING_PCT / 100)
            if price <= trail_price:
                exit_reason = "TRAIL"

        # Stop loss
        elif price <= pos.sl_price:
            exit_reason = "SL"

        # Time expiry
        else:
            opened = datetime.fromisoformat(pos.opened_at)
            if (now - opened).total_seconds() > MAX_HOLD_HOURS * 3600:
                exit_reason = "EXPIRED"

        if exit_reason:
            to_close.append((sym, pos, price, pnl_pct, pnl_usd, exit_reason))

    for sym, pos, price, pnl_pct, pnl_usd, reason in to_close:
        sell_qty = pos.qty * 0.998  # account for exchange fees on buy
        success = place_sell(sym, sell_qty) if not PAPER_MODE else True
        if success or PAPER_MODE:
            del st.positions[sym]
            st.daily_pnl += pnl_usd
            st.total_pnl += pnl_usd
            st.total_trades += 1
            if pnl_usd >= 0:
                st.wins += 1
            else:
                st.losses += 1

            icon = "🟢" if pnl_usd >= 0 else "🔴"
            notify(f"{icon} CLOSE {sym} [{reason}]\n"
                   f"Entry: {pos.entry_price:.6f} → Exit: {price:.6f}\n"
                   f"PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})\n"
                   f"Daily: ${st.daily_pnl:+.2f}")

            held_min = int((datetime.now(timezone.utc) -
                           datetime.fromisoformat(pos.opened_at)).total_seconds() / 60)
            st.history.append({
                "symbol": sym,
                "entry": pos.entry_price,
                "exit": price,
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usd": round(pnl_usd, 2),
                "reason": reason,
                "held_min": held_min,
                "closed_at": now.isoformat(),
            })
            if len(st.history) > 200:
                st.history = st.history[-200:]

            # Learn from this trade
            learn_from_trade(st, sym, pnl_pct, pnl_usd, reason, held_min)

    save_state(st)


def open_position(st: DayState, signal: Signal):
    if signal.symbol in st.positions:
        return

    if len(st.positions) >= MAX_POSITIONS:
        return

    if st.daily_pnl <= -MAX_DAILY_LOSS:
        logger.info("Daily loss limit reached: $%.2f", st.daily_pnl)
        return

    balance = fetch_balance()
    size = min(TRADE_SIZE_USDT, balance * 0.95)
    if size < 5:
        logger.info("Insufficient balance: $%.2f", balance)
        return

    price = signal.price
    tp_price = price * (1 + TAKE_PROFIT_PCT / 100)
    sl_price = price * (1 - STOP_LOSS_PCT / 100)
    qty = size / price

    success = place_buy(signal.symbol, size, price)
    if not success:
        return

    pos = Position(
        symbol=signal.symbol,
        entry_price=price,
        qty=qty,
        usdt_size=size,
        tp_price=tp_price,
        sl_price=sl_price,
        highest_price=price,
        trailing_active=False,
        opened_at=datetime.now(timezone.utc).isoformat(),
        reason=signal.reason,
    )

    st.positions[signal.symbol] = pos.to_dict()
    st.daily_trades += 1

    notify(f"🔵 OPEN {signal.symbol}\n"
           f"Price: {price:.6f} | Size: ${size:.2f}\n"
           f"TP: {tp_price:.6f} (+{TAKE_PROFIT_PCT}%) | SL: {sl_price:.6f} (-{STOP_LOSS_PCT}%)\n"
           f"Score: {signal.score:.0f} | {signal.reason}")

    save_state(st)


# ══════════════════════════════════════════════════════════════
# SCAN CYCLE
# ══════════════════════════════════════════════════════════════

def scan_markets(st: DayState) -> list[Signal]:
    signals = []
    for symbol in WATCHLIST:
        if symbol in st.positions:
            continue
        try:
            sig = analyze_symbol(symbol)
            if sig:
                # Apply self-learning boost
                mem_boost, mem_reasons = get_memory_boost(st, symbol)
                sig.score = min(sig.score + mem_boost, 99)
                if mem_reasons:
                    sig.reason += " | " + " ".join(mem_reasons)
                # Skip if memory says avoid (score dropped below threshold)
                if sig.score >= 55:
                    signals.append(sig)
        except Exception as e:
            logger.debug("Error analyzing %s: %s", symbol, e)
        time.sleep(0.3)

    signals.sort(key=lambda s: s.score, reverse=True)
    return signals


_cycle_count = 0

def run_cycle(st: DayState):
    global _cycle_count
    _cycle_count += 1
    roll_day(st)

    # Check exits first
    if st.positions:
        check_exits(st)

    # Check risk limits
    if st.daily_pnl <= -MAX_DAILY_LOSS:
        logger.info("⛔ Daily loss limit ($%.2f) — paused", st.daily_pnl)
        return
    if len(st.positions) >= MAX_POSITIONS:
        if _cycle_count % 12 == 0:
            logger.info("⏸ Max positions (%d/%d) — waiting for exit", len(st.positions), MAX_POSITIONS)
        return

    # Scan for new entries
    signals = scan_markets(st)

    if signals:
        logger.info("📡 Found %d signals — best: %s (score %.0f)",
                     len(signals), signals[0].symbol, signals[0].score)

    # Take best signals (max 2 new entries per cycle)
    for sig in signals[:2]:
        if len(st.positions) >= MAX_POSITIONS:
            break
        open_position(st, sig)

    # Healthcheck every 30 min (6 cycles × 5 min)
    if _cycle_count % 6 == 0:
        pos_info = f"{len(st.positions)}/{MAX_POSITIONS} positions"
        logger.info("💓 Cycle %d | %s | trades today: %d | PnL: $%.2f",
                     _cycle_count, pos_info, st.daily_trades, st.daily_pnl)


# ══════════════════════════════════════════════════════════════
# BACKTEST (simplified)
# ══════════════════════════════════════════════════════════════

def backtest():
    logger.info("═══ BACKTEST MODE ═══")
    results = {"wins": 0, "losses": 0, "pnl": 0.0, "trades": []}

    for symbol in WATCHLIST[:10]:
        candles = fetch_klines(symbol, "15", 200)
        if not candles or len(candles) < 50:
            continue

        closes = [c["close"] for c in candles]
        rsi_vals = compute_rsi(closes, 14)
        if len(rsi_vals) < 30:
            continue

        # Simulate: find RSI bounce entries
        for i in range(20, len(rsi_vals) - 10):
            if rsi_vals[i] > RSI_OVERSOLD and rsi_vals[i - 1] <= RSI_OVERSOLD:
                entry = closes[i]
                tp = entry * (1 + TAKE_PROFIT_PCT / 100)
                sl = entry * (1 - STOP_LOSS_PCT / 100)

                # Check next 10 candles for outcome
                for j in range(i + 1, min(i + 48, len(candles))):
                    high = candles[j]["high"]
                    low = candles[j]["low"]
                    if high >= tp:
                        results["wins"] += 1
                        results["pnl"] += TAKE_PROFIT_PCT
                        results["trades"].append({"sym": symbol, "pnl": TAKE_PROFIT_PCT})
                        break
                    elif low <= sl:
                        results["losses"] += 1
                        results["pnl"] -= STOP_LOSS_PCT
                        results["trades"].append({"sym": symbol, "pnl": -STOP_LOSS_PCT})
                        break
                else:
                    # Expired — use last close
                    final = closes[min(i + 47, len(closes) - 1)]
                    pnl = (final - entry) / entry * 100
                    if pnl > 0:
                        results["wins"] += 1
                    else:
                        results["losses"] += 1
                    results["pnl"] += pnl
                    results["trades"].append({"sym": symbol, "pnl": round(pnl, 2)})

        time.sleep(0.3)

    total = results["wins"] + results["losses"]
    if total == 0:
        logger.info("No trades found in backtest period")
        return

    wr = results["wins"] / total * 100
    avg_pnl = results["pnl"] / total
    logger.info("═══ BACKTEST RESULTS ═══")
    logger.info("Trades: %d | Win Rate: %.1f%% | Total PnL: %.2f%%", total, wr, results["pnl"])
    logger.info("Avg PnL/trade: %.2f%% | Wins: %d | Losses: %d",
                avg_pnl, results["wins"], results["losses"])

    if results["pnl"] > 0:
        logger.info("✅ Strategy is PROFITABLE (%.1f%% expected per trade)", avg_pnl)
    else:
        logger.info("⚠️ Strategy needs tuning (%.1f%% expected per trade)", avg_pnl)

    # Expectancy
    if results["wins"] > 0:
        avg_win = sum(t["pnl"] for t in results["trades"] if t["pnl"] > 0) / results["wins"]
    else:
        avg_win = 0
    if results["losses"] > 0:
        avg_loss = sum(t["pnl"] for t in results["trades"] if t["pnl"] < 0) / results["losses"]
    else:
        avg_loss = 0
    expectancy = (wr / 100 * avg_win) + ((1 - wr / 100) * avg_loss)
    logger.info("Expectancy: %.2f%% per trade | Avg Win: %.2f%% | Avg Loss: %.2f%%",
                expectancy, avg_win, avg_loss)


# ══════════════════════════════════════════════════════════════
# STATUS DISPLAY
# ══════════════════════════════════════════════════════════════

def show_status():
    st = load_state()
    print(f"\n{'═' * 50}")
    print(f"  DAY TRADING BOT STATUS")
    print(f"{'═' * 50}")
    print(f"  Mode: {st.mode}")
    print(f"  Daily PnL: ${st.daily_pnl:+.2f} | Total PnL: ${st.total_pnl:+.2f}")
    print(f"  Today's trades: {st.daily_trades} (unlimited)")
    print(f"  Win/Loss: {st.wins}/{st.losses} "
          f"({st.wins / max(st.wins + st.losses, 1) * 100:.0f}% WR)")
    print(f"\n  Open Positions ({len(st.positions)}/{MAX_POSITIONS}):")
    print(f"  {'─' * 46}")

    for sym, pos_dict in st.positions.items():
        pos = Position.from_dict(pos_dict)
        price = fetch_price(sym)
        if price:
            pnl_pct = (price - pos.entry_price) / pos.entry_price * 100
            icon = "🟢" if pnl_pct >= 0 else "🔴"
            print(f"  {icon} {sym:12s} | entry: {pos.entry_price:.5f} | "
                  f"now: {price:.5f} | {pnl_pct:+.2f}%")
        else:
            print(f"  ⚪ {sym:12s} | entry: {pos.entry_price:.5f} | price: N/A")

    if st.history:
        print(f"\n  Last 5 Trades:")
        print(f"  {'─' * 46}")
        for trade in st.history[-5:]:
            icon = "🟢" if trade["pnl_usd"] >= 0 else "🔴"
            print(f"  {icon} {trade['symbol']:12s} | {trade['pnl_pct']:+.2f}% "
                  f"(${trade['pnl_usd']:+.2f}) | {trade['reason']} | "
                  f"{trade['held_min']}min")

    if st.memory:
        print(f"\n  🧠 Memory ({len(st.memory)} coins learned):")
        print(f"  {'─' * 46}")
        sorted_mem = sorted(st.memory.items(),
                            key=lambda x: x[1].get("trades", 0), reverse=True)
        for sym, m in sorted_mem[:10]:
            wr = m["wins"] / max(m["trades"], 1) * 100
            streak = st.streak.get(sym, 0)
            streak_txt = f" | streak: {streak}❌" if streak >= 2 else ""
            print(f"  {sym:8s} | {m['trades']} trades | WR: {wr:.0f}% | "
                  f"avg: {m['avg_pnl']:+.1f}%{streak_txt}")

    if st.hour_stats:
        best_hours = sorted(st.hour_stats.items(),
                            key=lambda x: x[1].get("pnl", 0), reverse=True)
        good = [h for h, d in best_hours if d.get("pnl", 0) > 0]
        bad = [h for h, d in best_hours if d.get("pnl", 0) < 0]
        if good:
            print(f"\n  ⏰ Best hours (UTC): {', '.join(good[:5])}")
        if bad:
            print(f"  ⏰ Worst hours (UTC): {', '.join(bad[:3])}")

    print(f"{'═' * 50}\n")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    global PAPER_MODE

    parser = argparse.ArgumentParser(description="Day Trading Bot (Bybit Spot)")
    parser.add_argument("--live", action="store_true", help="Enable live trading")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--backtest", action="store_true", help="Run backtest")
    parser.add_argument("--scan", action="store_true", help="Scan once and show signals")
    args = parser.parse_args()

    if args.live:
        PAPER_MODE = False
        if not BYBIT_KEY or not BYBIT_SECRET:
            logger.error("Missing BYBIT_API_KEY/SECRET in env")
            sys.exit(1)

    if args.status:
        show_status()
        return

    if args.backtest:
        backtest()
        return

    if args.scan:
        print(f"\n{'═' * 60}")
        print(f"  SCANNING {len(WATCHLIST)} COINS (5 strategies)...")
        print(f"{'═' * 60}")
        print(f"\n  📊 Market Overview:")
        print(f"  {'─' * 56}")
        for sym in WATCHLIST:
            candles_15m = fetch_klines(sym, "15", 100)
            candles_1h = fetch_klines(sym, "60", 50)
            if not candles_15m or len(candles_15m) < 25:
                continue
            closes_15m = [c["close"] for c in candles_15m]
            rsi_vals = compute_rsi(closes_15m, 14)
            if not rsi_vals or len(rsi_vals) < 2:
                continue
            rsi = rsi_vals[-1]
            rsi_p = rsi_vals[-2]
            vol_r = volume_ratio(candles_15m)
            # trend
            tr = "?"
            if candles_1h and len(candles_1h) >= 25:
                c1h = [c["close"] for c in candles_1h]
                e9 = compute_ema(c1h, 9)
                e21 = compute_ema(c1h, 21)
                if e9 and e21:
                    tr = "↑" if e9[-1] > e21[-1] else "↓"
            rsi_dir = "↑" if rsi > rsi_p else "↓"
            icon = "🟢" if rsi <= RSI_OVERSOLD else "⚪" if rsi <= 50 else "🔴"
            note = ""
            if rsi <= RSI_OVERSOLD and rsi > rsi_p:
                note = " ← RSI bounce!"
            elif tr == "↑" and 42 <= rsi <= 55 and rsi > rsi_p:
                note = " ← pullback candidate"
            elif vol_r >= 1.3 and tr == "↑":
                note = " ← volume spike"
            print(f"  {icon} {sym:12s} RSI:{rsi:5.1f}{rsi_dir} | vol:×{vol_r:.1f} | "
                  f"trend:{tr}{note}")
            time.sleep(0.15)
        print()
        st = load_state()
        signals = scan_markets(st)
        if not signals:
            print("  ❌ No signals found — conditions not met")
        else:
            print(f"  ✅ Found {len(signals)} signal(s):\n")
            for i, sig in enumerate(signals, 1):
                print(f"  {i}. {sig.symbol:12s} | score: {sig.score:.0f} | "
                      f"RSI: {sig.rsi:.1f} | trend: {sig.ema_trend} | "
                      f"vol: ×{sig.volume_ratio:.1f}")
                print(f"     price: {sig.price:.6f} | {sig.reason}")
                print(f"     TP: {sig.price * (1 + TAKE_PROFIT_PCT/100):.6f} (+{TAKE_PROFIT_PCT}%) | "
                      f"SL: {sig.price * (1 - STOP_LOSS_PCT/100):.6f} (-{STOP_LOSS_PCT}%)")
                print()
        intel = load_bot_intel()
        if intel:
            print(f"  📊 Cross-bot intel loaded: {len(intel)} coins with data")
        print(f"{'═' * 55}\n")
        return

    # Main trading loop
    mode = "LIVE" if not PAPER_MODE else "PAPER"
    notify(f"🚀 Day Trading Bot Started [{mode}]\n"
           f"Strategy: RSI Bounce + EMA Trend\n"
           f"TP: {TAKE_PROFIT_PCT}% | SL: {STOP_LOSS_PCT}% | Trail: {TRAILING_PCT}%\n"
           f"Size: ${TRADE_SIZE_USDT} | Max: {MAX_POSITIONS} positions\n"
           f"Watchlist: {len(WATCHLIST)} coins")

    st = load_state()
    st.mode = mode
    save_state(st)

    while True:
        try:
            run_cycle(st)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            save_state(st)
            break
        except Exception as e:
            logger.error("Cycle error: %s", e)

        time.sleep(SCAN_INTERVAL_SEC)


if __name__ == "__main__":
    main()
