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
from datetime import datetime
from pathlib import Path

if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE, STATE_FILE, LOG_FILE = BASE_DIR/".env3", BASE_DIR/"sniper_state.json", BASE_DIR/"sniper.log"
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

logger = logging.getLogger("sniper"); logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try: _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception: pass

MIN_P, MAX_P = 0.95, 0.99          # نطاق YES
MIN_MIN, MAX_HR = 5, 6             # 5 دقائق - 6 ساعات
MIN_VOL = 1000; TRADE_USD = 3.0
MIN_NET_PROFIT = 0.02; FEE_RATE = 0.02
MAX_TRADES_DAY, MAX_OPEN = 30, 12
DAILY_LOSS_HALT, SCAN_SEC = 5.0, 90

@dataclass
class Position:
    market_id: str; token_id: str; question: str; entry_price: float
    size_usd: float; expected_profit: float; entry_time: str; hours_left: float

@dataclass
class BotState:
    positions: list = field(default_factory=list); trades_today: int = 0
    daily_pnl: float = 0.0; day: str = ""; halted: bool = False
    total_trades: int = 0; total_pnl: float = 0.0

def load_state() -> BotState:
    if STATE_FILE.exists():
        try: return BotState(**json.loads(STATE_FILE.read_text()))
        except Exception: pass
    return BotState()

def save_state(s: BotState):
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2, default=str))

def http_get(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sniper-bot/1.0"})
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

def calc_net_profit(price: float, size: float) -> float:
    contracts = size / price
    gross = contracts * (1.0 - price)
    fee = contracts * 2 * min(price, 1 - price) * FEE_RATE
    return round(gross - fee, 4)

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

def get_token_id(market: dict, side: str) -> str:
    r = _match_token(market.get("tokens") or [], side)
    if r: return r
    cid = market.get("conditionId") or market.get("condition_id") or market.get("id", "")
    if cid:
        clob = http_get(f"{CLOB_API}/markets/{cid}")
        if clob: r = _match_token(clob.get("tokens") or [], side)
    return r or ""

def fetch_sniper_targets() -> list[dict]:
    data = http_get(f"{GAMMA_API}/markets?active=true&closed=false&limit=200&order=endDate&ascending=true")
    if not data: return []
    markets = data if isinstance(data, list) else data.get("markets", [])
    out, now = [], datetime.utcnow()
    for m in markets:
        end_str = m.get("endDateIso") or m.get("endDate") or ""
        if not end_str: continue
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).replace(tzinfo=None)
            mins = (end_dt - now).total_seconds() / 60; hrs = mins / 60
        except Exception: continue
        if mins < MIN_MIN or hrs > MAX_HR: continue
        vol = float(m.get("volumeNum") or m.get("volume") or m.get("volume24hr") or 0)
        if vol < MIN_VOL: continue
        o = m.get("outcomePrices") or []
        if isinstance(o, str):
            try: o = json.loads(o)
            except Exception: continue
        if len(o) < 2: continue
        yp = float(o[0])
        if not (MIN_P <= yp <= MAX_P): continue
        net = calc_net_profit(yp, TRADE_USD)
        if net < MIN_NET_PROFIT: continue
        out.append({"market": m, "market_id": m.get("conditionId") or m.get("id", ""),
            "question": m.get("question", ""), "yes_price": yp, "no_price": float(o[1]),
            "volume": vol, "hours_left": round(hrs, 2), "minutes_left": round(mins, 1),
            "net_profit": net})
    out.sort(key=lambda t: t["net_profit"], reverse=True)
    return out

def get_clob_client():
    try:
        from py_clob_client.client import ClobClient; from py_clob_client.constants import POLYGON
        c = ClobClient(host=CLOB_API, key=PK, chain_id=POLYGON, funder=FUNDER, signature_type=1)
        c.set_api_creds(c.create_or_derive_api_creds()); return c
    except Exception as e: logger.error(f"فشل CLOB: {e}"); return None

def execute_snipe(tgt: dict, st: BotState, client, live: bool) -> bool:
    if any(p["market_id"] == tgt["market_id"] for p in st.positions): return False
    if len(st.positions) >= MAX_OPEN or st.trades_today >= MAX_TRADES_DAY or st.halted: return False
    tid = get_token_id(tgt["market"], "YES")
    if not tid: logger.warning(f"لم يُعثر على token: {tgt['question'][:50]}"); return False
    price = round(tgt["yes_price"], 2)
    pos = Position(market_id=tgt["market_id"], token_id=tid, question=tgt["question"][:80],
        entry_price=price, size_usd=TRADE_USD, expected_profit=tgt["net_profit"],
        entry_time=datetime.utcnow().isoformat(), hours_left=tgt["hours_left"])
    if live and client:
        try:
            from py_clob_client.clob_types import OrderArgs
            from py_clob_client.order_builder.constants import BUY
            resp = client.post_order(client.create_order(OrderArgs(
                token_id=tid, price=price, size=round(TRADE_USD/price, 1), side=BUY)))
            logger.info(f"أمر: {resp}")
        except Exception as e:
            logger.error(f"فشل: {e}"); tg(f"❌ فشل snipe: {tgt['question'][:50]}\n{e}"); return False
    st.positions.append(asdict(pos)); st.trades_today += 1; st.total_trades += 1
    lbl = "LIVE" if live else "PAPER"
    msg = (f"{'🎯' if live else '📋'} [{lbl}] Snipe!\n{tgt['question'][:70]}\n"
           f"YES@{price} ربح:${tgt['net_profit']:.4f} ينتهي:{tgt['minutes_left']:.0f}min")
    logger.info(msg.replace("\n", " | ")); tg(msg); return True

