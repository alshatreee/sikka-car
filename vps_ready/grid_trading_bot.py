"""
grid_trading_bot.py — بوت تداول الشبكة (Grid) على Bybit Spot
=============================================================
يضع شبكة أوامر شراء وبيع ضمن نطاق سعري. يربح من تذبذب السوق الجانبي.
شراء من الأسفل، بيع من الأعلى، تكراراً داخل النطاق.

    python3 grid_trading_bot.py              # ورقي (افتراضي)
    python3 grid_trading_bot.py --live       # تداول حقيقي
    python3 grid_trading_bot.py --check      # فحص الاتصال
    python3 grid_trading_bot.py --grid       # عرض مستويات الشبكة

    pip install ccxt python-dotenv requests
"""
from __future__ import annotations
import json, os, sys, time, requests
from dataclasses import dataclass, field, asdict
from pathlib import Path
from dotenv import load_dotenv

# ── المسارات ──
BASE_DIR = Path(r"C:\Users\xman9\Desktop") if os.name == "nt" else Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE   = BASE_DIR / ".env_naif"
STATE_FILE = BASE_DIR / "grid_state.json"
LOG_FILE   = BASE_DIR / "grid.log"
load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# ── الإعدادات ──
BYBIT_KEY     = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET  = os.getenv("BYBIT_API_SECRET", "")
BYBIT_TESTNET = os.getenv("BYBIT_TESTNET", "true").lower() == "true"
NOTIFY_TOKEN  = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT   = os.getenv("TELEGRAM_CHAT_ID", "")
ASSET         = os.getenv("GRID_ASSET", "ETH/USDT")
NUM_LEVELS    = int(os.getenv("GRID_LEVELS", "15"))
GRID_SIZE     = float(os.getenv("GRID_SIZE", "5"))
GRID_LOW_ENV  = os.getenv("GRID_LOW", "")
GRID_HIGH_ENV = os.getenv("GRID_HIGH", "")
EMERGENCY_PCT = float(os.getenv("GRID_EMERGENCY_PCT", "5.0"))
MAX_DAILY_TRADES = 50
DAILY_LOSS_LIMIT = 15.0
CHECK_INTERVAL   = 30
PAPER = "--live" not in sys.argv

# ── التسجيل والإشعارات ──
def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def notify(msg: str):
    if not NOTIFY_TOKEN or not NOTIFY_CHAT:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{NOTIFY_TOKEN}/sendMessage",
                      json={"chat_id": NOTIFY_CHAT, "text": msg, "parse_mode": "HTML"},
                      timeout=10)
    except Exception as e:
        log(f"خطأ إشعار: {e}")

# ── الحالة ──
@dataclass
class GridLevel:
    idx: int; price: float; side: str; filled: bool = False  # side: buy|sell|empty

@dataclass
class State:
    day: str = ""; daily_trades: int = 0; daily_pnl: float = 0.0; halted: bool = False
    grid_low: float = 0.0; grid_high: float = 0.0; spacing: float = 0.0
    levels: list[dict] = field(default_factory=list)
    completed: list[dict] = field(default_factory=list)
    total_profit: float = 0.0

def load_state() -> State:
    if STATE_FILE.exists():
        try:
            return State(**json.loads(STATE_FILE.read_text()))
        except Exception:
            pass
    return State()

def save_state(s: State):
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2, ensure_ascii=False))

# ── إنشاء البورصة ──
def make_exchange():
    import ccxt
    ex = ccxt.bybit({"apiKey": BYBIT_KEY, "secret": BYBIT_SECRET,
                      "sandbox": BYBIT_TESTNET, "options": {"defaultType": "spot"}})
    ex.load_markets()
    return ex

# ── جلب السعر (ورقي) ──
def paper_price() -> float:
    sym = ASSET.replace("/", "")
    r = requests.get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={sym}",
                     timeout=10)
    return float(r.json()["result"]["list"][0]["lastPrice"])

