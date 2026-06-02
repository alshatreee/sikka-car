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
ENV_FILE, STATE_FILE, LOG_FILE = (
    BASE_DIR / ".env_monthly", BASE_DIR / "monthly_state.json", BASE_DIR / "monthly.log")
load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# ---------- config ----------
TG_API_ID    = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH  = os.getenv("TG_API_HASH", "")
TG_CHANNELS  = [c.strip() for c in os.getenv("MONTHLY_CHANNELS",
                os.getenv("MONTHLY_CHANNEL", "")).split(",") if c.strip()]
TG_SESSION   = str(BASE_DIR / "monthly_session")
BYBIT_KEY    = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET = os.getenv("BYBIT_API_SECRET", "")
BYBIT_TESTNET = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
KUCOIN_KEY    = os.getenv("KUCOIN_API_KEY", "")
KUCOIN_SECRET = os.getenv("KUCOIN_API_SECRET", "")
KUCOIN_PASS   = os.getenv("KUCOIN_PASSPHRASE", "")
NOTIFY_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

CAPITAL      = float(os.getenv("MONTHLY_CAPITAL", "1000"))
TRADE_PCT    = float(os.getenv("MONTHLY_TRADE_PCT", "10"))
TRADE_SIZE   = CAPITAL * TRADE_PCT / 100
SL_PCT       = float(os.getenv("MONTHLY_SL_PCT", "5.0"))
CATASTROPHIC_SL_PCT = float(os.getenv("MONTHLY_CATASTROPHIC_SL", "30.0"))
MAX_HOLD_DAYS = int(os.getenv("MONTHLY_MAX_HOLD_DAYS", "45"))
MAX_DAILY_TRADES = 10
MAX_OPEN = 10
MAX_DAILY_LOSS_PCT = float(os.getenv("MONTHLY_MAX_LOSS_PCT", "5.0"))
MAX_DAILY_LOSS = CAPITAL * MAX_DAILY_LOSS_PCT / 100
PARTIAL_TP_PCT = float(os.getenv("MONTHLY_PARTIAL_TP_PCT", "3.0"))
PARTIAL_SELL_PCT = float(os.getenv("MONTHLY_PARTIAL_SELL_PCT", "50"))
REBUY_DROP_PCT = float(os.getenv("MONTHLY_REBUY_DROP_PCT", "10.0"))
BTC_DROP_LIMIT = float(os.getenv("MONTHLY_BTC_DROP_LIMIT", "5.0"))
LIMIT_ORDER_SLIP = float(os.getenv("MONTHLY_LIMIT_SLIP", "0.5"))  # % فوق السوق للشراء
MAX_TP_PCT = float(os.getenv("MONTHLY_MAX_TP_PCT", "100"))  # تجاهل توصيات T1 > 100%
MIN_TRADE_USDT = float(os.getenv("MONTHLY_MIN_TRADE_USDT", "5.0"))
KUCOIN_TRADE_SIZE = float(os.getenv("MONTHLY_KUCOIN_TRADE_SIZE", "100"))
BYBIT_TRADE_SIZE = float(os.getenv("MONTHLY_BYBIT_TRADE_SIZE", "100"))
PROTECTED_SYMBOLS = [s.strip().upper() for s in os.getenv("MONTHLY_PROTECTED_SYMBOLS", "").split(",") if s.strip()]
CHECK_INTERVAL = 300
PAPER_MODE = "--live" not in sys.argv

HISTORY_DAYS   = int(os.getenv("MONTHLY_HISTORY_DAYS", "30"))
REINFORCE_PCT  = float(os.getenv("MONTHLY_REINFORCE_PCT", "2.0"))
REINFORCE_CHECK_SEC = int(os.getenv("MONTHLY_REINFORCE_SEC", "600"))

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
    entered_symbols: list[str] = field(default_factory=list)

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
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2, ensure_ascii=False))

def rollover_day(s: State) -> None:
    today = time.strftime("%Y-%m-%d")
    if s.day != today:
        s.day, s.daily_trades, s.daily_pnl, s.halted = today, 0, 0.0, False
        save_state(s); log(f"=== يوم جديد {today} — إعادة تعيين ===")

# ---------- signal parser ----------
@dataclass
class Signal:
    trade_num: int; symbol: str; buy_price: float; sell_price: float; tp_pct: float
    reinforcements: list[float] = field(default_factory=list)

