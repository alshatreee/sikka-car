"""
resolution_sniper_bot.py — Resolution Sniper Bot
يشتري أسواق مسعّرة 0.95-0.99 وتنتهي خلال 6 ساعات (النتيجة شبه محسومة)

الاستخدام:
    python resolution_sniper_bot.py           # محاكاة (افتراضي)
    python resolution_sniper_bot.py --live    # تداول حقيقي
    python resolution_sniper_bot.py --check   # فحص الأسواق فقط
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time, urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

# ── المسارات ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = BASE_DIR / ".env3"
STATE_FILE = BASE_DIR / "sniper_state.json"
LOG_FILE = BASE_DIR / "sniper.log"
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

# ── تحميل .env3 ──
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
PK = ENV.get("PK", "").strip()
if PK.startswith("0x"):
    PK = PK[2:]
FUNDER = ENV.get("FUNDER", "")
TG_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = ENV.get("TELEGRAM_CHAT_ID", "")
PROXY = ENV.get("HTTPS_PROXY", "")
if PROXY:
    os.environ["HTTPS_PROXY"] = PROXY
    os.environ["HTTP_PROXY"] = PROXY

# ── إعداد اللوق ──
logger = logging.getLogger("sniper")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception:
    pass

# ── ثوابت الاستراتيجية ──
MIN_YES_PRICE = 0.95
MAX_YES_PRICE = 0.99
MIN_TIME_MINUTES = 5
MAX_TIME_HOURS = 6
MIN_VOLUME = 1000
TRADE_SIZE_USD = 3.0
MIN_NET_PROFIT = 0.02          # أقل ربح مقبول بعد الرسوم
FEE_RATE = 0.02                # رسوم Polymarket 2%
MAX_TRADES_DAY = 30
MAX_OPEN = 12
DAILY_LOSS_HALT = 5.0
SCAN_INTERVAL = 90

# ── حالة البوت ──
@dataclass
class Position:
    market_id: str
    token_id: str
    question: str
    entry_price: float
    size_usd: float
    expected_profit: float
    entry_time: str
    hours_left: float

@dataclass
class BotState:
    positions: list = field(default_factory=list)
    trades_today: int = 0
    daily_pnl: float = 0.0
    day: str = ""
    halted: bool = False
    total_trades: int = 0
    total_pnl: float = 0.0

def load_state() -> BotState:
    if STATE_FILE.exists():
        try: return BotState(**json.loads(STATE_FILE.read_text()))
        except Exception: pass
    return BotState()

def save_state(s: BotState):
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2, default=str))

# ── أدوات مساعدة ──
def http_get(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sniper-bot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning(f"HTTP خطأ: {url[:60]} — {e}")
        return None

def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def calc_fee(price: float) -> float:
    """رسوم Polymarket: 2% * 2 * min(p, 1-p)."""
    return 2 * min(price, 1 - price) * FEE_RATE

def calc_net_profit(entry_price: float, size_usd: float) -> float:
    """الربح الصافي المتوقع عند الحل = $1.00."""
    contracts = size_usd / entry_price
    gross = contracts * (1.0 - entry_price)
    fee = contracts * calc_fee(entry_price)
    return round(gross - fee, 4)

def _match_token(tokens, side: str) -> str:
    if isinstance(tokens, str):
        try: tokens = json.loads(tokens)
        except Exception: return ""
    for t in (tokens or []):
        outcome = str(t.get("outcome", "")).upper()
        tid = t.get("token_id") or t.get("tokenId") or ""
        if side == "YES" and outcome in ("YES", "1"): return str(tid)
        if side == "NO" and outcome in ("NO", "0"): return str(tid)
    return ""

def get_token_id(market: dict, side: str) -> str:
    result = _match_token(market.get("tokens") or [], side)
    if result: return result
    cid = market.get("conditionId") or market.get("condition_id") or market.get("id", "")
    if cid:
        clob = http_get(f"{CLOB_API}/markets/{cid}")
        if clob:
            result = _match_token(clob.get("tokens") or [], side)
    return result or ""

# ── البحث عن أسواق شبه محسومة ──
def fetch_sniper_targets() -> list[dict]:
    """يجلب أسواق بسعر YES مرتفع (0.95-0.99) وتنتهي قريباً."""
    data = http_get(f"{GAMMA_API}/markets?active=true&closed=false&limit=200&order=endDate&ascending=true")
    if not data: return []
    markets = data if isinstance(data, list) else data.get("markets", [])
    targets = []
    now = datetime.utcnow()

    for m in markets:
        # فلتر: وقت الانتهاء
        end_str = m.get("endDateIso") or m.get("endDate") or ""
        if not end_str:
            continue
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).replace(tzinfo=None)
            time_left = end_dt - now
            minutes_left = time_left.total_seconds() / 60
            hours_left = minutes_left / 60
        except Exception:
            continue
        if minutes_left < MIN_TIME_MINUTES or hours_left > MAX_TIME_HOURS:
            continue

        # فلتر: حجم التداول
        volume = float(m.get("volumeNum") or m.get("volume") or m.get("volume24hr") or 0)
        if volume < MIN_VOLUME:
            continue

        # فلتر: السعر
        outcomes = m.get("outcomePrices") or []
        if isinstance(outcomes, str):
            try: outcomes = json.loads(outcomes)
            except Exception: continue
        if len(outcomes) < 2:
            continue
        yes_p = float(outcomes[0])
        no_p = float(outcomes[1])

        if not (MIN_YES_PRICE <= yes_p <= MAX_YES_PRICE):
            continue

        # حساب الربح المتوقع
        net_profit = calc_net_profit(yes_p, TRADE_SIZE_USD)
        if net_profit < MIN_NET_PROFIT:
            continue

        targets.append({
            "market": m,
            "market_id": m.get("conditionId") or m.get("id", ""),
            "question": m.get("question", ""),
            "yes_price": yes_p,
            "no_price": no_p,
            "volume": volume,
            "hours_left": round(hours_left, 2),
            "minutes_left": round(minutes_left, 1),
            "net_profit": net_profit,
        })
    # رتب بأعلى ربح متوقع
    targets.sort(key=lambda t: t["net_profit"], reverse=True)
    return targets

# ── CLOB client ──
def get_clob_client():
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON
        client = ClobClient(host=CLOB_API, key=PK, chain_id=POLYGON,
                            funder=FUNDER, signature_type=1)
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        return client
    except Exception as e:
        logger.error(f"فشل الاتصال بـ CLOB: {e}")
        return None

# ── تنفيذ الصفقة ──
def execute_snipe(target: dict, state: BotState, client, live: bool) -> bool:
    # تحقق من الحدود
    for p in state.positions:
        if p["market_id"] == target["market_id"]:
            return False
    if len(state.positions) >= MAX_OPEN:
        return False
    if state.trades_today >= MAX_TRADES_DAY:
        return False
    if state.halted:
        return False

    market = target["market"]
    token_id = get_token_id(market, "YES")
    if not token_id:
        logger.warning(f"لم يُعثر على token_id: {target['question'][:50]}")
        return False

    price = round(target["yes_price"], 2)
    contracts = round(TRADE_SIZE_USD / price, 1)

    pos = Position(
        market_id=target["market_id"],
        token_id=token_id,
        question=target["question"][:80],
        entry_price=price,
        size_usd=TRADE_SIZE_USD,
        expected_profit=target["net_profit"],
        entry_time=datetime.utcnow().isoformat(),
        hours_left=target["hours_left"],
    )

    if live and client:
        try:
            from py_clob_client.clob_types import OrderArgs
            from py_clob_client.order_builder.constants import BUY
            order = client.create_order(OrderArgs(
                token_id=token_id, price=price, size=contracts, side=BUY))
            resp = client.post_order(order)
            logger.info(f"أمر منفذ: {resp}")
        except Exception as e:
            logger.error(f"فشل التنفيذ: {e}")
            tg(f"❌ فشل snipe: {target['question'][:50]}\n{e}")
            return False

    state.positions.append(asdict(pos))
    state.trades_today += 1
    state.total_trades += 1

    mode_label = "LIVE" if live else "PAPER"
    msg = (f"{'🎯' if live else '📋'} [{mode_label}] Snipe!\n"
           f"{target['question'][:70]}\n"
           f"YES @ {price} | ربح متوقع: ${target['net_profit']:.4f}\n"
           f"ينتهي خلال: {target['minutes_left']:.0f} دقيقة")
    logger.info(msg.replace("\n", " | "))
    tg(msg)
    return True

# ── إدارة المراكز ──
def manage_positions(state: BotState, live: bool, client):
    if not state.positions:
        return
    keep = []
    for p in state.positions:
        mdata = http_get(f"{GAMMA_API}/markets/{p['market_id']}")
        resolved = False
        pnl = 0.0

        if mdata:
            closed = mdata.get("closed", False)
            if closed:
                resolved = True
                # تحقق من النتيجة: هل YES فاز؟
                outcomes = mdata.get("outcomePrices") or []
                if isinstance(outcomes, str):
                    try: outcomes = json.loads(outcomes)
                    except Exception: outcomes = []
                if len(outcomes) >= 2:
                    final_yes = float(outcomes[0])
                    if final_yes >= 0.99:
                        # YES فاز — ربح
                        pnl = p["expected_profit"]
                    else:
                        # YES خسر — خسارة كاملة
                        pnl = -p["size_usd"]

        if resolved:
            state.daily_pnl += pnl
            state.total_pnl += pnl
            icon = "💰" if pnl >= 0 else "🔻"
            msg = f"{icon} Snipe انتهى — P&L:${pnl:+.4f}\n{p['question'][:60]}"
            logger.info(msg.replace("\n", " | "))
            tg(msg)
            continue

        keep.append(p)

    state.positions = keep
    if state.daily_pnl <= -DAILY_LOSS_HALT:
        state.halted = True
        msg = f"🛑 إيقاف طوارئ — خسارة يومية ${state.daily_pnl:.2f}"
        logger.warning(msg)
        tg(msg)

# ── الأوامر ──
def cmd_check():
    logger.info("🔍 فحص أسواق شبه محسومة...")
    targets = fetch_sniper_targets()
    logger.info(f"وُجد {len(targets)} هدف مؤهل")
    for t in targets[:10]:
        logger.info(f"  {t['question'][:60]}")
        logger.info(f"    YES:{t['yes_price']:.3f} | ربح:${t['net_profit']:.4f}"
                     f" | {t['minutes_left']:.0f}min | vol:${t['volume']:,.0f}")
    state = load_state()
    print(f"\n{'='*45}")
    print(f"  حالة Resolution Sniper Bot")
    print(f"{'='*45}")
    print(f"  اليوم           : {state.day}")
    print(f"  صفقات اليوم     : {state.trades_today}/{MAX_TRADES_DAY}")
    print(f"  مراكز مفتوحة    : {len(state.positions)}/{MAX_OPEN}")
    print(f"  P&L اليوم       : ${state.daily_pnl:+.4f}")
    print(f"  P&L إجمالي      : ${state.total_pnl:+.4f}")
    print(f"  إجمالي صفقات    : {state.total_trades}")
    print(f"  متوقف           : {state.halted}")
    print(f"{'='*45}")

# ── الدورة الرئيسية ──
def run_cycle(state: BotState, live: bool, client):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if state.day != today:
        state.day = today
        state.trades_today = 0
        state.daily_pnl = 0.0
        state.halted = False
    if state.halted:
        logger.warning("النظام متوقف — تجاوز حد الخسارة")
        return

    manage_positions(state, live, client)

    if len(state.positions) >= MAX_OPEN:
        return
    if state.trades_today >= MAX_TRADES_DAY:
        return

    targets = fetch_sniper_targets()
    if not targets:
        return

    executed = 0
    for t in targets:
        if len(state.positions) >= MAX_OPEN:
            break
        if state.trades_today >= MAX_TRADES_DAY:
            break
        if execute_snipe(t, state, client, live):
            executed += 1
    if executed:
        logger.info(f"تم تنفيذ {executed} صفقات snipe")
    save_state(state)

def main():
    ap = argparse.ArgumentParser(description="Polymarket Resolution Sniper Bot")
    ap.add_argument("--live", action="store_true", help="تداول حقيقي")
    ap.add_argument("--check", action="store_true", help="فحص الأسواق والحالة")
    args = ap.parse_args()

    if args.check:
        cmd_check()
        return

    live = args.live
    mode = "LIVE" if live else "PAPER"
    print(f"""
