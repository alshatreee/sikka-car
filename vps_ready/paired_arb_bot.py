"""
paired_arb_bot.py — Paired Position Arbitrage Bot
عندما (P_YES + P_NO) <= 0.95 على Polymarket، اشترِ الجانبين معاً
واحد يُحل عند $1.00 = ربح مضمون

الاستخدام:
    python paired_arb_bot.py              # محاكاة (افتراضي)
    python paired_arb_bot.py --live       # تداول حقيقي
    python paired_arb_bot.py --check      # فحص الأسواق فقط
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
STATE_FILE = BASE_DIR / "paired_arb_state.json"
LOG_FILE = BASE_DIR / "paired_arb.log"
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
logger = logging.getLogger("paired_arb")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception:
    pass

# ── ثوابت الاستراتيجية ──
MAX_SUM_PRICE = 0.95          # (yes + no) <= 0.95
MAX_SPREAD = 0.55             # abs(yes - no) <= 0.55
PAIR_SIZE_USD = 2.0           # $1 لكل جانب
MAX_HOLD_HOURS = 6
MAX_PAIRS_DAY = 30
MAX_OPEN_PAIRS = 8
DAILY_LOSS_HALT = 10.0
SCAN_INTERVAL = 60
CRYPTO_KEYWORDS = ["btc", "bitcoin", "eth", "ethereum", "sol", "solana"]
DIRECTION_KEYWORDS = ["up", "down"]

# ── حالة البوت ──
@dataclass
class Pair:
    market_id: str
    question: str
    yes_token: str
    no_token: str
    yes_price: float
    no_price: float
    sum_price: float
    size_usd: float
    entry_time: str
    expected_profit: float

@dataclass
class BotState:
    pairs: list = field(default_factory=list)
    trades_today: int = 0
    daily_pnl: float = 0.0
    day: str = ""
    halted: bool = False
    total_pairs: int = 0
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
        req = urllib.request.Request(url, headers={"User-Agent": "paired-arb/1.0"})
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

def get_both_tokens(market: dict) -> tuple[str, str]:
    """يرجع (yes_token_id, no_token_id) من السوق."""
    yes_id = _match_token(market.get("tokens") or [], "YES")
    no_id = _match_token(market.get("tokens") or [], "NO")
    if yes_id and no_id:
        return yes_id, no_id
    cid = market.get("conditionId") or market.get("condition_id") or market.get("id", "")
    if cid:
        clob = http_get(f"{CLOB_API}/markets/{cid}")
        if clob:
            yes_id = yes_id or _match_token(clob.get("tokens") or [], "YES")
            no_id = no_id or _match_token(clob.get("tokens") or [], "NO")
    return yes_id, no_id

def get_market_prices(market: dict) -> tuple[float, float]:
    outcomes = market.get("outcomePrices") or []
    if isinstance(outcomes, str):
        try: outcomes = json.loads(outcomes)
        except Exception: outcomes = []
    if len(outcomes) >= 2:
        return float(outcomes[0]), float(outcomes[1])
    return 0.5, 0.5

# ── البحث عن أسواق كريبتو قصيرة المدى ──
def fetch_crypto_pairs() -> list[dict]:
    """يجلب أسواق crypto up/down قصيرة المدى (<=24 ساعة)."""
    data = http_get(f"{GAMMA_API}/markets?active=true&closed=false&limit=100&order=volume24hr&ascending=false")
    if not data: return []
    markets = data if isinstance(data, list) else data.get("markets", [])
    candidates = []
    for m in markets:
        q = str(m.get("question", "")).lower()
        # فلتر: لازم يحتوي على عملة كريبتو + اتجاه
        has_crypto = any(kw in q for kw in CRYPTO_KEYWORDS)
        has_direction = any(kw in q for kw in DIRECTION_KEYWORDS)
        if not (has_crypto and has_direction):
            continue
        # فلتر: وقت الانتهاء <= 24 ساعة
        end_str = m.get("endDateIso") or m.get("endDate") or ""
        if not end_str:
            continue
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).replace(tzinfo=None)
            hours_left = (end_dt - datetime.utcnow()).total_seconds() / 3600
        except Exception:
            continue
        if hours_left < 0.1 or hours_left > 24:
            continue
        yes_p, no_p = get_market_prices(m)
        sum_price = yes_p + no_p
        spread = abs(yes_p - no_p)
        # شرط الدخول: المجموع <= 0.95 والفرق <= 0.55
        if sum_price > MAX_SUM_PRICE or spread > MAX_SPREAD:
            continue
        if yes_p < 0.01 or no_p < 0.01:
            continue
        expected_profit = round((1.0 - sum_price) * (PAIR_SIZE_USD / 2), 4)
        candidates.append({
            "market": m,
            "market_id": m.get("conditionId") or m.get("id", ""),
            "question": m.get("question", ""),
            "yes_price": yes_p,
            "no_price": no_p,
            "sum_price": round(sum_price, 4),
            "spread": round(spread, 4),
            "hours_left": round(hours_left, 2),
            "expected_profit": expected_profit,
        })
    # رتب بأقل مجموع (أكبر فرصة ربح)
    candidates.sort(key=lambda c: c["sum_price"])
    return candidates

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
def execute_pair(candidate: dict, state: BotState, client, live: bool) -> bool:
    """يشتري الجانبين YES و NO معاً."""
    # تحقق من عدم الازدواج
    for p in state.pairs:
        if p["market_id"] == candidate["market_id"]:
            return False
    if len(state.pairs) >= MAX_OPEN_PAIRS:
        return False
    if state.trades_today >= MAX_PAIRS_DAY:
        return False
    if state.halted:
        return False

    market = candidate["market"]
    yes_token, no_token = get_both_tokens(market)
    if not yes_token or not no_token:
        logger.warning(f"لم يُعثر على tokens: {candidate['question'][:50]}")
        return False

    yes_p = round(candidate["yes_price"], 2)
    no_p = round(candidate["no_price"], 2)
    half_size = PAIR_SIZE_USD / 2
    yes_contracts = round(half_size / yes_p, 1)
    no_contracts = round(half_size / no_p, 1)

    pair = Pair(
        market_id=candidate["market_id"],
        question=candidate["question"][:80],
        yes_token=yes_token, no_token=no_token,
        yes_price=yes_p, no_price=no_p,
        sum_price=candidate["sum_price"],
        size_usd=PAIR_SIZE_USD,
        entry_time=datetime.utcnow().isoformat(),
        expected_profit=candidate["expected_profit"],
    )

    if live and client:
        try:
            from py_clob_client.clob_types import OrderArgs
            from py_clob_client.order_builder.constants import BUY
            # شراء YES
            yes_order = client.create_order(OrderArgs(
                token_id=yes_token, price=yes_p, size=yes_contracts, side=BUY))
            resp_yes = client.post_order(yes_order)
            # شراء NO
            no_order = client.create_order(OrderArgs(
                token_id=no_token, price=no_p, size=no_contracts, side=BUY))
            resp_no = client.post_order(no_order)
            logger.info(f"أوامر منفذة — YES: {resp_yes} | NO: {resp_no}")
        except Exception as e:
            logger.error(f"فشل التنفيذ: {e}")
            tg(f"❌ فشل تنفيذ زوج: {candidate['question'][:50]}\n{e}")
            return False

    state.pairs.append(asdict(pair))
    state.trades_today += 1
    state.total_pairs += 1

    mode_label = "LIVE" if live else "PAPER"
    msg = (f"{'✅' if live else '📋'} [{mode_label}] زوج جديد\n"
           f"{candidate['question'][:70]}\n"
           f"YES:{yes_p} + NO:{no_p} = {candidate['sum_price']}\n"
           f"ربح متوقع: ${candidate['expected_profit']:.4f}")
    logger.info(msg.replace("\n", " | "))
    tg(msg)
    return True

# ── إدارة المراكز ──
def manage_pairs(state: BotState, live: bool, client):
    if not state.pairs:
        return
    now = datetime.utcnow()
    keep = []
    for p in state.pairs:
        try:
            entry_dt = datetime.fromisoformat(p["entry_time"])
            hold_hours = (now - entry_dt).total_seconds() / 3600
        except Exception:
            hold_hours = 0

        # تحقق هل السوق انتهى (resolved)
        mdata = http_get(f"{GAMMA_API}/markets/{p['market_id']}")
        resolved = False
        pnl = 0.0
        if mdata:
            closed = mdata.get("closed", False)
            resolved_str = mdata.get("resolved") or mdata.get("resolutionSource")
            if closed or resolved_str:
                resolved = True
                # واحد من الجانبين يُحل عند 1.00
                pnl = round((1.0 - p["sum_price"]) * (p["size_usd"] / 2), 4)

        if resolved:
            state.daily_pnl += pnl
            state.total_pnl += pnl
            msg = (f"💰 زوج انتهى — ربح: ${pnl:+.4f}\n{p['question'][:60]}")
            logger.info(msg.replace("\n", " | "))
            tg(msg)
            continue

        # تجاوز وقت الاحتفاظ = إغلاق بسعر السوق
        if hold_hours >= MAX_HOLD_HOURS:
            # نحاول بيع الجانبين بسعر السوق الحالي
            current_yes, current_no = 0.5, 0.5
            if mdata:
                current_yes, current_no = get_market_prices(mdata)
            # تقدير P&L عند البيع: (بيع YES + بيع NO) - (شراء YES + شراء NO)
            sell_total = current_yes + current_no
            pnl = round((sell_total - p["sum_price"]) * (p["size_usd"] / 2), 4)
            state.daily_pnl += pnl
            state.total_pnl += pnl
            if live and client:
                try:
                    from py_clob_client.clob_types import OrderArgs
                    from py_clob_client.order_builder.constants import SELL
                    half = p["size_usd"] / 2
                    if current_yes > 0.01:
                        y_order = client.create_order(OrderArgs(
                            token_id=p["yes_token"], price=round(current_yes, 2),
                            size=round(half / p["yes_price"], 1), side=SELL))
                        client.post_order(y_order)
                    if current_no > 0.01:
                        n_order = client.create_order(OrderArgs(
                            token_id=p["no_token"], price=round(current_no, 2),
                            size=round(half / p["no_price"], 1), side=SELL))
                        client.post_order(n_order)
                except Exception as e:
                    logger.error(f"خطأ إغلاق زوج: {e}")
            msg = (f"⏰ إغلاق زمني ({hold_hours:.1f}h) P&L:${pnl:+.4f}\n{p['question'][:60]}")
            logger.info(msg.replace("\n", " | "))
            tg(msg)
            continue

        keep.append(p)

    state.pairs = keep
    # فحص إيقاف الخسارة اليومي
    if state.daily_pnl <= -DAILY_LOSS_HALT:
        state.halted = True
        msg = f"🛑 إيقاف طوارئ — خسارة يومية ${state.daily_pnl:.2f}"
        logger.warning(msg)
        tg(msg)

# ── الأوامر ──
def cmd_check():
    logger.info("🔍 فحص الأسواق...")
    candidates = fetch_crypto_pairs()
    logger.info(f"وُجد {len(candidates)} سوق مؤهل")
    for c in candidates[:10]:
        logger.info(f"  {c['question'][:60]}")
        logger.info(f"    YES:{c['yes_price']:.3f} + NO:{c['no_price']:.3f} = {c['sum_price']:.3f}"
                     f" | ربح:${c['expected_profit']:.4f} | {c['hours_left']:.1f}h")
    state = load_state()
    print(f"\n{'='*45}")
    print(f"  حالة Paired Arb Bot")
    print(f"{'='*45}")
    print(f"  اليوم         : {state.day}")
    print(f"  أزواج اليوم   : {state.trades_today}/{MAX_PAIRS_DAY}")
    print(f"  أزواج مفتوحة  : {len(state.pairs)}/{MAX_OPEN_PAIRS}")
    print(f"  P&L اليوم     : ${state.daily_pnl:+.4f}")
    print(f"  P&L إجمالي    : ${state.total_pnl:+.4f}")
    print(f"  إجمالي أزواج  : {state.total_pairs}")
    print(f"  متوقف         : {state.halted}")
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

    manage_pairs(state, live, client)

    if len(state.pairs) >= MAX_OPEN_PAIRS:
        return
    if state.trades_today >= MAX_PAIRS_DAY:
        return

    candidates = fetch_crypto_pairs()
    if not candidates:
        return

    executed = 0
    for c in candidates:
        if len(state.pairs) >= MAX_OPEN_PAIRS:
            break
        if state.trades_today >= MAX_PAIRS_DAY:
            break
        if execute_pair(c, state, client, live):
            executed += 1
    if executed:
        logger.info(f"تم تنفيذ {executed} أزواج جديدة")
    save_state(state)

def main():
    ap = argparse.ArgumentParser(description="Polymarket Paired Arbitrage Bot")
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
║   🔄 Polymarket Paired Arbitrage Bot     ║
║   الوضع: {mode:6}                         ║
║   شرط: (YES + NO) <= {MAX_SUM_PRICE}              ║
║   حجم الزوج: ${PAIR_SIZE_USD:.0f}                       ║
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

    tg(f"🔄 بدء paired_arb_bot ({mode})\nشرط: YES+NO <= {MAX_SUM_PRICE}")
    state = load_state()
    cycle = 0
    try:
        while True:
            cycle += 1
            logger.info(f"── دورة #{cycle} | أزواج:{len(state.pairs)} P&L:${state.daily_pnl:+.4f} ──")
            run_cycle(state, live, client)
            time.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        save_state(state)
        logger.info("تم الإيقاف")
        tg(f"🛑 إيقاف paired_arb_bot\nP&L: ${state.total_pnl:+.4f}")

if __name__ == "__main__":
    main()