def parse_signal(text: str) -> Signal | None:
    """يحلل صيغتين: (1) سعر الشراء/البيع البسيطة (2) الشراء والتعزيز المفصّلة."""
    if not text:
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
        buy_p, sell_p = float(buy_m.group(1)), float(sell_m.group(1))
        pct_m = re.search(r"سعر\s*البيع\s*[:\s]*[\d.]+\s*\(?\s*%?([\d.]+)\s*%\)?", text)
        tp_pct = float(pct_m.group(1)) if pct_m else (
            round((sell_p - buy_p) / buy_p * 100, 2) if buy_p > 0 else 0.0)
        reinf = parse_reinforcements(text)
        return Signal(trade_num, symbol, buy_p, sell_p, tp_pct, reinf)

    # صيغة 2: الشراء والتعزيز + أهداف الصفقة
    if "الشراء والتعزيز" in text or "التعزيز الأول" in text:
        buy_p, reinf = _parse_buy_and_reinforce(text)
        sell_p, tp_pct = _parse_targets(text, buy_p)
        if buy_p > 0:
            return Signal(trade_num, symbol, buy_p, sell_p, tp_pct, reinf)

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
        if "الشراء الأول" in line or "الشراء" in line and "تعزيز" not in line.lower():
            if buy_price == 0:
                buy_price = price
        if "التعزيز" in line:
            reinforcements.append(price)
    return buy_price, sorted(reinforcements)

def _parse_targets(text: str, buy_price: float) -> tuple[float, float]:
    """يستخرج أول هدف من 'أهداف الصفقة'."""
    sell_price = 0.0
    in_targets = False
    for line in text.split("\n"):
        if "أهداف الصفقة" in line:
            in_targets = True; continue
        if "أهداف التعزيز" in line:
            break
        if in_targets:
            m = re.search(r"[-–]\s*([\d.]+)\s*\(([\d.]+)%\)", line)
            if m:
                sell_price = float(m.group(1))
                tp_pct = float(m.group(2))
                return sell_price, tp_pct
    if sell_price == 0 and buy_price > 0:
        sell_price = buy_price * 1.20
    tp_pct = round((sell_price - buy_price) / buy_price * 100, 2) if buy_price > 0 else 0
    return sell_price, tp_pct

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

_exchanges: dict = {}
_EXCHANGE_PRIORITY = ["bybit", "kucoin"]

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
            if f:
                return f
        except (TypeError, ValueError):
            continue
    return default

def spot_buy(exchange, pair: str, usdt_amount: float) -> dict | None:
    """شراء بأمر محدود (0.5% فوق السوق) مع احتياط سوق إذا لم يُنفَّذ خلال 30 ثانية"""
    try:
        price = _safe_float(exchange.fetch_ticker(pair).get("last"))
        if not price:
            return None
        qty = usdt_amount / price
        limit_price = round(price * (1 + LIMIT_ORDER_SLIP / 100), 8)

        if PAPER_MODE:
            log(f"أمر شراء [ورقي]: {pair} | سعر={price} | كمية={qty:.6f} | ${usdt_amount}")
            return {"filled": qty, "amount": qty, "average": price, "price": price}

        order = exchange.create_limit_buy_order(pair, qty, limit_price)
        log(f"أمر شراء محدود: {pair} | سعر={limit_price:.6g} | كمية={qty:.6f} | ${usdt_amount}")

        # انتظار التنفيذ حتى 30 ثانية
        oid = order.get("id")
        if oid:
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
            # إلغاء والتحويل لأمر سوق
            try:
                exchange.cancel_order(oid, pair)
            except Exception:
                pass
            log(f"لم يُنفَّذ الأمر المحدود — تحويل لأمر سوق: {pair}")
            order = exchange.create_market_buy_order(pair, qty)
        return order
    except Exception as e:
        log(f"خطأ في الشراء: {pair} — {e}"); return None

def spot_sell(exchange, pair: str, qty: float) -> dict | None:
    try:
        order = exchange.create_market_sell_order(pair, qty)
        log(f"أمر بيع: {pair} | كمية={qty:.6f}"); return order
    except Exception as e:
        log(f"خطأ في البيع: {pair} — {e}"); return None

def place_stop_loss(exchange, pair: str, qty: float, trigger_price: float) -> str | None:
    try:
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
        size = free_usdt * TRADE_PCT / 100
        log(f"رصيد: ${free_usdt:.2f} | حجم الصفقة: ${size:.2f} ({TRADE_PCT}%)")
        return round(size, 2)
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
            return
        rebuy_qty = _safe_float(order.get("filled"), order.get("amount"), default=rebuy_qty)

    new_qty = pos["qty"] + rebuy_qty

    if not PAPER_MODE:
        new_sl_oid = place_stop_loss(exchange, pair, new_qty, pos["sl"])
        pos["sl_order_id"] = new_sl_oid

    pos["qty"] = new_qty
    pos["partial_taken"] = False
    pos["partial_usdt"] = 0
    save_state(state)

    drop_pct = (price - pos["entry"]) / pos["entry"] * 100
    msg = (f"إعادة شراء: {pair}\n"
           f"شراء @ {price} ({drop_pct:+.1f}%)\n"
           f"${partial_usdt:.2f} → {rebuy_qty:.6f} | إجمالي: {new_qty:.6f}")
    log(msg); notify(msg)

