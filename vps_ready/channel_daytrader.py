#!/usr/bin/env python3
"""
channel_daytrader.py — Day Trading Bot Based on Telegram Channel Signals

Monitors Arabic crypto channels for buy signals, enters with tight
profit targets (2-5%), and accumulates small daily gains.

Strategy:
  1. Scan channels every 10 min for new signals (شراء, buy, long, etc.)
  2. Verify signal with quick technical check (RSI not overbought, trend ok)
  3. Buy $50 per trade on Bybit spot
  4. Exit at signal's target or default +3%, stop at -4%
  5. Learn which channels have best win rate, weight signals accordingly

Usage:
    python channel_daytrader.py              # paper mode
    python channel_daytrader.py --live       # real trading
    python channel_daytrader.py --status     # show positions + stats
    python channel_daytrader.py --scan       # scan channels once
"""
from __future__ import annotations
import argparse, json, hashlib, hmac, logging, os, re, sys, time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from telethon.sync import TelegramClient
    _HAS_TELETHON = True
except ImportError:
    _HAS_TELETHON = False

# ── Paths ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE   = BASE_DIR / ".env_monthly"
STATE_FILE = BASE_DIR / "channel_daytrader_state.json"
LOG_FILE   = BASE_DIR / "channel_daytrader.log"
SESSION    = str(BASE_DIR / "channel_dt_session")
RAW_MSGS_FILE = BASE_DIR / "channel_raw_messages.json"

# ── Load env ──
def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

ENV = load_env()
TG_API_ID    = int(ENV.get("TG_API_ID", "0"))
TG_API_HASH  = ENV.get("TG_API_HASH", "")
BYBIT_KEY    = ENV.get("BYBIT_API_KEY", "")
BYBIT_SECRET = ENV.get("BYBIT_API_SECRET", "")
TG_TOKEN     = ENV.get("TELEGRAM_TOKEN", "")
TG_CHAT      = ENV.get("TELEGRAM_CHAT_ID", "")

# ══════════════════════════════════════════════════════════════
# STRATEGY PARAMETERS
# ══════════════════════════════════════════════════════════════

TRADE_SIZE_USDT   = float(ENV.get("CDT_TRADE_SIZE", "50.0"))
MAX_POSITIONS     = int(ENV.get("CDT_MAX_POSITIONS", "5"))
MAX_DAILY_LOSS    = float(ENV.get("CDT_MAX_LOSS", "50.0"))

TAKE_PROFIT_PCT   = float(ENV.get("CDT_TP_PCT", "3.0"))
STOP_LOSS_PCT     = float(ENV.get("CDT_SL_PCT", "4.0"))
MAX_HOLD_HOURS    = int(ENV.get("CDT_MAX_HOLD", "24"))

SCAN_INTERVAL_SEC = int(ENV.get("CDT_SCAN_SEC", "600"))

WATCH_CHANNELS = [
    "cryptomena1", "arabcharts", "crypto_q88",
    "ahmadchats", "Naif_Alert", "vipdrprofit",
]

PAPER_MODE = True

# ── Signal parsing patterns ──

# Buy/bullish keywords (Arabic + transliterated English)
_BUY_RE = re.compile(
    r'شراء|buy|long|صعود|صاعد|دخول|إيجابي|bullish|اختراق|ارتفاع|فرصة'
    r'|بول\s*ران|بول\s*رن|بولش|بولي?ش'              # bull run, bullish
    r'|بامب|بمب|بامبينق|بمبنق'                       # pump, pumping
    r'|بريك\s*أوت|بريك\s*اوت|بريكاوت'               # breakout
    r'|لونق|لونج'                                     # long
    r'|رالي|رالى'                                     # rally
    r'|مون|تو\s*ذا?\s*مون|موون'                      # moon, to the moon
    r'|سبورت|دعم'                                     # support
    r'|ريفرسال|انعكاس'                                # reversal
    r'|ريكفري|تعاف[يى]'                               # recovery
    r'|اكيوميوليت|اكيوملي?ت|تجميع'                    # accumulate
    r'|باي|با[يى]'                                     # buy
    r'|انتري|إنتري'                                    # entry
    r'|سيقنال|سيجنال|إشارة|اشارة'                     # signal
    r'|تريند\s*أب|تريند\s*اب|ترند\s*صاعد'            # trend up
    r'|قاع|قاعين|ارتداد|رجوع',                        # bottom, bounce
    re.I
)

