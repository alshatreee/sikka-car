"""
monthly_channel_bot.py — Bybit Spot trader من قناة تيلجرام شهرية عربية

يقرأ توصيات بصيغة: رقم الصفقة / العملة / سعر الشراء / سعر البيع (%)
وينفذ سبوت على Bybit. الوضع الافتراضي ورقي.

    python3 monthly_channel_bot.py              # ورقي
    python3 monthly_channel_bot.py --live       # حقيقي
    python3 monthly_channel_bot.py --check      # فحص

    pip install telethon ccxt python-dotenv requests
"""
from __future__ import annotations
import asyncio, json, os, re, sys, time
from dataclasses import dataclass, field, asdict
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
TG_CHANNEL   = os.getenv("MONTHLY_CHANNEL", "channel_name_here")
TG_SESSION   = str(BASE_DIR / "monthly_session")
BYBIT_KEY    = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET = os.getenv("BYBIT_API_SECRET", "")
BYBIT_TESTNET = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
NOTIFY_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

CAPITAL      = float(os.getenv("MONTHLY_CAPITAL", "1000"))
TRADE_PCT    = float(os.getenv("MONTHLY_TRADE_PCT", "10"))
TRADE_SIZE   = CAPITAL * TRADE_PCT / 100          # $100 default
SL_PCT       = float(os.getenv("MONTHLY_SL_PCT", "5.0"))
MAX_HOLD_DAYS = int(os.getenv("MONTHLY_MAX_HOLD_DAYS", "30"))
MAX_DAILY_TRADES, MAX_OPEN, MAX_DAILY_LOSS = 10, 10, 50.0
CHECK_INTERVAL = 300   # 5 min
PAPER_MODE = "--live" not in sys.argv

# ---------- logging / notify ----------
def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
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

def load_state() -> State:
    if STATE_FILE.exists():
        try: return State(**json.loads(STATE_FILE.read_text()))
        except Exception: pass
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

def parse_signal(text: str) -> Signal | None:
    """يحلل رسالة القناة العربية ويستخرج التوصية."""
    if not text:
        return None
    num_m = re.search(r"رقم\s*الصفقة\s*[:\s]*\(?(\d+)\)?", text)
    sym_m = re.search(r"العملة\s*[:\s]*([A-Za-z0-9]+)", text)
    buy_m = re.search(r"سعر\s*الشراء\s*[:\s]*([\d.]+)", text)
    sell_m = re.search(r"سعر\s*البيع\s*[:\s]*([\d.]+)", text)
    if not (sym_m and buy_m and sell_m):
        return None
    symbol, buy_p, sell_p = sym_m.group(1).upper(), float(buy_m.group(1)), float(sell_m.group(1))
    pct_m = re.search(r"سعر\s*البيع\s*[:\s]*[\d.]+\s*\(?([\d.]+)%\)?", text)
    tp_pct = float(pct_m.group(1)) if pct_m else (
        round((sell_p - buy_p) / buy_p * 100, 2) if buy_p > 0 else 0.0)
    return Signal(int(num_m.group(1)) if num_m else 0, symbol, buy_p, sell_p, tp_pct)

# ---------- exchange ----------
def get_exchange():
    import ccxt
    ex = ccxt.bybit({"apiKey": BYBIT_KEY, "secret": BYBIT_SECRET,
                      "options": {"defaultType": "spot"}})
    if BYBIT_TESTNET:
        ex.set_sandbox_mode(True)
    return ex

def verify_symbol(exchange, symbol: str) -> str | None:
    """يتحقق من وجود الزوج على Bybit Spot."""
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
        price = exchange.fetch_ticker(pair)["last"]
        qty = usdt_amount / price
        order = exchange.create_market_buy_order(pair, qty)
        log(f"أمر شراء: {pair} | كمية={qty:.6f} | ${usdt_amount}")
        return order
    except Exception as e:
        log(f"خطأ في الشراء: {pair} — {e}"); return None

def spot_sell(exchange, pair: str, qty: float) -> dict | None:
    try:
        order = exchange.create_market_sell_order(pair, qty)
        log(f"أمر بيع: {pair} | كمية={qty:.6f}"); return order
    except Exception as e:
        log(f"خطأ في البيع: {pair} — {e}"); return None

