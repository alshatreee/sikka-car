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
from datetime import datetime
from pathlib import Path

if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE, STATE_FILE, LOG_FILE = BASE_DIR/".env3", BASE_DIR/"paired_arb_state.json", BASE_DIR/"paired_arb.log"
GAMMA_API, CLOB_API = "https://gamma-api.polymarket.com", "https://clob.polymarket.com"

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

logger = logging.getLogger("paired_arb"); logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try: _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception: pass

MAX_SUM, MAX_SPREAD = 0.95, 0.55
PAIR_SIZE, MAX_HOLD_H, MAX_PAIRS_DAY, MAX_OPEN = 2.0, 6, 30, 8
DAILY_LOSS_HALT, SCAN_SEC = 10.0, 60
CRYPTO_KW = ["btc", "bitcoin", "eth", "ethereum", "sol", "solana"]
DIR_KW = ["up", "down"]

@dataclass
class Pair:
    market_id: str; question: str; yes_token: str; no_token: str
    yes_price: float; no_price: float; sum_price: float
    size_usd: float; entry_time: str; expected_profit: float

@dataclass
class BotState:
    pairs: list = field(default_factory=list); trades_today: int = 0
    daily_pnl: float = 0.0; day: str = ""; halted: bool = False
    total_pairs: int = 0; total_pnl: float = 0.0

def load_state() -> BotState:
    if STATE_FILE.exists():
        try: return BotState(**json.loads(STATE_FILE.read_text()))
        except Exception: pass
    return BotState()

def save_state(s: BotState):
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2, default=str))

def http_get(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "paired-arb/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode())
    except Exception as e:
        logger.warning(f"HTTP خطأ: {url[:60]} — {e}"); return None

def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception: pass

def _match_token(tokens, side: str) -> str:
    if isinstance(tokens, str):
        try: tokens = json.loads(tokens)
        except Exception: return ""
    for t in (tokens or []):
        o = str(t.get("outcome", "")).upper()
        tid = t.get("token_id") or t.get("tokenId") or ""
        if side == "YES" and o in ("YES", "1"): return str(tid)
        if side == "NO" and o in ("NO", "0"): return str(tid)
    return ""

def get_both_tokens(market: dict) -> tuple[str, str]:
    y = _match_token(market.get("tokens") or [], "YES")
    n = _match_token(market.get("tokens") or [], "NO")
    if y and n: return y, n
    cid = market.get("conditionId") or market.get("condition_id") or market.get("id", "")
    if cid:
        clob = http_get(f"{CLOB_API}/markets/{cid}")
        if clob:
            y = y or _match_token(clob.get("tokens") or [], "YES")
            n = n or _match_token(clob.get("tokens") or [], "NO")
    return y, n

def get_prices(market: dict) -> tuple[float, float]:
    o = market.get("outcomePrices") or []
    if isinstance(o, str):
        try: o = json.loads(o)
        except Exception: o = []
    return (float(o[0]), float(o[1])) if len(o) >= 2 else (0.5, 0.5)

def fetch_crypto_pairs() -> list[dict]:
    data = http_get(f"{GAMMA_API}/markets?active=true&closed=false&limit=100&order=volume24hr&ascending=false")
    if not data: return []
    markets = data if isinstance(data, list) else data.get("markets", [])
    out = []
    for m in markets:
        q = str(m.get("question", "")).lower()
        if not (any(k in q for k in CRYPTO_KW) and any(k in q for k in DIR_KW)): continue
        end_str = m.get("endDateIso") or m.get("endDate") or ""
        if not end_str: continue
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).replace(tzinfo=None)
            hrs = (end_dt - datetime.utcnow()).total_seconds() / 3600
        except Exception: continue
        if hrs < 0.1 or hrs > 24: continue
        yp, np = get_prices(m)
        sp = yp + np
        if sp > MAX_SUM or abs(yp - np) > MAX_SPREAD or yp < 0.01 or np < 0.01: continue
        out.append({"market": m, "market_id": m.get("conditionId") or m.get("id", ""),
            "question": m.get("question", ""), "yes_price": yp, "no_price": np,
            "sum_price": round(sp, 4), "spread": round(abs(yp-np), 4),
            "hours_left": round(hrs, 2),
            "expected_profit": round((1.0 - sp) * (PAIR_SIZE / 2), 4)})
    out.sort(key=lambda c: c["sum_price"])
    return out

