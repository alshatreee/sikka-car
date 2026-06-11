"""
monthly_channel_bot.py — Bybit Spot trader من قنوات تيلجرام شهرية عربية

يقرأ توصيات بصيغة: رقم الصفقة / العملة / سعر الشراء / سعر البيع (%)
+ يفحص أسعار التعزيز من الرسائل القديمة (شهر كامل)
وينفذ سبوت على Bybit. الوضع الافتراضي ورقي.

    python3 monthly_channel_bot.py              # ورقي
    python3 monthly_channel_bot.py --live       # حقيقي
    python3 monthly_channel_bot.py --check      # فحص

    pip install telethon ccxt python-dotenv requests
"""
from __future__ import annotations
import asyncio, json, os, re, sys, time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# ---------- paths ----------
BASE_DIR = Path(r"C:\Users\xman9\Desktop") if os.name == "nt" else Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE, STATE_FILE, LOG_FILE, TRACKER_FILE = (
    BASE_DIR / ".env_monthly", BASE_DIR / "monthly_state.json", BASE_DIR / "monthly.log",
    BASE_DIR / "signal_tracker.json")
ML_RECOMMENDATIONS_FILE = BASE_DIR / "ml_recommendations.json"
load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# ---------- config ----------
TG_API_ID    = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH  = os.getenv("TG_API_HASH", "")
TG_CHANNELS  = [c.strip() for c in os.getenv("MONTHLY_CHANNELS",
                os.getenv("MONTHLY_CHANNEL", "")).split(",") if c.strip()]
TG_SESSION   = str(BASE_DIR / "monthly_session")
BYBIT_KEY    = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET = os.getenv("BYBIT_API_SECRET", "")
BYBIT_TESTNET = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
KUCOIN_KEY    = os.getenv("KUCOIN_API_KEY", "")
KUCOIN_SECRET = os.getenv("KUCOIN_API_SECRET", "")
KUCOIN_PASS   = os.getenv("KUCOIN_PASSPHRASE", "")
GATE_KEY      = os.getenv("GATE_API_KEY", "")
GATE_SECRET   = os.getenv("GATE_API_SECRET", "")
NOTIFY_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

CAPITAL      = float(os.getenv("MONTHLY_CAPITAL", "1000"))
TRADE_PCT    = float(os.getenv("MONTHLY_TRADE_PCT", "15"))
TRADE_SIZE   = CAPITAL * TRADE_PCT / 100
SL_PCT       = float(os.getenv("MONTHLY_SL_PCT", "5.0"))
CATASTROPHIC_SL_PCT = float(os.getenv("MONTHLY_CATASTROPHIC_SL", "999"))
MAX_HOLD_DAYS = int(os.getenv("MONTHLY_MAX_HOLD_DAYS", "0"))
MAX_DAILY_TRADES = 10
MAX_OPEN = 10
MAX_DAILY_LOSS_PCT = float(os.getenv("MONTHLY_MAX_LOSS_PCT", "5.0"))
MAX_DAILY_LOSS = CAPITAL * MAX_DAILY_LOSS_PCT / 100
PARTIAL_TP_PCT = float(os.getenv("MONTHLY_PARTIAL_TP_PCT", "999"))
PARTIAL_SELL_PCT = float(os.getenv("MONTHLY_PARTIAL_SELL_PCT", "50"))
REBUY_DROP_PCT = float(os.getenv("MONTHLY_REBUY_DROP_PCT", "5.0"))
BTC_DROP_LIMIT = float(os.getenv("MONTHLY_BTC_DROP_LIMIT", "5.0"))
LIMIT_ORDER_SLIP = float(os.getenv("MONTHLY_LIMIT_SLIP", "0.5"))  # % فوق السوق للشراء
MIN_TRADE_USDT = float(os.getenv("MONTHLY_MIN_TRADE_USDT", "20.0"))
KUCOIN_TRADE_SIZE = float(os.getenv("MONTHLY_KUCOIN_TRADE_SIZE", "100"))
BYBIT_TRADE_SIZE = float(os.getenv("MONTHLY_BYBIT_TRADE_SIZE", "100"))
PROTECTED_SYMBOLS = [s.strip().upper() for s in os.getenv("MONTHLY_PROTECTED_SYMBOLS", "").split(",") if s.strip()]
MAX_CONSECUTIVE_LOSSES = int(os.getenv("MONTHLY_MAX_CONSEC_LOSSES", "3"))
TRAILING_STOP_ACTIVATE_PCT = float(os.getenv("MONTHLY_TRAIL_ACTIVATE", "999"))
TRAILING_STOP_DISTANCE_PCT = float(os.getenv("MONTHLY_TRAIL_DISTANCE", "3.0"))
MAX_CONCURRENT = int(os.getenv("MONTHLY_MAX_CONCURRENT", "50"))
PHASE1_RATIO = float(os.getenv("MONTHLY_PHASE1_RATIO", "0.4"))
PHASE2_DELAY_MIN = int(os.getenv("MONTHLY_PHASE2_DELAY", "120"))
ENTRY_PHASES = [
    {"ratio": 0.25, "delay_min": 0},
    {"ratio": 0.25, "delay_min": 120},
    {"ratio": 0.25, "delay_min": 300},
    {"ratio": 0.25, "delay_min": 600},
]
PHASE_CANCEL_RISE_PCT = float(os.getenv("MONTHLY_PHASE_CANCEL_RISE", "5.0"))
ATR_PERIOD = int(os.getenv("MONTHLY_ATR_PERIOD", "14"))
ATR_SL_MULTIPLIER = float(os.getenv("MONTHLY_ATR_SL_MULT", "2.0"))
CHECK_INTERVAL = 300
PAPER_MODE = "--live" not in sys.argv

HISTORY_DAYS   = int(os.getenv("MONTHLY_HISTORY_DAYS", "30"))
REINFORCE_PCT  = float(os.getenv("MONTHLY_REINFORCE_PCT", "2.0"))
REINFORCE_CHECK_SEC = int(os.getenv("MONTHLY_REINFORCE_SEC", "600"))
SMART_ENTRY_WAIT_MIN = int(os.getenv("MONTHLY_SMART_ENTRY_WAIT", "60"))
SMART_ENTRY_BOUNCE_PCT = float(os.getenv("MONTHLY_SMART_BOUNCE", "1.0"))