# Bearish — skip these
_SELL_RE = re.compile(
    r'بيع\s*فوري|بيع\s*كامل|خروج\s*فوري|خروج\s*كامل'
    r'|بير\s*ران|بيرش|بيري?ش|شورت|short|sell\s*all'
    r'|دامب|دمب|dump|هبوط\s*حاد|انهيار|كراش|crash'
    r'|سكام|scam|نصب|احتيال',
    re.I
)

_COIN_RE = re.compile(
    r'\b([A-Z]{2,10})(?:/USDT|USDT|\s*/\s*USDT)\b'
)
_PRICE_RE = re.compile(
    r'(?:سعر|entry|price|دخول|انتري|إنتري|عند)[:\s]*\$?([\d.]+)',
    re.I
)
_TARGET_RE = re.compile(
    r'(?:هدف|target|tp|الهدف|بيع|تيك\s*بروفت|تارقت|تارجت)[:\s]*\$?([\d.]+)',
    re.I
)
_STOP_RE = re.compile(
    r'(?:وقف|stop|sl|ستوب|ستوب\s*لوس|وقف\s*خسار[ةه])[:\s]*\$?([\d.]+)',
    re.I
)

_BLACKLIST = {
    "USD", "USDT", "USDC", "NFT", "CEO", "DCA", "ATH", "ATL",
    "RSI", "ETF", "SEC", "API", "URL", "PDF", "VIP", "THE",
    "BNB", "FOR", "ALL", "NEW", "NOW", "TOP", "BIG", "LOW",
    "HIGH", "FREE", "JOIN", "BEST", "PUMP", "DUMP",
}

# ── Logging ──
logger = logging.getLogger("channel_dt")
logger.setLevel(logging.INFO)
logger.propagate = False
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _fh.setFormatter(_fmt)
    logger.addHandler(_fh)
except Exception:
    _sh = logging.StreamHandler()
    _sh.setFormatter(_fmt)
    logger.addHandler(_sh)