# ---------- trade logic ----------
def open_trade(state: State, signal: Signal, reason: str = "توصية جديدة") -> bool:
    rollover_day(state)
    if signal.symbol in PROTECTED_SYMBOLS:
        log(f"عملة محمية — تجاهل: {signal.symbol}"); return False
    if state.halted:
        log("متوقف — تجاوز حد الخسارة اليومي"); return False
    if state.daily_trades >= MAX_DAILY_TRADES:
        log(f"حد الصفقات اليومي ({MAX_DAILY_TRADES})"); return False
    if len(state.open_positions) >= MAX_OPEN:
        log(f"حد المراكز المفتوحة ({MAX_OPEN})"); return False

    pair, ex_name = find_pair_exchange(signal.symbol)
    if not pair:
        log(f"الزوج غير موجود: {signal.symbol}/USDT"); return False
    if pair in state.open_positions:
        log(f"مركز مفتوح بالفعل: {pair}"); return False
    if any(p.get("symbol") == signal.symbol for p in state.open_positions.values()):
        log(f"العملة مفتوحة بالفعل بمنصة أخرى: {signal.symbol}"); return False

    exchange = _exchanges[ex_name]
    _fixed = {"kucoin": KUCOIN_TRADE_SIZE, "bybit": BYBIT_TRADE_SIZE}.get(ex_name)
    trade_size = _fixed if _fixed else get_trade_size(exchange)
    if trade_size < MIN_TRADE_USDT:
        log(f"رصيد غير كافٍ: ${trade_size:.2f} < ${MIN_TRADE_USDT}"); return False

    entry, qty = signal.buy_price, trade_size / signal.buy_price

    if not PAPER_MODE:
        order = spot_buy(exchange, pair, trade_size)
        if not order:
            return False
        try:
            entry = float(order.get("average") or order.get("price") or entry)
            qty = float(order.get("filled") or order.get("amount") or qty)
        except (TypeError, ValueError):
            pass

    state.open_positions[pair] = {
        "trade_num": signal.trade_num, "symbol": signal.symbol, "pair": pair,
        "entry": entry, "qty": qty, "tp": signal.sell_price,
        "tp_pct": signal.tp_pct, "opened": time.time(),
        "opened_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason, "exchange": ex_name,
    }
    state.daily_trades += 1
    if signal.symbol not in state.entered_symbols:
        state.entered_symbols.append(signal.symbol)
    save_state(state)

    mode = "ورقي" if PAPER_MODE else "حقيقي"
    msg = (f"صفقة [{mode}] — {reason}\n#{signal.trade_num} | {pair} [{ex_name}]\n"
           f"دخول: {entry} | هدف: {signal.sell_price} ({signal.tp_pct}%)\n"
           f"بيع جزئي عند +{PARTIAL_TP_PCT}% | إعادة شراء عند -{REBUY_DROP_PCT}% | ${trade_size:.0f}")
    log(msg); notify(msg); return True

