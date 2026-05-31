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
NOTIFY_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

CAPITAL      = float(os.getenv("MONTHLY_CAPITAL", "1000"))
TRADE_PCT    = float(os.getenv("MONTHLY_TRADE_PCT", "10"))
TRADE_SIZE   = CAPITAL * TRADE_PCT / 100
SL_PCT       = float(os.getenv("MONTHLY_SL_PCT", "5.0"))
MAX_HOLD_DAYS = int(os.getenv("MONTHLY_MAX_HOLD_DAYS", "30"))
MAX_DAILY_TRADES = 10
MAX_OPEN = 10
MAX_DAILY_LOSS_PCT = float(os.getenv("MONTHLY_MAX_LOSS_PCT", "5.0"))
MAX_DAILY_LOSS = CAPITAL * MAX_DAILY_LOSS_PCT / 100
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

def place_stop_loss(exchange, pair: str, qty: float, trigger_price: float) -> str | None:
    try:
        order = exchange.create_order(pair, 'market', 'sell', qty, None, {
            'triggerPrice': str(trigger_price),
        })
        oid = order.get('id', '')
        log(f"أمر وقف خسارة: {pair} @ {trigger_price} | أمر={oid}")
        return oid
    except Exception as e:
        log(f"خطأ وقف الخسارة: {pair} — {e}")
        return None

def cancel_sl_order(exchange, pair: str, order_id: str):
    try:
        exchange.cancel_order(order_id, pair)
        log(f"إلغاء وقف خسارة: {pair} | أمر={order_id}")
    except Exception as e:
        log(f"خطأ إلغاء الأمر: {pair} — {e}")

# ---------- trade logic ----------
def open_trade(state: State, signal: Signal, exchange, reason: str = "توصية جديدة") -> bool:
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

    sl_order_id = None
    if not PAPER_MODE:
        sl_order_id = place_stop_loss(exchange, pair, qty, sl_price)

    state.open_positions[pair] = {
        "trade_num": signal.trade_num, "symbol": signal.symbol, "pair": pair,
        "entry": entry, "qty": qty, "sl": sl_price, "tp": signal.sell_price,
        "tp_pct": signal.tp_pct, "opened": time.time(),
        "opened_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason, "sl_order_id": sl_order_id,
    }
    state.daily_trades += 1; save_state(state)

    mode = "ورقي" if PAPER_MODE else "حقيقي"
    sl_info = "أمر منصة" if sl_order_id else "فحص دوري"
    msg = (f"صفقة [{mode}] — {reason}\n#{signal.trade_num} | {pair}\n"
           f"دخول: {entry} | هدف: {signal.sell_price} ({signal.tp_pct}%)\n"
           f"وقف: {sl_price} (-{SL_PCT}%) [{sl_info}] | ${TRADE_SIZE:.0f}")
    log(msg); notify(msg); return True

def close_trade(state: State, pair: str, reason: str, price: float, exchange, skip_sell: bool = False):
    pos = state.open_positions.pop(pair, None)
    if not pos:
        return
    pnl = (price - pos["entry"]) * pos["qty"]
    pnl_pct = (price - pos["entry"]) / pos["entry"] * 100

    if not PAPER_MODE:
        sl_oid = pos.get("sl_order_id")
        if sl_oid and not skip_sell:
            cancel_sl_order(exchange, pair, sl_oid)
        if not skip_sell:
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

        sl_oid = pos.get("sl_order_id")
        if sl_oid and not PAPER_MODE:
            try:
                sl_order = exchange.fetch_order(sl_oid, pair)
                if sl_order.get('status') in ('closed', 'filled'):
                    fill_price = float(sl_order.get('average', 0)) or price
                    close_trade(state, pair, "وقف خسارة", fill_price, exchange, skip_sell=True)
                    continue
            except Exception as e:
                log(f"فحص أمر SL {pair}: {e}")

        if PAPER_MODE and price <= pos["sl"]:
            close_trade(state, pair, "وقف خسارة", price, exchange)
        elif price >= pos["tp"]:
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
    log(f"مسح التاريخ: {total_signals} توصية، {total_reinf} سعر تعزيز")
    if state.reinforcements:
        for sym, entries in state.reinforcements.items():
            prices = [e["price"] for e in entries]
            log(f"  {sym}: تعزيزات {prices}")

async def check_reinforcements(state: State, exchange):
    """يفحص هل السعر الحالي قريب من سعر تعزيز → يشتري."""
    if not state.reinforcements:
        return
    rollover_day(state)
    if state.halted:
        return

    for symbol, entries in list(state.reinforcements.items()):
        if not entries:
            continue
        pair = verify_symbol(exchange, symbol)
        if not pair:
            continue
        if pair in state.open_positions:
            continue
        try:
            price = exchange.fetch_ticker(pair)["last"]
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
                log(f"💡 تعزيز! {symbol} @ ${price} قريب من ${reinf_price} (فرق {diff_pct:.1f}%)")
                if open_trade(state, sig, exchange, reason=f"تعزيز @ {reinf_price}"):
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
        notify(f"توصية جديدة #{signal.trade_num}\nالعملة: {signal.symbol}\n"
               f"شراء: {signal.buy_price}\nبيع: {signal.sell_price} ({signal.tp_pct}%)")
        if active_ex:
            open_trade(state, signal, active_ex, reason="توصية جديدة")
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

    async def reinforcement_checker():
        while True:
            await asyncio.sleep(REINFORCE_CHECK_SEC)
            try:
                if active_ex and state.reinforcements:
                    await check_reinforcements(state, active_ex)
            except Exception as e:
                log(f"خطأ في فحص التعزيزات: {e}")

    asyncio.create_task(position_checker())
    asyncio.create_task(reinforcement_checker())
    log(f"Listening... (cap=${CAPITAL}, size={TRADE_PCT}%, SL={SL_PCT}%)")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