# ── Telegram notify ──
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
        req = urllib.request.Request(url, headers={"User-Agent": "channel-dt/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
# CHANNEL SIGNAL EXTRACTION
# ══════════════════════════════════════════════════════════════

@dataclass
class ChannelSignal:
    channel: str
    symbol: str
    entry_price: float
    target_price: float
    stop_price: float
    tp_pct: float
    sl_pct: float
    raw_text: str
    timestamp: str


def parse_signal(text: str, channel: str) -> ChannelSignal | None:
    if not _BUY_RE.search(text):
        return None
    if _SELL_RE.search(text) and not re.search(r'شراء|buy|long|دخول', text, re.I):
        return None

    coins = _COIN_RE.findall(text)
    coins = [c.upper() for c in coins if c.upper() not in _BLACKLIST and len(c) >= 2]
    if not coins:
        return None

    symbol = coins[0]

    price_match = _PRICE_RE.search(text)
    target_match = _TARGET_RE.search(text)
    stop_match = _STOP_RE.search(text)

    entry_price = float(price_match.group(1)) if price_match else 0
    target_price = float(target_match.group(1)) if target_match else 0
    stop_price = float(stop_match.group(1)) if stop_match else 0

    # Calculate TP/SL percentages
    tp_pct = TAKE_PROFIT_PCT
    sl_pct = STOP_LOSS_PCT
    if entry_price > 0 and target_price > 0:
        tp_pct = (target_price - entry_price) / entry_price * 100
        if tp_pct > 20:
            tp_pct = TAKE_PROFIT_PCT
    if entry_price > 0 and stop_price > 0:
        sl_pct = (entry_price - stop_price) / entry_price * 100
        if sl_pct > 20:
            sl_pct = STOP_LOSS_PCT

    return ChannelSignal(
        channel=channel,
        symbol=symbol,
        entry_price=entry_price,
        target_price=target_price,
        stop_price=stop_price,
        tp_pct=max(tp_pct, 1.5),
        sl_pct=max(sl_pct, 2.0),
        raw_text=text[:200],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _save_raw_messages(messages_batch: list[dict]):
    existing = []
    if RAW_MSGS_FILE.exists():
        try:
            existing = json.loads(RAW_MSGS_FILE.read_text())
        except Exception:
            existing = []
    existing.extend(messages_batch)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    existing = [m for m in existing if m.get("ts", "") > cutoff]
    existing = existing[-500:]
    RAW_MSGS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=1))


def scan_channels() -> list[ChannelSignal]:
    if not _HAS_TELETHON or not TG_API_ID or not TG_API_HASH:
        logger.warning("Telethon not configured")
        return []

    signals = []
    raw_batch = []
    try:
        with TelegramClient(SESSION, TG_API_ID, TG_API_HASH) as client:
            since = datetime.now(timezone.utc) - timedelta(minutes=SCAN_INTERVAL_SEC // 60 + 5)
            for ch_name in WATCH_CHANNELS:
                try:
                    entity = client.get_entity(ch_name)
                    messages = client.get_messages(entity, limit=20)
                    for msg in messages:
                        if not msg.text:
                            continue
                        if msg.date and msg.date.replace(tzinfo=timezone.utc) < since:
                            continue
                        raw_batch.append({
                            "channel": ch_name,
                            "text": msg.text,
                            "ts": msg.date.replace(tzinfo=timezone.utc).isoformat() if msg.date else datetime.now(timezone.utc).isoformat(),
                            "msg_id": msg.id,
                        })
                        sig = parse_signal(msg.text, ch_name)
                        if sig:
                            signals.append(sig)
                except Exception as e:
                    logger.debug("Channel %s: %s", ch_name, e)
    except Exception as e:
        logger.error("Telegram scan error: %s", e)

    if raw_batch:
        try:
            _save_raw_messages(raw_batch)
        except Exception:
            pass

    return signals


# ══════════════════════════════════════════════════════════════
# MARKET DATA (Bybit)
# ══════════════════════════════════════════════════════════════

def fetch_price(symbol: str) -> float | None:
    sym = f"{symbol}USDT"
    data = http_get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={sym}")
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


def fetch_rsi(symbol: str) -> float | None:
    sym = f"{symbol}USDT"
    url = (f"https://api.bybit.com/v5/market/kline?"
           f"category=spot&symbol={sym}&interval=15&limit=30")
    data = http_get(url)
    if not data or data.get("retCode") != 0:
        return None
    rows = data.get("result", {}).get("list", [])
    if not rows or len(rows) < 16:
        return None
    closes = []
    for r in reversed(rows):
        try:
            if r[4]:
                closes.append(float(r[4]))
        except (ValueError, IndexError):
            continue
    if len(closes) < 16:
        return None

    period = 14
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


# ══════════════════════════════════════════════════════════════
# BYBIT EXECUTION
# ══════════════════════════════════════════════════════════════

def bybit_signed_post(params: dict) -> dict | None:
    ts = str(int(time.time() * 1000))
    recv = "5000"
    body = json.dumps(params)
    sign_str = f"{ts}{BYBIT_KEY}{recv}{body}"
    sig = hmac.new(BYBIT_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    try:
        req = urllib.request.Request(
            "https://api.bybit.com/v5/order/create",
            data=body.encode(),
            headers={
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


def bybit_signed_get(path: str, params: str) -> dict | None:
    ts = str(int(time.time() * 1000))
    recv = "5000"
    sign_str = f"{ts}{BYBIT_KEY}{recv}{params}"
    sig = hmac.new(BYBIT_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    try:
        req = urllib.request.Request(
            f"https://api.bybit.com{path}?{params}",
            headers={
                "X-BAPI-API-KEY": BYBIT_KEY,
                "X-BAPI-TIMESTAMP": ts,
                "X-BAPI-RECV-WINDOW": recv,
                "X-BAPI-SIGN": sig,
            })
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.error("Bybit GET: %s", e)
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


def _get_lot_step(symbol: str) -> float:
    sym = f"{symbol}USDT" if not symbol.endswith("USDT") else symbol
    data = http_get(f"https://api.bybit.com/v5/market/instruments-info?category=spot&symbol={sym}")
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
    import math
    return math.floor(qty / step) * step


def place_buy(symbol: str, usdt_amount: float, price: float) -> bool:
    if PAPER_MODE:
        logger.info("📝 PAPER BUY %sUSDT — $%.2f @ %.6f", symbol, usdt_amount, price)
        return True
    qty = usdt_amount / price
    step = _get_lot_step(symbol)
    qty = _round_qty(qty, step)
    if qty <= 0:
        logger.error("❌ BUY %s: qty rounded to 0", symbol)
        return False
    result = bybit_signed_post({
        "category": "spot", "symbol": f"{symbol}USDT",
        "side": "Buy", "orderType": "Market",
        "qty": str(qty), "marketUnit": "baseCoin",
    })
    if result and result.get("retCode") == 0:
        logger.info("✅ BUY %sUSDT — $%.2f @ %.6f (qty=%s)", symbol, usdt_amount, price, qty)
        return True
    logger.error("❌ BUY failed %s: %s", symbol, result)
    return False


def place_sell(symbol: str, qty: float) -> bool:
    if PAPER_MODE:
        logger.info("📝 PAPER SELL %sUSDT — qty %.6f", symbol, qty)
        return True
    sell_qty = qty * 0.998
    step = _get_lot_step(symbol)
    sell_qty = _round_qty(sell_qty, step)
    if sell_qty <= 0:
        logger.error("❌ SELL %s: qty rounded to 0", symbol)
        return False
    result = bybit_signed_post({
        "category": "spot", "symbol": f"{symbol}USDT",
        "side": "Sell", "orderType": "Market",
        "qty": str(sell_qty), "marketUnit": "baseCoin",
    })
    if result and result.get("retCode") == 0:
        return True
    logger.error("❌ SELL failed %s: %s", symbol, result)
    return False


# ══════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════

@dataclass
class CDTState:
    positions: dict = field(default_factory=dict)
    daily_trades: int = 0
    daily_pnl: float = 0.0
    daily_date: str = ""
    total_pnl: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    history: list = field(default_factory=list)
    mode: str = "PAPER"
    # Learning
    channel_stats: dict = field(default_factory=dict)  # channel → {wins, losses, pnl}
    symbol_stats: dict = field(default_factory=dict)   # symbol → {wins, losses, pnl}
    seen_signals: list = field(default_factory=list)    # hash of recent signals

    def to_dict(self) -> dict:
        return asdict(self)


def load_state() -> CDTState:
    if STATE_FILE.exists():
        try:
            raw = json.loads(STATE_FILE.read_text())
            st = CDTState()
            for k, v in raw.items():
                if hasattr(st, k):
                    setattr(st, k, v)
            return st
        except Exception:
            pass
    return CDTState()


def save_state(st: CDTState):
    STATE_FILE.write_text(json.dumps(st.to_dict(), indent=2, default=str))


def roll_day(st: CDTState):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if st.daily_date != today:
        if st.daily_date and st.daily_trades > 0:
            notify(f"📊 Channel DayTrader | trades: {st.daily_trades} | "
                   f"PnL: ${st.daily_pnl:+.2f} | W/L: {st.wins}/{st.losses}")
        st.daily_date = today
        st.daily_trades = 0
        st.daily_pnl = 0.0


# ══════════════════════════════════════════════════════════════
# SIGNAL SCORING & FILTERING
# ══════════════════════════════════════════════════════════════

def score_signal(st: CDTState, sig: ChannelSignal) -> float:
    score = 50.0

    # Channel reputation
    ch = st.channel_stats.get(sig.channel, {})
    ch_trades = ch.get("wins", 0) + ch.get("losses", 0)
    if ch_trades >= 3:
        ch_wr = ch.get("wins", 0) / ch_trades * 100
        if ch_wr >= 70:
            score += 15
        elif ch_wr >= 50:
            score += 5
        elif ch_wr < 30:
            score -= 15

    # Symbol history
    sym = st.symbol_stats.get(sig.symbol, {})
    sym_trades = sym.get("wins", 0) + sym.get("losses", 0)
    if sym_trades >= 3:
        sym_wr = sym.get("wins", 0) / sym_trades * 100
        if sym_wr >= 70:
            score += 10
        elif sym_wr < 30:
            score -= 10

    # Has clear targets (better signal quality)
    if sig.target_price > 0:
        score += 5
    if sig.stop_price > 0:
        score += 5

    # Reasonable TP (2-10% = day trading range)
    if 2 <= sig.tp_pct <= 10:
        score += 5
    elif sig.tp_pct > 15:
        score -= 5

    # AI analysis boost (from bot_monitor Cerebras)
    ai_file = BASE_DIR / "ai_channel_analysis.json"
    if ai_file.exists():
        try:
            ai = json.loads(ai_file.read_text())
            for s in ai.get("buy", []):
                if s.get("symbol", "").upper() == sig.symbol.upper():
                    conf = s.get("confidence", "low")
                    score += {"high": 12, "medium": 8, "low": 4}.get(conf, 4)
                    break
            for s in ai.get("sell", []):
                if s.get("symbol", "").upper() == sig.symbol.upper():
                    score -= 15
                    break
        except Exception:
            pass

    return score


def verify_technical(symbol: str) -> tuple[bool, str]:
    rsi = fetch_rsi(symbol)
    if rsi is None:
        return True, "no RSI data"
    if rsi > 75:
        return False, f"RSI overbought ({rsi:.0f})"
    if rsi < 25:
        return True, f"RSI oversold ({rsi:.0f}) — strong buy"
    return True, f"RSI ok ({rsi:.0f})"


# ══════════════════════════════════════════════════════════════
# POSITION MANAGEMENT
# ══════════════════════════════════════════════════════════════

def check_exits(st: CDTState):
    to_close = []
    now = datetime.now(timezone.utc)

    for sym, pos in list(st.positions.items()):
        price = fetch_price(sym)
        if price is None:
            continue

        pnl_pct = (price - pos["entry"]) / pos["entry"] * 100
        pnl_usd = pos["size"] * pnl_pct / 100

        exit_reason = None
        tp = pos.get("tp_pct", TAKE_PROFIT_PCT)
        sl = pos.get("sl_pct", STOP_LOSS_PCT)

        if pnl_pct >= tp:
            exit_reason = "TP"
        elif pnl_pct <= -sl:
            exit_reason = "SL"
        else:
            opened = datetime.fromisoformat(pos["opened_at"])
            if (now - opened).total_seconds() > MAX_HOLD_HOURS * 3600:
                exit_reason = "EXPIRED"

        if exit_reason:
            to_close.append((sym, pos, price, pnl_pct, pnl_usd, exit_reason))

    for sym, pos, price, pnl_pct, pnl_usd, reason in to_close:
        success = place_sell(sym, pos["qty"]) if not PAPER_MODE else True
        if success or PAPER_MODE:
            del st.positions[sym]
            st.daily_pnl += pnl_usd
            st.total_pnl += pnl_usd
            st.total_trades += 1

            is_win = pnl_usd >= 0
            if is_win:
                st.wins += 1
            else:
                st.losses += 1

            # Learn from trade
            ch = pos.get("channel", "")
            if ch not in st.channel_stats:
                st.channel_stats[ch] = {"wins": 0, "losses": 0, "pnl": 0.0}
            st.channel_stats[ch]["wins" if is_win else "losses"] += 1
            st.channel_stats[ch]["pnl"] = round(st.channel_stats[ch]["pnl"] + pnl_usd, 2)

            if sym not in st.symbol_stats:
                st.symbol_stats[sym] = {"wins": 0, "losses": 0, "pnl": 0.0}
            st.symbol_stats[sym]["wins" if is_win else "losses"] += 1
            st.symbol_stats[sym]["pnl"] = round(st.symbol_stats[sym]["pnl"] + pnl_usd, 2)

            icon = "🟢" if is_win else "🔴"
            notify(f"{icon} CH-CLOSE {sym}USDT [{reason}]\n"
                   f"Channel: {ch}\n"
                   f"Entry: {pos['entry']:.6f} → Exit: {price:.6f}\n"
                   f"PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})")

            st.history.append({
                "symbol": sym, "channel": ch,
                "pnl_pct": round(pnl_pct, 2), "pnl_usd": round(pnl_usd, 2),
                "reason": reason, "closed_at": now.isoformat(),
            })
            if len(st.history) > 200:
                st.history = st.history[-200:]

    save_state(st)


def open_from_signal(st: CDTState, sig: ChannelSignal):
    if sig.symbol in st.positions:
        return
    if len(st.positions) >= MAX_POSITIONS:
        return
    if st.daily_pnl <= -MAX_DAILY_LOSS:
        return

    # Dedup: don't act on same signal twice
    sig_hash = hashlib.md5(f"{sig.symbol}{sig.channel}{sig.timestamp[:13]}".encode()).hexdigest()[:12]
    if sig_hash in st.seen_signals:
        return
    st.seen_signals.append(sig_hash)
    if len(st.seen_signals) > 500:
        st.seen_signals = st.seen_signals[-500:]

    # Technical verification
    ok, reason = verify_technical(sig.symbol)
    if not ok:
        logger.info("⛔ Skip %s from %s — %s", sig.symbol, sig.channel, reason)
        return

    price = fetch_price(sig.symbol)
    if price is None:
        return

    balance = fetch_balance()
    size = min(TRADE_SIZE_USDT, balance * 0.95)
    if size < 5:
        return

    success = place_buy(sig.symbol, size, price)
    if not success:
        return

    # Use signal targets if reasonable, otherwise defaults
    tp_pct = sig.tp_pct if 1.5 <= sig.tp_pct <= 10 else TAKE_PROFIT_PCT
    sl_pct = sig.sl_pct if 2 <= sig.sl_pct <= 10 else STOP_LOSS_PCT

    st.positions[sig.symbol] = {
        "entry": price,
        "qty": size / price,
        "size": size,
        "tp_pct": tp_pct,
        "sl_pct": sl_pct,
        "channel": sig.channel,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "reason": f"signal from {sig.channel}",
    }
    st.daily_trades += 1

    notify(f"🔵 CH-OPEN {sig.symbol}USDT\n"
           f"Channel: {sig.channel}\n"
           f"Price: {price:.6f} | Size: ${size:.2f}\n"
           f"TP: +{tp_pct:.1f}% | SL: -{sl_pct:.1f}%")

    save_state(st)


# ══════════════════════════════════════════════════════════════
# MAIN CYCLE
# ══════════════════════════════════════════════════════════════

_cycle_count = 0

def run_cycle(st: CDTState):
    global _cycle_count
    _cycle_count += 1
    roll_day(st)

    # Check exits
    if st.positions:
        check_exits(st)

    if st.daily_pnl <= -MAX_DAILY_LOSS:
        if _cycle_count % 6 == 0:
            logger.info("⛔ Daily loss limit — paused")
        return

    if len(st.positions) >= MAX_POSITIONS:
        if _cycle_count % 6 == 0:
            logger.info("⏸ Max positions — waiting")
        return

    # Scan channels for signals
    logger.info("🔍 Cycle %d — scanning %d channels...", _cycle_count, len(WATCH_CHANNELS))
    signals = scan_channels()

    if signals:
        scored = [(sig, score_signal(st, sig)) for sig in signals]
        scored.sort(key=lambda x: x[1], reverse=True)

        logger.info("📡 Found %d channel signals", len(signals))
        for sig, score in scored:
            logger.info("  → %s score %.0f from %s", sig.symbol, score, sig.channel)
            if score >= 50 and len(st.positions) < MAX_POSITIONS:
                open_from_signal(st, sig)
    else:
        logger.info("📭 No new signals from channels")

    # Healthcheck every 6 cycles
    if _cycle_count % 6 == 0:
        logger.info("💓 Cycle %d | %d/%d positions | trades: %d | PnL: $%.2f",
                     _cycle_count, len(st.positions), MAX_POSITIONS,
                     st.daily_trades, st.daily_pnl)


# ══════════════════════════════════════════════════════════════
# STATUS
# ══════════════════════════════════════════════════════════════

def show_status():
    st = load_state()
    print(f"\n{'═' * 50}")
    print(f"  CHANNEL DAYTRADER STATUS")
    print(f"{'═' * 50}")
    print(f"  Mode: {st.mode}")
    print(f"  Daily PnL: ${st.daily_pnl:+.2f} | Total PnL: ${st.total_pnl:+.2f}")
    print(f"  Today's trades: {st.daily_trades} (unlimited)")
    print(f"  Win/Loss: {st.wins}/{st.losses} "
          f"({st.wins / max(st.wins + st.losses, 1) * 100:.0f}% WR)")

    print(f"\n  Open Positions ({len(st.positions)}/{MAX_POSITIONS}):")
    print(f"  {'─' * 46}")
    for sym, pos in st.positions.items():
        price = fetch_price(sym)
        if price:
            pnl = (price - pos["entry"]) / pos["entry"] * 100
            icon = "🟢" if pnl >= 0 else "🔴"
            print(f"  {icon} {sym:8s} | {pos['channel']:15s} | {pnl:+.2f}%")

    if st.channel_stats:
        print(f"\n  🧠 Channel Learning:")
        print(f"  {'─' * 46}")
        for ch, data in sorted(st.channel_stats.items(),
                               key=lambda x: x[1].get("pnl", 0), reverse=True):
            total = data["wins"] + data["losses"]
            wr = data["wins"] / max(total, 1) * 100
            print(f"  {ch:15s} | {total} trades | WR: {wr:.0f}% | PnL: ${data['pnl']:+.2f}")

    print(f"{'═' * 50}\n")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    global PAPER_MODE

    parser = argparse.ArgumentParser(description="Channel DayTrader (Bybit Spot)")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--scan", action="store_true")
    args = parser.parse_args()

    if args.live:
        PAPER_MODE = False
        if not BYBIT_KEY or not BYBIT_SECRET:
            logger.error("Missing Bybit API keys")
            sys.exit(1)

    if args.status:
        show_status()
        return

    if args.scan:
        print(f"\n{'═' * 50}")
        print(f"  Scanning {len(WATCH_CHANNELS)} channels...")
        print(f"{'═' * 50}")
        signals = scan_channels()
        if not signals:
            print("  ❌ No buy signals in recent messages")
        else:
            print(f"  ✅ Found {len(signals)} signal(s):\n")
            for sig in signals:
                print(f"  {sig.symbol:8s} | {sig.channel:15s} | "
                      f"entry: {sig.entry_price or 'market'} | "
                      f"TP: +{sig.tp_pct:.1f}% | SL: -{sig.sl_pct:.1f}%")
        print(f"{'═' * 50}\n")
        return

    mode = "LIVE" if not PAPER_MODE else "PAPER"
    notify(f"🚀 Channel DayTrader Started [{mode}]\n"
           f"Channels: {len(WATCH_CHANNELS)} | TP: {TAKE_PROFIT_PCT}% | SL: {STOP_LOSS_PCT}%\n"
           f"Size: ${TRADE_SIZE_USDT} | Max: {MAX_POSITIONS} positions\n"
           f"Scan every {SCAN_INTERVAL_SEC // 60} min")

    st = load_state()
    st.mode = mode
    save_state(st)

    while True:
        try:
            run_cycle(st)
        except KeyboardInterrupt:
            save_state(st)
            break
        except Exception as e:
            logger.error("Cycle error: %s", e)
        time.sleep(SCAN_INTERVAL_SEC)


if __name__ == "__main__":
    main()