def get_clob_client():
    try:
        from py_clob_client.client import ClobClient; from py_clob_client.constants import POLYGON
        c = ClobClient(host=CLOB_API, key=PK, chain_id=POLYGON, funder=FUNDER, signature_type=1)
        c.set_api_creds(c.create_or_derive_api_creds()); return c
    except Exception as e: logger.error(f"فشل CLOB: {e}"); return None

def execute_pair(cand: dict, st: BotState, client, live: bool) -> bool:
    if any(p["market_id"] == cand["market_id"] for p in st.pairs): return False
    if len(st.pairs) >= MAX_OPEN or st.trades_today >= MAX_PAIRS_DAY or st.halted: return False
    yt, nt_ = get_both_tokens(cand["market"])
    if not yt or not nt_:
        logger.warning(f"لم يُعثر على tokens: {cand['question'][:50]}"); return False
    yp, np_ = round(cand["yes_price"], 2), round(cand["no_price"], 2)
    half = PAIR_SIZE / 2
    pair = Pair(market_id=cand["market_id"], question=cand["question"][:80],
        yes_token=yt, no_token=nt_, yes_price=yp, no_price=np_,
        sum_price=cand["sum_price"], size_usd=PAIR_SIZE,
        entry_time=datetime.utcnow().isoformat(), expected_profit=cand["expected_profit"])
    if live and client:
        try:
            from py_clob_client.clob_types import OrderArgs
            from py_clob_client.order_builder.constants import BUY
            r1 = client.post_order(client.create_order(OrderArgs(
                token_id=yt, price=yp, size=round(half/yp, 1), side=BUY)))
            r2 = client.post_order(client.create_order(OrderArgs(
                token_id=nt_, price=np_, size=round(half/np_, 1), side=BUY)))
            logger.info(f"أوامر: YES={r1} NO={r2}")
        except Exception as e:
            logger.error(f"فشل: {e}"); tg(f"❌ فشل زوج: {cand['question'][:50]}\n{e}"); return False
    st.pairs.append(asdict(pair)); st.trades_today += 1; st.total_pairs += 1
    lbl = "LIVE" if live else "PAPER"
    msg = (f"{'✅' if live else '📋'} [{lbl}] زوج جديد\n{cand['question'][:70]}\n"
           f"YES:{yp}+NO:{np_}={cand['sum_price']} ربح:${cand['expected_profit']:.4f}")
    logger.info(msg.replace("\n", " | ")); tg(msg); return True

def manage_pairs(st: BotState, live: bool, client):
    if not st.pairs: return
    now = datetime.utcnow(); keep = []
    for p in st.pairs:
        try: hold_h = (now - datetime.fromisoformat(p["entry_time"])).total_seconds() / 3600
        except Exception: hold_h = 0
        mdata = http_get(f"{GAMMA_API}/markets/{p['market_id']}")
        resolved, pnl = False, 0.0
        if mdata and (mdata.get("closed") or mdata.get("resolved") or mdata.get("resolutionSource")):
            resolved = True; pnl = round((1.0 - p["sum_price"]) * (p["size_usd"] / 2), 4)
        if resolved:
            st.daily_pnl += pnl; st.total_pnl += pnl
            logger.info(f"💰 زوج انتهى — ربح:${pnl:+.4f} | {p['question'][:60]}")
            tg(f"💰 زوج انتهى — ربح:${pnl:+.4f}\n{p['question'][:60]}"); continue
        if hold_h >= MAX_HOLD_H:
            cy, cn = get_prices(mdata) if mdata else (0.5, 0.5)
            pnl = round((cy + cn - p["sum_price"]) * (p["size_usd"] / 2), 4)
            st.daily_pnl += pnl; st.total_pnl += pnl
            if live and client:
                try:
                    from py_clob_client.clob_types import OrderArgs
                    from py_clob_client.order_builder.constants import SELL
                    half = p["size_usd"] / 2
                    if cy > 0.01: client.post_order(client.create_order(OrderArgs(
                        token_id=p["yes_token"], price=round(cy,2), size=round(half/p["yes_price"],1), side=SELL)))
                    if cn > 0.01: client.post_order(client.create_order(OrderArgs(
                        token_id=p["no_token"], price=round(cn,2), size=round(half/p["no_price"],1), side=SELL)))
                except Exception as e: logger.error(f"خطأ إغلاق: {e}")
            logger.info(f"⏰ إغلاق زمني ({hold_h:.1f}h) P&L:${pnl:+.4f} | {p['question'][:60]}")
            tg(f"⏰ إغلاق ({hold_h:.1f}h) P&L:${pnl:+.4f}\n{p['question'][:60]}"); continue
        keep.append(p)
    st.pairs = keep
    if st.daily_pnl <= -DAILY_LOSS_HALT:
        st.halted = True; logger.warning(f"🛑 إيقاف — خسارة ${st.daily_pnl:.2f}")
        tg(f"🛑 إيقاف طوارئ — خسارة ${st.daily_pnl:.2f}")