╔══════════════════════════════════════════╗
║   🎯 Resolution Sniper Bot               ║
║   الوضع: {mode:6}                         ║
║   نطاق السعر: {MIN_YES_PRICE}-{MAX_YES_PRICE} YES           ║
║   حجم الصفقة: ${TRADE_SIZE_USD:.0f}                       ║
╚══════════════════════════════════════════╝
""")

    client = None
    if live:
        if not PK:
            logger.error("PK غير موجود في .env3")
            return
        client = get_clob_client()
        if not client:
            logger.error("فشل الاتصال — تحويل لوضع Paper")
            live = False
    else:
        logger.info("وضع المحاكاة — لا تنفيذ حقيقي")

    tg(f"🎯 بدء resolution_sniper_bot ({mode})\nنطاق: {MIN_YES_PRICE}-{MAX_YES_PRICE}")
    state = load_state()
    cycle = 0
    try:
        while True:
            cycle += 1
            logger.info(f"── دورة #{cycle} | مراكز:{len(state.positions)} P&L:${state.daily_pnl:+.4f} ──")
            run_cycle(state, live, client)
            time.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        save_state(state)
        logger.info("تم الإيقاف")
        tg(f"🛑 إيقاف resolution_sniper_bot\nP&L: ${state.total_pnl:+.4f}")

if __name__ == "__main__":
    main()