# ── حساب النطاق التلقائي ──
def auto_range(ex) -> tuple[float, float]:
    if GRID_LOW_ENV and GRID_HIGH_ENV:
        log("⚙️ نطاق يدوي من الإعدادات")
        return float(GRID_LOW_ENV), float(GRID_HIGH_ENV)
    ohlcv = ex.fetch_ohlcv(ASSET, "1d", limit=30) if ex else _paper_ohlcv()
    highs = [c[2] for c in ohlcv]
    lows  = [c[3] for c in ohlcv]
    h, l  = max(highs), min(lows)
    buf   = (h - l) * 0.05
    log(f"📊 نطاق 30 يوم: {l:.2f} - {h:.2f} | بفر 5%: {l - buf:.2f} - {h + buf:.2f}")
    return round(l - buf, 2), round(h + buf, 2)

def _paper_ohlcv() -> list:
    sym = ASSET.replace("/", "")
    r = requests.get(f"https://api.bybit.com/v5/market/kline?category=spot&symbol={sym}"
                     f"&interval=D&limit=30", timeout=10)
    rows = r.json()["result"]["list"]
    return [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])]
            for c in rows]

# ── بناء الشبكة ──
def build_grid(low: float, high: float, current: float) -> list[dict]:
    spacing = (high - low) / NUM_LEVELS
    levels = []
    for i in range(NUM_LEVELS + 1):
        price = round(low + i * spacing, 2)
        side = "buy" if price < current else ("sell" if price > current else "empty")
        levels.append(asdict(GridLevel(idx=i, price=price, side=side)))
    return levels

# ── تنفيذ أمر (حقيقي) ──
def place_order(ex, side: str, price: float) -> dict | None:
    try:
        amt = round(GRID_SIZE / price, 6)
        order = ex.create_limit_order(ASSET, side, amt, price)
        log(f"✅ أمر {side} عند {price:.2f} | الكمية: {amt}")
        return order
    except Exception as e:
        log(f"❌ فشل أمر {side} عند {price}: {e}")
        return None

# ── يوم جديد ──
def reset_day(st: State):
    today = time.strftime("%Y-%m-%d")
    if st.day != today:
        if st.day:
            summary = (f"📋 <b>ملخص يومي — Grid</b>\n"
                       f"الصفقات: {st.daily_trades}\n"
                       f"الربح: ${st.daily_pnl:.2f}\n"
                       f"الإجمالي: ${st.total_profit:.2f}")
            notify(summary)
            log(f"ملخص {st.day}: صفقات={st.daily_trades} ربح=${st.daily_pnl:.2f}")
        st.day = today; st.daily_trades = 0; st.daily_pnl = 0.0; st.halted = False

# ── فحص الاتصال ──
def check_mode():
    log("── وضع الفحص ──")
    try:
        p = paper_price()
        log(f"سعر {ASSET}: ${p:.2f}")
    except Exception as e:
        log(f"خطأ في جلب السعر: {e}"); return
    if not PAPER and BYBIT_KEY:
        try:
            ex = make_exchange()
            bal = ex.fetch_balance()
            usdt = bal.get("USDT", {}).get("free", 0)
            log(f"رصيد USDT: ${usdt:.2f}")
        except Exception as e:
            log(f"خطأ اتصال البورصة: {e}")
    log(f"الوضع: {'ورقي 📄' if PAPER else 'حقيقي 🔴'}")
    log(f"الأصل: {ASSET} | مستويات: {NUM_LEVELS} | حجم: ${GRID_SIZE}")
    log(f"رأس المال المطلوب: ${NUM_LEVELS * GRID_SIZE:.0f}")
    log("✅ الفحص تم")