def manage_positions(st: BotState, live: bool, client):
    if not st.positions: return
    keep = []
    for p in st.positions:
        mdata = http_get(f"{GAMMA_API}/markets/{p['market_id']}")
        if mdata and mdata.get("closed"):
            o = mdata.get("outcomePrices") or []
            if isinstance(o, str):
                try: o = json.loads(o)
                except Exception: o = []
            final_yes = float(o[0]) if len(o) >= 2 else 0
            pnl = p["expected_profit"] if final_yes >= 0.99 else -p["size_usd"]
            st.daily_pnl += pnl; st.total_pnl += pnl
            icon = "💰" if pnl >= 0 else "🔻"
            logger.info(f"{icon} Snipe انتهى P&L:${pnl:+.4f} | {p['question'][:60]}")
            tg(f"{icon} Snipe انتهى P&L:${pnl:+.4f}\n{p['question'][:60]}"); continue
        keep.append(p)
    st.positions = keep
    if st.daily_pnl <= -DAILY_LOSS_HALT:
        st.halted = True; logger.warning(f"🛑 إيقاف — خسارة ${st.daily_pnl:.2f}")
        tg(f"🛑 إيقاف طوارئ — خسارة ${st.daily_pnl:.2f}")

def cmd_check():
    logger.info("🔍 فحص أسواق شبه محسومة...")
    tgts = fetch_sniper_targets()
    logger.info(f"وُجد {len(tgts)} هدف")
    for t in tgts[:10]:
        logger.info(f"  {t['question'][:55]} YES:{t['yes_price']:.3f}"
                     f" ربح:${t['net_profit']:.4f} {t['minutes_left']:.0f}min vol:${t['volume']:,.0f}")
    st = load_state()
    print(f"\n{'='*42}\n  حالة Resolution Sniper Bot\n{'='*42}")
    print(f"  اليوم: {st.day} | صفقات: {st.trades_today}/{MAX_TRADES_DAY} | مفتوحة: {len(st.positions)}/{MAX_OPEN}")
    print(f"  P&L يوم: ${st.daily_pnl:+.4f} | إجمالي: ${st.total_pnl:+.4f} | متوقف: {st.halted}\n{'='*42}")

def run_cycle(st: BotState, live: bool, client):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if st.day != today: st.day = today; st.trades_today = 0; st.daily_pnl = 0.0; st.halted = False
    if st.halted: logger.warning("النظام متوقف"); return
    manage_positions(st, live, client)
    if len(st.positions) >= MAX_OPEN or st.trades_today >= MAX_TRADES_DAY: return
    tgts = fetch_sniper_targets()
    executed = 0
    for t in tgts:
        if len(st.positions) >= MAX_OPEN or st.trades_today >= MAX_TRADES_DAY: break
        if execute_snipe(t, st, client, live): executed += 1
    if executed: logger.info(f"تم تنفيذ {executed} صفقات snipe")
    save_state(st)

def main():
    ap = argparse.ArgumentParser(description="Polymarket Resolution Sniper Bot")
    ap.add_argument("--live", action="store_true"); ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check: cmd_check(); return
    live, mode = args.live, "LIVE" if args.live else "PAPER"
    print(f"\n╔══════════════════════════════════════════╗\n"
          f"║  🎯 Resolution Sniper Bot — {mode:6}       ║\n"
          f"║  نطاق: {MIN_P}-{MAX_P} YES | صفقة: ${TRADE_USD:.0f}       ║\n"
          f"╚══════════════════════════════════════════╝\n")
    client = None
    if live:
        if not PK: logger.error("PK غير موجود في .env3"); return
        client = get_clob_client()
        if not client: logger.error("فشل CLOB — تحويل لـ Paper"); live = False
    else: logger.info("وضع المحاكاة — لا تنفيذ حقيقي")
    tg(f"🎯 بدء sniper_bot ({mode})"); st = load_state(); cycle = 0
    try:
        while True:
            cycle += 1
            logger.info(f"── دورة #{cycle} | مراكز:{len(st.positions)} P&L:${st.daily_pnl:+.4f} ──")
            run_cycle(st, live, client); time.sleep(SCAN_SEC)
    except KeyboardInterrupt:
        save_state(st); logger.info("تم الإيقاف"); tg(f"🛑 إيقاف sniper_bot P&L:${st.total_pnl:+.4f}")

if __name__ == "__main__":
    main()
