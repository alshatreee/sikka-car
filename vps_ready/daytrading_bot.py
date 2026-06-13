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
import argparse, fcntl, json, hashlib, hmac, logging, os, signal, sys, time, statistics
import urllib.request
from dataclasses import dataclass, field, asdict
from decimal import Decimal
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
            with open(f, encoding="utf-8") as fh:
                for line in fh:
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
TRADE_SIZE_PCT     = float(ENV.get("DT_TRADE_SIZE_PCT", "15"))
MIN_TRADE_USDT     = float(ENV.get("DT_MIN_TRADE", "20.0"))
MAX_POSITIONS      = int(ENV.get("DT_MAX_POSITIONS", "5"))
MAX_DAILY_LOSS     = float(ENV.get("DT_MAX_LOSS", "50.0"))

# Cross-bot intelligence files
ML_RECS_FILE       = BASE_DIR / "ml_recommendations.json"
CHANNEL_MEM_FILE   = BASE_DIR / "channel_memory.json"
SIGNAL_TRACKER     = BASE_DIR / "signal_tracker.json"
AI_ANALYSIS_FILE   = BASE_DIR / "ai_channel_analysis.json"

# Entry: RSI bounce from oversold
RSI_OVERSOLD       = float(ENV.get("DT_RSI_OVERSOLD", "35"))
RSI_BOUNCE_MIN     = float(ENV.get("DT_RSI_BOUNCE", "3"))
MIN_VOLUME_SPIKE   = float(ENV.get("DT_VOL_SPIKE", "1.3"))

# Exit targets (tight for day trading)
TAKE_PROFIT_PCT    = float(ENV.get("DT_TP_PCT", "3.0"))
# SL must stay below TP: risking 2 to make 3 breaks even at 40% win rate
STOP_LOSS_PCT      = float(ENV.get("DT_SL_PCT", "2.0"))
TRAILING_ACTIVATE  = float(ENV.get("DT_TRAIL_ACT", "1.5"))
TRAILING_PCT       = float(ENV.get("DT_TRAIL_PCT", "0.8"))
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
    except Exception as e:
        logger.debug("Telegram notify error: %s", e)


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