# ── عرض الشبكة ──
def show_grid():
    log("── مستويات الشبكة ──")
    try:
        price = paper_price()
    except Exception as e:
        log(f"خطأ: {e}"); return
    ex = None
    if not PAPER and BYBIT_KEY:
        try:
            ex = make_exchange()
        except Exception:
            pass
    low, high = auto_range(ex)
    spacing = (high - low) / NUM_LEVELS
    log(f"النطاق: ${low:.2f} - ${high:.2f} | الفاصل: ${spacing:.2f}")
    log(f"السعر الحالي: ${price:.2f}\n")
    for i in range(NUM_LEVELS, -1, -1):
        p = round(low + i * spacing, 2)
        marker = " ◄ سعر حالي" if abs(p - price) < spacing / 2 else ""
        side = "بيع 🔴" if p > price else ("شراء 🟢" if p < price else "محايد ⚪")
        log(f"  L{i:02d}  ${p:>10.2f}  {side}{marker}")
    log(f"\nالطوارئ عند: ${low * (1 - EMERGENCY_PCT / 100):.2f} (-{EMERGENCY_PCT}%)")

# ── الحلقة الرئيسية ──
def run():
    log(f"🚀 بدء Grid Bot | {'ورقي' if PAPER else 'حقيقي'} | {ASSET}")
    ex = None
    if not PAPER:
        try:
            ex = make_exchange()
            log("✅ اتصال Bybit Spot")
        except Exception as e:
            log(f"❌ فشل اتصال البورصة: {e}"); return

    # حساب النطاق
    try:
        price = paper_price() if PAPER else float(ex.fetch_ticker(ASSET)["last"])
    except Exception as e:
        log(f"❌ فشل جلب السعر: {e}"); return
    low, high = auto_range(ex)
    spacing = round((high - low) / NUM_LEVELS, 2)
    emergency_price = round(low * (1 - EMERGENCY_PCT / 100), 2)

    # تهيئة الحالة
    st = load_state()
    reset_day(st)
    st.grid_low = low; st.grid_high = high; st.spacing = spacing
    st.levels = build_grid(low, high, price)
    save_state(st)

    capital = NUM_LEVELS * GRID_SIZE
    init_msg = (f"🔧 <b>Grid Bot — تشغيل</b>\n"
                f"الأصل: {ASSET}\nالنطاق: ${low:.2f} - ${high:.2f}\n"
                f"المستويات: {NUM_LEVELS} | الفاصل: ${spacing:.2f}\n"
                f"الحجم/مستوى: ${GRID_SIZE} | الإجمالي: ${capital:.0f}\n"
                f"الطوارئ: ${emergency_price:.2f}\n"
                f"الوضع: {'ورقي 📄' if PAPER else 'حقيقي 🔴'}")
    log(init_msg.replace("<b>", "").replace("</b>", ""))
    notify(init_msg)

    # وضع الأوامر الأولية (حقيقي)
    if not PAPER and ex:
        for lv in st.levels:
            if lv["side"] in ("buy", "sell"):
                place_order(ex, lv["side"], lv["price"])

    # حلقة المراقبة
    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            reset_day(st)
            if st.halted:
                continue

            # جلب السعر
            try:
                price = paper_price() if PAPER else float(ex.fetch_ticker(ASSET)["last"])
            except Exception as e:
                log(f"خطأ سعر: {e}"); continue

            # فحص الطوارئ
            if price <= emergency_price:
                log(f"🚨 طوارئ! السعر ${price:.2f} تحت ${emergency_price:.2f}")
                notify(f"🚨 <b>طوارئ Grid!</b>\nالسعر ${price:.2f} كسر النطاق.\nإيقاف جميع الأوامر.")
                if not PAPER and ex:
                    try:
                        ex.cancel_all_orders(ASSET)
                        log("تم إلغاء جميع الأوامر")
                    except Exception as e:
                        log(f"خطأ إلغاء: {e}")
                st.halted = True; save_state(st); continue

            # حدود يومية
            if st.daily_trades >= MAX_DAILY_TRADES:
                log("⚠️ وصلنا حد الصفقات اليومي"); continue
            if st.daily_pnl <= -DAILY_LOSS_LIMIT:
                log("⚠️ وصلنا حد الخسارة اليومي"); st.halted = True; save_state(st); continue

            # فحص المستويات
            for lv in st.levels:
                if lv["filled"]:
                    continue
                lp = lv["price"]

                # ورقي: محاكاة التعبئة
                if PAPER:
                    if lv["side"] == "buy" and price <= lp:
                        lv["filled"] = True
                        log(f"📗 شراء ورقي L{lv['idx']} عند ${lp:.2f} (السعر: ${price:.2f})")
                        # ضع أمر بيع فوق
                        sell_idx = lv["idx"] + 1
                        if sell_idx <= NUM_LEVELS:
                            for sv in st.levels:
                                if sv["idx"] == sell_idx and sv["side"] != "sell":
                                    sv["side"] = "sell"; sv["filled"] = False
                                    log(f"  ← أمر بيع جديد L{sell_idx} عند ${sv['price']:.2f}")
                                    break

                    elif lv["side"] == "sell" and price >= lp:
                        lv["filled"] = True
                        # حساب الربح
                        buy_price = lp - spacing
                        profit = round(GRID_SIZE * spacing / buy_price, 4)
                        st.daily_pnl += profit; st.total_profit += profit
                        st.daily_trades += 1
                        trade = {"buy": round(buy_price, 2), "sell": lp,
                                 "profit": profit, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
                        st.completed.append(trade)
                        log(f"📕 بيع ورقي L{lv['idx']} عند ${lp:.2f} | ربح: ${profit:.4f}")
                        notify(f"💰 دورة Grid\nشراء: ${buy_price:.2f} → بيع: ${lp:.2f}\n"
                               f"ربح: ${profit:.4f}\nإجمالي: ${st.total_profit:.2f}")
                        # ضع أمر شراء تحت
                        buy_idx = lv["idx"] - 1
                        if buy_idx >= 0:
                            for bv in st.levels:
                                if bv["idx"] == buy_idx and bv["side"] != "buy":
                                    bv["side"] = "buy"; bv["filled"] = False
                                    log(f"  ← أمر شراء جديد L{buy_idx} عند ${bv['price']:.2f}")
                                    break

                # حقيقي: نراقب ونعيد الأوامر
                elif not PAPER and ex:
                    if lv["side"] == "buy" and price <= lp:
                        lv["filled"] = True
                        sell_price = round(lp + spacing, 2)
                        place_order(ex, "sell", sell_price)
                        sell_idx = lv["idx"] + 1
                        for sv in st.levels:
                            if sv["idx"] == sell_idx:
                                sv["side"] = "sell"; sv["filled"] = False; break
                        log(f"📗 شراء حقيقي L{lv['idx']} → بيع عند ${sell_price:.2f}")

                    elif lv["side"] == "sell" and price >= lp:
                        lv["filled"] = True
                        buy_price_real = round(lp - spacing, 2)
                        profit = round(GRID_SIZE * spacing / buy_price_real, 4)
                        st.daily_pnl += profit; st.total_profit += profit
                        st.daily_trades += 1
                        st.completed.append({"buy": buy_price_real, "sell": lp,
                                             "profit": profit,
                                             "time": time.strftime("%Y-%m-%d %H:%M:%S")})
                        place_order(ex, "buy", buy_price_real)
                        buy_idx = lv["idx"] - 1
                        for bv in st.levels:
                            if bv["idx"] == buy_idx:
                                bv["side"] = "buy"; bv["filled"] = False; break
                        log(f"📕 بيع حقيقي L{lv['idx']} | ربح: ${profit:.4f}")
                        notify(f"💰 دورة Grid\nشراء: ${buy_price_real:.2f} → بيع: ${lp:.2f}\n"
                               f"ربح: ${profit:.4f}")

            save_state(st)

        except KeyboardInterrupt:
            log("⏹ إيقاف يدوي")
            notify(f"⏹ Grid Bot توقف\nإجمالي الربح: ${st.total_profit:.2f}")
            save_state(st); break
        except Exception as e:
            log(f"خطأ عام: {e}")
            time.sleep(10)

# ── نقطة الدخول ──
if __name__ == "__main__":
    if "--check" in sys.argv:
        check_mode()
    elif "--grid" in sys.argv:
        show_grid()
    else:
        run()
