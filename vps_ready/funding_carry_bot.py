"""
funding_carry_bot.py — Funding Rate Carry Bot (Bybit)
شراء Spot + بيع Futures (perpetual) — تحصيل Funding كل 8h — دلتا محايدة

الاستخدام:
    python funding_carry_bot.py              # محاكاة (افتراضي)
    python funding_carry_bot.py --live       # تداول حقيقي
    python funding_carry_bot.py --check      # عرض الحالة
    python funding_carry_bot.py --rates      # عرض معدلات التمويل الحالية
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time, urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# ── المسارات ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots"); BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE   = BASE_DIR / ".env_naif"
STATE_FILE = BASE_DIR / "funding_carry_state.json"
LOG_FILE   = BASE_DIR / "funding_carry.log"

# ── تحميل البيئة ──
def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); env[k.strip()] = v.strip()
    return env

ENV = load_env()
BYBIT_KEY      = ENV.get("BYBIT_API_KEY", "")
BYBIT_SECRET   = ENV.get("BYBIT_API_SECRET", "")
BYBIT_TESTNET  = ENV.get("BYBIT_TESTNET", "true").lower() == "true"
TG_TOKEN       = ENV.get("TELEGRAM_TOKEN", "")
TG_CHAT        = ENV.get("TELEGRAM_CHAT_ID", "")
ASSETS         = [a.strip() for a in ENV.get("CARRY_ASSETS", "BTC/USDT,ETH/USDT,SOL/USDT").split(",")]
POSITION_SIZE  = float(ENV.get("CARRY_SIZE", "50"))
LEVERAGE       = int(ENV.get("CARRY_LEVERAGE", "3"))
MIN_RATE       = float(ENV.get("CARRY_MIN_RATE", "0.01")) / 100  # 0.01% → 0.0001
MAX_POSITIONS  = int(ENV.get("CARRY_MAX_POSITIONS", "3"))
MAX_HOLD_DAYS  = int(ENV.get("CARRY_MAX_HOLD_DAYS", "7"))
DAILY_LOSS_LIM = 5.0
CHECK_SEC      = 1800  # 30 دقيقة
NEG_PERIODS    = 3     # 3 فترات سلبية متتالية للإغلاق
REBALANCE_THR  = 0.02  # 2% فرق بين الجانبين
BASIS_RISK_THR = 0.005 # 0.5% فرق بين spot و futures

# ── تسجيل الأحداث ──
logger = logging.getLogger("funding_carry"); logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception: pass

# ── تيليجرام ──
def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                                    data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception: pass

# ── الحالة ──
@dataclass
class Position:
    symbol: str; spot_entry: float; futures_entry: float; size_usd: float
    open_time: str; funding_collected: float = 0.0
    neg_funding_count: int = 0; funding_payments: int = 0

@dataclass
class BotState:
    positions: list = field(default_factory=list)
    daily_pnl: float = 0.0; total_pnl: float = 0.0
    total_funding: float = 0.0; day: str = ""
    halted: bool = False; closed_count: int = 0

def load_state() -> BotState:
    if STATE_FILE.exists():
        try: return BotState(**json.loads(STATE_FILE.read_text()))
        except Exception: pass
    return BotState()

def save_state(st: BotState):
    STATE_FILE.write_text(json.dumps(asdict(st), indent=2, default=str))

# ── Bybit عبر ccxt ──
def _bybit_exchange(default_type: str):
    import ccxt
    cfg = {"apiKey": BYBIT_KEY, "secret": BYBIT_SECRET, "enableRateLimit": True,
           "options": {"defaultType": default_type}}
    ex = ccxt.bybit(cfg)
    if BYBIT_TESTNET: ex.set_sandbox_mode(True)
    return ex

def get_spot_exchange(): return _bybit_exchange("spot")
def get_futures_exchange(): return _bybit_exchange("linear")

def _bybit_get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "carry-bot/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def fetch_price(symbol: str) -> float:
    sym = symbol.replace("/", "")
    try:
        data = _bybit_get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={sym}")
        return float(data["result"]["list"][0]["lastPrice"])
    except Exception as e:
        logger.warning(f"خطأ جلب سعر {symbol}: {e}"); return 0.0

def fetch_funding_rate(symbol: str) -> float | None:
    sym = symbol.replace("/", "")
    try:
        data = _bybit_get(f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={sym}")
        return float(data["result"]["list"][0]["fundingRate"])
    except Exception as e:
        logger.warning(f"خطأ جلب funding {symbol}: {e}"); return None

def fetch_funding_history(symbol: str, limit: int = 24) -> list[float]:
    sym = symbol.replace("/", "")
    try:
        data = _bybit_get(f"https://api.bybit.com/v5/market/funding/history?category=linear&symbol={sym}&limit={limit}")
        return [float(h["fundingRate"]) for h in data["result"]["list"]]
    except Exception as e:
        logger.warning(f"خطأ جلب تاريخ funding {symbol}: {e}"); return []

# ── فتح مركز carry ──
def open_carry(symbol: str, rate: float, st: BotState, live: bool) -> bool:
    if any(p["symbol"] == symbol for p in st.positions): return False
    if len(st.positions) >= MAX_POSITIONS or st.halted: return False

    spot_price = fetch_price(symbol)
    if spot_price <= 0: return False
    qty = POSITION_SIZE / spot_price; lbl = "LIVE" if live else "PAPER"
    if live:
        try:
            spot_ex = get_spot_exchange()
            fut_ex = get_futures_exchange()
            try: fut_ex.set_leverage(LEVERAGE, symbol)
            except Exception as e: logger.warning(f"تعيين رافعة: {e}")
            # شراء spot
            spot_order = spot_ex.create_order(symbol, "market", "buy", qty)
            # بيع futures
            fut_order = fut_ex.create_order(symbol, "market", "sell", qty)
            logger.info(f"أوامر حقيقية: spot={spot_order.get('id','?')} fut={fut_order.get('id','?')}")
        except Exception as e:
            logger.error(f"فشل فتح مركز {symbol}: {e}")
            tg(f"❌ فشل فتح carry {symbol}: {e}"); return False

    fut_price = fetch_price(symbol)  # سعر futures تقريبي
    pos = asdict(Position(symbol=symbol, spot_entry=spot_price, futures_entry=fut_price or spot_price,
                          size_usd=POSITION_SIZE, open_time=datetime.now(timezone.utc).isoformat()))
    st.positions.append(pos)

    daily_rate = rate * 3 * 100  # 3 دفعات يومياً
    est_daily = POSITION_SIZE * rate * 3
    msg = (f"{'✅' if live else '📋'} [{lbl}] مركز carry جديد\n"
           f"الأصل: {symbol}\n"
           f"معدل التمويل: {rate*100:.4f}% / 8h ({daily_rate:.3f}% يومياً)\n"
           f"الحجم: ${POSITION_SIZE:.0f} لكل جانب\n"
           f"الربح المتوقع: ~${est_daily:.3f}/يوم")
    logger.info(msg.replace("\n", " | ")); tg(msg)
    return True

# ── إغلاق مركز carry ──
def close_carry(pos: dict, reason: str, st: BotState, live: bool) -> float:
    symbol = pos["symbol"]
    spot_now = fetch_price(symbol)
    if spot_now <= 0: spot_now = pos["spot_entry"]
    spot_pnl = (spot_now - pos["spot_entry"]) / pos["spot_entry"] * pos["size_usd"]
    fut_pnl = (pos["futures_entry"] - spot_now) / pos["futures_entry"] * pos["size_usd"]
    price_pnl = spot_pnl + fut_pnl
    total_pnl = pos["funding_collected"] + price_pnl; lbl = "LIVE" if live else "PAPER"
    if live:
        try:
            spot_ex = get_spot_exchange()
            fut_ex = get_futures_exchange()
            qty = pos["size_usd"] / spot_now
            spot_ex.create_order(symbol, "market", "sell", qty)
            fut_ex.create_order(symbol, "market", "buy", qty)
        except Exception as e:
            logger.error(f"خطأ إغلاق {symbol}: {e}")

    msg = (f"🔒 [{lbl}] إغلاق carry\n"
           f"الأصل: {symbol} | السبب: {reason}\n"
           f"تمويل محصّل: ${pos['funding_collected']:.4f}\n"
           f"فرق السعر: ${price_pnl:+.4f}\n"
           f"إجمالي PnL: ${total_pnl:+.4f}")
    logger.info(msg.replace("\n", " | ")); tg(msg)

    st.daily_pnl += total_pnl; st.total_pnl += total_pnl; st.closed_count += 1
    return total_pnl

# ── محاكاة دفعة تمويل ──
def simulate_funding(pos: dict) -> float:
    """محاكاة تحصيل funding بناءً على المعدل الحقيقي"""
    rate = fetch_funding_rate(pos["symbol"])
    if rate is None: return 0.0
    # من يحمل Short يحصّل funding عندما يكون موجباً
    payment = pos["size_usd"] * rate if rate > 0 else -pos["size_usd"] * abs(rate)
    pos["funding_collected"] += payment
    pos["funding_payments"] += 1
    if rate < 0:
        pos["neg_funding_count"] += 1
    else:
        pos["neg_funding_count"] = 0
    return payment

# ── إدارة المراكز ──
def manage_positions(st: BotState, live: bool):
    if not st.positions: return
    now = datetime.now(timezone.utc); keep = []
    for pos in st.positions:
        symbol = pos["symbol"]
        # محاكاة/تحصيل funding
        payment = simulate_funding(pos)
        st.total_funding += max(payment, 0)
        if payment != 0:
            logger.info(f"💰 funding {symbol}: ${payment:+.4f} (إجمالي: ${pos['funding_collected']:.4f})")

        # حساب مدة الاحتفاظ
        try:
            open_dt = datetime.fromisoformat(pos["open_time"])
            if open_dt.tzinfo is None: open_dt = open_dt.replace(tzinfo=timezone.utc)
            hold_days = (now - open_dt).total_seconds() / 86400
        except Exception: hold_days = 0

        # فحص basis risk
        spot_now = fetch_price(symbol)
        if spot_now > 0 and pos["spot_entry"] > 0:
            basis = abs(spot_now - pos["futures_entry"]) / pos["spot_entry"]
        else:
            basis = 0

        # فحص rebalance
        if spot_now > 0:
            spot_val = pos["size_usd"] * (spot_now / pos["spot_entry"])
            fut_val = pos["size_usd"] * (pos["futures_entry"] / spot_now)
            if spot_val > 0 and fut_val > 0:
                divergence = abs(spot_val - fut_val) / max(spot_val, fut_val)
                if divergence > REBALANCE_THR:
                    logger.info(f"⚖️ إعادة توازن {symbol}: فرق {divergence*100:.1f}%")

        # شروط الإغلاق
        reason = None
        if pos["neg_funding_count"] >= NEG_PERIODS:
            reason = f"funding سلبي {pos['neg_funding_count']} فترات متتالية"
        elif basis > BASIS_RISK_THR:
            reason = f"مخاطر basis ({basis*100:.2f}% > {BASIS_RISK_THR*100:.1f}%)"
        elif st.daily_pnl <= -DAILY_LOSS_LIM:
            reason = f"حد الخسارة اليومي (${st.daily_pnl:.2f})"
            st.halted = True
        elif hold_days >= MAX_HOLD_DAYS:
            # إعادة تقييم: أغلق فقط إذا المعدل منخفض
            cur_rate = fetch_funding_rate(symbol)
            if cur_rate is not None and cur_rate < MIN_RATE:
                reason = f"أقصى مدة ({hold_days:.1f} يوم) + معدل منخفض"
            else:
                logger.info(f"🔄 {symbol}: {hold_days:.1f} يوم لكن المعدل لا يزال جيداً — استمرار")

        if reason:
            close_carry(pos, reason, st, live)
        else:
            keep.append(pos)
    st.positions = keep

# ── ملخص يومي ──
def daily_summary(st: BotState):
    msg = (f"📊 ملخص يومي — Funding Carry\n"
           f"مراكز مفتوحة: {len(st.positions)}/{MAX_POSITIONS}\n"
           f"PnL اليوم: ${st.daily_pnl:+.4f}\n"
           f"إجمالي PnL: ${st.total_pnl:+.4f}\n"
           f"إجمالي funding محصّل: ${st.total_funding:.4f}\n"
           f"صفقات مغلقة: {st.closed_count}")
    for p in st.positions:
        msg += f"\n  {p['symbol']}: funding=${p['funding_collected']:.4f} ({p['funding_payments']} دفعة)"
    logger.info(msg.replace("\n", " | ")); tg(msg)

# ── عرض المعدلات ──
def cmd_rates():
    logger.info("📈 معدلات التمويل الحالية:")
    print(f"\n{'='*55}\n  معدلات التمويل — Bybit Perpetual\n{'='*55}")
    for symbol in ASSETS:
        rate = fetch_funding_rate(symbol)
        if rate is not None:
            daily = rate * 3 * 100
            annual = daily * 365
            hist = fetch_funding_history(symbol, 9)  # آخر 3 أيام
            avg = sum(hist) / len(hist) * 100 if hist else 0
            status = "✅" if rate >= MIN_RATE else "⚠️"
            est = POSITION_SIZE * rate * 3
            print(f"  {status} {symbol:12s} | حالي: {rate*100:+.4f}% | يومي: {daily:+.3f}% | سنوي: {annual:+.1f}%")
            print(f"     متوسط 3 أيام: {avg:+.4f}% | ربح يومي تقديري: ${est:.3f}")
        else:
            print(f"  ❌ {symbol:12s} | فشل الجلب")
    print(f"\n  الحد الأدنى: {MIN_RATE*100:.4f}% / 8h | الحجم: ${POSITION_SIZE:.0f} لكل جانب")
    print(f"{'='*55}")

# ── فحص الحالة ──
def cmd_check():
    st = load_state()
    print(f"\n{'='*55}\n  حالة Funding Carry Bot\n{'='*55}")
    print(f"  اليوم: {st.day} | مراكز: {len(st.positions)}/{MAX_POSITIONS}")
    print(f"  PnL يوم: ${st.daily_pnl:+.4f} | إجمالي: ${st.total_pnl:+.4f}")
    print(f"  funding محصّل: ${st.total_funding:.4f} | متوقف: {st.halted}")
    if st.positions:
        for p in st.positions:
            sp = fetch_price(p["symbol"])
            ppnl = ((sp - p["spot_entry"]) / p["spot_entry"] + (p["futures_entry"] - sp) / p["futures_entry"]) * p["size_usd"] if sp > 0 else 0
            print(f"  {p['symbol']:10s} funding:${p['funding_collected']:.4f} price:${ppnl:+.4f} total:${p['funding_collected']+ppnl:+.4f}")
    else: print("  لا توجد مراكز مفتوحة")
    print(f"{'='*55}")

# ── الدورة الرئيسية ──
def run_cycle(st: BotState, live: bool):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if st.day != today:
        if st.day: daily_summary(st)
        st.day = today; st.daily_pnl = 0.0; st.halted = False

    if st.halted:
        logger.warning("🛑 النظام متوقف — حد الخسارة اليومي"); return

    manage_positions(st, live)

    if len(st.positions) >= MAX_POSITIONS: return

    # البحث عن فرص carry جديدة
    for symbol in ASSETS:
        if len(st.positions) >= MAX_POSITIONS: break
        if any(p["symbol"] == symbol for p in st.positions): continue

        rate = fetch_funding_rate(symbol)
        if rate is None: continue
        if rate < MIN_RATE:
            logger.info(f"⏭ {symbol}: معدل {rate*100:.4f}% < الحد {MIN_RATE*100:.4f}%")
            continue

        # تحقق من الاستقرار: متوسط آخر 3 فترات
        hist = fetch_funding_history(symbol, 3)
        if hist and sum(1 for h in hist if h > 0) < 2:
            logger.info(f"⏭ {symbol}: تاريخ funding غير مستقر")
            continue

        logger.info(f"🎯 فرصة carry: {symbol} @ {rate*100:.4f}%")
        open_carry(symbol, rate, st, live)

def main():
    ap = argparse.ArgumentParser(description="Funding Rate Carry Bot — Bybit")
    ap.add_argument("--live", action="store_true", help="تداول حقيقي")
    ap.add_argument("--check", action="store_true", help="عرض الحالة")
    ap.add_argument("--rates", action="store_true", help="عرض معدلات التمويل")
    args = ap.parse_args()

    if args.rates: cmd_rates(); return
    if args.check: cmd_check(); return

    live = args.live; mode = "LIVE" if live else "PAPER"
    print(f"\n╔══════════════════════════════════════════╗\n"
          f"║  💰 Funding Rate Carry Bot — {mode:6}      ║\n"
          f"║  الأصول: {', '.join(ASSETS):31s} ║\n"
          f"║  الحجم: ${POSITION_SIZE:.0f} | رافعة: {LEVERAGE}x              ║\n"
          f"╚══════════════════════════════════════════╝\n")

    if live and not BYBIT_KEY:
        logger.error("BYBIT_API_KEY غير موجود في .env_naif"); return
    if not live:
        logger.info("وضع المحاكاة — لا تنفيذ حقيقي")

    tg(f"💰 بدء Funding Carry Bot ({mode})\nالأصول: {', '.join(ASSETS)}\nالحجم: ${POSITION_SIZE:.0f}")
    st = load_state(); cycle = 0

    try:
        while True:
            cycle += 1
            logger.info(f"── دورة #{cycle} | مراكز:{len(st.positions)} "
                        f"PnL:${st.daily_pnl:+.4f} funding:${st.total_funding:.4f} ──")
            run_cycle(st, live); save_state(st)
            logger.info(f"الانتظار {CHECK_SEC // 60} دقيقة...")
            time.sleep(CHECK_SEC)
    except KeyboardInterrupt:
        save_state(st); daily_summary(st)
        logger.info("تم الإيقاف")
        tg(f"🛑 إيقاف Funding Carry Bot | PnL:${st.total_pnl:+.4f} | funding:${st.total_funding:.4f}")

if __name__ == "__main__":
    main()