def _safe_float(val, default=0.0) -> float:
    if not val or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def fetch_balance() -> float:
    if PAPER_MODE:
        return 999.0
    data = bybit_signed_get("/v5/account/wallet-balance", "accountType=UNIFIED")
    if not data or data.get("retCode") != 0:
        logger.debug("Balance API failed: %s", data)
        return 0.0
    coins = data.get("result", {}).get("list", [{}])[0].get("coin", [])
    for c in coins:
        if c.get("coin") == "USDT":
            for field in ("availableToWithdraw", "walletBalance", "equity"):
                val = _safe_float(c.get(field))
                if val > 0:
                    return val
            return 0.0
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
                    def _safe_float(v, default=0.0):
                        try:
                            return float(v) if v != "" else default
                        except (ValueError, TypeError):
                            return default
                    intel[sym_upper] = {
                        "ml_profit": _safe_float(data.get("max_profit_pct", data.get("entry_saving_pct", 0))),
                        "ml_drawdown": abs(_safe_float(data.get("max_drawdown_pct", 0))),
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

    # AI channel analysis (Cerebras via bot_monitor)
    if AI_ANALYSIS_FILE.exists():
        try:
            ai = json.loads(AI_ANALYSIS_FILE.read_text())
            for sig in ai.get("buy", []):
                sym = sig.get("symbol", "").upper().replace("USDT", "")
                if sym:
                    if sym not in intel:
                        intel[sym] = {}
                    conf = sig.get("confidence", "low")
                    intel[sym]["ai_buy"] = {"high": 3, "medium": 2, "low": 1}.get(conf, 1)
                    intel[sym]["ai_reason"] = sig.get("reason", "")
            for sig in ai.get("sell", []):
                sym = sig.get("symbol", "").upper().replace("USDT", "")
                if sym:
                    if sym not in intel:
                        intel[sym] = {}
                    intel[sym]["ai_sell"] = True
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

    # AI analysis boost (from Cerebras via bot_monitor)
    ai_buy = data.get("ai_buy", 0)
    if ai_buy >= 3:
        boost += 12
        reasons.append(f"AI🟢high")
    elif ai_buy >= 2:
        boost += 8
        reasons.append(f"AI🟢med")
    elif ai_buy >= 1:
        boost += 4
        reasons.append(f"AI🟢low")
    if data.get("ai_sell"):
        boost -= 15
        reasons.append("AI🔴sell")

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

    # Strategy 1: RSI Bounce — require confirmation (last candle green)
    last_green = candles_15m[-1]["close"] > candles_15m[-1]["open"]
    rsi_bounce = rsi_now > rsi_prev and rsi_prev <= RSI_OVERSOLD
    rsi_cross_up = rsi_now > RSI_OVERSOLD and rsi_prev <= RSI_OVERSOLD
    if (rsi_bounce or rsi_cross_up) and last_green:
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

    # Only trade coins in 1h uptrend — downtrend "bounces" were the
    # main loss source (7 of last 10 trades hit SL within hours)
    if trend != "up":
        return None

    # ── COMMON SCORING ──
    score += 12
    reason_parts.append("uptrend")

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

    if score < 50:
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


def _get_lot_step(symbol: str) -> float:
    data = http_get(f"https://api.bybit.com/v5/market/instruments-info?category=spot&symbol={symbol}")
    if data and data.get("retCode") == 0:
        items = data.get("result", {}).get("list", [])
        if items:
            step = items[0].get("lotSizeFilter", {}).get("basePrecision", "")
            if step:
                try:
                    return float(step)
                except ValueError:
                    pass
    return 0.01


def _round_qty(qty: float, step: float) -> float:
    # Decimal avoids float artifacts like 9.870000000000001 that Bybit
    # rejects with "Order quantity has too many decimals" (retCode 170137)
    d_step = Decimal(str(step))
    return float((Decimal(str(qty)) // d_step) * d_step)


def _qty_str(qty: float) -> str:
    # plain decimal string, never scientific notation, no trailing zeros
    s = format(Decimal(str(qty)), 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


def place_buy(symbol: str, usdt_amount: float, price: float) -> float | None:
    """Buy symbol. Returns actual rounded qty on success, None on failure."""
    if PAPER_MODE:
        step = _get_lot_step(symbol)
        qty = _round_qty(usdt_amount / price, step)
        if qty <= 0:
            logger.error("❌ PAPER BUY %s: qty rounded to 0 (step=%s)", symbol, step)
            return None
        logger.info("📝 PAPER BUY %s — $%.2f @ %.6f (qty=%s)", symbol, usdt_amount, price, qty)
        return qty

    qty = usdt_amount / price
    step = _get_lot_step(symbol)
    qty = _round_qty(qty, step)

    if qty <= 0:
        logger.error("❌ BUY %s: qty rounded to 0 (step=%s)", symbol, step)
        return None

    result = bybit_signed_post({
        "category": "spot",
        "symbol": symbol,
        "side": "Buy",
        "orderType": "Market",
        "qty": _qty_str(qty),
        "marketUnit": "baseCoin",
    })
    if result and result.get("retCode") == 0:
        logger.info("✅ BUY %s — $%.2f @ %.6f (qty=%s step=%s)", symbol, usdt_amount, price, qty, step)
        return qty
    logger.error("❌ BUY failed %s: %s", symbol, result)
    return None


def fetch_coin_balance(symbol: str) -> float:
    """Free (spot-available) balance of a base coin, e.g. 'BTC'. 0.0 on failure."""
    if PAPER_MODE:
        return 0.0
    coin = symbol.upper().replace("USDT", "")
    data = bybit_signed_get("/v5/account/wallet-balance", "accountType=UNIFIED")
    if not data or data.get("retCode") != 0:
        return 0.0
    coins = data.get("result", {}).get("list", [{}])[0].get("coin", [])
    for c in coins:
        if c.get("coin") == coin:
            for field in ("availableToWithdraw", "free", "walletBalance"):
                val = _safe_float(c.get(field))
                if val > 0:
                    return val
            return 0.0
    return 0.0


def place_sell(symbol: str, qty: float) -> bool:
    if PAPER_MODE:
        logger.info("📝 PAPER SELL %s — qty %.6f", symbol, qty)
        return True

    # Cap to the real held balance so the order can't be rejected for trying to
    # sell more than we hold (fees are taken from the base coin on the buy).
    free = fetch_coin_balance(symbol)
    if free > 0:
        qty = min(qty, free)
    step = _get_lot_step(symbol)
    qty = _round_qty(qty, step)

    if qty <= 0:
        logger.error("❌ SELL %s: qty rounded to 0 (step=%s, held=%.8f)", symbol, step, free)
        return False

    result = bybit_signed_post({
        "category": "spot",
        "symbol": symbol,
        "side": "Sell",
        "orderType": "Market",
        "qty": _qty_str(qty),
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
    highest_price: float = 0.0
    trailing_active: bool = False
    opened_at: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        pos = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        if not pos.highest_price:
            pos.highest_price = pos.entry_price
        if not pos.opened_at:
            pos.opened_at = datetime.now(timezone.utc).isoformat()
        return pos


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
    daily_wins: int = 0
    daily_losses: int = 0
    history: list = field(default_factory=list)
    mode: str = "PAPER"
    # Self-learning memory
    memory: dict = field(default_factory=dict)       # symbol → learning data
    hour_stats: dict = field(default_factory=dict)   # hour → {wins, losses, pnl}
    streak: dict = field(default_factory=dict)       # symbol → consecutive losses
    sl_times: list = field(default_factory=list)     # recent stop-loss timestamps (circuit breaker)

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
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(st.to_dict(), indent=2, default=str))
    tmp.replace(STATE_FILE)


def roll_day(st: DayState):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if st.daily_date != today:
        if st.daily_date and (st.daily_trades > 0):
            logger.info(f"📊 Day Trading Daily | trades: {st.daily_trades} | "
                   f"PnL: ${st.daily_pnl:+.2f} | W/L: {st.daily_wins}/{st.daily_losses}")
        st.daily_date = today
        st.daily_trades = 0
        st.daily_pnl = 0.0
        st.daily_wins = 0
        st.daily_losses = 0
        st.streak = {}  # fresh day, clear streak penalties


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

    # Per-symbol learning (activate after just 2 trades)
    m = st.memory.get(sym)
    if m and m["trades"] >= 2:
        wr = m["wins"] / m["trades"] * 100
        if wr >= 70:
            boost += 10
            reasons.append(f"myWR{wr:.0f}%")
        elif wr >= 50:
            boost += 5
            reasons.append(f"myWR{wr:.0f}%")
        elif wr == 0:
            boost -= 25
            reasons.append(f"⛔myWR0%")
        elif wr < 40:
            boost -= 15
            reasons.append(f"⚠myWR{wr:.0f}%")

        if m["avg_pnl"] > 2:
            boost += 5
            reasons.append(f"avgPnL+{m['avg_pnl']:.1f}%")
        elif m["avg_pnl"] < -2:
            boost -= 10
            reasons.append(f"⚠avgPnL{m['avg_pnl']:.1f}%")

    # Streak penalty (consecutive losses = avoid)
    streak = st.streak.get(sym, 0)
    if streak >= 2:
        boost -= 20
        reasons.append(f"⛔streak{streak}")
    elif streak >= 1:
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

_ai_sell_cache = {"ts": 0.0, "syms": set()}

def _ai_says_sell_strong(symbol: str) -> bool:
    """True if bot_monitor's AI flagged this coin as a HIGH-confidence SELL.

    Cached for 120s. Fail-safe: on missing/unreadable data, returns False so a
    transient glitch never force-closes a position.
    """
    now = time.time()
    if now - _ai_sell_cache["ts"] > 120:
        syms = set()
        if AI_ANALYSIS_FILE.exists():
            try:
                ai = json.loads(AI_ANALYSIS_FILE.read_text())
                for s in ai.get("sell", []):
                    conf = str(s.get("confidence", "")).lower().strip()
                    if (conf.startswith("high") or conf.startswith("very high")
                            or conf in ("عالي", "عالية", "عاليه")):
                        syms.add(s.get("symbol", "").upper().replace("USDT", ""))
            except Exception:
                pass
        _ai_sell_cache["syms"] = syms
        _ai_sell_cache["ts"] = now
    return symbol.upper().replace("USDT", "") in _ai_sell_cache["syms"]


def check_exits(st: DayState):
    to_close = []
    now = datetime.now(timezone.utc)

    for sym, pos_dict in list(st.positions.items()):
        try:
            pos = Position.from_dict(pos_dict)
            price = fetch_price(sym)
            if price is None:
                continue

            pnl_pct = (price - pos.entry_price) / pos.entry_price * 100
            pnl_usd = pos.usdt_size * pnl_pct / 100

            # Update highest price for trailing
            if price > pos.highest_price:
                pos.highest_price = price
                st.positions[sym] = pos.to_dict()

            # Activate trailing once profit crosses the threshold — must be
            # outside the new-high block so it triggers even when the price
            # plateaus at or just below the previous high.
            if not pos.trailing_active and pnl_pct >= TRAILING_ACTIVATE:
                pos.trailing_active = True
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
                if opened.tzinfo is None:
                    opened = opened.replace(tzinfo=timezone.utc)
                if (now - opened).total_seconds() > MAX_HOLD_HOURS * 3600:
                    exit_reason = "EXPIRED"

            # AI high-confidence sell — only when no price-based exit fired
            # (TP/SL/TRAIL take precedence). Closing here keeps THIS bot's state
            # consistent instead of bot_monitor selling behind its back.
            if exit_reason is None and _ai_says_sell_strong(sym):
                exit_reason = "AI_SELL"

            if exit_reason:
                to_close.append((sym, pos, price, pnl_pct, pnl_usd, exit_reason))
        except Exception as e:
            logger.error("check_exits error for %s: %s", sym, e)
            continue

    for sym, pos, price, pnl_pct, pnl_usd, reason in to_close:
        # place_sell caps to the real held balance, so pass the full qty
        success = place_sell(sym, pos.qty) if not PAPER_MODE else True
        if not success and not PAPER_MODE:
            # If the real holding is just dust (< $1, below exchange min),
            # abandon the position instead of retrying the same sell forever.
            held = fetch_coin_balance(sym)
            if held * price < 1.0:
                logger.info("🧹 %s holding is dust (%.8f ≈ $%.4f) — abandoning position",
                            sym, held, held * price)
                success = True
        if success or PAPER_MODE:
            del st.positions[sym]
            save_state(st)

            st.daily_pnl += pnl_usd
            st.total_pnl += pnl_usd
            st.total_trades += 1
            if pnl_usd >= 0:
                st.wins += 1
                st.daily_wins += 1
            else:
                st.losses += 1
                st.daily_losses += 1

            if reason == "SL":
                st.sl_times.append(now.isoformat())
                st.sl_times = st.sl_times[-20:]

            icon = "🟢" if pnl_usd >= 0 else "🔴"
            notify(f"{icon} CLOSE {sym} [{reason}]\n"
                   f"Entry: {pos.entry_price:.6f} → Exit: {price:.6f}\n"
                   f"PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})\n"
                   f"Daily: ${st.daily_pnl:+.2f}")

            _opened = datetime.fromisoformat(pos.opened_at)
            if _opened.tzinfo is None:
                _opened = _opened.replace(tzinfo=timezone.utc)
            held_min = int((datetime.now(timezone.utc) - _opened).total_seconds() / 60)
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

            save_state(st)

            # Learn from this trade
            try:
                learn_from_trade(st, sym, pnl_pct, pnl_usd, reason, held_min)
                save_state(st)
            except Exception as e:
                logger.error("learn_from_trade error for %s: %s", sym, e)

    save_state(st)


def open_position(st: DayState, signal: Signal):
    if signal.symbol in st.positions:
        return

    # Don't buy a coin AI strongly flags as a sell — it would be force-closed by
    # AI_SELL next cycle, wasting a buy+sell fee round-trip.
    if _ai_says_sell_strong(signal.symbol):
        logger.info("⛔ %s — AI يوصي بالبيع بثقة عالية، تخطّي الشراء", signal.symbol)
        return

    if len(st.positions) >= MAX_POSITIONS:
        return

    if st.daily_pnl <= -MAX_DAILY_LOSS:
        logger.info("Daily loss limit reached: $%.2f", st.daily_pnl)
        return

    # fetch_balance() returns FREE USDT (already excludes money spent on open
    # positions — those USDT are now held as coins), so 15% of it is naturally
    # self-limiting. MAX_POSITIONS caps total exposure. Do NOT subtract open
    # position sizes here — that would double-count and shrink sizes wrongly.
    balance = fetch_balance()
    size = round(balance * TRADE_SIZE_PCT / 100, 2)
    logger.info("💰 Free USDT: $%.2f | Size: $%.2f (%.0f%%)", balance, size, TRADE_SIZE_PCT)
    if size < MIN_TRADE_USDT:
        logger.info("Size $%.2f < min $%.0f — skip", size, MIN_TRADE_USDT)
        return

    # Use live price for entry, TP/SL — the signal price is a stale candle close
    price = fetch_price(signal.symbol)
    if price is None:
        return
    tp_price = price * (1 + TAKE_PROFIT_PCT / 100)
    sl_price = price * (1 - STOP_LOSS_PCT / 100)

    qty = place_buy(signal.symbol, size, price)
    if qty is None:
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
    save_state(st)

    notify(f"🔵 OPEN {signal.symbol}\n"
           f"Price: {price:.6f} | Size: ${size:.2f}\n"
           f"TP: {tp_price:.6f} (+{TAKE_PROFIT_PCT}%) | SL: {sl_price:.6f} (-{STOP_LOSS_PCT}%)\n"
           f"Score: {signal.score:.0f} | {signal.reason}")


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
                if sig.score >= 62:
                    signals.append(sig)
        except Exception as e:
            logger.debug("Error analyzing %s: %s", symbol, e)
        time.sleep(0.3)

    signals.sort(key=lambda s: s.score, reverse=True)
    return signals


_cycle_count = 0
_shutdown_requested = False

_btc_trend_cache = {"ts": 0.0, "up": True}


def btc_trend_up() -> bool:
    """Market filter: most losses cluster in market-wide drops, so block
    new entries while BTC EMA9 < EMA21 on 1h. Cached 15 min."""
    now = time.time()
    if now - _btc_trend_cache["ts"] < 900:
        return _btc_trend_cache["up"]
    up = _btc_trend_cache["up"]  # keep last known on API failure
    candles = fetch_klines("BTCUSDT", "60", 50)
    if candles and len(candles) >= 25:
        closes = [c["close"] for c in candles]
        e9 = compute_ema(closes, 9)
        e21 = compute_ema(closes, 21)
        if e9 and e21:
            up = e9[-1] > e21[-1]
    _btc_trend_cache["ts"] = now
    _btc_trend_cache["up"] = up
    return up


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

    # Market filter: no new longs while BTC 1h trend is down
    if not btc_trend_up():
        if _cycle_count % 6 == 0:
            logger.info("🌧 BTC 1h downtrend — skipping new entries")
        return

    # Circuit breaker: 3+ stop-losses within 4h = hostile market, pause entries
    now_utc = datetime.now(timezone.utc)
    recent_sl = []
    for t in st.sl_times:
        try:
            ts = datetime.fromisoformat(t)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if (now_utc - ts).total_seconds() < 4 * 3600:
                recent_sl.append(t)
        except Exception:
            continue
    if len(recent_sl) >= 3:
        if _cycle_count % 6 == 0:
            logger.info("🛑 Circuit breaker: %d SLs in 4h — paused until market calms", len(recent_sl))
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

    # Prevent duplicate instances — store handle on module so GC can't release the lock
    global _lock_fh
    _lock_fh = open(BASE_DIR / ".daytrading_bot.lock", "w")
    try:
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        logger.error("❌ نسخة أخرى من daytrading_bot تعمل بالفعل — إيقاف")
        sys.exit(1)

    # Main trading loop
    mode = "LIVE" if not PAPER_MODE else "PAPER"
    logger.info(f"🚀 Day Trading Bot Started [{mode}] PID={os.getpid()}\n"
           f"Strategy: RSI Bounce + EMA Trend\n"
           f"TP: {TAKE_PROFIT_PCT}% | SL: {STOP_LOSS_PCT}% | Trail: {TRAILING_PCT}%\n"
           f"Size: {TRADE_SIZE_PCT}% of balance (min ${MIN_TRADE_USDT}) | Max: {MAX_POSITIONS} positions\n"
           f"Watchlist: {len(WATCHLIST)} coins")

    st = load_state()
    st.mode = mode
    save_state(st)

    def _shutdown(signum, _frame):
        global _shutdown_requested
        _shutdown_requested = True
        logger.info("Signal %s received — saving state and exiting", signum)
        save_state(st)
        sys.exit(0)
    signal.signal(signal.SIGTERM, _shutdown)

    while True:
        try:
            run_cycle(st)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            save_state(st)
            break
        except SystemExit:
            # Honor an intentional shutdown (SIGTERM); only swallow a stray
            # SystemExit raised by library code mid-cycle.
            if _shutdown_requested:
                raise
            logger.error("Unexpected SystemExit inside run_cycle — ignoring")
        except Exception as e:
            import traceback
            logger.error("Cycle error: %s\n%s", e, traceback.format_exc())

        time.sleep(SCAN_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        logger.critical("FATAL: %s", traceback.format_exc())
        raise
