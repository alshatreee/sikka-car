"""
smart_channel_bot.py — بوت التداول الذكي متعدد القنوات

يستمع لـ 6 قنوات تيلجرام + يعتمد على:
  - تعلم ذاتي: يتتبع دقة كل قناة ويعطيها وزناً
  - تحليل AI: يقرأ ai_channel_analysis.json من bot_monitor
  - وقف خسارة مُفعّل: ATR + ثابت + كارثي
  - تسجيل نقاط لكل إشارة (قناة + AI + تقنية)

    python3 smart_channel_bot.py              # ورقي
    python3 smart_channel_bot.py --live       # حقيقي
    python3 smart_channel_bot.py --check      # فحص
    python3 smart_channel_bot.py --status     # حالة المراكز

    pip install telethon ccxt python-dotenv requests
"""
from __future__ import annotations
import asyncio, fcntl, json, os, re, sys, time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# ---------- paths ----------
BASE_DIR = Path(r"C:\Users\xman9\Desktop") if os.name == "nt" else Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = BASE_DIR / ".env_monthly"
STATE_FILE = BASE_DIR / "smart_state.json"
LOG_FILE = BASE_DIR / "smart_channel.log"
LEARNING_FILE = BASE_DIR / "smart_learning.json"
AI_ANALYSIS_FILE = BASE_DIR / "ai_channel_analysis.json"
CHANNEL_MEMORY_FILE = BASE_DIR / "channel_memory.json"
# raw channel messages → consumed by bot_monitor to produce ai_channel_analysis.json.
# smart_channel_bot now feeds this (channel_daytrader used to, but it's stopped).
RAW_MSGS_FILE = BASE_DIR / "channel_raw_messages.json"
load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# ---------- config ----------
TG_API_ID    = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH  = os.getenv("TG_API_HASH", "")
# Reuse the (now retired) channel_daytrader session, which is ALREADY
# authorized. Creating a brand-new session needs a phone login, which Telegram
# flood-blocks. Override with SMART_SESSION if you have a dedicated session.
TG_SESSION   = str(BASE_DIR / os.getenv("SMART_SESSION", "channel_dt_session"))
BYBIT_KEY    = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET = os.getenv("BYBIT_API_SECRET", "")
BYBIT_TESTNET = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
NOTIFY_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

CAPITAL      = float(os.getenv("SMART_CAPITAL", "500"))
TRADE_PCT    = float(os.getenv("SMART_TRADE_PCT", "10"))
TRADE_SIZE   = CAPITAL * TRADE_PCT / 100
SL_PCT       = float(os.getenv("SMART_SL_PCT", "5.0"))
MIN_SL_PCT   = float(os.getenv("SMART_MIN_SL_PCT", "3.0"))  # أضيق وقف مسموح — يمنع الخروج على الضجيج
CATASTROPHIC_SL_PCT = float(os.getenv("SMART_CATASTROPHIC_SL", "15.0"))
MAX_HOLD_DAYS = int(os.getenv("SMART_MAX_HOLD_DAYS", "30"))
MAX_DAILY_TRADES = int(os.getenv("SMART_MAX_DAILY_TRADES", "8"))
# keep MAX_OPEN * BYBIT_TRADE_SIZE within CAPITAL (8*50=400<500); the live
# free-balance check is the real guard, this is just a sane upper bound.
MAX_OPEN = int(os.getenv("SMART_MAX_OPEN", "8"))
MAX_DAILY_LOSS_PCT = float(os.getenv("SMART_MAX_LOSS_PCT", "5.0"))
MAX_DAILY_LOSS = CAPITAL * MAX_DAILY_LOSS_PCT / 100
MIN_TRADE_USDT = float(os.getenv("SMART_MIN_TRADE_USDT", "20.0"))
BYBIT_TRADE_SIZE = float(os.getenv("SMART_BYBIT_TRADE_SIZE", "50"))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("SMART_MAX_CONSEC_LOSSES", "4"))
LIMIT_ORDER_SLIP = float(os.getenv("SMART_LIMIT_SLIP", "0.5"))

# trailing stop
TRAILING_STOP_ACTIVATE_PCT = float(os.getenv("SMART_TRAIL_ACTIVATE", "8.0"))
TRAILING_STOP_DISTANCE_PCT = float(os.getenv("SMART_TRAIL_DISTANCE", "3.0"))

# ATR
ATR_PERIOD = int(os.getenv("SMART_ATR_PERIOD", "14"))
ATR_SL_MULTIPLIER = float(os.getenv("SMART_ATR_SL_MULT", "2.0"))

# entry phases
ENTRY_PHASES = [
    {"ratio": 0.50, "delay_min": 0},
    {"ratio": 0.50, "delay_min": 120},
]
PHASE_CANCEL_RISE_PCT = float(os.getenv("SMART_PHASE_CANCEL_RISE", "5.0"))

# BTC filter
BTC_DROP_LIMIT = float(os.getenv("SMART_BTC_DROP_LIMIT", "5.0"))

# smart entry
SMART_ENTRY_WAIT_MIN = int(os.getenv("SMART_ENTRY_WAIT", "60"))
SMART_ENTRY_BOUNCE_PCT = float(os.getenv("SMART_BOUNCE", "1.0"))

# signal scoring thresholds
MIN_SIGNAL_SCORE = float(os.getenv("SMART_MIN_SCORE", "55.0"))

# faster loop so a sharp drop is caught sooner (software SL is a backup to the
# exchange-native stop placed on entry).
CHECK_INTERVAL = int(os.getenv("SMART_CHECK_INTERVAL", "60"))
PAPER_MODE = "--live" not in sys.argv

# ---------- قنوات التداول (توصيات → تفتح صفقات) ----------
WATCH_CHANNELS = [
    "cryptomena1", "arabcharts", "crypto_q88",
    "ahmadchats", "Naif_Alert", "vipdrprofit",
    "tracer",  # DeFiTracer على تلجرام
]

# ---------- قنوات الأخبار (تغذّي الـAI فقط، لا تتداول منها) ----------
# قنوات أخبار/إعلانات عامة — لا تحتوي توصيات بسعر دخول، فلا نفتح منها صفقات،
# لكن نمرّر رسائلها لتحليل الـAI (سياق/معنويات السوق).
NEWS_CHANNELS = [
    "CoingraphNews", "Coin_Post", "CoinMarketCapAnnouncements",
]

# كل القنوات التي نستمع لها (تداول + أخبار)
ALL_CHANNELS = WATCH_CHANNELS + NEWS_CHANNELS
_NEWS_SET = {c.lower() for c in NEWS_CHANNELS}

PROTECTED_SYMBOLS = [s.strip().upper() for s in os.getenv("SMART_PROTECTED_SYMBOLS", "").split(",") if s.strip()]

_STABLECOINS = {"USDC", "USDT", "BUSD", "DAI", "TUSD", "FDUSD"}

# ---------- logging / notify ----------
_IS_TTY = sys.stdin and sys.stdin.isatty()

