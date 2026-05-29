#!/usr/bin/env python3
"""
clob_mm_bot.py — Polymarket CLOB Market Maker
Quotes YES/NO around midpoint, earns spread + liquidity rewards.
Avellaneda-Stoikov simplified inventory skew. Non-directional.

Usage:
    python clob_mm_bot.py           # paper mode
    python clob_mm_bot.py --live    # live trading
    python clob_mm_bot.py --check   # show status

    pip install py-clob-client python-dotenv requests
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time, urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──
if os.name == "nt": BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else: BASE_DIR = Path("/root/bots"); BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE, STATE_FILE, LOG_FILE = BASE_DIR/".env3", BASE_DIR/"clob_mm_state.json", BASE_DIR/"clob_mm.log"
GAMMA_API, CLOB_API = "https://gamma-api.polymarket.com", "https://clob.polymarket.com"

# ── Load .env3 ──
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
FUNDER   = ENV.get("FUNDER", "")
TG_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = ENV.get("TELEGRAM_CHAT_ID", "")
PROXY    = ENV.get("POLYMARKET_PROXY", "") or ENV.get("HTTPS_PROXY", "")
if PROXY: os.environ["HTTPS_PROXY"] = PROXY; os.environ["HTTP_PROXY"] = PROXY

# ── Parameters ──
TARGET_SPREAD  = 0.03    # 3c between bid and ask
MIN_SPREAD     = 0.02    # floor — never tighter
ORDER_SIZE     = 2.0     # $2 per side
MAX_INVENTORY  = 20.0    # $20 max exposure per market per side
MAX_MARKETS    = 3       # quote on 3 markets simultaneously
MIN_LIQUIDITY  = 30_000  # only quote on liquid markets ($30k+)
MIN_EXPIRY_HRS = 72      # avoid near-expiry markets
REFRESH_SEC    = 60      # cancel and re-quote interval
SCAN_SEC       = 600     # scan for new markets interval
MOVE_HALT      = 0.05    # halt quoting if >5% move
MAX_DAILY_LOSS = 10.0    # kill switch
FEE_RATE       = 0.02    # Polymarket maker fee rate
MAX_TRADES_DAY = 200

# ── Logging ──
logger = logging.getLogger("clob_mm"); logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try: _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception: pass

# ── Telegram ──
def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                                    data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception: pass

def http_get(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "clob-mm/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning(f"HTTP err: {url[:80]} — {e}"); return None

# ── State ──
@dataclass
class QuotedMarket:
    condition_id: str; question: str; token_yes: str; token_no: str
    yes_inv: float = 0.0; no_inv: float = 0.0
    fills_yes: int = 0; fills_no: int = 0
    spread_earned: float = 0.0; rebates_earned: float = 0.0
    last_mid: float = 0.5; last_quote_ts: float = 0.0
    active_order_ids: list = field(default_factory=list)

@dataclass
class BotState:
    markets: list = field(default_factory=list)
    trades_today: int = 0; daily_pnl: float = 0.0
    day: str = ""; halted: bool = False
    total_pnl: float = 0.0; total_fills: int = 0
    total_rebates: float = 0.0; last_scan_ts: float = 0.0

def load_state() -> BotState:
    if STATE_FILE.exists():
        try: return BotState(**json.loads(STATE_FILE.read_text()))
        except Exception: pass
    return BotState()

def save_state(s: BotState):
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2, default=str))

# ── CLOB Client ──
def get_clob_client():
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON
        c = ClobClient(host=CLOB_API, key=PK, chain_id=POLYGON, funder=FUNDER, signature_type=1)
        c.set_api_creds(c.create_or_derive_api_creds()); return c
    except Exception as e:
        logger.error(f"CLOB init failed: {e}"); return None

# ── Helpers ──
def calc_fee(price: float, size_usd: float) -> float:
    shares = size_usd / price if price > 0 else 0
    return shares * FEE_RATE * min(price, 1.0 - price)

def get_yes_price(market: dict) -> float:
    o = market.get("outcomePrices") or []
    if isinstance(o, str):
        try: o = json.loads(o)
        except Exception: o = []
    return float(o[0]) if len(o) >= 1 else 0.0

def _parse_tokens(tokens) -> tuple[str, str]:
    yes_id, no_id = "", ""
    for t in (tokens or []):
        if isinstance(t, str): continue
        o, tid = str(t.get("outcome", "")).upper(), str(t.get("token_id") or t.get("tokenId") or "")
        if o in ("YES", "1"): yes_id = tid
        elif o in ("NO", "0"): no_id = tid
    return yes_id, no_id

def get_token_ids(market: dict) -> tuple[str, str]:
    """Return (yes_token_id, no_token_id)."""
    tokens = market.get("tokens") or market.get("clobTokenIds") or []
    if isinstance(tokens, str):
        try: tokens = json.loads(tokens)
        except Exception: return "", ""
    yes_id, no_id = _parse_tokens(tokens)
    if not yes_id or not no_id:
        cid = market.get("conditionId") or market.get("condition_id") or ""
        if cid:
            clob = http_get(f"{CLOB_API}/markets/{cid}")
            if clob: yes_id, no_id = _parse_tokens(clob.get("tokens") or [])
    return yes_id, no_id

# ── Market selection ──
def select_markets(existing_ids: set) -> list[dict]:
    """Fetch active markets from Gamma API, filter by liquidity/time/spread."""
    data = http_get(f"{GAMMA_API}/markets?active=true&closed=false&limit=100")
    if not data: return []
    candidates = []
    for m in (data if isinstance(data, list) else []):
        if m.get("closed") or m.get("resolved"): continue
        cid = m.get("conditionId") or m.get("condition_id") or ""
        if not cid or cid in existing_ids: continue
        vol = float(m.get("volume") or m.get("volumeNum") or 0)
        if vol < MIN_LIQUIDITY: continue
        price = get_yes_price(m)
        if price < 0.10 or price > 0.90: continue
        end_str = m.get("endDateIso") or m.get("endDate") or ""
        if not end_str: continue
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            hrs_left = (end_dt - datetime.now(timezone.utc)).total_seconds() / 3600
            if hrs_left < MIN_EXPIRY_HRS: continue
        except Exception: continue
        yes_id, no_id = get_token_ids(m)
        if not yes_id or not no_id: continue
        question = m.get("question") or m.get("groupItemTitle") or "?"
        candidates.append({"condition_id": cid, "question": question,
                           "token_yes": yes_id, "token_no": no_id,
                           "volume": vol, "price": price, "hrs_left": hrs_left})
    candidates.sort(key=lambda x: x["volume"], reverse=True)
    return candidates

# ── Orderbook / fair price ──
def get_fair_price(token_id: str) -> float | None:
    """Fetch midpoint from CLOB orderbook."""
    book = http_get(f"{CLOB_API}/book?token_id={token_id}")
    if not book: return None
    bids, asks = book.get("bids") or [], book.get("asks") or []
    bb = float(bids[0]["price"]) if bids else None
    ba = float(asks[0]["price"]) if asks else None
    if bb is not None and ba is not None: return round((bb + ba) / 2, 4)
    return bb or ba

# ── Quote calculation (Avellaneda-Stoikov simplified) ──
def calc_quotes(fair: float, yes_inv: float, no_inv: float):
    """Return (bid_yes, ask_yes, bid_no, ask_no) with inventory skew."""
    hs = max(TARGET_SPREAD / 2, MIN_SPREAD / 2)
    net = yes_inv - no_inv  # positive = long YES
    skew = (net / MAX_INVENTORY) * hs if MAX_INVENTORY > 0 else 0.0
    # YES quotes — skew shifts both quotes down when long YES (eager to sell)
    by = max(0.01, min(0.99, round(fair - hs - skew, 2)))
    ay = max(0.01, min(0.99, round(fair + hs - skew, 2)))
    if ay - by < MIN_SPREAD: ay = round(by + MIN_SPREAD, 2)
    # NO quotes — inverted skew
    fn = round(1.0 - fair, 4)
    bn = max(0.01, min(0.99, round(fn - hs + skew, 2)))
    an = max(0.01, min(0.99, round(fn + hs + skew, 2)))
    if an - bn < MIN_SPREAD: an = round(bn + MIN_SPREAD, 2)
    return by, ay, bn, an

# ── Order placement (live) ──
def place_quotes_live(client, mkt: dict, by: float, ay: float,
                      bn: float, an: float, size: float) -> list[str]:
    oids = []
    try:
        from py_clob_client.clob_types import OrderArgs
        from py_clob_client.order_builder.constants import BUY, SELL
    except ImportError: logger.error("py-clob-client missing"); return oids
    for label, tok, px, side in [
        ("Y-BID", mkt["token_yes"], by, BUY),  ("Y-ASK", mkt["token_yes"], ay, SELL),
        ("N-BID", mkt["token_no"],  bn, BUY),  ("N-ASK", mkt["token_no"],  an, SELL),
    ]:
        try:
            shares = round(size / px, 1) if px > 0 else 0
            if shares < 0.1: continue
            signed = client.create_order(OrderArgs(
                token_id=tok, price=round(px, 2), size=shares, side=side))
            resp = client.post_order(signed)
            oid = resp.get("orderID") or resp.get("id") or ""
            if oid: oids.append(oid)
            logger.info(f"  {label} p={px:.2f} sz={shares:.1f} -> {oid[:12] if oid else 'ok'}")
        except Exception as e: logger.warning(f"  {label} failed: {e}")
    return oids

def cancel_orders_live(client, order_ids: list[str]):
    for oid in order_ids:
        try: client.cancel(oid)
        except Exception: pass

def cancel_all_live(client):
    try: client.cancel_all(); logger.info("Cancelled all open orders")
    except Exception as e: logger.warning(f"cancel_all failed: {e}")

# ── Paper mode simulation ──
def simulate_fills(mkt: dict, by: float, ay: float, bn: float, an: float, size: float) -> dict:
    """Simulate fills when fair price crosses our quotes."""
    fair = get_fair_price(mkt["token_yes"])
    if fair is None: return {"y": None, "n": None}
    res = {"y": None, "n": None}
    if fair <= by: res["y"] = ("BID", by, size)
    elif fair >= ay: res["y"] = ("ASK", ay, size)
    fn = 1.0 - fair
    if fn <= bn: res["n"] = ("BID", bn, size)
    elif fn >= an: res["n"] = ("ASK", an, size)
    return res

def process_paper_fills(mkt: dict, fills: dict) -> float:
    pnl = 0.0
    for key, inv_key, fill_key in [("y", "yes_inv", "fills_yes"), ("n", "no_inv", "fills_no")]:
        if not fills[key]: continue
        side, price, sz = fills[key]
        if side == "BID": mkt[inv_key] += sz
        else: mkt[inv_key] -= sz; pnl += sz * TARGET_SPREAD / 2
        mkt[fill_key] += 1
        mkt["spread_earned"] += sz * TARGET_SPREAD / 4
    return pnl

# ── Status display ──
def cmd_check():
    st = load_state()
    print(f"\n{'='*55}\n  CLOB Market Maker — Status\n{'='*55}")
    print(f"  Day: {st.day} | Trades: {st.trades_today}/{MAX_TRADES_DAY} | Halted: {st.halted}")
    print(f"  Daily P&L: ${st.daily_pnl:+.4f} | Total P&L: ${st.total_pnl:+.4f}")
    print(f"  Fills: {st.total_fills} | Rebates: ${st.total_rebates:.4f}")
    print(f"  Active markets: {len(st.markets)}/{MAX_MARKETS}")
    for i, m in enumerate(st.markets):
        q = m.get("question", "?")[:45]
        yi, ni = m.get("yes_inv", 0), m.get("no_inv", 0)
        se = m.get("spread_earned", 0)
        print(f"  [{i+1}] {q}")
        print(f"      Mid={m.get('last_mid',0):.2f} | Y=${yi:+.1f} N=${ni:+.1f} "
              f"| Fills: Y={m.get('fills_yes',0)} N={m.get('fills_no',0)} | Spr=${se:.3f}")
    print(f"{'='*55}\n")

# ── Core cycle ──
def refresh_quotes(mkt: dict, st: BotState, client, live: bool) -> float:
    """Cancel stale quotes, place new ones. Returns paper P&L."""
    if live and client and mkt.get("active_order_ids"):
        cancel_orders_live(client, mkt["active_order_ids"]); mkt["active_order_ids"] = []
    fair = get_fair_price(mkt["token_yes"])
    if fair is None: logger.warning(f"  No book: {mkt['question'][:40]}"); return 0.0
    if mkt["last_mid"] > 0 and abs(fair - mkt["last_mid"]) > MOVE_HALT:
        logger.warning(f"  Large move {mkt['question'][:30]}: {mkt['last_mid']:.2f}->{fair:.2f}")
        return 0.0
    mkt["last_mid"] = fair
    by, ay, bn, an = calc_quotes(fair, mkt.get("yes_inv", 0.0), mkt.get("no_inv", 0.0))
    logger.info(f"  {mkt['question'][:35]} mid={fair:.3f} Y={by:.2f}/{ay:.2f} N={bn:.2f}/{an:.2f}")
    pnl = 0.0
    if live and client:
        oids = place_quotes_live(client, mkt, by, ay, bn, an, ORDER_SIZE)
        mkt["active_order_ids"] = oids; st.trades_today += len(oids)
    else:
        fills = simulate_fills(mkt, by, ay, bn, an, ORDER_SIZE)
        pnl = process_paper_fills(mkt, fills)
        for key, label in [("y", "YES"), ("n", "NO")]:
            if fills[key]:
                side, px, sz = fills[key]
                logger.info(f"    PAPER {label} {side} @ {px:.2f} ${sz:.1f}")
                st.total_fills += 1; st.trades_today += 1
    # Liquidity rebate estimate (quadratic scoring — higher near midpoint)
    rebate = ORDER_SIZE * 0.001 * max(0, 1.0 - 2.0 * abs(fair - 0.5))
    mkt["rebates_earned"] = mkt.get("rebates_earned", 0) + rebate
    st.total_rebates += rebate; mkt["last_quote_ts"] = time.time()
    for inv_val, lbl in [(mkt["yes_inv"], "YES"), (mkt["no_inv"], "NO")]:
        if abs(inv_val) > MAX_INVENTORY * 0.8:
            logger.warning(f"  {lbl} inv ${inv_val:.1f} near max")
            tg(f"-- MM Inv: {mkt['question'][:35]}\n{lbl} ${inv_val:.1f}")
    return pnl

def scan_and_add_markets(st: BotState):
    if len(st.markets) >= MAX_MARKETS: return
    existing = {m["condition_id"] for m in st.markets}
    for c in select_markets(existing):
        if len(st.markets) >= MAX_MARKETS: break
        new = asdict(QuotedMarket(condition_id=c["condition_id"], question=c["question"],
                                  token_yes=c["token_yes"], token_no=c["token_no"],
                                  last_mid=c["price"]))
        st.markets.append(new)
        logger.info(f"+ Market: {c['question'][:50]} (vol=${c['volume']:.0f})")
        tg(f"+ MM New Market\n{c['question'][:50]}\nVol=${c['volume']:.0f} Mid={c['price']:.2f}")
    st.last_scan_ts = time.time()

def remove_stale_markets(st: BotState, client, live: bool):
    keep = []
    for mkt in st.markets:
        mdata = http_get(f"{GAMMA_API}/markets/{mkt['condition_id']}")
        remove = False
        if mdata and (mdata.get("closed") or mdata.get("resolved")):
            se = mkt.get("spread_earned", 0)
            logger.info(f"- Closed: {mkt['question'][:40]} spr=${se:.3f}")
            st.total_pnl += se; st.daily_pnl += se; remove = True
        elif mdata:
            end_str = mdata.get("endDateIso") or mdata.get("endDate") or ""
            if end_str:
                try:
                    hrs = (datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                           - datetime.now(timezone.utc)).total_seconds() / 3600
                    if hrs < MIN_EXPIRY_HRS / 2:
                        logger.info(f"- Expiry ({hrs:.0f}h): {mkt['question'][:40]}"); remove = True
                except Exception: pass
        if remove:
            if live and client and mkt.get("active_order_ids"):
                cancel_orders_live(client, mkt["active_order_ids"])
        else: keep.append(mkt)
    st.markets = keep

def run_cycle(st: BotState, live: bool, client):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if st.day != today:
        if st.day:
            tg(f"-- MM Daily\nP&L:${st.daily_pnl:+.4f} Fills:{st.total_fills} "
               f"Rebates:${st.total_rebates:.4f}")
        st.day = today; st.trades_today = 0; st.daily_pnl = 0.0; st.halted = False
    # Kill switch
    if st.daily_pnl <= -MAX_DAILY_LOSS:
        if not st.halted:
            st.halted = True
            logger.warning(f"KILL: P&L ${st.daily_pnl:.2f} < -${MAX_DAILY_LOSS}")
            tg(f"!! MM HALTED — loss ${st.daily_pnl:.2f}")
            if live and client: cancel_all_live(client)
        return
    if st.halted: return
    # Scan periodically
    if time.time() - st.last_scan_ts > SCAN_SEC or not st.markets:
        remove_stale_markets(st, client, live)
        scan_and_add_markets(st)
    # Refresh quotes
    cycle_pnl = 0.0
    for mkt in st.markets:
        if st.trades_today >= MAX_TRADES_DAY: break
        cycle_pnl += refresh_quotes(mkt, st, client, live)
    st.daily_pnl += cycle_pnl; st.total_pnl += cycle_pnl
    save_state(st)

# ── Entry point ──
def main():
    ap = argparse.ArgumentParser(description="Polymarket CLOB Market Maker")
    ap.add_argument("--live", action="store_true", help="Live trading")
    ap.add_argument("--check", action="store_true", help="Show status")
    args = ap.parse_args()
    if args.check: cmd_check(); return

    live, mode = args.live, "LIVE" if args.live else "PAPER"
    print(f"\n{'='*55}\n  CLOB Market Maker — {mode}\n"
          f"  Spread: {TARGET_SPREAD*100:.0f}c | Size: ${ORDER_SIZE} | Max inv: ${MAX_INVENTORY}\n"
          f"  Markets: {MAX_MARKETS} | Min liq: ${MIN_LIQUIDITY:,.0f} | Refresh: {REFRESH_SEC}s\n"
          f"  Kill switch: -${MAX_DAILY_LOSS} daily\n{'='*55}\n")

    client = None
    if live:
        if not PK: logger.error("PK not found in .env3"); return
        client = get_clob_client()
        if not client: logger.error("CLOB failed — paper fallback"); live = False
    else:
        logger.info("Paper mode — no real orders")

    tg(f"-- MM Start ({mode}) spread={TARGET_SPREAD} sz=${ORDER_SIZE} mkts={MAX_MARKETS}")
    st = load_state(); cycle = 0
    try:
        while True:
            cycle += 1
            logger.info(f"-- #{cycle} mkts={len(st.markets)}/{MAX_MARKETS} "
                        f"trades={st.trades_today}/{MAX_TRADES_DAY} P&L=${st.daily_pnl:+.4f} --")
            run_cycle(st, live, client)
            time.sleep(REFRESH_SEC)
    except KeyboardInterrupt:
        logger.info("Shutting down")
        if live and client: cancel_all_live(client)
        save_state(st)
        tg(f"-- MM Stop | P&L:${st.total_pnl:+.4f} Fills:{st.total_fills} "
           f"Rebates:${st.total_rebates:.4f}")

if __name__ == "__main__":
    main()