# ---------- trade logic ----------
def open_trade(state: State, signal: Signal, exchange) -> bool:
    rollover_day(state)
    if state.halted:
        log("متوقف — تجاوز حد الخسارة اليومي"); return False
    if state.daily_trades >= MAX_DAILY_TRADES:
        log(f"حد الصفقات اليومي ({MAX_DAILY_TRADES})"); return False
    if len(state.open_positions) >= MAX_OPEN:
        log(f"حد المراكز المفتوحة ({MAX_OPEN})"); return False

    pair = verify_symbol(exchange, signal.symbol)
    if not pair:
        log(f"الزوج غير موجود: {signal.symbol}/USDT"); return False
    if pair in state.open_positions:
        log(f"مركز مفتوح بالفعل: {pair}"); return False

    sl_price = round(signal.buy_price * (1 - SL_PCT / 100), 8)
    entry, qty = signal.buy_price, TRADE_SIZE / signal.buy_price

    if not PAPER_MODE:
        order = spot_buy(exchange, pair, TRADE_SIZE)
        if not order:
            return False
        entry = float(order.get("average", entry))
        qty = float(order.get("filled", qty))

    state.open_positions[pair] = {
        "trade_num": signal.trade_num, "symbol": signal.symbol, "pair": pair,
        "entry": entry, "qty": qty, "sl": sl_price, "tp": signal.sell_price,
        "tp_pct": signal.tp_pct, "opened": time.time(),
        "opened_str": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    state.daily_trades += 1; save_state(state)

    mode = "ورقي" if PAPER_MODE else "حقيقي"
    msg = (f"صفقة جديدة [{mode}]\n#{signal.trade_num} | {pair}\n"
           f"دخول: {entry} | هدف: {signal.sell_price} ({signal.tp_pct}%)\n"
           f"وقف: {sl_price} (-{SL_PCT}%) | كمية: {qty:.6f} | ${TRADE_SIZE:.0f}")
    log(msg); notify(msg); return True

def close_trade(state: State, pair: str, reason: str, price: float, exchange):
    pos = state.open_positions.pop(pair, None)
    if not pos:
        return
    pnl = (price - pos["entry"]) * pos["qty"]
    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100

    if not PAPER_MODE:
        spot_sell(exchange, pair, pos["qty"])

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

async def check_positions(state: State, exchange):
    """فحص المراكز — وقف/هدف/مدة قصوى."""
    rollover_day(state)
    if not state.open_positions:
        return
    for pair in list(state.open_positions):
        pos = state.open_positions.get(pair)
        if not pos:
            continue
        try:
            price = exchange.fetch_ticker(pair)["last"]
        except Exception as e:
            log(f"خطأ في جلب سعر {pair}: {e}"); continue
        if price <= pos["sl"]:
            close_trade(state, pair, "وقف خسارة", price, exchange)
        elif price >= pos["tp"]:
            close_trade(state, pair, "هدف ربح", price, exchange)
        elif (time.time() - pos["opened"]) / 86400 >= MAX_HOLD_DAYS:
            close_trade(state, pair, f"مدة قصوى ({MAX_HOLD_DAYS} يوم)", price, exchange)

# ---------- check mode ----------
def run_check():
    log("=== وضع الفحص ===")
    log(f"TG_API_ID: {'OK' if TG_API_ID else 'مفقود'} | TG_API_HASH: {'OK' if TG_API_HASH else 'مفقود'}")
    log(f"القناة: {TG_CHANNEL}")
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

    test_msg = "رقم الصفقة: (5)\nالعملة: PEPE\nالمنصة: بايبت\nسعر الشراء: 0.00001350\nسعر البيع: 0.00001620 (20%)"
    sig = parse_signal(test_msg)
    if sig:
        log(f"اختبار: {sig.symbol} شراء={sig.buy_price} بيع={sig.sell_price} ({sig.tp_pct}%)")
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
    log(f"القناة: {TG_CHANNEL} | رأس المال: ${CAPITAL} | حجم: ${TRADE_SIZE}")
    notify(f"بدء البوت الشهري [{mode}]\nالقناة: {TG_CHANNEL}")

    state = load_state(); rollover_day(state)

    exchange = get_exchange() if not PAPER_MODE else None
    if exchange:
        exchange.load_markets(); log(f"Bybit متصل | testnet={BYBIT_TESTNET}")

    paper_ex = None
    if PAPER_MODE:
        try:
            paper_ex = get_exchange(); paper_ex.load_markets()
        except Exception:
            log("تحذير: لا يمكن تحميل الأسواق للتحقق")
    active_ex = exchange or paper_ex

    client = TelegramClient(TG_SESSION, TG_API_ID, TG_API_HASH)

    @client.on(events.NewMessage(chats=TG_CHANNEL))
    async def on_signal(event):
        text = event.raw_text
        if not text:
            return
        log(f"رسالة جديدة: {text[:80]}...")
        signal = parse_signal(text)
        if not signal:
            log("لم يتم التعرف على التوصية"); return
        log(f"توصية: #{signal.trade_num} {signal.symbol} شراء={signal.buy_price} بيع={signal.sell_price} ({signal.tp_pct}%)")
        notify(f"توصية جديدة #{signal.trade_num}\nالعملة: {signal.symbol}\n"
               f"شراء: {signal.buy_price}\nبيع: {signal.sell_price} ({signal.tp_pct}%)")
        if active_ex:
            open_trade(state, signal, active_ex)
        else:
            log("لا يوجد اتصال بالمنصة — تخطي")

    async def position_checker():
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            try:
                if active_ex and state.open_positions:
                    await check_positions(state, active_ex)
            except Exception as e:
                log(f"خطأ في فحص المراكز: {e}")

    await client.start()
    log("تيلجرام متصل — في انتظار التوصيات...")
    asyncio.create_task(position_checker())
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