def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    if _IS_TTY:
        print(line, flush=True)
    try:
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def notify(msg: str) -> None:
    if not NOTIFY_TOKEN or not NOTIFY_CHAT:
        return
    try:
        import requests
        for chunk in _split_for_telegram(msg):
            requests.post(f"https://api.telegram.org/bot{NOTIFY_TOKEN}/sendMessage",
                          json={"chat_id": NOTIFY_CHAT, "text": chunk, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        log(f"خطأ في الإشعار: {e}")

def _split_for_telegram(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts

# ---------- lock file ----------
_lock_fh = None

def _acquire_lock():
    global _lock_fh
    lock_path = BASE_DIR / "smart_channel_bot.lock"
    _lock_fh = open(lock_path, "w")
    try:
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fh.write(str(os.getpid()))
        _lock_fh.flush()
    except BlockingIOError:
        print("خطأ: نسخة أخرى تعمل بالفعل")
        sys.exit(1)

# ---------- atomic write ----------
def _atomic_write(path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text)
    tmp.replace(path)

# ---------- raw message feed (keeps bot_monitor's AI alive) ----------
def _save_raw_message(channel: str, text: str, msg_id: int) -> None:
    """Append one channel message for bot_monitor's AI analysis pipeline.
    Same format/24h-rolling-window as the (now stopped) channel_daytrader."""
    existing = []
    if RAW_MSGS_FILE.exists():
        try:
            existing = json.loads(RAW_MSGS_FILE.read_text())
        except Exception:
            existing = []
    existing.append({
        "channel": channel, "text": text, "msg_id": msg_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    existing = [m for m in existing if m.get("ts", "") > cutoff]
    existing = existing[-500:]
    try:
        _atomic_write(RAW_MSGS_FILE, json.dumps(existing, ensure_ascii=False, indent=1))
    except Exception as e:
        log(f"خطأ حفظ الرسالة الخام: {e}")

# ---------- state ----------
@dataclass
class State:
    day: str = ""
    daily_trades: int = 0
    daily_pnl: float = 0.0
    halted: bool = False
    open_positions: dict[str, dict] = field(default_factory=dict)
    trade_history: list[dict] = field(default_factory=list)
    pending_signals: list[dict] = field(default_factory=list)
    executed_signals: list[str] = field(default_factory=list)
    entered_symbols: list[str] = field(default_factory=list)
    consecutive_losses: int = 0

def load_state() -> State:
    if STATE_FILE.exists():
        try:
            raw = json.loads(STATE_FILE.read_text())
            st = State()
            for k, v in raw.items():
                if hasattr(st, k):
                    setattr(st, k, v)
            return st
        except Exception:
            pass
    return State()

def save_state(s: State) -> None:
    _atomic_write(STATE_FILE, json.dumps(asdict(s), indent=2, ensure_ascii=False))

def rollover_day(s: State) -> None:
    today = time.strftime("%Y-%m-%d")
    if s.day != today:
        s.day, s.daily_trades, s.daily_pnl, s.halted = today, 0, 0.0, False
        s.consecutive_losses = 0
        save_state(s)
        log(f"=== يوم جديد {today} — إعادة تعيين ===")

# ---------- self-learning ----------
def _load_learning() -> dict:
    if LEARNING_FILE.exists():
        try:
            return json.loads(LEARNING_FILE.read_text())
        except Exception:
            pass
    return {"channels": {}, "symbols": {}, "updated": ""}

def _save_learning(data: dict) -> None:
    data["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _atomic_write(LEARNING_FILE, json.dumps(data, indent=2, ensure_ascii=False))

def learning_record_trade(channel: str, symbol: str, pnl: float, pnl_pct: float) -> None:
    data = _load_learning()
    is_win = pnl > 0

    ch = data["channels"].setdefault(channel, {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0})
    ch["trades"] += 1
    ch["wins" if is_win else "losses"] += 1
    ch["pnl"] = round(ch["pnl"] + pnl, 2)

    sym = data["symbols"].setdefault(symbol, {"wins": 0, "losses": 0, "pnl": 0.0, "trades": 0})
    sym["trades"] += 1
    sym["wins" if is_win else "losses"] += 1
    sym["pnl"] = round(sym["pnl"] + pnl, 2)

    _save_learning(data)

def _channel_score(channel: str) -> float:
    data = _load_learning()
    ch = data.get("channels", {}).get(channel)
    if not isinstance(ch, dict) or ch.get("trades", 0) < 3:
        return 0.0
    wins, losses = ch.get("wins", 0), ch.get("losses", 0)
    total = wins + losses
    if total == 0:
        return 0.0
    return wins / total * 100

def _symbol_score(symbol: str) -> float:
    data = _load_learning()
    sym = data.get("symbols", {}).get(symbol)
    if not isinstance(sym, dict) or sym.get("trades", 0) < 3:
        return 0.0
    wins, losses = sym.get("wins", 0), sym.get("losses", 0)
    total = wins + losses
    if total == 0:
        return 0.0
    return wins / total * 100

# ---------- AI analysis ----------
_ai_cache: dict = {"ts": 0.0, "data": None}

def _load_ai_analysis() -> dict | None:
    now = time.time()
    if now - _ai_cache["ts"] < 120 and _ai_cache["data"] is not None:
        return _ai_cache["data"]
    if AI_ANALYSIS_FILE.exists():
        try:
            _ai_cache["data"] = json.loads(AI_ANALYSIS_FILE.read_text())
            _ai_cache["ts"] = now
        except Exception:
            _ai_cache["data"] = None
    return _ai_cache["data"]

def _ai_signal_boost(symbol: str) -> float:
    ai = _load_ai_analysis()
    if not ai:
        return 0.0
    sym = symbol.upper().replace("USDT", "")
    for s in (ai.get("buy") or []):
        if isinstance(s, dict) and s.get("symbol", "").upper().replace("USDT", "") == sym:
            conf = s.get("confidence", "low")
            return {"high": 15.0, "medium": 10.0, "low": 5.0}.get(conf, 5.0)
    for s in (ai.get("sell") or []):
        if isinstance(s, dict) and s.get("symbol", "").upper().replace("USDT", "") == sym:
            return -20.0
    return 0.0

# ---------- signal scoring ----------
@dataclass
class ChannelSignal:
    channel: str
    symbol: str
    buy_price: float
    sell_price: float
    stop_price: float
    tp_pct: float
    targets: list[dict] = field(default_factory=list)
    reinforcements: list[float] = field(default_factory=list)
    trade_num: int = 0
    raw_text: str = ""
    msg_id: int = 0
    score: float = 0.0

def score_signal(sig: ChannelSignal) -> float:
    score = 50.0

    # 1) channel reputation from self-learning
    ch_wr = _channel_score(sig.channel)
    if ch_wr > 0:
        if ch_wr >= 70:
            score += 15
        elif ch_wr >= 50:
            score += 5
        elif ch_wr < 30:
            score -= 15

    # 2) symbol history from self-learning
    sym_wr = _symbol_score(sig.symbol)
    if sym_wr > 0:
        if sym_wr >= 70:
            score += 10
        elif sym_wr < 30:
            score -= 10

    # 3) AI analysis boost/veto
    ai_boost = _ai_signal_boost(sig.symbol)
    score += ai_boost

    # 4) signal quality
    if sig.sell_price > 0:
        score += 5
    if sig.stop_price > 0:
        score += 5
    if sig.targets:
        score += 3
    if sig.reinforcements:
        score += 2

    # 5) reasonable TP range
    if 5 <= sig.tp_pct <= 30:
        score += 5
    elif sig.tp_pct > 50:
        score -= 5

    return round(score, 1)

# ---------- signal parsing ----------
_BUY_KEYWORDS = re.compile(
    r'شراء|صعود|صاعد|دخول|إيجابي|اختراق|ارتفاع|فرصة'
    r'|\bbuy\b|\blong\b|bullish'
    r'|بول\s*ران|بول\s*رن|بولش|بولي?ش'
    r'|بامب|بمب|بامبينق|بمبنق'
    r'|بريك\s*أوت|بريك\s*اوت|بريكاوت'
    r'|لونق|لونج'
    r'|رالي|رالى'
    r'|سبورت|دعم'
    r'|ريفرسال|انعكاس'
    r'|اكيوميوليت|اكيوملي?ت|تجميع'
    r'|انتري|إنتري'
    r'|قاع(?![ا-ي])|ارتداد',
    re.I
)

_SELL_KEYWORDS = re.compile(
    r'بيع\s*فوري|بيع\s*كامل|خروج\s*فوري|خروج\s*كامل'
    r'|بير\s*ران|بيرش|بيري?ش|شورت|\bshort\b|sell\s*all'
    r'|دامب|دمب|\bdump\b|هبوط\s*حاد|انهيار|كراش|crash'
    r'|كسر\s*(?:ال)?دعم|كسر\s*(?:ال)?سبورت|فقد\s*(?:ال)?دعم'
    r'|سكام|scam|نصب|احتيال',
    re.I
)

_COMPLETED_PATTERNS = re.compile(
    r"تم\s*تحقيق|تحقق\s*الهدف|وصل\s*الهدف|تم\s*الوصول|تم\s*البيع|أغلقت|مغلقة|closed|reached|done",
    re.IGNORECASE,
)

_COIN_RE = re.compile(
    r'(?:(?:\$|#)([A-Z]{2,10}))'
    r'|(?:([A-Z]{2,10})/USDT)'
    r'|(?:العملة\s*[:\s]*([A-Za-z0-9]{2,10}))'
    r'|\b([A-Z]{2,10})(?:/USDT|USDT)\b',
    re.MULTILINE,
)

_PRICE_RE = re.compile(
    r'(?:سعر\s*(?:ال)?شراء|entry|price|دخول|انتري|إنتري|عند)[:\s]*\$?([\d.]+)',
    re.I
)
_TARGET_RE = re.compile(
    r'(?:هدف|target|tp|الهدف|سعر\s*(?:ال)?بيع|تيك\s*بروفت|تارقت|تارجت)[:\s]*\$?([\d.]+)',
    re.I
)
_STOP_RE = re.compile(
    r'(?:وقف|stop|sl|ستوب|ستوب\s*لوس|وقف\s*خسار[ةه])[:\s]*\$?([\d.]+)',
    re.I
)

_COIN_BLACKLIST = {
    "THE", "AND", "FOR", "NOT", "BUT", "ALL", "ARE", "WAS", "HAS", "HAD",
    "CAN", "HER", "HIS", "HOW", "ITS", "LET", "MAY", "NEW", "NOW", "OLD",
    "OUR", "OUT", "OWN", "SAY", "SHE", "TOO", "USE", "WAY", "WHO", "BOY",
    "DID", "GET", "HIM", "MAN", "RUN", "TOP", "VIP", "USD", "API", "URL",
    "APP", "YOU", "ANY", "BIG", "DAY", "END", "FEW", "GOT", "SET", "TRY",
    "WIN", "YES", "BUY", "PUT", "SELL", "LONG", "SHORT", "STOP", "TAKE",
    "HOLD", "DROP", "PUMP", "DUMP", "MOON", "BEAR", "BULL", "HIGH", "LOSS",
    "GAIN", "FREE", "JOIN", "LINK", "SPOT", "FUTURES", "ATR", "RSI",
    "MACD", "EMA", "SMA", "NEWS", "ALERT", "UPDATE", "NOTE", "WARNING",
    "CONFIRMED", "BOTTOM", "BREAK", "ENTRY", "EXIT", "CHART", "PRICE",
    "MARKET", "TRADE", "ORDER", "LIMIT", "DAILY", "WEEKLY", "MONTHLY",
    "OPEN", "CLOSE", "ABOVE", "BELOW", "SUPPORT", "RESISTANCE", "LEVEL",
    "RISK", "SIGNAL", "PROFIT", "TARGET", "SETUP", "TREND", "ZONE",
    "FTX", "CEX", "DEX", "NFT", "ETF", "SEC", "IPO", "OTC", "ICO",
    "USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "BNB",
}


def parse_channel_signal(text: str, channel: str, msg_id: int = 0) -> ChannelSignal | None:
    if not text:
        return None
    if _COMPLETED_PATTERNS.search(text):
        return None

    # --- format 1: monthly-style structured signal ---
    sym_m = re.search(r"العملة\s*[:\s]*([A-Za-z0-9]+)", text)
    if sym_m:
        symbol = sym_m.group(1).upper()
        if symbol in _COIN_BLACKLIST or symbol in _STABLECOINS:
            return None
        num_m = re.search(r"رقم\s*الصفقة\s*[:\s]*\(?(\d+)\)?", text)
        trade_num = int(num_m.group(1)) if num_m else 0

        buy_m = re.search(r"سعر\s*الشراء\s*[:\s]*([\d.]+)", text)
        sell_m = re.search(r"سعر\s*البيع\s*[:\s]*([\d.]+)", text)
        if buy_m and sell_m:
            buy_p, sell_p = float(buy_m.group(1)), float(sell_m.group(1))
            tp_pct = round((sell_p - buy_p) / buy_p * 100, 2) if buy_p > 0 else 0.0
            reinf = _parse_reinforcements(text)
            stop_m = _STOP_RE.search(text)
            stop_p = float(stop_m.group(1)) if stop_m else 0.0
            return ChannelSignal(
                channel=channel, symbol=symbol, buy_price=buy_p,
                sell_price=sell_p, stop_price=stop_p, tp_pct=tp_pct,
                reinforcements=reinf, trade_num=trade_num,
                raw_text=text[:300], msg_id=msg_id,
            )

        # format 2: الشراء والتعزيز + أهداف
        if "الشراء والتعزيز" in text or "التعزيز الأول" in text:
            buy_p, reinf = _parse_buy_and_reinforce(text)
            sell_p, tp_pct = _parse_targets_summary(text, buy_p)
            all_targets = _parse_all_targets(text, buy_p)
            stop_m = _STOP_RE.search(text)
            stop_p = float(stop_m.group(1)) if stop_m else 0.0
            if buy_p > 0:
                return ChannelSignal(
                    channel=channel, symbol=symbol, buy_price=buy_p,
                    sell_price=sell_p, stop_price=stop_p, tp_pct=tp_pct,
                    targets=all_targets, reinforcements=reinf,
                    trade_num=trade_num, raw_text=text[:300], msg_id=msg_id,
                )

    # --- format 3: channel-daytrader style (coin + buy keywords) ---
    if not _BUY_KEYWORDS.search(text):
        return None
    if _SELL_KEYWORDS.search(text) and not re.search(r'شراء|buy|long|دخول', text, re.I):
        return None

    coins = []
    for m in _COIN_RE.finditer(text):
        c = (m.group(1) or m.group(2) or m.group(3) or m.group(4) or "").upper()
        if c and len(c) >= 2 and c not in _COIN_BLACKLIST and c not in _STABLECOINS:
            coins.append(c)
    if not coins:
        return None
    symbol = coins[0]

    price_m = _PRICE_RE.search(text)
    target_m = _TARGET_RE.search(text)
    stop_m = _STOP_RE.search(text)

    entry_price = float(price_m.group(1)) if price_m else 0.0
    target_price = float(target_m.group(1)) if target_m else 0.0
    stop_price = float(stop_m.group(1)) if stop_m else 0.0

    tp_pct = 10.0
    if entry_price > 0 and target_price > entry_price:
        tp_pct = round((target_price - entry_price) / entry_price * 100, 2)
        if tp_pct > 50:
            tp_pct = 10.0
    if target_price <= 0 and entry_price > 0:
        target_price = entry_price * 1.10

    return ChannelSignal(
        channel=channel, symbol=symbol, buy_price=entry_price,
        sell_price=target_price, stop_price=stop_price, tp_pct=tp_pct,
        raw_text=text[:300], msg_id=msg_id,
    )


def _parse_reinforcements(text: str) -> list[float]:
    prices = []
    for line in text.split("\n"):
        if "تعزيز" not in line:
            continue
        m = re.search(r"[-–]\s*(\d+\.?\d*)", line)
        if not m:
            m = re.search(r"(\d+\.\d+)", line)
        if m:
            try:
                p = float(m.group(1))
            except ValueError:
                continue
            if p > 0 and p not in prices:
                prices.append(p)
    return sorted(prices)


def _parse_buy_and_reinforce(text: str) -> tuple[float, list[float]]:
    buy_price = 0.0
    reinforcements = []
    for line in text.split("\n"):
        price_m = re.search(r"[-–]\s*([\d.]+)\s*\(", line)
        if not price_m:
            continue
        try:
            price = float(price_m.group(1))
        except ValueError:
            continue
        if price <= 0:
            continue
        if ("الشراء الأول" in line or "الشراء" in line) and "تعزيز" not in line.lower():
            if buy_price == 0:
                buy_price = price
        if "التعزيز" in line:
            reinforcements.append(price)
    return buy_price, sorted(reinforcements)


def _parse_targets_summary(text: str, buy_price: float) -> tuple[float, float]:
    all_targets = _parse_all_targets(text, buy_price)
    if all_targets:
        last = all_targets[-1]
        return last["price"], last["pct"]
    sell_price = buy_price * 1.15 if buy_price > 0 else 0
    tp_pct = 15.0 if buy_price > 0 else 0
    return sell_price, tp_pct


def _parse_all_targets(text: str, buy_price: float) -> list[dict]:
    targets = []
    in_targets = False
    for line in text.split("\n"):
        if "أهداف الصفقة" in line:
            in_targets = True
            continue
        if "أهداف التعزيز" in line:
            break
        if in_targets:
            m = re.search(r"[-–]\s*([\d.]+)\s*\(([\d.]+)%\)", line)
            if m:
                price = float(m.group(1))
                pct = float(m.group(2))
                completed = "✅" in line or "✓" in line
                targets.append({"price": price, "pct": pct, "completed": completed})
    return targets


# ---------- exchange ----------
def get_exchange():
    import ccxt
    ex = ccxt.bybit({"apiKey": BYBIT_KEY, "secret": BYBIT_SECRET,
                      "options": {"defaultType": "spot"}})
    if BYBIT_TESTNET:
        ex.set_sandbox_mode(True)
    return ex

_exchange = None

def _safe_float(*values, default=0.0) -> float:
    for v in values:
        if v is None:
            continue
        try:
            f = float(v)
            if f or f == 0.0:
                return f
        except (TypeError, ValueError):
            continue
    return default


def _prec_qty(exchange, pair: str, qty: float) -> float:
    try:
        return float(exchange.amount_to_precision(pair, qty))
    except Exception:
        return float(f"{qty:.6f}")


def verify_symbol(exchange, symbol: str) -> str | None:
    pair = f"{symbol}/USDT"
    exchange.load_markets()
    if pair in exchange.markets and exchange.markets[pair].get("spot"):
        return pair
    alt = f"{symbol}USDT"
    for mk, info in exchange.markets.items():
        if info["id"] == alt and info.get("spot"):
            return mk
    return None


def spot_buy(exchange, pair: str, usdt_amount: float) -> dict | None:
    try:
        price = _safe_float(exchange.fetch_ticker(pair).get("last"))
        if not price:
            return None

        if not PAPER_MODE:
            try:
                free = float(exchange.fetch_balance().get("USDT", {}).get("free", 0))
            except Exception:
                free = usdt_amount
            if usdt_amount > free:
                usdt_amount = free * 0.99
            if usdt_amount < 5:
                log(f"تخطي شراء {pair} — رصيد متاح ${free:.2f} غير كافٍ")
                return None

        qty = _prec_qty(exchange, pair, usdt_amount / price)
        if qty <= 0:
            return None
        limit_price = round(price * (1 + LIMIT_ORDER_SLIP / 100), 8)
        try:
            limit_price = float(exchange.price_to_precision(pair, limit_price))
        except Exception:
            pass

        if PAPER_MODE:
            log(f"أمر شراء [ورقي]: {pair} | سعر={price} | كمية={qty:.6f} | ${usdt_amount}")
            return {"filled": qty, "amount": qty, "average": price, "price": price}

        params = {"orderLinkId": f"sc{int(time.time()*1000)}{os.urandom(4).hex()}"}
        order = exchange.create_limit_buy_order(pair, qty, limit_price, params)
        log(f"أمر شراء محدود: {pair} | سعر={limit_price:.6g} | كمية={qty:.6f} | ${usdt_amount}")

        oid = order.get("id")
        if oid:
            fetched = None
            for _ in range(6):
                time.sleep(5)
                try:
                    fetched = exchange.fetch_order(oid, pair)
                    if fetched.get("status") in ("closed", "filled"):
                        log(f"أمر شراء نُفِّذ: {pair}")
                        return fetched
                    if fetched.get("status") == "canceled":
                        break
                except Exception:
                    pass
            try:
                exchange.cancel_order(oid, pair)
            except Exception:
                pass
            filled = 0.0
            limit_avg = limit_price
            try:
                final = exchange.fetch_order(oid, pair)
                filled = _safe_float(final.get("filled"))
                limit_avg = _safe_float(final.get("average"), default=limit_price) or limit_price
            except Exception:
                if fetched:
                    filled = _safe_float(fetched.get("filled"))
                    limit_avg = _safe_float(fetched.get("average"), default=limit_price) or limit_price
            remainder = _prec_qty(exchange, pair, qty - filled)
            if remainder <= 0 or filled >= qty * 0.999:
                # nothing actually filled → real failure, don't fake a position
                if filled <= 0:
                    log(f"الأمر المحدود لم يُنفَّذ ولا كمية متبقية: {pair}")
                    return None
                return {"filled": filled, "amount": filled, "average": limit_avg, "price": limit_avg}
            log(f"لم يُنفَّذ الأمر المحدود — أمر سوق للمتبقي {remainder:.6f}: {pair}")
            try:
                fresh = _safe_float(exchange.fetch_ticker(pair).get("last"))
                if fresh:
                    price = fresh
            except Exception:
                pass
            params2 = {"orderLinkId": f"sc{int(time.time()*1000)}{os.urandom(4).hex()}"}
            order = exchange.create_order(pair, 'market', 'buy', remainder, price, params2)
            if order and filled > 0:
                mkt_filled = _safe_float(order.get("filled"), default=remainder)
                mkt_avg = _safe_float(order.get("average"), default=price) or price
                total_filled = filled + mkt_filled
                if total_filled > 0:
                    vwap = (filled * limit_avg + mkt_filled * mkt_avg) / total_filled
                    order["average"] = vwap
                order["filled"] = total_filled
                order["amount"] = total_filled
        return order
    except Exception as e:
        err = str(e)
        if "insufficient" in err.lower() or "170131" in err or "200004" in err:
            log(f"تخطي شراء {pair} — رصيد غير كافٍ")
        else:
            log(f"خطأ في الشراء: {pair} — {e}")
        return None


def spot_sell(exchange, pair: str, qty: float) -> dict | None:
    try:
        if not PAPER_MODE:
            try:
                base = pair.split("/")[0]
                free = float(exchange.fetch_balance().get(base, {}).get("free", 0))
                if free > 0 and free < qty:
                    qty = free
            except Exception:
                pass
        qty = _prec_qty(exchange, pair, qty)
        if qty <= 0:
            return None
        if PAPER_MODE:
            price = _safe_float(exchange.fetch_ticker(pair).get("last"))
            log(f"أمر بيع [ورقي]: {pair} | كمية={qty:.6f}")
            return {"filled": qty, "amount": qty, "average": price, "price": price}
        params = {"orderLinkId": f"sc{int(time.time()*1000)}{os.urandom(4).hex()}"}
        order = exchange.create_market_sell_order(pair, qty, params)
        log(f"أمر بيع: {pair} | كمية={qty:.6f}")
        return order
    except Exception as e:
        log(f"خطأ في البيع: {pair} — {e}")
        return None


# ---------- exchange-native stop loss (#3) ----------
# Software SL in check_positions is a BACKUP. The real protection is a stop
# order resting on Bybit, so positions survive a bot crash / server reboot.
def place_exchange_stop(exchange, pair: str, qty: float, trigger_price: float) -> str | None:
    """Place a resting stop-market sell on Bybit. Returns order id or None."""
    if PAPER_MODE:
        return None
    try:
        qty = _prec_qty(exchange, pair, qty)
        if qty <= 0:
            return None
        params = {
            "triggerPrice": float(exchange.price_to_precision(pair, trigger_price)),
            "triggerDirection": 2,   # trigger when price falls to/through trigger
            "orderLinkId": f"scsl{int(time.time()*1000)}{os.urandom(3).hex()}",
        }
        order = exchange.create_order(pair, "market", "sell", qty, None, params)
        oid = order.get("id", "")
        log(f"وقف على المنصّة: {pair} @ {trigger_price:.6g} | أمر={oid}")
        return oid
    except Exception as e:
        log(f"تعذّر وضع وقف على المنصّة {pair}: {e}")
        return None


def cancel_exchange_stop(exchange, pair: str, order_id: str | None) -> None:
    if PAPER_MODE or not order_id:
        return
    try:
        params = {"orderFilter": "StopOrder"} if getattr(exchange, "id", "") == "bybit" else {}
        exchange.cancel_order(order_id, pair, params=params)
        log(f"إلغاء وقف المنصّة: {pair} | أمر={order_id}")
    except Exception as e:
        log(f"تعذّر إلغاء وقف المنصّة {pair}: {e}")


def replace_exchange_stop(exchange, pos: dict, pair: str, qty: float, trigger_price: float) -> None:
    """Cancel any existing stop and place a fresh one for the new qty/trigger."""
    cancel_exchange_stop(exchange, pair, pos.get("sl_order_id"))
    pos["sl_order_id"] = place_exchange_stop(exchange, pair, qty, trigger_price)


# ---------- ATR ----------
_atr_cache: dict[str, tuple[float, float]] = {}

def calc_atr(exchange, pair: str) -> float | None:
    now = time.time()
    cached = _atr_cache.get(pair)
    if cached and now - cached[0] < 3600:
        return cached[1]
    try:
        ohlcv = exchange.fetch_ohlcv(pair, "1d", limit=ATR_PERIOD + 1)
        if len(ohlcv) < ATR_PERIOD + 1:
            return None
        trs = []
        for i in range(1, len(ohlcv)):
            h, l, prev_c = ohlcv[i][2], ohlcv[i][3], ohlcv[i - 1][4]
            trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
        atr = sum(trs[-ATR_PERIOD:]) / ATR_PERIOD
        _atr_cache[pair] = (now, atr)
        return atr
    except Exception as e:
        log(f"خطأ ATR {pair}: {e}")
        return None


# ---------- BTC filter ----------
_btc_sma_cache: tuple[float, float] | None = None

def btc_trend_ok(exchange) -> bool:
    global _btc_sma_cache
    try:
        ticker = exchange.fetch_ticker("BTC/USDT")
        last = _safe_float(ticker.get("last"))
        change = ticker.get("percentage")
        if change is None:
            op = _safe_float(ticker.get("open"))
            change = (last - op) / op * 100 if op and last else 0

        if change <= -BTC_DROP_LIMIT:
            log(f"فلتر BTC: {change:+.1f}% خلال 24س — إيقاف الشراء")
            return False

        now = time.time()
        if _btc_sma_cache is None or now - _btc_sma_cache[0] > 3600:
            ohlcv = exchange.fetch_ohlcv("BTC/USDT", "1d", limit=51)
            if len(ohlcv) >= 50:
                sma50 = sum(c[4] for c in ohlcv[-50:]) / 50
                _btc_sma_cache = (now, sma50)

        if _btc_sma_cache and last < _btc_sma_cache[1]:
            log(f"فلتر BTC: السعر ${last:.0f} تحت SMA50 ${_btc_sma_cache[1]:.0f} — إيقاف الشراء")
            return False

        return True
    except Exception as e:
        log(f"خطأ فلتر BTC: {e}")
        return True


# ---------- trade logic ----------
def open_trade(state: State, sig: ChannelSignal, exchange, reason: str = "إشارة قناة") -> bool:
    rollover_day(state)
    if sig.symbol in PROTECTED_SYMBOLS:
        log(f"عملة محمية — تجاهل: {sig.symbol}")
        return False
    if state.halted:
        log("متوقف — تجاوز حد الخسارة اليومي")
        return False
    if state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        log(f"متوقف — {state.consecutive_losses} خسائر متتالية")
        return False
    if state.daily_trades >= MAX_DAILY_TRADES:
        log(f"حد الصفقات اليومي ({MAX_DAILY_TRADES})")
        return False
    if len(state.open_positions) >= MAX_OPEN:
        log(f"حد المراكز المفتوحة ({MAX_OPEN})")
        return False

    pair = verify_symbol(exchange, sig.symbol)
    if not pair:
        log(f"الزوج غير موجود: {sig.symbol}/USDT")
        return False
    if pair in state.open_positions:
        log(f"مركز مفتوح بالفعل: {pair}")
        return False
    if any(p.get("symbol") == sig.symbol for p in state.open_positions.values()):
        log(f"العملة مفتوحة بالفعل: {sig.symbol}")
        return False

    if not PAPER_MODE:
        try:
            free = float(exchange.fetch_balance().get("USDT", {}).get("free", 0))
            if free < 1:
                return False
        except Exception:
            pass

    base_size = BYBIT_TRADE_SIZE
    trade_size = base_size
    if sig.tp_pct >= 20:
        trade_size = round(base_size * 1.3, 2)
    elif sig.tp_pct >= 10:
        trade_size = round(base_size * 1.1, 2)

    if trade_size < MIN_TRADE_USDT:
        log(f"حجم صفقة ${trade_size:.2f} أقل من الحد الأدنى")
        return False

    phase1_ratio = ENTRY_PHASES[0]["ratio"]
    phase1_size = round(trade_size * phase1_ratio, 2)
    remaining_phases = []
    for i, ph in enumerate(ENTRY_PHASES[1:], start=2):
        remaining_phases.append({
            "num": i, "ratio": ph["ratio"],
            "size": round(trade_size * ph["ratio"], 2),
            "delay_min": ph["delay_min"], "done": False,
        })

    entry_price = sig.buy_price if sig.buy_price > 0 else None
    if not entry_price:
        try:
            entry_price = _safe_float(exchange.fetch_ticker(pair).get("last"))
        except Exception:
            return False
    if not entry_price:
        return False

    qty = phase1_size / entry_price

    if not PAPER_MODE:
        order = spot_buy(exchange, pair, phase1_size)
        if not order:
            return False
        try:
            entry_price = float(order.get("average") or order.get("price") or entry_price)
            filled_qty = float(order.get("filled") or order.get("amount") or 0)
        except (TypeError, ValueError):
            filled_qty = 0
        # never record a position we don't actually hold
        if filled_qty <= 0 or entry_price <= 0:
            log(f"شراء {pair} لم يُنفَّذ فعلياً (كمية={filled_qty}) — تجاهل")
            return False
        qty = filled_qty

    # stop loss calculation — ENABLED
    atr = calc_atr(exchange, pair)
    atr_sl = round(entry_price - atr * ATR_SL_MULTIPLIER, 8) if atr else None
    fixed_sl = entry_price * (1 - SL_PCT / 100)
    cat_sl = entry_price * (1 - CATASTROPHIC_SL_PCT / 100)

    # use best of ATR SL and fixed SL (whichever is higher / tighter)
    if atr_sl and atr_sl > cat_sl:
        effective_sl = max(atr_sl, fixed_sl)
    else:
        effective_sl = fixed_sl

    # use signal's own stop if provided and reasonable
    if sig.stop_price > 0 and sig.stop_price < entry_price:
        sig_sl_pct = (entry_price - sig.stop_price) / entry_price * 100
        if sig_sl_pct <= 20:
            effective_sl = max(effective_sl, sig.stop_price)

    # (#5) never let the stop be tighter than MIN_SL_PCT — avoids noise stop-outs
    widest_allowed = entry_price * (1 - MIN_SL_PCT / 100)
    if effective_sl > widest_allowed:
        effective_sl = widest_allowed

    targets_list = []
    if sig.targets:
        for t in sig.targets:
            targets_list.append({"price": t["price"], "pct": t["pct"], "hit": t.get("completed", False)})

    sell_price = sig.sell_price
    if sell_price <= 0 and entry_price > 0:
        sell_price = entry_price * 1.10

    state.open_positions[pair] = {
        "trade_num": sig.trade_num, "symbol": sig.symbol, "pair": pair,
        "entry": entry_price, "qty": qty,
        "tp": sell_price, "tp_pct": sig.tp_pct,
        "sl": round(effective_sl, 8),
        "atr_sl": atr_sl,
        "opened": time.time(),
        "opened_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason, "channel": sig.channel,
        "total_size": trade_size,
        "phases": remaining_phases,
        "targets": targets_list,
        "targets_hit": 0,
        "highest_price": entry_price,
        "score": sig.score,
        "sl_order_id": None,
    }
    state.daily_trades += 1
    if sig.symbol not in state.entered_symbols:
        state.entered_symbols.append(sig.symbol)

    # (#3) place a resting stop on the exchange so the position is protected
    # even if the bot dies. Software SL in check_positions remains a backup.
    if not PAPER_MODE:
        state.open_positions[pair]["sl_order_id"] = place_exchange_stop(
            exchange, pair, qty, effective_sl)
    save_state(state)

    mode = "ورقي" if PAPER_MODE else "حقيقي"
    sl_info = f"ATR={atr_sl:.4f}" if atr_sl else f"ثابت={fixed_sl:.4f}"
    n_phases = 1 + len(remaining_phases)
    msg = (f"صفقة [{mode}] — {reason}\n"
           f"{sig.symbol} ({pair}) [{sig.channel}]\n"
           f"دخول: {entry_price} | هدف: {sell_price} ({sig.tp_pct:.1f}%)\n"
           f"وقف: {effective_sl:.4f} ({sl_info})\n"
           f"حجم: دفعة 1/{n_phases} ${phase1_size:.0f} | نقاط: {sig.score:.0f}")
    log(msg)
    notify(msg)
    return True


def close_trade(state: State, pair: str, reason: str, price: float, exchange, skip_sell: bool = False):
    pos = state.open_positions.get(pair)
    if not pos:
        return
    sell_qty = pos["qty"]

    if not PAPER_MODE and not skip_sell:
        # cancel the resting exchange stop first so it can't fire on the coins
        # we're about to sell (or sell after we've already closed)
        cancel_exchange_stop(exchange, pair, pos.get("sl_order_id"))
        pos["sl_order_id"] = None
        try:
            balance = exchange.fetch_balance()
            sym_b = pair.split("/")[0]
            available = float(balance.get(sym_b, {}).get("free", 0))
            if available < sell_qty:
                sell_qty = available
        except Exception:
            pass
        if sell_qty * price < 1.0:
            log(f"كمية {pair} غبار (${sell_qty * price:.4f}) — إغلاق بدون بيع")
        elif sell_qty > 0:
            order = spot_sell(exchange, pair, sell_qty)
            if order is None:
                log(f"فشل بيع {pair} — تبقى مفتوحة لإعادة المحاولة")
                return

    # PnL on the quantity we actually sold (clamped to real balance above)
    pnl = (price - pos["entry"]) * sell_qty
    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100

    channel = pos.get("channel", "unknown")
    symbol = pos.get("symbol", pair.split("/")[0]).upper()

    state.open_positions.pop(pair, None)
    if symbol in state.entered_symbols:
        state.entered_symbols.remove(symbol)

    state.daily_pnl += pnl
    if state.daily_pnl <= -MAX_DAILY_LOSS:
        state.halted = True
        log(f"إيقاف التداول — خسارة يومية ${state.daily_pnl:.2f}")

    if pnl < 0:
        state.consecutive_losses += 1
    else:
        state.consecutive_losses = 0

    state.trade_history.append({
        "pair": pair, "entry": pos["entry"], "exit": price,
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
        "reason": reason, "channel": channel,
        "closed": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if len(state.trade_history) > 500:
        state.trade_history = state.trade_history[-500:]
    save_state(state)

    # self-learning: record result
    learning_record_trade(channel, symbol, pnl, pnl_pct)

    sign = "+" if pnl >= 0 else ""
    msg = (f"إغلاق: {pair} | {reason}\n"
           f"دخول: {pos['entry']} → خروج: {price}\n"
           f"ربح: {sign}${pnl:.2f} ({sign}{pnl_pct:.1f}%)\n"
           f"القناة: {channel}")
    log(msg)
    notify(msg)


def target_sell(state, pair: str, price: float, exchange, target: dict, sell_pct: float):
    pos = state.open_positions.get(pair)
    if not pos:
        return
    sell_ratio = min(sell_pct, 100) / 100
    sell_qty = pos["qty"] * sell_ratio
    remaining_qty = pos["qty"] - sell_qty

    if remaining_qty * price < MIN_TRADE_USDT:
        close_trade(state, pair, f"هدف ({target['pct']}%)", price, exchange)
        return

    if not PAPER_MODE:
        # the resting stop reserves the base coins, so cancel it before selling
        cancel_exchange_stop(exchange, pair, pos.get("sl_order_id"))
        pos["sl_order_id"] = None
        order = spot_sell(exchange, pair, sell_qty)
        if not order:
            # sell failed — restore a stop for the full (unchanged) qty
            pos["sl_order_id"] = place_exchange_stop(exchange, pair, pos["qty"], pos.get("sl") or price)
            save_state(state)
            return
    pos["qty"] = remaining_qty
    target["hit"] = True
    pos["targets_hit"] = pos.get("targets_hit", 0) + 1
    # re-place the stop for the remaining quantity
    if not PAPER_MODE and pos.get("sl"):
        pos["sl_order_id"] = place_exchange_stop(exchange, pair, remaining_qty, pos["sl"])
    save_state(state)

    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100
    hit_count = pos["targets_hit"]
    total_targets = len(pos.get("targets", []))
    msg = (f"🎯 هدف {hit_count}/{total_targets}: {pair}\n"
           f"بيع {sell_pct:.0f}% @ {price} (+{pnl_pct:.1f}%)")
    log(msg)
    notify(msg)


# ---------- position checker ----------
async def check_positions(state: State, exchange):
    rollover_day(state)
    if not state.open_positions:
        return
    for pair in list(state.open_positions):
        pos = state.open_positions.get(pair)
        if not pos:
            continue
        if pos.get("symbol") in PROTECTED_SYMBOLS:
            continue
        # guard against corrupted state: entry<=0 would crash every PnL calc
        # (close_trade also divides by entry) so drop the position safely here
        if _safe_float(pos.get("entry")) <= 0:
            log(f"⚠️ مركز تالف (entry<=0): {pair} — إزالة من الحالة")
            state.open_positions.pop(pair, None)
            sym = pos.get("symbol", pair.split("/")[0]).upper()
            if sym in state.entered_symbols:
                state.entered_symbols.remove(sym)
            save_state(state)
            continue
        try:
            price = _safe_float(exchange.fetch_ticker(pair).get("last"))
            if not price:
                continue
        except Exception as e:
            log(f"خطأ في جلب سعر {pair}: {e}")
            continue

        # track highest price
        highest = pos.get("highest_price", pos["entry"])
        if price > highest:
            pos["highest_price"] = price
            highest = price
            save_state(state)

        # 1) STOP LOSS (software backup to the exchange-native stop) — ENABLED.
        # (#6) catastrophic level is an INDEPENDENT floor, checked first, so it
        # still protects even if pos["sl"] was somehow set wider than it.
        cat_sl = pos["entry"] * (1 - CATASTROPHIC_SL_PCT / 100)
        if price <= cat_sl:
            sl_pct = (pos["entry"] - price) / pos["entry"] * 100
            close_trade(state, pair, f"وقف كارثي (-{sl_pct:.1f}%)", price, exchange)
            continue
        sl = pos.get("sl", 0)
        if sl > 0 and price <= sl:
            sl_pct = (pos["entry"] - price) / pos["entry"] * 100
            close_trade(state, pair, f"وقف خسارة (-{sl_pct:.1f}%)", price, exchange)
            continue

        # 2) trailing stop — activates after TRAILING_STOP_ACTIVATE_PCT gain
        gain_from_entry = (highest - pos["entry"]) / pos["entry"] * 100
        if gain_from_entry >= TRAILING_STOP_ACTIVATE_PCT:
            trail_stop = highest * (1 - TRAILING_STOP_DISTANCE_PCT / 100)
            if price <= trail_stop:
                close_trade(state, pair,
                    f"وقف متحرك (أعلى={highest:.4f} → نزل {TRAILING_STOP_DISTANCE_PCT}%)",
                    price, exchange)
                continue

        # 3) target sells (multi-target)
        targets = pos.get("targets", [])
        if len(targets) > 1:
            targets_hit = pos.get("targets_hit", 0)
            remaining_targets = [t for i, t in enumerate(targets) if i >= targets_hit and not t.get("hit")]
            if remaining_targets:
                next_target = remaining_targets[0]
                is_last = len(remaining_targets) == 1
                if price >= next_target["price"]:
                    if is_last:
                        close_trade(state, pair, f"هدف أخير ({next_target['pct']}%)", price, exchange)
                    else:
                        sell_pct_per = 100 / len(remaining_targets)
                        target_sell(state, pair, price, exchange, next_target, sell_pct_per)
                    continue
        else:
            if price >= pos["tp"]:
                close_trade(state, pair, "هدف ربح", price, exchange)
                continue

        # 4) max hold duration
        if MAX_HOLD_DAYS > 0 and (time.time() - pos["opened"]) / 86400 >= MAX_HOLD_DAYS:
            close_trade(state, pair, f"مدة قصوى ({MAX_HOLD_DAYS} يوم)", price, exchange)


# ---------- phase 2 entry ----------
async def check_phase2(state: State, exchange):
    for pair in list(state.open_positions):
        pos = state.open_positions.get(pair)
        if not pos:
            continue
        phases = pos.get("phases", [])
        pending = [p for p in phases if not p.get("done")]
        if not pending:
            continue

        elapsed_min = (time.time() - pos["opened"]) / 60

        if not PAPER_MODE:
            try:
                free = float(exchange.fetch_balance().get("USDT", {}).get("free", 0))
                if free < 1:
                    continue
            except Exception:
                pass

        try:
            price = _safe_float(exchange.fetch_ticker(pair).get("last"))
            if not price:
                continue
        except Exception:
            continue

        for phase in pending:
            if elapsed_min < phase["delay_min"]:
                break
            phase_size = phase.get("size", 0)
            if phase_size < MIN_TRADE_USDT:
                phase["done"] = True
                save_state(state)
                continue

            if price > pos["entry"] * (1 + PHASE_CANCEL_RISE_PCT / 100):
                phase["done"] = True
                save_state(state)
                log(f"دفعة {phase['num']} ألغيت: {pair} — السعر ارتفع +{PHASE_CANCEL_RISE_PCT}%")
                continue

            if not PAPER_MODE:
                order = spot_buy(exchange, pair, phase_size)
                if not order:
                    break
                try:
                    p_qty = float(order.get("filled") or order.get("amount") or phase_size / price)
                    p_price = float(order.get("average") or order.get("price") or price)
                except (TypeError, ValueError):
                    p_qty = phase_size / price
                    p_price = price
            else:
                p_qty = phase_size / price
                p_price = price

            old_qty, old_entry = pos["qty"], pos["entry"]
            new_qty = old_qty + p_qty
            new_entry = (old_entry * old_qty + p_price * p_qty) / new_qty
            pos["qty"] = new_qty
            pos["entry"] = round(new_entry, 8)
            phase["done"] = True

            # update stop loss for new (lower) average entry
            atr = calc_atr(exchange, pair)
            if atr:
                pos["atr_sl"] = round(new_entry - atr * ATR_SL_MULTIPLIER, 8)
            fixed_sl = new_entry * (1 - SL_PCT / 100)
            atr_sl = pos.get("atr_sl")
            if atr_sl and atr_sl > new_entry * (1 - CATASTROPHIC_SL_PCT / 100):
                new_sl = max(atr_sl, fixed_sl)
            else:
                new_sl = fixed_sl
            # (#5) enforce minimum stop width
            widest_allowed = new_entry * (1 - MIN_SL_PCT / 100)
            if new_sl > widest_allowed:
                new_sl = widest_allowed
            pos["sl"] = round(new_sl, 8)

            # (#3) replace the resting exchange stop for the new qty/trigger
            if not PAPER_MODE:
                replace_exchange_stop(exchange, pos, pair, new_qty, pos["sl"])

            save_state(state)
            total_phases = 1 + len(phases)
            msg = (f"دفعة {phase['num']}/{total_phases}: {pair}\n"
                   f"شراء إضافي ${phase_size:.0f} @ {p_price:.4f}\n"
                   f"متوسط جديد: {new_entry:.4f} | وقف: {pos['sl']:.4f}")
            log(msg)
            notify(msg)


# ---------- pending signals (smart entry) ----------
async def check_pending_signals(state: State, exchange):
    if not state.pending_signals:
        return
    rollover_day(state)
    if state.halted:
        return

    if not PAPER_MODE:
        try:
            free = float(exchange.fetch_balance().get("USDT", {}).get("free", 0))
            if free < 1:
                return
        except Exception:
            pass

    for sig_data in list(state.pending_signals):
        symbol = sig_data["symbol"]
        buy_price = sig_data.get("buy_price", 0)
        if symbol in state.entered_symbols:
            state.pending_signals.remove(sig_data)
            continue
        pair = verify_symbol(exchange, symbol)
        if not pair:
            continue
        if pair in state.open_positions:
            continue
        try:
            price = _safe_float(exchange.fetch_ticker(pair).get("last"))
            if not price:
                continue
        except Exception:
            continue

        # if no buy price, use current market price
        if buy_price <= 0:
            buy_price = price

        # before we start watching, wait for price to dip near/below target.
        # once watching has begun, the bounce/timeout logic below governs entry
        # (the margin gate must not keep skipping or timeout never fires).
        if "watch_start" not in sig_data:
            margin = buy_price * 1.02  # within 2% of target
            if price > margin:
                continue
            sig_data["watch_start"] = time.time()
            sig_data["lowest_seen"] = price
            save_state(state)
            log(f"مراقبة: {symbol} @ ${price:.4f} (هدف: ${buy_price}) — ننتظر سعر أفضل")
            continue

        if price < sig_data.get("lowest_seen", price):
            sig_data["lowest_seen"] = price
            save_state(state)

        lowest = sig_data["lowest_seen"]
        elapsed_min = (time.time() - sig_data["watch_start"]) / 60
        bounced = lowest > 0 and price > lowest * (1 + SMART_ENTRY_BOUNCE_PCT / 100)
        timed_out = elapsed_min >= SMART_ENTRY_WAIT_MIN

        if not (bounced and elapsed_min >= 10) and not timed_out:
            continue

        entry_reason = "ارتداد" if bounced else "انتهاء الانتظار"

        # respect BTC trend for pending entries too
        if not btc_trend_ok(exchange):
            continue

        sig = ChannelSignal(
            channel=sig_data.get("channel", "unknown"),
            symbol=symbol,
            buy_price=price,
            sell_price=sig_data.get("sell_price", price * 1.10),
            stop_price=sig_data.get("stop_price", 0),
            tp_pct=sig_data.get("tp_pct", 10.0),
            targets=[{"price": t["price"], "pct": t["pct"], "completed": False}
                     for t in sig_data.get("targets", [])],
            trade_num=sig_data.get("trade_num", 0),
            score=sig_data.get("score", 50),
        )
        log(f"شراء ذكي: {symbol} @ ${price:.4f} ({entry_reason})")
        if open_trade(state, sig, exchange, reason=f"إشارة معلّقة ({entry_reason})"):
            state.pending_signals.remove(sig_data)
            state.executed_signals.append(sig_data.get("key", f"{symbol}_0"))
            if len(state.executed_signals) > 500:
                state.executed_signals = state.executed_signals[-500:]
            save_state(state)


# ---------- stats ----------
def compute_stats(history: list[dict]) -> str:
    if len(history) < 3:
        return f"صفقات مغلقة: {len(history)} (يحتاج 3+ لدقة التحليل)"
    wins = [t for t in history if t.get("pnl", 0) > 0]
    losses = [t for t in history if t.get("pnl", 0) <= 0]
    n = len(history)
    wr = len(wins) / n * 100
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
    expectancy = (wr / 100 * avg_win) + ((1 - wr / 100) * avg_loss)
    total = sum(t["pnl"] for t in history)

    # channel breakdown
    ch_stats = {}
    for t in history:
        ch = t.get("channel", "unknown")
        ch_stats.setdefault(ch, {"wins": 0, "losses": 0, "pnl": 0.0})
        ch_stats[ch]["wins" if t.get("pnl", 0) > 0 else "losses"] += 1
        ch_stats[ch]["pnl"] += t.get("pnl", 0)

    verdict = "إيجابي ✅" if expectancy > 0 else "سلبي ⚠️"
    lines = [
        f"📊 <b>إحصائيات ({n} صفقة)</b>",
        f"نسبة الربح: {wr:.1f}% ({len(wins)} ربح / {len(losses)} خسارة)",
        f"متوسط الربح: ${avg_win:.2f} | متوسط الخسارة: ${avg_loss:.2f}",
        f"التوقع الرياضي: ${expectancy:.2f}/صفقة ({verdict})",
        f"الإجمالي: ${total:.2f}",
        "",
        "<b>أداء القنوات:</b>",
    ]
    for ch, data in sorted(ch_stats.items(), key=lambda x: x[1]["pnl"], reverse=True):
        ch_total = data["wins"] + data["losses"]
        ch_wr = data["wins"] / ch_total * 100 if ch_total > 0 else 0
        lines.append(f"  {ch}: {ch_wr:.0f}% ({data['wins']}W/{data['losses']}L) ${data['pnl']:.2f}")

    return "\n".join(lines)


# ---------- check mode ----------
def run_check():
    log("=== وضع الفحص ===")
    log(f"TG_API_ID: {'OK' if TG_API_ID else 'مفقود'}")
    log(f"قنوات التداول: {WATCH_CHANNELS}")
    log(f"قنوات الأخبار (AI فقط): {NEWS_CHANNELS}")
    log(f"رأس المال: ${CAPITAL} | حجم: ${BYBIT_TRADE_SIZE}")
    log(f"وقف خسارة: {SL_PCT}% ثابت | كارثي: {CATASTROPHIC_SL_PCT}%")
    log(f"وقف متحرك: +{TRAILING_STOP_ACTIVATE_PCT}% → -{TRAILING_STOP_DISTANCE_PCT}%")
    log(f"الوضع: {'ورقي' if PAPER_MODE else 'حقيقي'}")
    log(f"الحد الأدنى للنقاط: {MIN_SIGNAL_SCORE}")

    if BYBIT_KEY:
        try:
            ex = get_exchange()
            ex.load_markets()
            usdt = ex.fetch_balance().get("USDT", {}).get("free", 0)
            log(f"Bybit: متصل | USDT={usdt}")
        except Exception as e:
            log(f"Bybit: خطأ — {e}")

    ai = _load_ai_analysis()
    if ai:
        log(f"AI: {len(ai.get('buy', []))} شراء, {len(ai.get('sell', []))} بيع")
    else:
        log("AI: لا يوجد تحليل")

    learning = _load_learning()
    channels = learning.get("channels", {})
    if channels:
        log("تعلم القنوات:")
        for ch, data in channels.items():
            total = data.get("trades", 0)
            wr = data.get("wins", 0) / total * 100 if total > 0 else 0
            log(f"  {ch}: {wr:.0f}% ({total} صفقة) ${data.get('pnl', 0):.2f}")

    state = load_state()
    log(f"مراكز: {len(state.open_positions)} | معلقة: {len(state.pending_signals)}")
    log("=== انتهى الفحص ===")


def run_status():
    state = load_state()
    print(f"مراكز مفتوحة: {len(state.open_positions)}")
    for pair, pos in state.open_positions.items():
        age_h = (time.time() - pos.get("opened", 0)) / 3600
        print(f"  {pos.get('symbol', '?')} ({pair}) @ {pos['entry']} | "
              f"وقف: {pos.get('sl', 'N/A')} | هدف: {pos.get('tp', 'N/A')} | "
              f"قناة: {pos.get('channel', '?')} | عمر: {age_h:.1f}س")
    print(f"\nمعلقة: {len(state.pending_signals)}")
    for s in state.pending_signals:
        print(f"  {s.get('symbol', '?')} من {s.get('channel', '?')} — شراء: {s.get('buy_price', 0)}")
    report = compute_stats(state.trade_history)
    if report:
        clean = report.replace("<b>", "").replace("</b>", "")
        print(f"\n{clean}")

    learning = _load_learning()
    channels = learning.get("channels", {})
    if channels:
        print("\nتعلم القنوات:")
        for ch, data in sorted(channels.items(), key=lambda x: x[1].get("pnl", 0), reverse=True):
            total = data.get("trades", 0)
            w, l = data.get("wins", 0), data.get("losses", 0)
            wr = w / total * 100 if total > 0 else 0
            print(f"  {ch}: {wr:.0f}% W/R ({w}W/{l}L) PnL: ${data.get('pnl', 0):.2f}")


# ---------- main ----------
async def main():
    if "--check" in sys.argv:
        run_check()
        return
    if "--status" in sys.argv:
        run_status()
        return

    _acquire_lock()

    from telethon import TelegramClient, events
    mode = "ورقي" if PAPER_MODE else "حقيقي"
    log(f"=== بدء البوت الذكي [{mode}] ===")
    log(f"قنوات التداول: {WATCH_CHANNELS}")
    log(f"قنوات الأخبار (AI فقط): {NEWS_CHANNELS}")
    log(f"رأس المال: ${CAPITAL} | حجم: ${BYBIT_TRADE_SIZE} | وقف: {SL_PCT}%")
    log(f"حد النقاط: {MIN_SIGNAL_SCORE} | AI: {'مفعّل' if AI_ANALYSIS_FILE.exists() else 'غير متاح'}")

    state = load_state()
    rollover_day(state)

    global _exchange
    try:
        _exchange = get_exchange()
        _exchange.load_markets()
        log(f"Bybit متصل | testnet={BYBIT_TESTNET}")
    except Exception as e:
        log(f"خطأ Bybit: {e}")
        return

    client = TelegramClient(TG_SESSION, TG_API_ID, TG_API_HASH)
    await client.start()
    me = await client.get_me()
    log(f"Telegram connected as {me.first_name}")

    # map resolved chat-id -> the exact configured channel name. This makes
    # channel identity reliable regardless of whether a message exposes a
    # username or only a title (a news channel without a username must NOT be
    # mistaken for a trading channel), and keeps learning-stats keys stable.
    chat_id_to_name: dict[int, str] = {}
    for ch_name in ALL_CHANNELS:
        kind = "أخبار" if ch_name.lower() in _NEWS_SET else "تداول"
        try:
            entity = await client.get_entity(ch_name)
            chat_id_to_name[entity.id] = ch_name
            log(f"Listening [{kind}]: {getattr(entity, 'title', ch_name)} (id={entity.id})")
        except Exception as e:
            log(f"خطأ في قناة {ch_name}: {e}")

    @client.on(events.NewMessage(chats=ALL_CHANNELS))
    async def on_signal(event):
        try:
            text = event.raw_text
            if not text:
                return

            # resolve the channel to its CONFIGURED name via chat-id (reliable).
            # fall back to username/title only if the id isn't in the map.
            channel_name = chat_id_to_name.get(getattr(event, "chat_id", None))
            if not channel_name:
                chat = event.chat
                channel_name = "unknown"
                if chat:
                    channel_name = getattr(chat, 'username', None) or \
                                   getattr(chat, 'title', None) or str(chat.id)

            log(f"[{channel_name}] رسالة: {text[:80]}...")

            # feed bot_monitor's AI pipeline with the raw message (every message,
            # not just parsed signals) so ai_channel_analysis.json stays fresh
            try:
                _save_raw_message(channel_name, text, event.id)
            except Exception:
                pass

            # news channels are feed-only — never open a trade from a news headline
            if channel_name.lower() in _NEWS_SET:
                return

            sig = parse_channel_signal(text, channel_name, msg_id=event.id)
            if not sig:
                return

            sig.score = score_signal(sig)
            log(f"إشارة: {sig.symbol} من {sig.channel} | نقاط: {sig.score:.0f} | "
                f"شراء={sig.buy_price} هدف={sig.sell_price}")

            if sig.score < MIN_SIGNAL_SCORE:
                log(f"تجاهل: نقاط {sig.score:.0f} < {MIN_SIGNAL_SCORE}")
                return

            # (#12) while halted (daily loss / loss streak), ignore signals
            # outright — do NOT queue them, or they'd all fire at once after
            # the day rolls over.
            if state.halted or state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                log("متوقف (إيقاف يومي/خسائر متتالية) — تجاهل الإشارة بدل تعليقها")
                return

            sig_key = f"{sig.symbol}_{sig.channel}_{event.id}"
            if sig_key in state.executed_signals:
                log(f"إشارة سبق تنفيذها: {sig_key}")
                return
            # don't double-track a symbol already held or already queued
            if sig.symbol in state.entered_symbols or \
               any(p.get("symbol") == sig.symbol for p in state.open_positions.values()):
                log(f"العملة مفتوحة بالفعل — تجاهل: {sig.symbol}")
                return

            notify(f"إشارة جديدة [{sig.channel}]\n{sig.symbol} | نقاط: {sig.score:.0f}\n"
                   f"شراء: {sig.buy_price} | هدف: {sig.sell_price} ({sig.tp_pct:.1f}%)")

            # BTC trend negative → queue as pending instead of discarding the signal
            btc_ok = btc_trend_ok(_exchange)
            if btc_ok and open_trade(state, sig, _exchange, reason=f"إشارة [{sig.channel}]"):
                state.executed_signals.append(sig_key)
                if len(state.executed_signals) > 500:
                    state.executed_signals = state.executed_signals[-500:]
                save_state(state)
            else:
                if not btc_ok:
                    log("BTC trend سلبي — حفظ كإشارة معلّقة")
                if not any(p.get("symbol") == sig.symbol for p in state.pending_signals):
                    state.pending_signals.append({
                        "key": sig_key, "symbol": sig.symbol,
                        "channel": sig.channel,
                        "buy_price": sig.buy_price, "sell_price": sig.sell_price,
                        "stop_price": sig.stop_price,
                        "tp_pct": sig.tp_pct, "trade_num": sig.trade_num,
                        "targets": [{"price": t["price"], "pct": t["pct"]}
                                    for t in sig.targets] if sig.targets else [],
                        "score": sig.score,
                        "added": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    save_state(state)
                    log(f"إشارة معلّقة: {sig_key}")
        except Exception as e:
            # an event callback must never raise — keep the listener alive
            log(f"خطأ في معالجة الإشارة: {e}")

    async def position_checker():
        first = True
        while True:
            # check existing positions immediately on startup (don't wait a
            # full interval before the first stop-loss evaluation), then loop
            if not first:
                await asyncio.sleep(CHECK_INTERVAL)
            first = False
            try:
                log(f"نبض — مراكز: {len(state.open_positions)} | معلقة: {len(state.pending_signals)}")
                if state.open_positions:
                    await check_positions(state, _exchange)
                    await check_phase2(state, _exchange)
            except Exception as e:
                log(f"خطأ في فحص المراكز: {e}")

    async def pending_checker():
        while True:
            await asyncio.sleep(600)
            try:
                if state.pending_signals:
                    await check_pending_signals(state, _exchange)
            except Exception as e:
                log(f"خطأ في فحص المعلقة: {e}")

    async def daily_stats():
        while True:
            now = datetime.now()
            target = now.replace(hour=21, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_sec = (target - now).total_seconds()
            await asyncio.sleep(wait_sec)
            try:
                report = compute_stats(state.trade_history)
                if report:
                    notify(report)
                    log("تقرير يومي أُرسل")
            except Exception as e:
                log(f"خطأ تقرير: {e}")

    asyncio.create_task(position_checker())
    asyncio.create_task(pending_checker())
    asyncio.create_task(daily_stats())

    log(f"Listening... (cap=${CAPITAL}, "
        f"SL={SL_PCT}%/catastrophic={CATASTROPHIC_SL_PCT}%, "
        f"trailing=+{TRAILING_STOP_ACTIVATE_PCT}%→-{TRAILING_STOP_DISTANCE_PCT}%, "
        f"min_score={MIN_SIGNAL_SCORE}, max_open={MAX_OPEN}, "
        f"max_hold={MAX_HOLD_DAYS}d)")
    if PROTECTED_SYMBOLS:
        log(f"عملات محمية: {PROTECTED_SYMBOLS}")
    await client.run_until_disconnected()


if __name__ == "__main__":
    if "--stats" in sys.argv:
        state = load_state()
        report = compute_stats(state.trade_history)
        clean = report.replace("<b>", "").replace("</b>", "")
        print(clean)
        sys.exit(0)
    if "--status" in sys.argv:
        run_status()
        sys.exit(0)
    if "--sell" in sys.argv:
        idx = sys.argv.index("--sell")
        if idx + 1 >= len(sys.argv):
            print("الاستخدام: --sell SYMBOL")
            sys.exit(1)
        symbol = sys.argv[idx + 1].upper()
        state = load_state()
        found = False
        for pair, pos in list(state.open_positions.items()):
            if pos.get("symbol", pair.split("/")[0]).upper() == symbol:
                import ccxt
                ex = get_exchange()
                ex.load_markets()
                price = float(ex.fetch_ticker(pair).get("last", 0))
                if price <= 0:
                    print(f"❌ تعذر جلب سعر {pair}")
                    sys.exit(1)
                print(f"بيع {pair} @ {price}...")
                order = spot_sell(ex, pair, pos["qty"])
                if order:
                    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100
                    pnl = (price - pos["entry"]) * pos["qty"]
                    channel = pos.get("channel", "unknown")
                    # re-read state right before mutating so a concurrently
                    # running live bot's changes aren't clobbered by this CLI sell
                    state = load_state()
                    state.trade_history.append({
                        "pair": pair, "entry": pos["entry"], "exit": price,
                        "pnl": round(pnl, 4), "pnl_pct": round(pnl_pct, 2),
                        "reason": "بيع يدوي (CLI)", "channel": channel,
                        "closed": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    state.open_positions.pop(pair, None)
                    if symbol in state.entered_symbols:
                        state.entered_symbols.remove(symbol)
                    save_state(state)
                    learning_record_trade(channel, symbol, pnl, pnl_pct)
                    sign = "+" if pnl >= 0 else ""
                    print(f"✅ تم بيع {pair} @ {price} | ربح: {sign}{pnl_pct:.1f}%")
                    notify(f"بيع يدوي: {pair}\nسعر: {price} ({sign}{pnl_pct:.1f}%)")
                else:
                    print(f"❌ فشل بيع {pair}")
                found = True
                break
        if not found:
            print(f"❌ {symbol} غير موجود في المراكز المفتوحة")
        sys.exit(0)
    asyncio.run(main())
