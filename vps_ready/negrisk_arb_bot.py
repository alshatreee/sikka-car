"""
negrisk_arb_bot.py — Negative-Risk Arbitrage Bot (Multi-Outcome)
أسواق متعددة النتائج: إذا مجموع أسعار كل النتائج < $1.00
اشترِ حصة من كل نتيجة — واحدة ستُحل عند $1.00 = ربح مضمون

الفرق عن paired_arb_bot:
  paired_arb  → YES/NO على نفس السوق الثنائي
  negrisk_arb → عدة نتائج لنفس الحدث (مثلاً: من يفوز بالانتخابات؟ A, B, C, D)

الاستخدام:
    python negrisk_arb_bot.py              # محاكاة (افتراضي)
    python negrisk_arb_bot.py --live       # تداول حقيقي
    python negrisk_arb_bot.py --check      # فحص الحالة فقط
    python negrisk_arb_bot.py --scan       # عرض الفرص بدون تداول
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
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = BASE_DIR / ".env3"
STATE_FILE = BASE_DIR / "negrisk_arb_state.json"
LOG_FILE = BASE_DIR / "negrisk_arb.log"
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

# ── تحميل .env3 ──
def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); env[k.strip()] = v.strip()
    return env

ENV = load_env()
PK = ENV.get("PK", "").strip()
if PK.startswith("0x"): PK = PK[2:]
FUNDER = ENV.get("FUNDER", "")
TG_TOKEN, TG_CHAT = ENV.get("TELEGRAM_BOT_TOKEN", ""), ENV.get("TELEGRAM_CHAT_ID", "")
PROXY = ENV.get("HTTPS_PROXY", "")
if PROXY: os.environ["HTTPS_PROXY"] = PROXY; os.environ["HTTP_PROXY"] = PROXY

# ── إعدادات قابلة للتخصيص ──
NEGRISK_MIN_EV = float(os.environ.get("NEGRISK_MIN_EV", "3.0"))       # % أدنى عائد متوقع
NEGRISK_MAX_SUM = float(os.environ.get("NEGRISK_MAX_SUM", "0.97"))    # أقصى مجموع أسعار
NEGRISK_SIZE = float(os.environ.get("NEGRISK_SIZE", "1.0"))           # $ لكل نتيجة
MAX_OPEN = 5            # أقصى مجموعات مفتوحة
MAX_TRADES_DAY = 20     # أقصى تداولات يومية
DAILY_LOSS_HALT = 10.0  # حد الخسارة اليومي $
SCAN_SEC = 120          # فحص كل 120 ثانية
MIN_VOLUME = 500        # أدنى حجم لكل نتيجة $
MIN_HOURS = 1.0         # أدنى وقت قبل الحل (ساعة)

# ── التسجيل ──
logger = logging.getLogger("negrisk_arb"); logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try: _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception: pass

# ── هياكل البيانات ──
@dataclass
class Outcome:
    market_id: str; token_id: str; question: str; price: float

@dataclass
class ArbSet:
    event_id: str; event_title: str; outcomes: list
    total_cost: float; expected_profit: float; total_fees: float
    opened_at: str

@dataclass
class BotState:
    arb_sets: list = field(default_factory=list)
    trades_today: int = 0; daily_pnl: float = 0.0
    day: str = ""; halted: bool = False
    total_sets: int = 0; total_pnl: float = 0.0

def load_state() -> BotState:
    if STATE_FILE.exists():
        try: return BotState(**json.loads(STATE_FILE.read_text()))
        except Exception: pass
    return BotState()

def save_state(s: BotState):
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2, default=str))

# ── أدوات HTTP و Telegram ──
def http_get(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "negrisk-arb/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning(f"HTTP خطأ: {url} — {e}"); return None

def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception: pass

# ── حساب الرسوم ──
def calc_fee(price: float) -> float:
    """رسوم Polymarket لكل سهم: 2 * min(price, 1-price) * 0.02"""
    return 2.0 * min(price, 1.0 - price) * 0.02

def calc_set_fees(prices: list[float]) -> float:
    """إجمالي الرسوم لمجموعة آرب كاملة"""
    return sum(calc_fee(p) for p in prices)

# ── استخراج token_id من بيانات السوق ──
def get_yes_token(market: dict) -> str:
    tokens = market.get("tokens") or market.get("clobTokenIds") or []
    if isinstance(tokens, str):
        try: tokens = json.loads(tokens)
        except Exception: return ""
    for t in (tokens or []):
        if isinstance(t, str):
            continue
        o = str(t.get("outcome", "")).upper()
        tid = t.get("token_id") or t.get("tokenId") or ""
        if o in ("YES", "1"): return str(tid)
    # إذا لم يُعثر، حاول من CLOB
    cid = market.get("conditionId") or market.get("condition_id") or ""
    if cid:
        clob = http_get(f"{CLOB_API}/markets/{cid}")
        if clob:
            for t in (clob.get("tokens") or []):
                if isinstance(t, str):
                    continue
                o = str(t.get("outcome", "")).upper()
                if o in ("YES", "1"): return str(t.get("token_id") or t.get("tokenId") or "")
    return ""

def get_yes_price(market: dict) -> float:
    o = market.get("outcomePrices") or []
    if isinstance(o, str):
        try: o = json.loads(o)
        except Exception: o = []
    return float(o[0]) if len(o) >= 1 else 0.0

# ── جلب الأحداث متعددة النتائج ──
def fetch_events() -> list[dict]:
    """جلب الأحداث من Gamma API وتجميع الأسواق حسب الحدث"""
    # جلب الأحداث النشطة
    events_data = http_get(f"{GAMMA_API}/events?active=true&closed=false&limit=50")
    if not events_data: return []
    events = events_data if isinstance(events_data, list) else []
    results = []
    for event in events:
        markets = event.get("markets") or []
        if len(markets) < 2: continue
        title = event.get("title") or event.get("groupItemTitle") or "?"
        event_id = str(event.get("id") or event.get("slug") or "")
        outcomes = []
        skip_event = False
        for m in markets:
            if m.get("closed") or m.get("resolved"): skip_event = True; break
            price = get_yes_price(m)
            if price <= 0.01 or price >= 0.99: continue
            vol = float(m.get("volume") or m.get("volume24hr") or 0)
            if vol < MIN_VOLUME: skip_event = True; break
            # فحص وقت الحل
            end_str = m.get("endDateIso") or m.get("endDate") or ""
            if end_str:
                try:
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    hrs = (end_dt - datetime.utcnow()).total_seconds() / 3600
                    if hrs < MIN_HOURS: skip_event = True; break
                except Exception: pass
            token_id = get_yes_token(m)
            mid = m.get("conditionId") or m.get("condition_id") or m.get("id", "")
            gamma_id = str(m.get("id") or m.get("slug") or mid)
            q = m.get("question") or m.get("groupItemTitle") or ""
            outcomes.append({"market_id": str(mid), "gamma_id": gamma_id,
                             "token_id": token_id, "question": q, "price": price})
        if skip_event or len(outcomes) < 2: continue
        prices = [o["price"] for o in outcomes]
        price_sum = sum(prices)
        fees = calc_set_fees(prices)
        profit_per_dollar = (1.0 - price_sum - fees / NEGRISK_SIZE) if NEGRISK_SIZE > 0 else 0
        ev_pct = profit_per_dollar * 100
        results.append({"event_id": event_id, "title": title, "outcomes": outcomes,
                         "price_sum": round(price_sum, 4), "fees": round(fees, 4),
                         "expected_profit": round((1.0 - price_sum) * NEGRISK_SIZE - fees, 4),
                         "ev_pct": round(ev_pct, 2), "n_outcomes": len(outcomes)})
    return results

def find_opportunities() -> list[dict]:
    """فلترة الفرص المؤهلة"""
    events = fetch_events()
    opps = []
    for e in events:
        if e["price_sum"] > NEGRISK_MAX_SUM: continue
        if e["ev_pct"] < NEGRISK_MIN_EV: continue
        if e["expected_profit"] < 0.05: continue
        if not all(o.get("token_id") for o in e["outcomes"]): continue
        opps.append(e)
    opps.sort(key=lambda x: x["ev_pct"], reverse=True)
    return opps

# ── CLOB Client ──
def get_clob_client():
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON
        c = ClobClient(host=CLOB_API, key=PK, chain_id=POLYGON, funder=FUNDER, signature_type=1)
        c.set_api_creds(c.create_or_derive_api_creds()); return c
    except Exception as e:
        logger.error(f"فشل CLOB: {e}"); return None

# ── تنفيذ مجموعة آرب ──
def execute_arb_set(opp: dict, st: BotState, client, live: bool) -> bool:
    eid = opp["event_id"]
    if any(a["event_id"] == eid for a in st.arb_sets): return False
    if len(st.arb_sets) >= MAX_OPEN or st.trades_today >= MAX_TRADES_DAY or st.halted: return False
    outcomes_data = []
    for o in opp["outcomes"]:
        outcomes_data.append(asdict(Outcome(
            market_id=o["market_id"], token_id=o["token_id"],
            question=o["question"][:60], price=o["price"])))
    arb = ArbSet(event_id=eid, event_title=opp["title"][:80], outcomes=outcomes_data,
                 total_cost=round(opp["price_sum"] * NEGRISK_SIZE, 4),
                 expected_profit=opp["expected_profit"],
                 total_fees=round(opp["fees"] * NEGRISK_SIZE, 4),
                 opened_at=datetime.utcnow().isoformat())
    if live and client:
        try:
            from py_clob_client.clob_types import OrderArgs
            from py_clob_client.order_builder.constants import BUY
            for o in opp["outcomes"]:
                p = round(o["price"], 2)
                sz = round(NEGRISK_SIZE / p, 1) if p > 0 else 0
                r = client.post_order(client.create_order(OrderArgs(
                    token_id=o["token_id"], price=p, size=sz, side=BUY)))
                logger.info(f"أمر {o['question'][:30]}: {r}")
        except Exception as e:
            logger.error(f"فشل تنفيذ: {e}"); tg(f"❌ فشل آرب: {opp['title'][:50]}\n{e}"); return False
    st.arb_sets.append(asdict(arb)); st.trades_today += 1; st.total_sets += 1
    lbl = "LIVE" if live else "PAPER"
    names = " | ".join(o["question"][:25] for o in opp["outcomes"][:4])
    msg = (f"{'✅' if live else '📋'} [{lbl}] آرب جديد ({opp['n_outcomes']} نتائج)\n"
           f"{opp['title'][:60]}\nΣ={opp['price_sum']:.3f} ربح:${opp['expected_profit']:.4f} "
           f"EV:{opp['ev_pct']:.1f}%\n{names}")
    logger.info(msg.replace("\n", " | ")); tg(msg); return True

# ── إدارة المجموعات المفتوحة ──
def manage_sets(st: BotState, live: bool, client):
    if not st.arb_sets: return
    now = datetime.utcnow(); keep = []
    for arb in st.arb_sets:
        resolved = False; winning = None
        for o in arb["outcomes"]:
            mdata = http_get(f"{CLOB_API}/markets/{o['market_id']}")
            if not mdata:
                continue
            is_closed = mdata.get("closed") or mdata.get("active") is False
            if is_closed:
                res_price = get_yes_price(mdata) if mdata else 0
                if res_price >= 0.95: winning = o; resolved = True; break
                resolved = True
        if resolved:
            pnl = round(1.0 * NEGRISK_SIZE - arb["total_cost"] - arb["total_fees"], 4) if winning else round(-arb["total_cost"], 4)
            st.daily_pnl += pnl; st.total_pnl += pnl
            w_name = winning["question"][:40] if winning else "لا فائز"
            logger.info(f"💰 آرب انتهى — ربح:${pnl:+.4f} | فائز: {w_name}")
            tg(f"💰 آرب انتهى — ربح:${pnl:+.4f}\nفائز: {w_name}\n{arb['event_title'][:50]}"); continue
        keep.append(arb)
    st.arb_sets = keep
    if st.daily_pnl <= -DAILY_LOSS_HALT:
        st.halted = True; logger.warning(f"🛑 إيقاف — خسارة ${st.daily_pnl:.2f}")
        tg(f"🛑 إيقاف طوارئ — خسارة ${st.daily_pnl:.2f}")

# ── أوامر ──
def cmd_check():
    logger.info("🔍 فحص الحالة...")
    st = load_state()
    print(f"\n{'='*50}\n  حالة NegRisk Arb Bot\n{'='*50}")
    print(f"  اليوم: {st.day} | تداولات: {st.trades_today}/{MAX_TRADES_DAY} | مفتوحة: {len(st.arb_sets)}/{MAX_OPEN}")
    print(f"  P&L يوم: ${st.daily_pnl:+.4f} | إجمالي: ${st.total_pnl:+.4f} | متوقف: {st.halted}")
    for i, a in enumerate(st.arb_sets):
        print(f"  [{i+1}] {a['event_title'][:50]} — ${a['total_cost']:.2f} → ربح:${a['expected_profit']:.4f}")
    print(f"{'='*50}")

def cmd_scan():
    logger.info("🔍 مسح الفرص...")
    opps = find_opportunities()
    if not opps:
        print("\n  لا توجد فرص آرب سلبية حالياً\n"); return
    print(f"\n{'='*60}\n  فرص NegRisk Arbitrage ({len(opps)} فرصة)\n{'='*60}")
    for i, o in enumerate(opps[:15]):
        names = ", ".join(oc["question"][:20] for oc in o["outcomes"][:3])
        more = f" +{len(o['outcomes'])-3}" if len(o["outcomes"]) > 3 else ""
        print(f"\n  [{i+1}] {o['title'][:55]}")
        print(f"      نتائج: {o['n_outcomes']} | Σ={o['price_sum']:.3f} | EV:{o['ev_pct']:.1f}%")
        print(f"      ربح: ${o['expected_profit']:.4f} | رسوم: ${o['fees']:.4f}")
        print(f"      {names}{more}")
    print(f"\n{'='*60}")

# ── الدورة الرئيسية ──
def run_cycle(st: BotState, live: bool, client):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if st.day != today:
        st.day = today; st.trades_today = 0; st.daily_pnl = 0.0; st.halted = False
    if st.halted: logger.warning("النظام متوقف — تجاوز حد الخسارة"); return
    manage_sets(st, live, client)
    if len(st.arb_sets) >= MAX_OPEN or st.trades_today >= MAX_TRADES_DAY: return
    opps = find_opportunities()
    executed = 0
    for o in opps:
        if len(st.arb_sets) >= MAX_OPEN or st.trades_today >= MAX_TRADES_DAY: break
        if execute_arb_set(o, st, client, live): executed += 1
    if executed: logger.info(f"تم تنفيذ {executed} مجموعات آرب جديدة")
    save_state(st)

def main():
    ap = argparse.ArgumentParser(description="Polymarket Negative-Risk Arbitrage Bot (Multi-Outcome)")
    ap.add_argument("--live", action="store_true", help="تداول حقيقي")
    ap.add_argument("--check", action="store_true", help="فحص الحالة")
    ap.add_argument("--scan", action="store_true", help="مسح الفرص بدون تداول")
    args = ap.parse_args()
    if args.check: cmd_check(); return
    if args.scan: cmd_scan(); return
    live, mode = args.live, "LIVE" if args.live else "PAPER"
    print(f"\n╔══════════════════════════════════════════════════╗\n"
          f"║  📊 NegRisk Arbitrage Bot — {mode:6}               ║\n"
          f"║  شرط: Σ(أسعار) <= {NEGRISK_MAX_SUM} | حجم: ${NEGRISK_SIZE:.0f}/نتيجة    ║\n"
          f"║  أدنى EV: {NEGRISK_MIN_EV:.0f}% | مسح كل {SCAN_SEC}ث              ║\n"
          f"╚══════════════════════════════════════════════════╝\n")
    client = None
    if live:
        if not PK: logger.error("PK غير موجود في .env3"); return
        client = get_clob_client()
        if not client: logger.error("فشل CLOB — تحويل لوضع المحاكاة"); live = False
    else:
        logger.info("وضع المحاكاة — لا تنفيذ حقيقي")
    tg(f"📊 بدء negrisk_arb_bot ({mode}) | maxΣ={NEGRISK_MAX_SUM} EV>={NEGRISK_MIN_EV}%")
    st = load_state(); cycle = 0
    try:
        while True:
            cycle += 1
            logger.info(f"── دورة #{cycle} | مجموعات:{len(st.arb_sets)}/{MAX_OPEN} "
                        f"تداولات:{st.trades_today}/{MAX_TRADES_DAY} P&L:${st.daily_pnl:+.4f} ──")
            run_cycle(st, live, client)
            time.sleep(SCAN_SEC)
    except KeyboardInterrupt:
        save_state(st); logger.info("تم الإيقاف بواسطة المستخدم")
        tg(f"🛑 إيقاف negrisk_arb_bot | P&L:${st.total_pnl:+.4f} | مجموعات:{st.total_sets}")

if __name__ == "__main__":
    main()