def cmd_check():
    logger.info("🔍 فحص الأسواق...")
    cands = fetch_crypto_pairs()
    logger.info(f"وُجد {len(cands)} سوق مؤهل")
    for c in cands[:10]:
        logger.info(f"  {c['question'][:55]} YES:{c['yes_price']:.3f}+NO:{c['no_price']:.3f}"
                     f"={c['sum_price']:.3f} ربح:${c['expected_profit']:.4f} {c['hours_left']:.1f}h")
    st = load_state()
    print(f"\n{'='*42}\n  حالة Paired Arb Bot\n{'='*42}")
    print(f"  اليوم: {st.day} | أزواج: {st.trades_today}/{MAX_PAIRS_DAY} | مفتوحة: {len(st.pairs)}/{MAX_OPEN}")
    print(f"  P&L يوم: ${st.daily_pnl:+.4f} | إجمالي: ${st.total_pnl:+.4f} | متوقف: {st.halted}\n{'='*42}")

def run_cycle(st: BotState, live: bool, client):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if st.day != today: st.day = today; st.trades_today = 0; st.daily_pnl = 0.0; st.halted = False
    if st.halted: logger.warning("النظام متوقف"); return
    manage_pairs(st, live, client)
    if len(st.pairs) >= MAX_OPEN or st.trades_today >= MAX_PAIRS_DAY: return
    cands = fetch_crypto_pairs()
    executed = 0
    for c in cands:
        if len(st.pairs) >= MAX_OPEN or st.trades_today >= MAX_PAIRS_DAY: break
        if execute_pair(c, st, client, live): executed += 1
    if executed: logger.info(f"تم تنفيذ {executed} أزواج جديدة")
    save_state(st)

def main():
    ap = argparse.ArgumentParser(description="Polymarket Paired Arbitrage Bot")
    ap.add_argument("--live", action="store_true"); ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check: cmd_check(); return
    live, mode = args.live, "LIVE" if args.live else "PAPER"
    print(f"\n╔══════════════════════════════════════════╗\n"
          f"║  🔄 Paired Arbitrage Bot — {mode:6}        ║\n"
          f"║  شرط: YES+NO <= {MAX_SUM} | زوج: ${PAIR_SIZE:.0f}        ║\n"
          f"╚══════════════════════════════════════════╝\n")
    client = None
    if live:
        if not PK: logger.error("PK غير موجود في .env3"); return
        client = get_clob_client()
        if not client: logger.error("فشل CLOB — تحويل لـ Paper"); live = False
    else: logger.info("وضع المحاكاة — لا تنفيذ حقيقي")
    tg(f"🔄 بدء paired_arb_bot ({mode})"); st = load_state(); cycle = 0
    try:
        while True:
            cycle += 1
            logger.info(f"── دورة #{cycle} | أزواج:{len(st.pairs)} P&L:${st.daily_pnl:+.4f} ──")
            run_cycle(st, live, client); time.sleep(SCAN_SEC)
    except KeyboardInterrupt:
        save_state(st); logger.info("تم الإيقاف"); tg(f"🛑 إيقاف paired_arb_bot P&L:${st.total_pnl:+.4f}")

if __name__ == "__main__":
    main()