def close_trade(state: State, pair: str, reason: str, price: float, exchange, skip_sell: bool = False):
    pos = state.open_positions.pop(pair, None)
    if not pos:
        return
    sell_qty = pos["qty"]
    pnl = (price - pos["entry"]) * sell_qty
    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100

    if not PAPER_MODE and not skip_sell:
        try:
            balance = exchange.fetch_balance()
            sym = pair.split("/")[0]
            available = float(balance.get(sym, {}).get("free", 0))
            if available < sell_qty:
                sell_qty = available
        except Exception:
            pass
        if sell_qty > 0:
            spot_sell(exchange, pair, sell_qty)

    state.daily_pnl += pnl
    if state.daily_pnl <= -MAX_DAILY_LOSS:
        state.halted = True
        log(f"إيقاف التداول — خسارة يومية ${state.daily_pnl:.2f}")
        notify(f"إيقاف التداول — خسارة يومية ${state.daily_pnl:.2f}")

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

        # 1) وقف خسارة كارثي -30% (حماية من الانهيار الكامل)
        cat_sl = pos["entry"] * (1 - CATASTROPHIC_SL_PCT / 100)
        if price <= cat_sl:
            close_trade(state, pair, f"وقف كارثي -{CATASTROPHIC_SL_PCT:.0f}%", price, exchange)
            continue

        # 2) إعادة شراء بعد البيع الجزئي إذا نزل السعر -10%
        if pos.get("partial_taken"):
            rebuy_trigger = pos["entry"] * (1 - REBUY_DROP_PCT / 100)
            if price <= rebuy_trigger:
                partial_rebuy(state, pair, price, exchange)
                continue

        # 3) بيع جزئي عند ارتفاع +3%
        if not pos.get("partial_taken"):
            partial_tp_trigger = pos["entry"] * (1 + PARTIAL_TP_PCT / 100)
            if price >= partial_tp_trigger:
                partial_sell(state, pair, price, exchange)
                continue

        # 4) هدف ربح كامل
        if price >= pos["tp"]:
            close_trade(state, pair, "هدف ربح", price, exchange)
        elif (time.time() - pos["opened"]) / 86400 >= MAX_HOLD_DAYS:
            close_trade(state, pair, f"مدة قصوى ({MAX_HOLD_DAYS} يوم)", price, exchange)

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
                                 "date": msg.date.strftime("%Y-%m-%d") if msg.date else ""}
                        if not any(abs(e["price"] - rp) < 0.000001 for e in state.reinforcements[signal.symbol]):
                            state.reinforcements[signal.symbol].append(entry)

            reinf_only = parse_reinforcements(msg.text)
            if reinf_only and not signal:
                sym_m = re.search(r"([A-Z]{2,10})", msg.text)
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
        tp_pct_val = sig_data.get("tp_pct", 0)
        if tp_pct_val > MAX_TP_PCT:
            log(f"تجاهل توصية معلّقة: {symbol} هدف +{tp_pct_val:.0f}% > {MAX_TP_PCT:.0f}%")
            state.pending_signals.remove(sig_data)
            continue
        if -REINFORCE_PCT <= diff_pct <= REINFORCE_PCT:
            sig = Signal(
                trade_num=sig_data.get("trade_num", 0),
                symbol=symbol,
                buy_price=price,
                sell_price=sig_data.get("sell_price", buy_price * 1.15),
                tp_pct=sig_data.get("tp_pct", 15),
            )
            log(f"توصية معلّقة! {symbol} @ ${price:.4f} قريب من ${buy_price} (فرق {diff_pct:+.1f}%)")
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
    log(f"مدة قصوى: {MAX_HOLD_DAYS} يوم | حد الهدف: {MAX_TP_PCT}% (أعلى يُتجاهل)")

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

# ---------- main ----------
async def main():
    if "--check" in sys.argv:
        run_check(); return

    from telethon import TelegramClient, events
    mode = "ورقي" if PAPER_MODE else "حقيقي"
    log(f"=== بدء البوت الشهري [{mode}] ===")
    log(f"القنوات: {TG_CHANNELS} | رأس المال: ${CAPITAL} | حجم: ${TRADE_SIZE}")
    notify(f"بدء البوت الشهري [{mode}]\nالقنوات: {', '.join(TG_CHANNELS)}")

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

        if signal.reinforcements and signal.symbol:
            if signal.symbol not in state.reinforcements:
                state.reinforcements[signal.symbol] = []
            for rp in signal.reinforcements:
                entry = {"price": rp, "buy_price": signal.buy_price,
                         "sell_price": signal.sell_price, "tp_pct": signal.tp_pct,
                         "trade_num": signal.trade_num, "date": time.strftime("%Y-%m-%d")}
                if not any(abs(e["price"] - rp) < 0.000001 for e in state.reinforcements[signal.symbol]):
                    state.reinforcements[signal.symbol].append(entry)
            log(f"  تعزيزات {signal.symbol}: {signal.reinforcements}")

        log(f"توصية: #{signal.trade_num} {signal.symbol} شراء={signal.buy_price} "
            f"بيع={signal.sell_price} ({signal.tp_pct}%)")

        if signal.tp_pct > MAX_TP_PCT:
            log(f"تجاهل: {signal.symbol} هدف +{signal.tp_pct:.0f}% أعلى من الحد {MAX_TP_PCT:.0f}%")
            notify(f"تجاهل توصية #{signal.trade_num} {signal.symbol}\nالهدف +{signal.tp_pct:.0f}% أعلى من الحد المسموح ({MAX_TP_PCT:.0f}%)")
            return

        notify(f"توصية جديدة #{signal.trade_num}\nالعملة: {signal.symbol}\n"
               f"شراء: {signal.buy_price}\nبيع: {signal.sell_price} ({signal.tp_pct}%)")
        open_trade(state, signal, reason="توصية جديدة")

    async def position_checker():
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            try:
                if state.open_positions:
                    await check_positions(state)
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

    asyncio.create_task(position_checker())
    asyncio.create_task(reinforcement_checker())
    log(f"Listening... (cap=${CAPITAL}, size=$100 ثابت, "
        f"وقف_كارثي=-{CATASTROPHIC_SL_PCT}%, "
        f"partial_TP=+{PARTIAL_TP_PCT}%→{PARTIAL_SELL_PCT}%, rebuy=-{REBUY_DROP_PCT}%, "
        f"max_hold={MAX_HOLD_DAYS}d, max_tp={MAX_TP_PCT}%, "
        f"BTC_filter=24h+SMA50)")
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
    asyncio.run(main())