# ---------- قنوات المراقبة اليومية ----------
WATCH_CHANNELS = [
    "cryptomena1", "arabcharts", "crypto_q88",
    "ahmadchats", "Naif_Alert", "vipdrprofit",
]
DAILY_SUMMARY_HOUR = int(os.getenv("MONTHLY_SUMMARY_HOUR", "21"))
CHANNEL_MEMORY_FILE = BASE_DIR / "channel_memory.json"

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
        requests.post(f"https://api.telegram.org/bot{NOTIFY_TOKEN}/sendMessage",
                      json={"chat_id": NOTIFY_CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        log(f"خطأ في الإشعار: {e}")

# ---------- state ----------
@dataclass
class State:
    day: str = ""; daily_trades: int = 0; daily_pnl: float = 0.0; halted: bool = False
    open_positions: dict[str, dict] = field(default_factory=dict)
    trade_history: list[dict] = field(default_factory=list)
    reinforcements: dict[str, list] = field(default_factory=dict)
    reinforced_keys: list[str] = field(default_factory=list)
    pending_signals: list[dict] = field(default_factory=list)
    executed_signals: list[str] = field(default_factory=list)
    entered_symbols: list[str] = field(default_factory=list)  # must be cleaned when position is closed
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

def _atomic_write(path, text: str) -> None:
    """كتابة آمنة: ملف مؤقت ثم استبدال ذري — يمنع التلف عند توقف مفاجئ."""
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text)
    tmp.replace(path)

def save_state(s: State) -> None:
    _atomic_write(STATE_FILE, json.dumps(asdict(s), indent=2, ensure_ascii=False))

# ---------- ML recommendations ----------
_ml_recs_cache: dict = {}
_ml_recs_ts: float = 0

def _load_ml_recommendations() -> dict:
    global _ml_recs_cache, _ml_recs_ts
    if time.time() - _ml_recs_ts < 3600 and _ml_recs_cache:
        return _ml_recs_cache
    if ML_RECOMMENDATIONS_FILE.exists():
        try:
            _ml_recs_cache = json.loads(ML_RECOMMENDATIONS_FILE.read_text())
            _ml_recs_ts = time.time()
        except Exception:
            pass
    return _ml_recs_cache

def get_smart_phase2_delay(symbol: str) -> int:
    recs = _load_ml_recommendations()
    per_sym = recs.get("per_symbol", {}).get(symbol, {})
    optimal = per_sym.get("optimal_delay_min")
    if optimal and optimal > PHASE2_DELAY_MIN:
        return min(int(optimal), 360)
    return PHASE2_DELAY_MIN

# ---------- signal tracker (self-learning phase 1) ----------
_TRACK_CHECKPOINTS = [30, 60, 120, 240, 1440]  # minutes

_STABLECOINS = {"USDC", "USDT", "BUSD", "DAI", "TUSD", "FDUSD"}

def _load_tracker() -> list[dict]:
    if TRACKER_FILE.exists():
        try:
            return json.loads(TRACKER_FILE.read_text())
        except Exception:
            pass
    return []

def _clean_tracker(data: list[dict]) -> list[dict]:
    """حذف العملات المستقرة والتكرارات — يحتفظ بأقدم سجل لكل (عملة، منصة)."""
    cleaned = [r for r in data if r.get("symbol", "").upper() not in _STABLECOINS]
    seen_keys = set()
    unique = []
    for r in cleaned:
        sym = r.get("symbol", "").upper()
        ex = r.get("exchange", "")
        key = (sym, ex)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(r)
    return unique

def _save_tracker(data: list[dict]) -> None:
    _atomic_write(TRACKER_FILE, json.dumps(data, indent=2, ensure_ascii=False))

def tracker_add(symbol: str, pair: str, signal_price: float, entry_price: float,
                ex_name: str, source: str = "bot"):
    data = _load_tracker()
    data.append({
        "symbol": symbol, "pair": pair, "exchange": ex_name,
        "signal_price": signal_price, "entry_price": entry_price,
        "signal_time": time.time(), "signal_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "checkpoints": {},
    })
    _save_tracker(data)

_MANUAL_SCAN_FILE = BASE_DIR / "manual_trades_seen.json"

def _load_seen_trades() -> set:
    if _MANUAL_SCAN_FILE.exists():
        try:
            return set(json.loads(_MANUAL_SCAN_FILE.read_text()))
        except Exception:
            pass
    return set()

def _save_seen_trades(seen: set) -> None:
    _atomic_write(_MANUAL_SCAN_FILE, json.dumps(list(seen)[-2000:]))

def scan_manual_trades():
    seen = _load_seen_trades()
    state = load_state()
    bot_pairs = set(state.open_positions.keys())
    new_found = 0
    for ex_name, ex in _exchanges.items():
        try:
            since_ms = int((time.time() - 86400 * 7) * 1000)
            trades = ex.fetch_my_trades(None, since=since_ms, limit=100)
        except Exception:
            try:
                trades = ex.fetch_my_trades(None, limit=50)
            except Exception:
                continue
        buys = {}
        for t in trades:
            if t.get("side") != "buy":
                continue
            tid = f"{ex_name}_{t.get('id', t.get('timestamp', ''))}"
            if tid in seen:
                continue
            seen.add(tid)
            pair = t.get("symbol", "")
            if not pair or "/USDT" not in pair:
                continue
            base_sym = pair.split("/")[0].upper()
            if base_sym in _STABLECOINS:
                continue
            if pair in bot_pairs:
                continue
            if pair not in buys:
                buys[pair] = {"qty": 0, "cost": 0, "ts": t["timestamp"] / 1000}
            buys[pair]["qty"] += float(t.get("amount", 0))
            buys[pair]["cost"] += float(t.get("cost", 0))
        for pair, info in buys.items():
            if info["cost"] < 5:
                continue
            avg_price = info["cost"] / info["qty"] if info["qty"] > 0 else 0
            symbol = pair.split("/")[0]
            tracker_add(symbol, pair, avg_price, avg_price, ex_name, source="manual")
            new_found += 1
            log(f"📝 شراء يدوي مكتشف: {pair} [{ex_name}] @ ${avg_price:.4f} (${info['cost']:.0f})")
    _save_seen_trades(seen)
    return new_found

def tracker_update():
    data = _load_tracker()
    if not data:
        return
    now = time.time()
    changed = False
    for rec in data:
        if not rec.get("pair"):
            continue
        for cp_min in _TRACK_CHECKPOINTS:
            cp_key = f"{cp_min}m"
            if cp_key in rec.get("checkpoints", {}):
                continue
            elapsed_min = (now - rec["signal_time"]) / 60
            if elapsed_min < cp_min:
                continue
            ex = _exchanges.get(rec.get("exchange"))
            if not ex:
                for e in _exchanges.values():
                    if rec["pair"] in getattr(e, "markets", {}):
                        ex = e; break
            if not ex:
                continue
            try:
                ticker = ex.fetch_ticker(rec["pair"])
                price = float(ticker.get("last", 0))
                if price <= 0:
                    continue
                diff_pct = round((price - rec["signal_price"]) / rec["signal_price"] * 100, 2)
                rec.setdefault("checkpoints", {})[cp_key] = {
                    "price": price, "diff_pct": diff_pct,
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                changed = True
            except Exception:
                continue
    if changed:
        _save_tracker(data)

def _calc_avg_checkpoints(records: list[dict]) -> dict:
    avg = {}
    for cp_min in _TRACK_CHECKPOINTS:
        cp_key = f"{cp_min}m"
        vals = [r["checkpoints"][cp_key]["diff_pct"] for r in records if cp_key in r.get("checkpoints", {})]
        if vals:
            avg[cp_key] = round(sum(vals) / len(vals), 2)
    return avg

def tracker_report() -> str:
    data = _load_tracker()
    if not data:
        return ""
    complete = [r for r in data if len(r.get("checkpoints", {})) >= len(_TRACK_CHECKPOINTS)]
    if not complete:
        return ""
    labels = {"30m": "30 دقيقة", "60m": "ساعة", "120m": "ساعتين", "240m": "4 ساعات", "1440m": "24 ساعة"}
    lines = []
    bot_recs = [r for r in complete if r.get("source", "bot") == "bot"]
    manual_recs = [r for r in complete if r.get("source") == "manual"]
    for group_name, recs in [("توصيات البوت", bot_recs), ("شراء يدوي", manual_recs), ("الكل", complete)]:
        if not recs:
            continue
        avg = _calc_avg_checkpoints(recs)
        if not avg:
            continue
        lines.append(f"\n📊 {group_name} ({len(recs)} صفقة):")
        for k, v in avg.items():
            sign = "+" if v >= 0 else ""
            lines.append(f"  بعد {labels.get(k, k)}: {sign}{v}%")
        dip_30 = avg.get("30m", 0)
        rise_240 = avg.get("240m", 0)
        if dip_30 < -1 and rise_240 > dip_30:
            lines.append(f"  💡 نمط: انخفاض {dip_30}% ثم ارتداد — الدخول المتأخر أفضل")
    return "\n".join(lines) if lines else ""

def rollover_day(s: State) -> None:
    today = time.strftime("%Y-%m-%d")
    if s.day != today:
        s.day, s.daily_trades, s.daily_pnl, s.halted = today, 0, 0.0, False
        s.consecutive_losses = 0
        save_state(s); log(f"=== يوم جديد {today} — إعادة تعيين ===")

# ---------- signal parser ----------
@dataclass
class Signal:
    trade_num: int; symbol: str; buy_price: float; sell_price: float; tp_pct: float
    reinforcements: list[float] = field(default_factory=list)
    targets: list[dict] = field(default_factory=list)

_COMPLETED_PATTERNS = re.compile(
    r"تم\s*تحقيق|تحقق\s*الهدف|وصل\s*الهدف|تم\s*الوصول|تم\s*البيع|أغلقت|مغلقة|closed|reached|done",
    re.IGNORECASE,
)

def parse_signal(text: str) -> Signal | None:
    """يحلل صيغتين: (1) سعر الشراء/البيع البسيطة (2) الشراء والتعزيز المفصّلة."""
    if not text:
        return None
    if _COMPLETED_PATTERNS.search(text):
        return None
    sym_m = re.search(r"العملة\s*[:\s]*([A-Za-z0-9]+)", text)
    if not sym_m:
        return None
    symbol = sym_m.group(1).upper()
    num_m = re.search(r"رقم\s*الصفقة\s*[:\s]*\(?(\d+)\)?", text)
    trade_num = int(num_m.group(1)) if num_m else 0

    # صيغة 1: سعر الشراء / سعر البيع
    buy_m = re.search(r"سعر\s*الشراء\s*[:\s]*([\d.]+)", text)
    sell_m = re.search(r"سعر\s*البيع\s*[:\s]*([\d.]+)", text)
    if buy_m and sell_m:
        try:
            buy_p, sell_p = float(buy_m.group(1)), float(sell_m.group(1))
        except ValueError:
            return None
        pct_m = re.search(r"سعر\s*البيع\s*[:\s]*[\d.]+\s*\(?\s*%?([\d.]+)\s*%\)?", text)
        tp_pct = float(pct_m.group(1)) if pct_m else (
            round((sell_p - buy_p) / buy_p * 100, 2) if buy_p > 0 else 0.0)
        reinf = parse_reinforcements(text)
        return Signal(trade_num, symbol, buy_p, sell_p, tp_pct, reinf)

    # صيغة 2: الشراء والتعزيز + أهداف الصفقة
    if "الشراء والتعزيز" in text or "التعزيز الأول" in text:
        buy_p, reinf = _parse_buy_and_reinforce(text)
        sell_p, tp_pct = _parse_targets(text, buy_p)
        all_targets = _parse_all_targets(text, buy_p)
        if buy_p > 0:
            return Signal(trade_num, symbol, buy_p, sell_p, tp_pct, reinf, all_targets)

    return None

def _parse_buy_and_reinforce(text: str) -> tuple[float, list[float]]:
    """يستخرج سعر الشراء الأول وأسعار التعزيز من قسم 'الشراء والتعزيز'."""
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

def _parse_targets(text: str, buy_price: float) -> tuple[float, float]:
    """يستخرج أعلى هدف من 'أهداف الصفقة'."""
    all_targets = _parse_all_targets(text, buy_price)
    if all_targets:
        last = all_targets[-1]
        return last["price"], last["pct"]
    sell_price = buy_price * 1.20 if buy_price > 0 else 0
    tp_pct = 20.0 if buy_price > 0 else 0
    return sell_price, tp_pct

def _parse_all_targets(text: str, buy_price: float) -> list[dict]:
    """يستخرج جميع أهداف الصفقة."""
    targets = []
    in_targets = False
    for line in text.split("\n"):
        if "أهداف الصفقة" in line:
            in_targets = True; continue
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

def parse_reinforcements(text: str) -> list[float]:
    """يستخرج أسعار التعزيز — يعمل مع الصيغتين."""
    if "الشراء والتعزيز" in text or "التعزيز الأول" in text:
        _, reinf = _parse_buy_and_reinforce(text)
        return reinf
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

# ---------- exchange ----------
def get_exchange():
    import ccxt
    ex = ccxt.bybit({"apiKey": BYBIT_KEY, "secret": BYBIT_SECRET,
                      "options": {"defaultType": "spot"}})
    if BYBIT_TESTNET:
        ex.set_sandbox_mode(True)
    return ex

def get_kucoin_exchange():
    import ccxt
    return ccxt.kucoin({"apiKey": KUCOIN_KEY, "secret": KUCOIN_SECRET,
                         "password": KUCOIN_PASS,
                         "options": {"defaultType": "spot"}})

def get_gate_exchange():
    import ccxt
    return ccxt.gateio({"apiKey": GATE_KEY, "secret": GATE_SECRET,
                         "options": {"defaultType": "spot"}})

_exchanges: dict = {}
_EXCHANGE_PRIORITY = ["bybit", "kucoin"]
_disabled_exchanges: set = {"gateio"}

def find_pair_exchange(symbol: str):
    for name in _EXCHANGE_PRIORITY:
        ex = _exchanges.get(name)
        if not ex:
            continue
        pair = verify_symbol(ex, symbol)
        if pair:
            return pair, name
    return None, None

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

def _safe_float(*values, default=0.0) -> float:
    """يرجّع أول قيمة قابلة للتحويل لرقم — يتجاهل None والقيم الفارغة."""
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

def spot_buy(exchange, pair: str, usdt_amount: float) -> dict | None:
    """شراء بأمر محدود (0.5% فوق السوق) مع احتياط سوق إذا لم يُنفَّذ خلال 30 ثانية"""
    ex_id = getattr(exchange, 'id', '')
    if ex_id in _disabled_exchanges:
        return None
    try:
        price = _safe_float(exchange.fetch_ticker(pair).get("last"))
        if not price:
            return None

        # حد المبلغ بالرصيد المتاح فعلياً — تجنب أخطاء "رصيد غير كافٍ"
        if not PAPER_MODE:
            try:
                free = float(exchange.fetch_balance().get("USDT", {}).get("free", 0))
            except Exception:
                free = usdt_amount
            if usdt_amount > free:
                usdt_amount = free * 0.99  # هامش بسيط للرسوم
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

        order = exchange.create_limit_buy_order(pair, qty, limit_price)
        log(f"أمر شراء محدود: {pair} | سعر={limit_price:.6g} | كمية={qty:.6f} | ${usdt_amount}")

        # انتظار التنفيذ حتى 30 ثانية
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
            # إلغاء والتحويل لأمر سوق — شراء المتبقي فقط (جزء قد يكون تنفّذ)
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
                log(f"الأمر المحدود تنفّذ فعلياً ({filled:.6f}): {pair}")
                return {"filled": filled, "amount": filled, "average": limit_avg, "price": limit_avg}
            log(f"لم يُنفَّذ الأمر المحدود — أمر سوق للمتبقي {remainder:.6f}: {pair}")
            # تمرير السعر: ccxt يحسب التكلفة = كمية × سعر لمنصات spot
            order = exchange.create_order(pair, 'market', 'buy', remainder, price)
            if order and filled > 0:
                mkt_filled = _safe_float(order.get("filled"), default=remainder)
                mkt_avg = _safe_float(order.get("average"), default=price) or price
                total_filled = filled + mkt_filled
                # متوسط السعر المرجّح بين الجزء المحدود وجزء السوق
                if total_filled > 0:
                    vwap = (filled * limit_avg + mkt_filled * mkt_avg) / total_filled
                    order["average"] = vwap
                order["filled"] = total_filled
                order["amount"] = total_filled
        return order
    except Exception as e:
        err = str(e)
        if "permission" in err.lower() or "FORBIDDEN" in err:
            _disabled_exchanges.add(ex_id)
            log(f"تعطيل الشراء من {ex_id} — صلاحيات ناقصة")
        elif "insufficient" in err.lower() or "170131" in err or "200004" in err:
            # رصيد غير كافٍ — رسالة عادية بدون تنبيه
            log(f"تخطي شراء {pair} — رصيد غير كافٍ في {ex_id}")
        else:
            log(f"خطأ في الشراء: {pair} — {e}")
        return None

def _prec_qty(exchange, pair: str, qty: float) -> float:
    """تقريب الكمية لدقة المنصة — الأرقام الخام مثل 33.333333 تُرفض."""
    try:
        return float(exchange.amount_to_precision(pair, qty))
    except Exception:
        return float(f"{qty:.6f}")

def spot_sell(exchange, pair: str, qty: float) -> dict | None:
    # gate قراءة فقط — ممنوع أي أمر بيع حتى لو تلوثت الحالة
    if getattr(exchange, 'id', '') == 'gateio':
        log(f"رفض بيع {pair} على gate — مفتاح قراءة فقط")
        return None
    try:
        # حد الكمية بالرصيد الفعلي — الرسوم تقتطع من العملة المشتراة فلا نملك كامل qty
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
        order = exchange.create_market_sell_order(pair, qty)
        log(f"أمر بيع: {pair} | كمية={qty:.6f}"); return order
    except Exception as e:
        log(f"خطأ في البيع: {pair} — {e}"); return None

def place_stop_loss(exchange, pair: str, qty: float, trigger_price: float) -> str | None:
    if getattr(exchange, 'id', '') == 'gateio':
        return None
    try:
        qty = _prec_qty(exchange, pair, qty)
        if exchange.id == 'kucoin':
            params = {'stop': 'loss', 'stopPrice': str(trigger_price)}
        else:
            params = {'triggerPrice': str(trigger_price)}
        order = exchange.create_order(pair, 'market', 'sell', qty, None, params)
        oid = order.get('id', '')
        log(f"أمر وقف خسارة: {pair} @ {trigger_price} | أمر={oid}")
        return oid
    except Exception as e:
        log(f"خطأ وقف الخسارة: {pair} — {e}")
        return None

def cancel_sl_order(exchange, pair: str, order_id: str):
    try:
        params = {"stop": True, "orderFilter": "StopOrder"} if exchange.id == "bybit" else {}
        exchange.cancel_order(order_id, pair, params=params)
        log(f"إلغاء وقف خسارة: {pair} | أمر={order_id}")
    except Exception as e:
        log(f"خطأ إلغاء الأمر: {pair} — {e}")

_btc_sma_cache: tuple[float, float] | None = None  # (timestamp, sma50)

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

        # SMA50 اليومي — يُحدَّث كل ساعة
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

def get_trade_size(exchange) -> float:
    if PAPER_MODE:
        return TRADE_SIZE
    try:
        balance = exchange.fetch_balance()
        free_usdt = float(balance.get("USDT", {}).get("free", 0))
        size = round(free_usdt * TRADE_PCT / 100, 2)
        if size < MIN_TRADE_USDT:
            log(f"رصيد: ${free_usdt:.2f} | حجم ${size:.2f} أقل من الحد الأدنى ${MIN_TRADE_USDT} — تخطي")
            return 0
        log(f"رصيد: ${free_usdt:.2f} | حجم الصفقة: ${size:.2f} ({TRADE_PCT}%)")
        return size
    except Exception as e:
        log(f"خطأ جلب الرصيد: {e} — استخدام الحجم الثابت ${TRADE_SIZE}")
        return TRADE_SIZE

# ---------- partial TP / re-entry ----------
def partial_sell(state, pair: str, price: float, exchange):
    """بيع جزئي عند ارتفاع السعر — يحفظ المبلغ لإعادة الشراء عند النزول."""
    pos = state.open_positions.get(pair)
    if not pos or pos.get("partial_taken"):
        return
    sell_qty = pos["qty"] * PARTIAL_SELL_PCT / 100
    remaining_qty = pos["qty"] - sell_qty

    if not PAPER_MODE:
        order = spot_sell(exchange, pair, sell_qty)
        if not order:
            return
        fill_price = _safe_float(order.get("average"), order.get("price"), default=price)
        partial_usdt = fill_price * _safe_float(order.get("filled"), order.get("amount"), default=sell_qty)
    else:
        partial_usdt = price * sell_qty

    pos["qty"] = remaining_qty
    pos["partial_taken"] = True
    pos["partial_usdt"] = round(partial_usdt, 4)
    pos["last_sell_price"] = round(price, 8)
    save_state(state)

    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100
    msg = (f"بيع جزئي: {pair}\n"
           f"بيع {PARTIAL_SELL_PCT:.0f}% @ {price} (+{pnl_pct:.1f}%)\n"
           f"محفوظ: ${partial_usdt:.2f} | متبقي: {remaining_qty:.6f}")
    log(msg); notify(msg)

def partial_rebuy(state, pair: str, price: float, exchange):
    """إعادة شراء الكمية المباعة عند نزول السعر تحت سعر الدخول."""
    pos = state.open_positions.get(pair)
    if not pos or not pos.get("partial_taken"):
        return
    partial_usdt = pos.get("partial_usdt", 0)
    if partial_usdt <= 0:
        return

    rebuy_qty = partial_usdt / price
    if not PAPER_MODE:
        order = spot_buy(exchange, pair, partial_usdt)
        if not order:
            fails = pos.get("rebuy_fails", 0) + 1
            pos["rebuy_fails"] = fails
            save_state(state)
            if fails >= 2:
                pos["partial_taken"] = False
                pos["partial_usdt"] = 0
                save_state(state)
                log(f"⚠️ إعادة شراء {pair} فشلت {fails} مرات — تم إلغاء الإعادة. تحقق من الرصيد.")
            return
        rebuy_qty = _safe_float(order.get("filled"), order.get("amount"), default=rebuy_qty)

    new_qty = pos["qty"] + rebuy_qty

    if not PAPER_MODE and pos.get("sl"):
        new_sl_oid = place_stop_loss(exchange, pair, new_qty, pos["sl"])
        pos["sl_order_id"] = new_sl_oid

    pos["qty"] = new_qty
    pos["partial_taken"] = False
    pos["partial_usdt"] = 0
    pos.pop("rebuy_fails", None)
    save_state(state)

    drop_pct = (price - pos["entry"]) / pos["entry"] * 100
    msg = (f"إعادة شراء: {pair}\n"
           f"شراء @ {price} ({drop_pct:+.1f}%)\n"
           f"${partial_usdt:.2f} → {rebuy_qty:.6f} | إجمالي: {new_qty:.6f}")
    log(msg); notify(msg)

TARGET_REBUY_DROP_PCT = float(os.getenv("MONTHLY_TARGET_REBUY_DROP", "10.0"))

def target_sell(state, pair: str, price: float, exchange, target: dict, sell_pct: float):
    """بيع نسبة من الكمية عند وصول هدف معين (أهداف متعددة)."""
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
        order = spot_sell(exchange, pair, sell_qty)
        if not order:
            return
        fill_price = _safe_float(order.get("average"), order.get("price"), default=price)
        partial_usdt = fill_price * _safe_float(order.get("filled"), order.get("amount"), default=sell_qty)
    else:
        partial_usdt = price * sell_qty

    pos["qty"] = remaining_qty
    pos["partial_taken"] = True
    pos["partial_usdt"] = round(pos.get("partial_usdt", 0) + partial_usdt, 4)
    pos["last_sell_price"] = round(price, 8)
    target["hit"] = True
    pos["targets_hit"] = pos.get("targets_hit", 0) + 1
    save_state(state)

    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100
    hit_count = pos["targets_hit"]
    total_targets = len(pos.get("targets", []))
    msg = (f"🎯 هدف {hit_count}/{total_targets}: {pair}\n"
           f"بيع {sell_pct:.0f}% @ {price} (+{pnl_pct:.1f}%)\n"
           f"محفوظ: ${partial_usdt:.2f} | متبقي: {remaining_qty:.6f}")
    log(msg); notify(msg)

# ---------- ATR & dynamic sizing ----------
_atr_cache: dict[str, tuple[float, float]] = {}  # pair -> (timestamp, atr)

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

def dynamic_trade_size(base_size: float, tp_pct: float) -> float:
    if tp_pct >= 20:
        return round(base_size * 1.5, 2)
    elif tp_pct >= 10:
        return round(base_size * 1.2, 2)
    elif tp_pct < 5:
        return round(base_size * 0.7, 2)
    return base_size

# ---------- trade logic ----------
def open_trade(state: State, signal: Signal, reason: str = "توصية جديدة") -> bool:
    rollover_day(state)
    if signal.symbol in PROTECTED_SYMBOLS:
        log(f"عملة محمية — تجاهل: {signal.symbol}"); return False
    if state.halted:
        log("متوقف — تجاوز حد الخسارة اليومي"); return False
    if state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        log(f"متوقف — {state.consecutive_losses} خسائر متتالية (الحد: {MAX_CONSECUTIVE_LOSSES})")
        return False
    if state.daily_trades >= MAX_DAILY_TRADES:
        log(f"حد الصفقات اليومي ({MAX_DAILY_TRADES})"); return False
    if len(state.open_positions) >= MAX_CONCURRENT:
        log(f"حد المراكز المفتوحة ({MAX_CONCURRENT})"); return False

    pair, ex_name = find_pair_exchange(signal.symbol)
    if not pair:
        log(f"الزوج غير موجود: {signal.symbol}/USDT"); return False
    if pair in state.open_positions:
        log(f"مركز مفتوح بالفعل: {pair}"); return False
    if any(p.get("symbol") == signal.symbol for p in state.open_positions.values()):
        log(f"العملة مفتوحة بالفعل بمنصة أخرى: {signal.symbol}"); return False

    exchange = _exchanges[ex_name]
    if not PAPER_MODE:
        try:
            free = float(exchange.fetch_balance().get("USDT", {}).get("free", 0))
            if free < 1:
                return False
        except Exception:
            pass
    _fixed = {"kucoin": KUCOIN_TRADE_SIZE, "bybit": BYBIT_TRADE_SIZE}.get(ex_name)
    base_size = _fixed if _fixed else get_trade_size(exchange)
    trade_size = dynamic_trade_size(base_size, signal.tp_pct)
    if trade_size < MIN_TRADE_USDT:
        log(f"رصيد غير كافٍ: ${trade_size:.2f} < ${MIN_TRADE_USDT}"); return False

    phase1_ratio = ENTRY_PHASES[0]["ratio"] if ENTRY_PHASES else 0.25
    phase1_size = round(trade_size * phase1_ratio, 2)
    remaining_phases = []
    for i, ph in enumerate(ENTRY_PHASES[1:], start=2):
        remaining_phases.append({
            "num": i, "ratio": ph["ratio"],
            "size": round(trade_size * ph["ratio"], 2),
            "delay_min": ph["delay_min"], "done": False,
        })

    entry, qty = signal.buy_price, phase1_size / signal.buy_price

    if not PAPER_MODE:
        order = spot_buy(exchange, pair, phase1_size)
        if not order:
            return False
        try:
            entry = float(order.get("average") or order.get("price") or entry)
            qty = float(order.get("filled") or order.get("amount") or qty)
        except (TypeError, ValueError):
            pass

    atr = calc_atr(exchange, pair)
    atr_sl = round(entry - atr * ATR_SL_MULTIPLIER, 8) if atr else None
    cat_sl = entry * (1 - CATASTROPHIC_SL_PCT / 100)
    effective_sl = max(atr_sl, cat_sl) if atr_sl else cat_sl

    targets_list = []
    if signal.targets:
        for t in signal.targets:
            targets_list.append({"price": t["price"], "pct": t["pct"], "hit": t.get("completed", False)})

    state.open_positions[pair] = {
        "trade_num": signal.trade_num, "symbol": signal.symbol, "pair": pair,
        "entry": entry, "qty": qty, "tp": signal.sell_price,
        "tp_pct": signal.tp_pct, "opened": time.time(),
        "opened_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason, "exchange": ex_name,
        "swing_base": entry,
        "total_size": trade_size,
        "phases": remaining_phases,
        "atr_sl": atr_sl,
        "targets": targets_list,
        "targets_hit": 0,
    }
    state.daily_trades += 1
    if signal.symbol not in state.entered_symbols:
        state.entered_symbols.append(signal.symbol)
    save_state(state)
    tracker_add(signal.symbol, pair, signal.buy_price, entry, ex_name)

    mode = "ورقي" if PAPER_MODE else "حقيقي"
    sl_info = f"ATR={atr_sl:.4f}" if atr_sl else f"ثابت={cat_sl:.4f}"
    n_phases = 1 + len(remaining_phases)
    sz_info = f"دفعة 1/{n_phases} ${phase1_size:.0f} من ${trade_size:.0f}"
    msg = (f"صفقة [{mode}] — {reason}\n#{signal.trade_num} | {pair} [{ex_name}]\n"
           f"دخول: {entry} | هدف: {signal.sell_price} ({signal.tp_pct}%)\n"
           f"حجم: {sz_info} | وقف: {sl_info}")
    log(msg); notify(msg); return True

def close_trade(state: State, pair: str, reason: str, price: float, exchange, skip_sell: bool = False):
    pos = state.open_positions.get(pair)
    if not pos:
        return
    sell_qty = pos["qty"]
    pnl = (price - pos["entry"]) * sell_qty
    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100

    if not PAPER_MODE and not skip_sell:
        try:
            balance = exchange.fetch_balance()
            sym_b = pair.split("/")[0]
            available = float(balance.get(sym_b, {}).get("free", 0))
            if available < sell_qty:
                sell_qty = available
        except Exception:
            pass
        if sell_qty > 0:
            order = spot_sell(exchange, pair, sell_qty)
            if order is None:
                # البيع فشل — لا نحذف الصفقة، ستُعاد المحاولة في الدورة القادمة
                log(f"⚠️ فشل بيع {pair} — تبقى الصفقة مفتوحة لإعادة المحاولة")
                return

    # البيع نجح (أو ورقي/تخطي) — الآن نحذف الصفقة من السجل
    state.open_positions.pop(pair, None)
    # Clean entered_symbols so the symbol can be re-entered later
    sym = pos.get("symbol", pair.split("/")[0]).upper()
    if sym in state.entered_symbols:
        state.entered_symbols.remove(sym)

    state.daily_pnl += pnl
    if state.daily_pnl <= -MAX_DAILY_LOSS:
        state.halted = True
        log(f"إيقاف التداول — خسارة يومية ${state.daily_pnl:.2f}")

    if pnl < 0:
        state.consecutive_losses += 1
        if state.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            msg_halt = (f"إيقاف التداول — {state.consecutive_losses} خسائر متتالية\n"
                        f"يُستأنف تلقائياً في اليوم التالي")
            log(msg_halt)
    else:
        state.consecutive_losses = 0

    state.trade_history.append({"pair": pair, "entry": pos["entry"], "exit": price,
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "reason": reason,
        "closed": time.strftime("%Y-%m-%d %H:%M:%S")})
    if len(state.trade_history) > 200:
        state.trade_history = state.trade_history[-200:]
    save_state(state)

    sign = "+" if pnl >= 0 else ""
    msg = (f"إغلاق: {pair} | {reason}\n"
           f"دخول: {pos['entry']} → خروج: {price}\n"
           f"ربح: {sign}${pnl:.2f} ({sign}{pnl_pct:.1f}%)")
    log(msg); notify(msg)

    if pnl > MIN_TRADE_USDT and state.open_positions:
        reinvest_profit(state, pnl, pair)


def reinvest_profit(state: State, profit: float, closed_pair: str):
    """بعد ربح — يعزز أكثر عملة نازلة من المراكز المفتوحة."""
    worst_pair, worst_drop, worst_pos = None, 0, None
    for p, pos in state.open_positions.items():
        if p == closed_pair:
            continue
        ex = _exchanges.get(pos.get("exchange", "bybit"))
        if not ex:
            continue
        try:
            price = _safe_float(ex.fetch_ticker(p).get("last"))
            if not price:
                continue
        except Exception:
            continue
        drop = (price - pos["entry"]) / pos["entry"] * 100
        if drop < worst_drop:
            worst_drop = drop
            worst_pair = p
            worst_pos = pos

    if not worst_pair or worst_drop >= 0:
        log("لا توجد عملة نازلة للتعزيز من الأرباح")
        return

    ex_name = worst_pos.get("exchange", "bybit")
    exchange = _exchanges.get(ex_name)
    reinvest_amt = round(min(profit, BYBIT_TRADE_SIZE if ex_name == "bybit" else KUCOIN_TRADE_SIZE), 2)
    if reinvest_amt < MIN_TRADE_USDT:
        return

    try:
        cur_price = _safe_float(exchange.fetch_ticker(worst_pair).get("last"))
        if not cur_price:
            return
    except Exception:
        return

    if not PAPER_MODE:
        order = spot_buy(exchange, worst_pair, reinvest_amt)
        if not order:
            log(f"فشل تعزيز {worst_pair} من الأرباح")
            return
        try:
            r_qty = float(order.get("filled") or order.get("amount") or reinvest_amt / cur_price)
            r_price = float(order.get("average") or order.get("price") or cur_price)
        except (TypeError, ValueError):
            r_qty = reinvest_amt / cur_price
            r_price = cur_price
    else:
        r_qty = reinvest_amt / cur_price
        r_price = cur_price

    old_qty = worst_pos["qty"]
    old_entry = worst_pos["entry"]
    new_qty = old_qty + r_qty
    new_entry = (old_entry * old_qty + r_price * r_qty) / new_qty
    worst_pos["qty"] = new_qty
    worst_pos["entry"] = round(new_entry, 8)
    worst_pos["swing_base"] = new_entry
    save_state(state)

    msg = (f"تعزيز من أرباح: {worst_pair} (نازل {worst_drop:.1f}%)\n"
           f"شراء ${reinvest_amt:.0f} @ {r_price:.4f}\n"
           f"متوسط جديد: {new_entry:.4f} | إجمالي: {new_qty:.6f}")
    log(msg); notify(msg)


def compute_stats(history: list[dict]) -> str:
    """إحصائيات الأداء: نسبة الربح، التوقع الرياضي، الإجمالي"""
    if len(history) < 3:
        return f"صفقات مغلقة: {len(history)} (يحتاج 100+ لدقة التحليل)"
    wins   = [t for t in history if t.get("pnl", 0) > 0]
    losses = [t for t in history if t.get("pnl", 0) <= 0]
    n = len(history)
    wr = len(wins) / n * 100
    avg_win  = sum(t["pnl"] for t in wins)  / len(wins)  if wins   else 0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
    expectancy = (wr / 100 * avg_win) + ((1 - wr / 100) * avg_loss)
    total = sum(t["pnl"] for t in history)
    verdict = "إيجابي ✅" if expectancy > 0 else "سلبي — راجع الاستراتيجية ⚠️"
    return (
        f"📊 <b>إحصائيات ({n} صفقة)</b>\n"
        f"نسبة الربح: {wr:.1f}% ({len(wins)} ربح / {len(losses)} خسارة)\n"
        f"متوسط الربح: ${avg_win:.2f} | متوسط الخسارة: ${avg_loss:.2f}\n"
        f"التوقع الرياضي: ${expectancy:.2f}/صفقة ({verdict})\n"
        f"الإجمالي: ${total:.2f}"
    )


async def check_positions(state: State):
    rollover_day(state)
    if not state.open_positions:
        return
    for pair in list(state.open_positions):
        pos = state.open_positions.get(pair)
        if not pos:
            continue
        if pos.get("symbol") in PROTECTED_SYMBOLS:
            continue  # لا نبيع عملة محمية أبداً
        ex_name = pos.get("exchange", "bybit")
        exchange = _exchanges.get(ex_name)
        if not exchange:
            continue
        try:
            price = _safe_float(exchange.fetch_ticker(pair).get("last"))
            if not price:
                continue
        except Exception as e:
            log(f"خطأ في جلب سعر {pair}: {e}"); continue

        # تتبع أعلى سعر (للوقف المتحرك)
        highest = pos.get("highest_price", pos["entry"])
        if price > highest:
            pos["highest_price"] = price
            highest = price
            save_state(state)

        # أهداف >30%: سوينج متحرك — +3% من آخر سعر شراء
        high_target = pos.get("tp_pct", 0) > 30
        base = pos.get("swing_base", pos["entry"]) if high_target else pos["entry"]

        # 1) وقف خسارة — معطل حالياً
        # atr_sl = pos.get("atr_sl")
        # cat_sl = pos["entry"] * (1 - CATASTROPHIC_SL_PCT / 100)
        # effective_sl = max(atr_sl, cat_sl) if atr_sl else cat_sl
        # if price <= effective_sl:
        #     sl_type = "ATR" if atr_sl and effective_sl == atr_sl else f"كارثي -{CATASTROPHIC_SL_PCT:.0f}%"
        #     close_trade(state, pair, f"وقف {sl_type}", price, exchange)
        #     continue

        # 2) وقف متحرك — يتفعل بعد ربح +TRAILING_STOP_ACTIVATE_PCT%
        gain_from_entry = (highest - pos["entry"]) / pos["entry"] * 100
        if gain_from_entry >= TRAILING_STOP_ACTIVATE_PCT:
            trail_stop = highest * (1 - TRAILING_STOP_DISTANCE_PCT / 100)
            if price <= trail_stop:
                trail_pnl = (price - pos["entry"]) / pos["entry"] * 100
                close_trade(state, pair,
                    f"وقف متحرك (أعلى={highest:.4f} → نزل {TRAILING_STOP_DISTANCE_PCT}%)",
                    price, exchange)
                continue

        # 3) إعادة شراء بعد البيع على هدف — النزول من سعر البيع
        if pos.get("partial_taken"):
            last_sell = pos.get("last_sell_price", base)
            drop_pct = TARGET_REBUY_DROP_PCT if pos.get("targets") else REBUY_DROP_PCT
            rebuy_trigger = last_sell * (1 - drop_pct / 100)
            if price <= rebuy_trigger:
                partial_rebuy(state, pair, price, exchange)
                if high_target:
                    pos["swing_base"] = price
                    save_state(state)
                continue

        # 4) بيع على الأهداف (متعددة أو واحد)
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
                        sell_pct_per_target = 100 / len(remaining_targets)
                        target_sell(state, pair, price, exchange, next_target, sell_pct_per_target)
                    continue
            elif not pos.get("partial_taken"):
                if price >= pos["tp"]:
                    close_trade(state, pair, "هدف ربح", price, exchange)
                    continue
        else:
            if price >= pos["tp"]:
                close_trade(state, pair, "هدف ربح", price, exchange)
                continue

        # 5) مدة قصوى
        if MAX_HOLD_DAYS > 0 and (time.time() - pos["opened"]) / 86400 >= MAX_HOLD_DAYS:
            close_trade(state, pair, f"مدة قصوى ({MAX_HOLD_DAYS} يوم)", price, exchange)

# ---------- phase 2 entry ----------
async def check_phase2(state: State):
    for pair in list(state.open_positions):
        pos = state.open_positions.get(pair)
        if not pos:
            continue

        # --- backward compat: old phase2_size/phase2_done positions ---
        if "phase2_size" in pos and "phases" not in pos:
            if pos.get("phase2_done", True):
                continue
            ps = pos.get("phase2_size", 0)
            if ps >= MIN_TRADE_USDT:
                pos["phases"] = [{"num": 2, "ratio": 0, "size": ps,
                                  "delay_min": PHASE2_DELAY_MIN, "done": False}]
            else:
                pos["phase2_done"] = True
                save_state(state)
                continue

        phases = pos.get("phases", [])
        pending = [p for p in phases if not p.get("done")]
        if not pending:
            continue

        elapsed_min = (time.time() - pos["opened"]) / 60
        ex_name = pos.get("exchange", "bybit")
        exchange = _exchanges.get(ex_name)
        if not exchange:
            continue

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
                total_phases = 1 + len(phases)
                log(f"دفعة {phase['num']}/{total_phases} ألغيت: {pair} — السعر ارتفع +{PHASE_CANCEL_RISE_PCT}% فوق الدخول")
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

            old_qty = pos["qty"]
            old_entry = pos["entry"]
            new_qty = old_qty + p_qty
            new_entry = (old_entry * old_qty + p_price * p_qty) / new_qty
            pos["qty"] = new_qty
            pos["entry"] = round(new_entry, 8)
            pos["swing_base"] = new_entry
            phase["done"] = True

            if "phase2_done" in pos:
                pos["phase2_done"] = True

            atr = calc_atr(exchange, pair)
            if atr:
                pos["atr_sl"] = round(new_entry - atr * ATR_SL_MULTIPLIER, 8)

            save_state(state)
            total_phases = 1 + len(phases)
            msg = (f"دفعة {phase['num']}/{total_phases}: {pair}\n"
                   f"شراء إضافي ${phase_size:.0f} @ {p_price:.4f}\n"
                   f"متوسط جديد: {new_entry:.4f} | إجمالي: {new_qty:.6f}")
            log(msg); notify(msg)

# ---------- history scanner ----------
async def scan_history(client, state: State):
    """يمسح آخر شهر من الرسائل ويستخرج التوصيات والتعزيزات."""
    since = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
    total_signals = 0
    total_reinf = 0

    for channel_name in TG_CHANNELS:
        try:
            entity = await client.get_entity(channel_name)
            log(f"مسح تاريخ قناة: {channel_name} (آخر {HISTORY_DAYS} يوم)")
        except Exception as e:
            log(f"خطأ في الوصول لقناة {channel_name}: {e}")
            continue

        count = 0
        async for msg in client.iter_messages(entity, offset_date=since, reverse=True):
            if not msg.text:
                continue
            count += 1
            signal = parse_signal(msg.text)
            if signal:
                total_signals += 1
                sig_key = f"{signal.symbol}_{signal.trade_num}"
                if sig_key not in state.executed_signals:
                    existing = [s["key"] for s in state.pending_signals]
                    if sig_key not in existing:
                        state.pending_signals.append({
                            "key": sig_key, "symbol": signal.symbol,
                            "buy_price": signal.buy_price, "sell_price": signal.sell_price,
                            "tp_pct": signal.tp_pct, "trade_num": signal.trade_num,
                            "targets": [{"price": t["price"], "pct": t["pct"]} for t in signal.targets] if signal.targets else [],
                            "date": msg.date.strftime("%Y-%m-%d") if msg.date else "",
                        })
                if signal.reinforcements:
                    total_reinf += len(signal.reinforcements)
                    if signal.symbol not in state.reinforcements:
                        state.reinforcements[signal.symbol] = []
                    for rp in signal.reinforcements:
                        entry = {"price": rp, "buy_price": signal.buy_price,
                                 "sell_price": signal.sell_price, "tp_pct": signal.tp_pct,
                                 "trade_num": signal.trade_num,
                                 "targets": [{"price": t["price"], "pct": t["pct"]} for t in signal.targets] if signal.targets else [],
                                 "date": msg.date.strftime("%Y-%m-%d") if msg.date else ""}
                        if not any(abs(e["price"] - rp) < 0.000001 for e in state.reinforcements[signal.symbol]):
                            state.reinforcements[signal.symbol].append(entry)

            reinf_only = parse_reinforcements(msg.text)
            if reinf_only and not signal:
                sym_m = (re.search(r"(?:العملة|عملة)[:\s]*([A-Z]{2,10})", msg.text)
                         or re.search(r"(?:\$|#)([A-Z]{2,10})", msg.text)
                         or re.search(r"([A-Z]{2,10})/USDT", msg.text))
                if sym_m:
                    sym = sym_m.group(1).upper()
                    if sym not in ("USDT", "BTC", "ETH", "THE", "FOR", "AND", "NOT"):
                        if sym not in state.reinforcements:
                            state.reinforcements[sym] = []
                        for rp in reinf_only:
                            entry = {"price": rp, "buy_price": 0, "sell_price": 0,
                                     "tp_pct": 0, "trade_num": 0,
                                     "date": msg.date.strftime("%Y-%m-%d") if msg.date else ""}
                            if not any(abs(e["price"] - rp) < 0.000001 for e in state.reinforcements[sym]):
                                state.reinforcements[sym].append(entry)
                                total_reinf += 1

        log(f"  {channel_name}: {count} رسالة مفحوصة")

    save_state(state)
    log(f"مسح التاريخ: {total_signals} توصية، {total_reinf} سعر تعزيز، {len(state.pending_signals)} توصية معلّقة")
    if state.reinforcements:
        for sym, entries in state.reinforcements.items():
            prices = [e["price"] for e in entries]
            log(f"  {sym}: تعزيزات {prices}")
    if state.pending_signals:
        for s in state.pending_signals:
            log(f"  معلّقة: {s['symbol']} شراء={s['buy_price']} بيع={s['sell_price']}")

async def check_pending_signals(state: State):
    if not state.pending_signals:
        return
    rollover_day(state)
    if state.halted:
        return

    if not PAPER_MODE:
        try:
            ex = next(iter(_exchanges.values()))
            free = float(ex.fetch_balance().get("USDT", {}).get("free", 0))
            if free < 1:
                return
        except Exception:
            pass

    for sig_data in list(state.pending_signals):
        symbol = sig_data["symbol"]
        buy_price = sig_data["buy_price"]
        if buy_price <= 0:
            continue
        if symbol in state.entered_symbols:
            state.pending_signals.remove(sig_data)
            continue
        pair, ex_name = find_pair_exchange(symbol)
        if not pair:
            continue
        if pair in state.open_positions:
            continue
        try:
            price = _exchanges[ex_name].fetch_ticker(pair).get("last")
            if not price:
                continue
            price = float(price)
        except Exception:
            continue

        diff_pct = (price - buy_price) / buy_price * 100
        if price <= buy_price * (1 + REINFORCE_PCT / 100):
            if "watch_start" not in sig_data:
                sig_data["watch_start"] = time.time()
                sig_data["lowest_seen"] = price
                save_state(state)
                log(f"مراقبة: {symbol} @ ${price:.4f} (هدف شراء: ${buy_price}) — ننتظر سعر أفضل")
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
            saving = round((buy_price - price) / buy_price * 100, 1)

            sig_targets = sig_data.get("targets", [])
            sell_price = sig_data.get("sell_price", buy_price * 1.15)
            tp_pct = sig_data.get("tp_pct", 15)

            sig = Signal(
                trade_num=sig_data.get("trade_num", 0),
                symbol=symbol,
                buy_price=price,
                sell_price=sell_price,
                tp_pct=tp_pct,
                targets=[{"price": t["price"], "pct": t["pct"], "completed": False} for t in sig_targets] if sig_targets else [],
            )
            log(f"شراء ذكي: {symbol} @ ${price:.4f} ({entry_reason} | أقل سعر: ${lowest:.4f} | توفير: {saving:+.1f}%)")
            if open_trade(state, sig, reason=f"توصية معلّقة #{sig_data.get('trade_num',0)}"):
                state.pending_signals.remove(sig_data)
                state.executed_signals.append(sig_data["key"])
                if len(state.executed_signals) > 500:
                    state.executed_signals = state.executed_signals[-500:]
                save_state(state)

async def check_reinforcements(state: State):
    if not state.reinforcements:
        return
    rollover_day(state)
    if state.halted:
        return

    if not PAPER_MODE:
        try:
            ex = next(iter(_exchanges.values()))
            free = float(ex.fetch_balance().get("USDT", {}).get("free", 0))
            if free < 1:
                return
        except Exception:
            pass

    for symbol, entries in list(state.reinforcements.items()):
        if not entries:
            continue
        if symbol in state.entered_symbols:
            continue
        pair, ex_name = find_pair_exchange(symbol)
        if not pair:
            continue
        if pair in state.open_positions:
            continue
        try:
            price = _exchanges[ex_name].fetch_ticker(pair).get("last")
            if not price:
                continue
            price = float(price)
        except Exception:
            continue

        for entry in entries:
            reinf_price = entry["price"]
            if reinf_price <= 0:
                continue
            diff_pct = abs(price - reinf_price) / reinf_price * 100
            if diff_pct <= REINFORCE_PCT:
                key = f"{symbol}_{reinf_price}"
                if key in state.reinforced_keys:
                    continue

                entry_targets = entry.get("targets", [])
                if entry_targets:
                    sell_price = entry_targets[-1]["price"]
                    tp_pct = round((sell_price - price) / price * 100, 2)
                else:
                    sell_price = entry.get("sell_price", 0)
                    if sell_price <= 0:
                        sell_price = reinf_price * 1.15
                    tp_pct = entry.get("tp_pct", 0)
                    if tp_pct <= 0:
                        tp_pct = round((sell_price - reinf_price) / reinf_price * 100, 2)

                sig = Signal(
                    trade_num=entry.get("trade_num", 0),
                    symbol=symbol,
                    buy_price=price,
                    sell_price=sell_price,
                    tp_pct=tp_pct,
                    targets=entry_targets,
                )
                log(f"تعزيز! {symbol} @ ${price} قريب من ${reinf_price} (فرق {diff_pct:.1f}%)")
                if open_trade(state, sig, reason=f"تعزيز @ {reinf_price}"):
                    state.reinforced_keys.append(key)
                    if len(state.reinforced_keys) > 500:
                        state.reinforced_keys = state.reinforced_keys[-500:]
                    save_state(state)
                break

# ---------- check mode ----------
def run_check():
    log("=== وضع الفحص ===")
    log(f"TG_API_ID: {'OK' if TG_API_ID else 'مفقود'} | TG_API_HASH: {'OK' if TG_API_HASH else 'مفقود'}")
    log(f"القنوات: {TG_CHANNELS}")
    if BYBIT_KEY:
        try:
            ex = get_exchange(); ex.load_markets()
            usdt = ex.fetch_balance().get("USDT", {}).get("free", 0)
            log(f"Bybit: متصل | USDT={usdt} | testnet={BYBIT_TESTNET}")
        except Exception as e:
            log(f"Bybit: خطأ — {e}")
    else:
        log("Bybit: مفاتيح غير محددة")

    state = load_state()
    log(f"مراكز: {len(state.open_positions)} | صفقات اليوم: {state.daily_trades} | PnL: ${state.daily_pnl:.2f}")
    log(f"رأس المال: ${CAPITAL} | حجم: ${TRADE_SIZE} | الوضع: {'ورقي' if PAPER_MODE else 'حقيقي'}")
    log(f"بيع جزئي: {PARTIAL_SELL_PCT}% عند +{PARTIAL_TP_PCT}% | إعادة شراء عند -{REBUY_DROP_PCT}%")
    log(f"مدة قصوى: {MAX_HOLD_DAYS} يوم")

    if state.reinforcements:
        log(f"تعزيزات محفوظة ({len(state.reinforcements)} عملة):")
        for sym, entries in state.reinforcements.items():
            prices = [e["price"] for e in entries]
            log(f"  {sym}: {prices}")
    else:
        log("لا تعزيزات محفوظة — شغّل البوت ليمسح التاريخ")

    test_msg = ("رقم الصفقة: (5)\nالعملة: PEPE\nالمنصة: بايبت\n"
                "سعر الشراء: 0.00001350\nسعر البيع: 0.00001620 (20%)\n"
                "تعزيز أول: 0.00001200\nتعزيز ثاني: 0.00001100")
    sig = parse_signal(test_msg)
    if sig:
        log(f"اختبار: {sig.symbol} شراء={sig.buy_price} بيع={sig.sell_price} "
            f"({sig.tp_pct}%) تعزيزات={sig.reinforcements}")
    else:
        log("اختبار التحليل: فشل!")
    log("=== انتهى الفحص ===")

# ---------- ملخص القنوات اليومي ----------
_COIN_RE = re.compile(
    r'(?:(?:\$|#)([A-Z]{2,10}))'           # $BTC or #ETH
    r'|(?:([A-Z]{2,10})/USDT)'             # BTC/USDT
    r'|(?:عملة\s+([A-Z]{2,10}))'           # عملة BTC
    r'|(?:(?:^|\s)([A-Z]{2,10})(?:\s|$))',  # standalone BTC
    re.MULTILINE,
)
_COIN_BLACKLIST = {
    "THE", "AND", "FOR", "NOT", "BUT", "ALL", "ARE", "WAS", "HAS", "HAD",
    "CAN", "HER", "HIS", "HOW", "ITS", "LET", "MAY", "NEW", "NOW", "OLD",
    "OUR", "OUT", "OWN", "SAY", "SHE", "TOO", "USE", "WAY", "WHO", "BOY",
    "DID", "GET", "HIM", "MAN", "RUN", "TOP", "VIP", "USD", "API", "URL",
    "APP", "YOU", "ANY", "BIG", "DAY", "END", "FEW", "GOT", "SET", "TRY",
    "WIN", "YES", "BUY", "PUT", "SELL", "LONG", "SHORT", "STOP", "TAKE",
    "HOLD", "DROP", "PUMP", "DUMP", "MOON", "BEAR", "BULL", "HIGH", "LOSS",
    "GAIN", "FREE", "JOIN", "LINK", "SPOT", "FUTURES", "SPOT", "ATR", "RSI",
    "MACD", "EMA", "SMA", "NEWS", "ALERT", "UPDATE", "NOTE", "WARNING",
    "CONFIRMED", "BOTTOM", "BREAK", "ENTRY", "EXIT", "CHART", "PRICE",
    "MARKET", "TRADE", "ORDER", "LIMIT", "DAILY", "WEEKLY", "MONTHLY",
    "OPEN", "CLOSE", "ABOVE", "BELOW", "SUPPORT", "RESISTANCE", "LEVEL",
    "RISK", "SIGNAL", "PROFIT", "TARGET", "SETUP", "TREND", "ZONE",
    "FTX", "CEX", "DEX", "NFT", "ETF", "SEC", "IPO", "OTC", "ICO",
}
_SIGNAL_KEYWORDS = [
    (r"شراء|دخول|شراء قوي|صفقة شراء|long|لونق|لونج|باي|با[يى]|انتري|إنتري"
     r"|بول\s*ران|بول\s*رن|بولش|بولي?ش|بامب|بمب|بامبينق|بمبنق"
     r"|بريك\s*أوت|بريك\s*اوت|بريكاوت|رالي|رالى|مون|موون"
     r"|اكيوميوليت|اكيوملي?ت|تجميع|ارتداد|قاع|سيقنال|سيجنال", "شراء"),
    (r"بيع|خروج|صفقة بيع|short|شورت|دامب|دمب|بير\s*ران|بيرش|بيري?ش|هبوط|هابط", "بيع"),
    (r"هدف|TP|target|تيك\s*بروفت|تارقت|تارجت|بروفت", "هدف"),
    (r"وقف|SL|stop.?loss|ستوب|ستوب\s*لوس|وقف\s*خسار[ةه]", "وقف خسارة"),
    (r"تعزيز|reinforc|دي\s*سي\s*ايه?|DCA", "تعزيز"),
    (r"تحذير|warning|خطر|حذر|ريسك|مخاطر[ةه]", "تحذير"),
    (r"سبورت|دعم|سابورت", "دعم"),
    (r"ريزستنس|مقاوم[ةه]", "مقاومة"),
    (r"تريند|ترند|اتجاه", "اتجاه"),
    (r"هودل|هولد|HODL|تمسك", "هولد"),
]


def _load_channel_memory() -> dict:
    if CHANNEL_MEMORY_FILE.exists():
        try:
            return json.loads(CHANNEL_MEMORY_FILE.read_text())
        except Exception:
            pass
    return {"daily": {}, "coins": {}}


def _save_channel_memory(mem: dict):
    days = sorted(mem.get("daily", {}).keys())
    if len(days) > 90:
        for old in days[:-90]:
            del mem["daily"][old]
    _atomic_write(CHANNEL_MEMORY_FILE, json.dumps(mem, ensure_ascii=False, indent=2))


async def scan_watch_channels(client) -> str:
    from collections import Counter
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    coin_mentions = Counter()
    channel_summaries = {}
    signals_found = []

    for ch_name in WATCH_CHANNELS:
        try:
            entity = await client.get_entity(ch_name)
        except Exception:
            continue

        msg_count = 0
        try:
            async for msg in client.iter_messages(entity, offset_date=since, reverse=True):
                if not msg.text:
                    continue
                msg_count += 1
                text = msg.text

                for m in _COIN_RE.finditer(text):
                    coin = (m.group(1) or m.group(2) or m.group(3) or m.group(4) or "").upper()
                    if coin and len(coin) >= 2 and coin not in _COIN_BLACKLIST:
                        coin_mentions[coin] += 1

                for pat, label in _SIGNAL_KEYWORDS:
                    if re.search(pat, text, re.IGNORECASE):
                        coin_m = _COIN_RE.search(text)
                        if coin_m:
                            c = (coin_m.group(1) or coin_m.group(2) or coin_m.group(3) or coin_m.group(4) or "").upper()
                            if c and c not in _COIN_BLACKLIST:
                                signals_found.append(f"{c} ({label})")
                        break
        except Exception:
            continue

        if msg_count > 0:
            ch_title = getattr(entity, 'title', ch_name)
            channel_summaries[ch_title] = msg_count

    if not coin_mentions:
        return ""

    # --- حفظ في الذاكرة ---
    today = time.strftime("%Y-%m-%d")
    mem = _load_channel_memory()
    mem["daily"][today] = {
        "coins": dict(coin_mentions.most_common(30)),
        "signals": list(dict.fromkeys(signals_found))[:20],
        "channels": channel_summaries,
    }
    for coin, count in coin_mentions.items():
        if coin not in mem["coins"]:
            mem["coins"][coin] = {"total": 0, "days": 0, "first_seen": today, "signals": []}
        mem["coins"][coin]["total"] += count
        mem["coins"][coin]["days"] += 1
        mem["coins"][coin]["last_seen"] = today
    for sig in signals_found:
        coin_name = sig.split(" (")[0]
        if coin_name in mem["coins"]:
            sig_list = mem["coins"][coin_name].setdefault("signals", [])
            sig_list.append({"date": today, "type": sig})
            mem["coins"][coin_name]["signals"] = sig_list[-20:]
    _save_channel_memory(mem)

    # --- بناء الملخص ---
    top_coins = coin_mentions.most_common(10)
    coins_str = " | ".join(f"{c}: {n}×" for c, n in top_coins)

    ch_str = "\n".join(f"  {ch}: {n} رسالة" for ch, n in channel_summaries.items())

    unique_signals = list(dict.fromkeys(signals_found))[:10]
    sig_str = "، ".join(unique_signals) if unique_signals else "لا توجد"

    # --- تحليل أسبوعي من الذاكرة ---
    week_analysis = ""
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_coins = Counter()
    prev_week_coins = Counter()
    for day_str, day_data in mem.get("daily", {}).items():
        if day_str >= week_ago:
            for c, n in day_data.get("coins", {}).items():
                week_coins[c] += n
        elif day_str >= (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d"):
            for c, n in day_data.get("coins", {}).items():
                prev_week_coins[c] += n

    if week_coins:
        trending_up = []
        new_coins = []
        for coin, count in week_coins.most_common(15):
            prev = prev_week_coins.get(coin, 0)
            if prev == 0 and count >= 3:
                new_coins.append(coin)
            elif prev > 0 and count > prev * 1.5:
                trending_up.append(f"{coin} (+{int((count/prev - 1)*100)}%)")

        parts = []
        if trending_up:
            parts.append(f"صاعدة: {', '.join(trending_up[:5])}")
        if new_coins:
            parts.append(f"جديدة: {', '.join(new_coins[:5])}")

        consistent = [c for c, info in mem.get("coins", {}).items()
                       if info.get("days", 0) >= 5][:5]
        if consistent:
            parts.append(f"مستمرة: {', '.join(consistent)}")

        if parts:
            week_analysis = "\n\n<b>تحليل أسبوعي:</b>\n" + "\n".join(f"  {p}" for p in parts)

    total_days = len(mem.get("daily", {}))
    summary = (
        f"<b>📊 ملخص القنوات اليومي</b> (ذاكرة: {total_days} يوم)\n\n"
        f"<b>أكثر العملات ذكراً:</b>\n{coins_str}\n\n"
        f"<b>إشارات:</b> {sig_str}\n\n"
        f"<b>القنوات ({len(channel_summaries)}):</b>\n{ch_str}"
        f"{week_analysis}"
    )
    return summary


# ---------- main ----------
async def main():
    if "--check" in sys.argv:
        run_check(); return

    from telethon import TelegramClient, events
    mode = "ورقي" if PAPER_MODE else "حقيقي"
    log(f"=== بدء البوت الشهري [{mode}] ===")
    log(f"القنوات: {TG_CHANNELS} | رأس المال: ${CAPITAL} | حجم: ${TRADE_SIZE}")

    state = load_state(); rollover_day(state)

    try:
        bybit_ex = get_exchange(); bybit_ex.load_markets()
        _exchanges["bybit"] = bybit_ex
        log(f"Bybit متصل | testnet={BYBIT_TESTNET}")
    except Exception as e:
        log(f"خطأ Bybit: {e}")

    if KUCOIN_KEY:
        try:
            kc = get_kucoin_exchange(); kc.load_markets()
            _exchanges["kucoin"] = kc
            log("KuCoin متصل")
        except Exception as e:
            log(f"خطأ KuCoin: {e}")

    if GATE_KEY:
        try:
            gate = get_gate_exchange(); gate.load_markets()
            _exchanges["gateio"] = gate
            log("Gate.io متصل")
        except Exception as e:
            log(f"خطأ Gate: {e}")

    if not _exchanges:
        log("خطأ: لا منصة متصلة!"); return
    log(f"المنصات: {', '.join(_exchanges.keys())}")

    client = TelegramClient(TG_SESSION, TG_API_ID, TG_API_HASH)
    await client.start()

    me = await client.get_me()
    log(f"Telegram connected as {me.first_name}")

    # مسح تاريخ القنوات
    await scan_history(client, state)

    # عرض القنوات
    for ch_name in TG_CHANNELS:
        try:
            entity = await client.get_entity(ch_name)
            log(f"Listening to channel: {getattr(entity, 'title', ch_name)} (id={entity.id})")
        except Exception as e:
            log(f"خطأ في قناة {ch_name}: {e}")

    @client.on(events.NewMessage(chats=TG_CHANNELS))
    async def on_signal(event):
        text = event.raw_text
        if not text:
            return
        log(f"رسالة جديدة: {text[:80]}...")
        signal = parse_signal(text)
        if not signal:
            log("لم يتم التعرف على التوصية"); return

        sig_key = f"{signal.symbol}_{signal.trade_num}"
        if sig_key in state.executed_signals:
            log(f"توصية سبق تنفيذها — تجاهل: {sig_key}"); return

        if signal.reinforcements and signal.symbol:
            if signal.symbol not in state.reinforcements:
                state.reinforcements[signal.symbol] = []
            for rp in signal.reinforcements:
                entry = {"price": rp, "buy_price": signal.buy_price,
                         "sell_price": signal.sell_price, "tp_pct": signal.tp_pct,
                         "trade_num": signal.trade_num,
                         "targets": [{"price": t["price"], "pct": t["pct"]} for t in signal.targets] if signal.targets else [],
                         "date": time.strftime("%Y-%m-%d")}
                if not any(abs(e["price"] - rp) < 0.000001 for e in state.reinforcements[signal.symbol]):
                    state.reinforcements[signal.symbol].append(entry)
            log(f"  تعزيزات {signal.symbol}: {signal.reinforcements}")

        log(f"توصية: #{signal.trade_num} {signal.symbol} شراء={signal.buy_price} "
            f"بيع={signal.sell_price} ({signal.tp_pct}%)")

        notify(f"توصية جديدة #{signal.trade_num}\nالعملة: {signal.symbol}\n"
               f"شراء: {signal.buy_price}\nبيع: {signal.sell_price} ({signal.tp_pct}%)")
        if open_trade(state, signal, reason="توصية جديدة"):
            state.executed_signals.append(sig_key)
            if len(state.executed_signals) > 500:
                state.executed_signals = state.executed_signals[-500:]
            save_state(state)

    async def position_checker():
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            try:
                log(f"نبض — مراكز: {len(state.open_positions)} | معلقة: {len(state.pending_signals)}")
                if state.open_positions:
                    await check_positions(state)
                    await check_phase2(state)
                tracker_update()
            except Exception as e:
                log(f"خطأ في فحص المراكز: {e}")

    async def reinforcement_checker():
        while True:
            await asyncio.sleep(REINFORCE_CHECK_SEC)
            try:
                if state.reinforcements:
                    await check_reinforcements(state)
                if state.pending_signals:
                    await check_pending_signals(state)
            except Exception as e:
                log(f"خطأ في فحص التعزيزات: {e}")

    async def manual_trade_scanner():
        await asyncio.sleep(60)
        while True:
            try:
                scan_manual_trades()
            except Exception as e:
                log(f"خطأ مسح يدوي: {e}")
            await asyncio.sleep(3600)

    async def tracker_reporter():
        while True:
            await asyncio.sleep(86400)
            try:
                report = tracker_report()
                if report:
                    log(report)
            except Exception:
                pass

    async def daily_channel_summary():
        while True:
            now = datetime.now()
            target = now.replace(hour=DAILY_SUMMARY_HOUR, minute=0, second=0)
            if now >= target:
                target += timedelta(days=1)
            wait_sec = (target - now).total_seconds()
            await asyncio.sleep(wait_sec)
            try:
                summary = await scan_watch_channels(client)
                if summary:
                    log("ملخص القنوات اليومي حُفظ")
            except Exception as e:
                log(f"خطأ ملخص القنوات: {e}")

    asyncio.create_task(position_checker())
    asyncio.create_task(reinforcement_checker())
    asyncio.create_task(manual_trade_scanner())
    asyncio.create_task(tracker_reporter())
    asyncio.create_task(daily_channel_summary())
    log(f"Listening... (cap=${CAPITAL}, "
        f"sizing=dynamic(×0.7-×1.5), phases={len(ENTRY_PHASES)}×{ENTRY_PHASES[0]['ratio']:.0%}@{[p['delay_min'] for p in ENTRY_PHASES]}min, "
        f"max_open={MAX_CONCURRENT}, "
        f"SL=ATR×{ATR_SL_MULTIPLIER}/كارثي-{CATASTROPHIC_SL_PCT}%, "
        f"trailing=+{TRAILING_STOP_ACTIVATE_PCT}%→-{TRAILING_STOP_DISTANCE_PCT}%, "
        f"partial_TP=+{PARTIAL_TP_PCT}%→{PARTIAL_SELL_PCT}%, rebuy=-{REBUY_DROP_PCT}%, "
        f"max_hold={MAX_HOLD_DAYS}d, max_consec_loss={MAX_CONSECUTIVE_LOSSES})")
    if PROTECTED_SYMBOLS:
        log(f"عملات محمية: {PROTECTED_SYMBOLS}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    if "--stats" in sys.argv:
        state = load_state()
        report = compute_stats(state.trade_history)
        clean = report.replace("<b>","").replace("</b>","")
        print(clean)
        sys.exit(0)
    if "--clean-tracker" in sys.argv:
        data = _load_tracker()
        before = len(data)
        data = _clean_tracker(data)
        after = len(data)
        _save_tracker(data)
        print(f"✅ تنظيف التراكر: {before} → {after} (حذف {before - after})")
        sys.exit(0)
    if "--tracker" in sys.argv:
        data = _load_tracker()
        bot_count = sum(1 for r in data if r.get("source", "bot") == "bot")
        manual_count = sum(1 for r in data if r.get("source") == "manual")
        print(f"توصيات متتبعة: {len(data)} (بوت: {bot_count} | يدوي: {manual_count})")
        for r in data:
            cps = r.get("checkpoints", {})
            cp_str = " | ".join(f"{k}: {v['diff_pct']:+.1f}%" for k, v in sorted(cps.items()))
            src = "🤖" if r.get("source", "bot") == "bot" else "👤"
            print(f"  {src} {r['symbol']} [{r.get('exchange','')}] @ ${r['signal_price']} ({r['signal_str']}) — {cp_str or 'قيد التتبع'}")
        report = tracker_report()
        if report:
            print(f"\n{report}")
        sys.exit(0)
    if "--backfill" in sys.argv:
        import ccxt
        print("جاري تحليل الصفقات السابقة من بيانات المنصة...")
        exchanges = {}
        if BYBIT_KEY:
            try:
                ex = get_exchange(); ex.load_markets()
                exchanges["bybit"] = ex; print("Bybit متصل")
            except Exception as e:
                print(f"خطأ Bybit: {e}")
        if KUCOIN_KEY:
            try:
                ex = get_kucoin_exchange(); ex.load_markets()
                exchanges["kucoin"] = ex; print("KuCoin متصل")
            except Exception as e:
                print(f"خطأ KuCoin: {e}")
        if GATE_KEY:
            try:
                ex = get_gate_exchange(); ex.load_markets()
                exchanges["gateio"] = ex; print("Gate.io متصل")
            except Exception as e:
                print(f"خطأ Gate: {e}")
        state = load_state()
        all_trades = []
        for t in state.trade_history:
            all_trades.append({
                "symbol": t["pair"].split("/")[0], "pair": t["pair"],
                "entry_price": t["entry"], "closed_price": t.get("exit"),
                "opened": t.get("opened", 0),
                "opened_str": t.get("opened_str", t.get("closed", "")),
                "exchange": t.get("exchange", "bybit"),
            })
        for pair, pos in state.open_positions.items():
            all_trades.append({
                "symbol": pos.get("symbol", pair.split("/")[0]), "pair": pair,
                "entry_price": pos["entry"], "closed_price": None,
                "opened": pos.get("opened", 0),
                "opened_str": pos.get("opened_str", ""),
                "exchange": pos.get("exchange", "bybit"),
            })
        data = _load_tracker()
        existing_keys = {(r["symbol"], r.get("signal_str", "")) for r in data}
        added = 0
        for trade in all_trades:
            pair = trade["pair"]
            ex_name = trade["exchange"]
            ex = exchanges.get(ex_name)
            if not ex:
                ex = next(iter(exchanges.values()), None)
            if not ex or pair not in ex.markets:
                print(f"  {pair} — غير موجود في المنصة"); continue
            entry_ts = trade["opened"]
            if not entry_ts:
                print(f"  {pair} — بدون وقت دخول"); continue
            entry_str = trade["opened_str"]
            if (trade["symbol"], entry_str) in existing_keys:
                print(f"  {pair} — موجود بالفعل"); continue
            print(f"  {pair} — جاري جلب البيانات...", end=" ")
            try:
                since_ms = int(entry_ts * 1000)
                candles = ex.fetch_ohlcv(pair, "15m", since=since_ms, limit=200)
                if not candles:
                    print("لا توجد بيانات"); continue
            except Exception as e:
                print(f"خطأ: {e}"); continue
            entry_price = trade["entry_price"]
            rec = {
                "symbol": trade["symbol"], "pair": pair, "exchange": ex_name,
                "signal_price": entry_price, "entry_price": entry_price,
                "signal_time": entry_ts, "signal_str": entry_str,
                "checkpoints": {},
            }
            for cp_min in _TRACK_CHECKPOINTS:
                target_ts = entry_ts + cp_min * 60
                best = min(candles, key=lambda c: abs(c[0]/1000 - target_ts))
                if abs(best[0]/1000 - target_ts) < cp_min * 60 * 0.5:
                    price = best[4]
                    diff_pct = round((price - entry_price) / entry_price * 100, 2)
                    rec["checkpoints"][f"{cp_min}m"] = {
                        "price": price, "diff_pct": diff_pct,
                        "time": time.strftime("%Y-%m-%d %H:%M", time.gmtime(best[0]/1000)),
                    }
            data.append(rec)
            added += 1
            cp_str = " | ".join(f"{k}: {v['diff_pct']:+.1f}%" for k, v in sorted(rec["checkpoints"].items()))
            print(f"✓ {cp_str}")
        _save_tracker(data)
        print(f"\nتم إضافة {added} صفقة")
        report = tracker_report()
        if report:
            print(f"\n{report}")
        sys.exit(0)
    if "--set-targets" in sys.argv:
        idx = sys.argv.index("--set-targets")
        if idx + 2 >= len(sys.argv):
            print("الاستخدام: --set-targets SYMBOL سعر1,سعر2,سعر3...")
            print("مثال: --set-targets NEAR 1.40,1.70,2.26,3.00,7.00,12.8")
            sys.exit(1)
        symbol = sys.argv[idx + 1].upper()
        prices = [float(p) for p in sys.argv[idx + 2].split(",")]
        state = load_state()
        found = False
        for pair, pos in state.open_positions.items():
            if pos.get("symbol", pair.split("/")[0]).upper() == symbol:
                entry = pos["entry"]
                targets = []
                for p in prices:
                    pct = round((p - entry) / entry * 100, 2)
                    targets.append({"price": p, "pct": pct, "hit": False})
                pos["targets"] = targets
                pos["targets_hit"] = 0
                pos["tp"] = prices[-1]
                pos["tp_pct"] = round((prices[-1] - entry) / entry * 100, 2)
                save_state(state)
                print(f"✅ {pair} — تم تعيين {len(targets)} أهداف:")
                for t in targets:
                    print(f"  {t['price']} ({t['pct']:+.1f}%)")
                found = True
                break
        if not found:
            print(f"❌ {symbol} غير موجود في المراكز المفتوحة")
            print("المراكز الحالية:")
            for pair, pos in state.open_positions.items():
                t_count = len(pos.get("targets", []))
                print(f"  {pos.get('symbol', '?')} ({pair}) — أهداف: {t_count or 'لا يوجد'}")
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
                ex_name = pos.get("exchange", "bybit")
                import ccxt
                if ex_name == "bybit":
                    ex = get_exchange(); ex.load_markets()
                elif ex_name == "kucoin":
                    ex = get_kucoin_exchange(); ex.load_markets()
                elif ex_name == "gateio":
                    ex = get_gate_exchange(); ex.load_markets()
                else:
                    print(f"❌ منصة غير معروفة: {ex_name}"); sys.exit(1)
                price = float(ex.fetch_ticker(pair).get("last", 0))
                if price <= 0:
                    print(f"❌ تعذر جلب سعر {pair}"); sys.exit(1)
                print(f"بيع {pair} @ {price} على {ex_name}...")
                order = spot_sell(ex, pair, pos["qty"])
                if order:
                    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100
                    pnl = (price - pos["entry"]) * pos["qty"]
                    state.trade_history.append({
                        "pair": pair, "entry": pos["entry"], "exit": price,
                        "pnl": round(pnl, 4), "pnl_pct": round(pnl_pct, 2),
                        "reason": "بيع يدوي (CLI)", "exchange": ex_name,
                        "opened_str": pos.get("opened_str", ""),
                        "closed": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    del state.open_positions[pair]
                    # Clean entered_symbols so the symbol can be re-entered later
                    if symbol in state.entered_symbols:
                        state.entered_symbols.remove(symbol)
                    save_state(state)
                    sign = "+" if pnl >= 0 else ""
                    print(f"✅ تم بيع {pair} @ {price} | ربح: {sign}{pnl_pct:.1f}% (${sign}{pnl:.2f})")
                    msg = f"بيع يدوي: {pair}\nسعر: {price} ({sign}{pnl_pct:.1f}%)\nربح: ${sign}{pnl:.2f}"
                    notify(msg)
                else:
                    print(f"❌ فشل بيع {pair}")
                found = True
                break
        if not found:
            print(f"❌ {symbol} غير موجود في المراكز المفتوحة")
        sys.exit(0)
    if "--recover" in sys.argv:
        async def _recover():
            from telethon import TelegramClient
            RECOVER_SYMBOLS = {"NEAR", "MOVR", "APT", "ZEN", "UB", "NIL", "XLM"}
            print("جاري الاتصال بتيليجرام لاسترجاع التوصيات...")
            client = TelegramClient(TG_SESSION, TG_API_ID, TG_API_HASH)
            await client.start()

            # جلب الرصيد الفعلي من المنصات
            import ccxt
            exchanges_local = {}
            if BYBIT_KEY:
                try:
                    ex = get_exchange(); ex.load_markets()
                    exchanges_local["bybit"] = ex
                except Exception as e:
                    print(f"خطأ Bybit: {e}")
            if KUCOIN_KEY:
                try:
                    ex = get_kucoin_exchange(); ex.load_markets()
                    exchanges_local["kucoin"] = ex
                except Exception as e:
                    print(f"خطأ KuCoin: {e}")

            # رصيد كل عملة في المنصات
            holdings = {}  # symbol -> {qty, exchange}
            for ex_name, ex in exchanges_local.items():
                try:
                    bal = ex.fetch_balance()
                    for sym, info in bal.items():
                        if not isinstance(info, dict): continue
                        total = float(info.get("total", 0))
                        if total > 0 and sym.upper() in RECOVER_SYMBOLS:
                            holdings[sym.upper()] = {"qty": total, "exchange": ex_name}
                except Exception:
                    pass

            print(f"عملات موجودة في المنصات: {list(holdings.keys())}")

            # مسح التوصيات من القنوات
            since = datetime.now(timezone.utc) - timedelta(days=60)
            found_signals = {}  # symbol -> signal

            for channel_name in TG_CHANNELS:
                try:
                    entity = await client.get_entity(channel_name)
                except Exception:
                    continue
                async for msg in client.iter_messages(entity, offset_date=since, reverse=True):
                    if not msg.text:
                        continue
                    sig = parse_signal(msg.text)
                    if sig and sig.symbol.upper() in holdings:
                        found_signals[sig.symbol.upper()] = sig

            state = load_state()
            added = 0
            for symbol, holding in holdings.items():
                # تخطي إذا موجود بالفعل
                already = any(p.get("symbol") == symbol for p in state.open_positions.values())
                if already:
                    print(f"  {symbol} — موجود بالفعل في البوت، تخطي")
                    continue

                sig = found_signals.get(symbol)
                ex_name = holding["exchange"]
                ex = exchanges_local.get(ex_name)
                qty = holding["qty"]

                try:
                    pair = f"{symbol}/USDT"
                    price = float(ex.fetch_ticker(pair).get("last", 0))
                except Exception:
                    price = 0

                if sig:
                    entry = sig.buy_price
                    tp = sig.sell_price
                    tp_pct = sig.tp_pct
                    targets_list = [{"price": t["price"], "pct": t["pct"], "hit": False}
                                    for t in sig.targets] if sig.targets else []
                    trade_num = sig.trade_num
                    print(f"  ✅ {symbol} — توصية وجدت: دخول={entry} هدف={tp} أهداف={len(targets_list)}")
                else:
                    entry = price if price else qty
                    tp = round(price * 1.20, 6) if price else 0
                    tp_pct = 20.0
                    targets_list = []
                    trade_num = 0
                    print(f"  ⚠️ {symbol} — لا توصية، هدف افتراضي +20% @ {tp}")

                state.open_positions[pair] = {
                    "trade_num": trade_num, "symbol": symbol, "pair": pair,
                    "entry": entry, "qty": qty, "tp": tp, "tp_pct": tp_pct,
                    "opened": time.time(), "opened_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "reason": "استرجاع يدوي", "exchange": ex_name,
                    "swing_base": entry, "total_size": round(entry * qty, 2),
                    "phases": [], "atr_sl": None, "targets": targets_list, "targets_hit": 0,
                }
                added += 1

            save_state(state)
            print(f"\n✅ تم إضافة {added} عملة للبوت")
            await client.disconnect()

        asyncio.run(_recover())
        sys.exit(0)
    asyncio.run(main())
