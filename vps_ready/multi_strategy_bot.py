"""
multi_strategy_bot.py — بوت تداول متعدد الاستراتيجيات لـ Polymarket
يشغل 4 استراتيجيات بالتوازي: Whale Detection, Momentum, Edge Scoring, Volume Spike

الاستخدام:
    python multi_strategy_bot.py                # paper trading (افتراضي)
    python multi_strategy_bot.py --live         # تداول حقيقي
    python multi_strategy_bot.py --check        # عرض الحالة
    python multi_strategy_bot.py --strategy whale|momentum|edge|volume
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time, urllib.request, urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path

if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = BASE_DIR / ".env3"
STATE_FILE = BASE_DIR / "multi_strategy_state.json"
LOG_FILE = BASE_DIR / "multi_strategy.log"
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"

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

logger = logging.getLogger("multi_strat")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception:
    pass

MAX_POSITIONS = 10
MAX_TRADE_USD = 3.0
MAX_TRADES_DAY = 20
MAX_DAILY_LOSS = 20.0
SL_PCT, TP_PCT = 0.25, 0.40
MAX_HOLD_HOURS = 36
SCAN_INTERVAL = 180

@dataclass
class Signal:
    strategy: str; market_id: str; token_id: str; question: str
    side: str; price: float; score: float; reason: str

@dataclass
class Position:
    strategy: str; market_id: str; token_id: str; question: str
    side: str; entry_price: float; size_usd: float; entry_time: str
    sl_price: float; tp_price: float

@dataclass
class BotState:
    positions: list = field(default_factory=list)
    trades_today: int = 0
    daily_pnl: float = 0.0
    day: str = ""
    halted: bool = False
    paper_pnl: float = 0.0
    total_trades: int = 0
    price_history: dict = field(default_factory=dict)

def load_state() -> BotState:
    if STATE_FILE.exists():
        try: return BotState(**json.loads(STATE_FILE.read_text()))
        except Exception: pass
    return BotState()

def save_state(s: BotState):
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2, default=str))

def http_get(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "multi-strat-bot/1.0"})
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
    return 2 * min(price, 1 - price) * 0.02 * 100

def fetch_markets(limit: int = 100) -> list[dict]:
    data = http_get(f"{GAMMA_API}/markets?active=true&closed=false&limit={limit}&order=volume24hr&ascending=false")
    if not data: return []
    return data if isinstance(data, list) else data.get("markets", [])

def get_market_price(market: dict) -> tuple[float, float]:
    outcomes = market.get("outcomePrices") or []
    if isinstance(outcomes, str):
        try: outcomes = json.loads(outcomes)
        except Exception: outcomes = []
    if len(outcomes) >= 2:
        return float(outcomes[0]), float(outcomes[1])
    return 0.5, 0.5

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
            if result: return result
    return ""

# ═══════════ Strategy 1: Whale Detection ═══════════
def strategy_whale(markets_map: dict) -> list[Signal]:
    signals = []
    activity = http_get(f"{DATA_API}/trades?limit=50")
    if not activity: return signals
    items = activity if isinstance(activity, list) else activity.get("data", [])
    for item in items:
        try:
            usd_value = float(item.get("usdcSize") or item.get("value") or item.get("size") or 0)
            if usd_value < 500: continue
            side = str(item.get("side") or item.get("outcome") or "").upper()
            if side not in ("YES", "NO"): side = "YES"
            market_id = item.get("conditionId") or item.get("market") or item.get("assetId") or ""
            if not market_id or market_id not in markets_map: continue
            market = markets_map[market_id]
            yes_p, no_p = get_market_price(market)
            price = yes_p if side == "YES" else no_p
            if price >= 0.75: continue
            whale_price = usd_value / max(float(item.get("size") or item.get("shares") or 1), 1)
            edge = abs(price - whale_price) / max(min(price, whale_price), 0.01) if whale_price > 0 else 0.05
            if edge < 0.03: continue
            token_id = get_token_id(market, side)
            if not token_id: continue
            q = str(market.get("question", ""))[:50]
            signals.append(Signal(
                strategy="whale", market_id=market_id, token_id=token_id,
                question=q, side=side, price=price,
                score=min(95, 60 + edge * 200), reason=f"whale ${usd_value:.0f} edge={edge:.1%}"))
        except Exception:
            continue
    return signals

# ═══════════ Strategy 2: Momentum / Mean Reversion ═══════════
def strategy_momentum(markets: list[dict], state: BotState) -> list[Signal]:
    signals = []
    now = time.time()
    for m in markets:
        mid = m.get("conditionId") or m.get("id", "")
        if not mid: continue
        yes_p, _ = get_market_price(m)
        volume = float(m.get("volume24hr") or m.get("volume") or 0)
        history = state.price_history.get(mid, [])
        history.append([now, yes_p])
        state.price_history[mid] = history[-30:]
        old_entries = [h for h in history if now - h[0] >= 900]
        if not old_entries: continue
        old_price = old_entries[-1][1]
        if old_price == 0: continue
        change_pct = (yes_p - old_price) / old_price
        q = str(m.get("question", ""))[:50]
        if change_pct <= -0.08 and volume > 5000:
            token_id = get_token_id(m, "YES")
            if token_id:
                signals.append(Signal(
                    strategy="momentum", market_id=mid, token_id=token_id,
                    question=q, side="YES", price=yes_p,
                    score=min(90, 65 + abs(change_pct) * 200),
                    reason=f"mean_revert {change_pct:+.1%} vol=${volume:.0f}"))
        elif change_pct >= 0.12 and yes_p < 0.80:
            token_id = get_token_id(m, "YES")
            if token_id:
                signals.append(Signal(
                    strategy="momentum", market_id=mid, token_id=token_id,
                    question=q, side="YES", price=yes_p,
                    score=min(88, 60 + change_pct * 150),
                    reason=f"momentum_follow {change_pct:+.1%}"))
    return signals

# ═══════════ Strategy 3: Edge Scoring ═══════════
def strategy_edge(markets: list[dict]) -> list[Signal]:
    signals = []
    for m in markets:
        mid = m.get("conditionId") or m.get("id", "")
        if not mid: continue
        yes_p, no_p = get_market_price(m)
        liquidity = float(m.get("liquidityNum") or m.get("liquidity") or 0)
        volume = float(m.get("volume24hr") or m.get("volume") or 0)
        end_str = m.get("endDateIso") or m.get("endDate") or ""
        days_left = 30.0
        if end_str:
            try:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).replace(tzinfo=None)
                days_left = max(0, (end_dt - datetime.utcnow()).total_seconds() / 86400)
            except Exception: pass
        liq_score = min(25, (liquidity / 200_000) * 25)
        vol_score = min(25, (volume / 100_000) * 25)
        price_score = max(0, 25 - abs(yes_p - 0.50) * 50)
        if days_left < 1: time_score = 5
        elif days_left < 7: time_score = 15
        elif days_left < 30: time_score = 25
        else: time_score = 20
        composite = liq_score + vol_score + price_score + time_score
        if composite < 70: continue
        side, price = ("YES", yes_p) if yes_p <= no_p else ("NO", no_p)
        potential_profit = 1.0 - price
        fee_cost = calc_fee(price) / 100
        net_edge = (potential_profit - fee_cost) / price if price > 0 else 0
        if net_edge < 0.05: continue
        token_id = get_token_id(m, side)
        if not token_id: continue
        signals.append(Signal(
            strategy="edge", market_id=mid, token_id=token_id,
            question=str(m.get("question", ""))[:50], side=side, price=price,
            score=composite, reason=f"composite={composite:.0f} edge={net_edge:.1%}"))
    return signals

# ═══════════ Strategy 4: Volume Spike ═══════════
def strategy_volume(markets: list[dict]) -> list[Signal]:
    signals = []
    for m in markets:
        mid = m.get("conditionId") or m.get("id", "")
        if not mid: continue
        volume_24h = float(m.get("volume24hr") or m.get("volume") or 0)
        if volume_24h < 1000: continue
        liq = float(m.get("liquidityNum") or m.get("liquidity") or 1)
        vol_liq_ratio = volume_24h / liq if liq > 0 else 0
        if vol_liq_ratio < 3: continue
        yes_p, _ = get_market_price(m)
        if yes_p > 0.60: continue
        token_id = get_token_id(m, "YES")
        if not token_id: continue
        signals.append(Signal(
            strategy="volume", market_id=mid, token_id=token_id,
            question=str(m.get("question", ""))[:50], side="YES", price=yes_p,
            score=min(92, 55 + vol_liq_ratio * 5),
            reason=f"vol_spike ratio={vol_liq_ratio:.1f}x"))
    return signals

# ═══════════ تنفيذ الصفقات ═══════════
def get_clob_client():
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON
        client = ClobClient(host=CLOB_API, key=PK, chain_id=POLYGON,
                            funder=FUNDER, signature_type=1)
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        logger.info("متصل بـ CLOB API")
        return client
    except Exception as e:
        logger.error(f"فشل الاتصال بـ CLOB: {e}")
        return None

def execute_trade(signal: Signal, state: BotState, client, live: bool) -> bool:
    for p in state.positions:
        if p["market_id"] == signal.market_id: return False
    if len(state.positions) >= MAX_POSITIONS: return False
    if state.trades_today >= MAX_TRADES_DAY: return False
    if state.halted: return False
    price = signal.price
    sl = round(price * (1 - SL_PCT), 4)
    tp = round(price * (1 + TP_PCT), 4)
    pos = Position(
        strategy=signal.strategy, market_id=signal.market_id,
        token_id=signal.token_id, question=signal.question,
        side=signal.side, entry_price=price, size_usd=MAX_TRADE_USD,
        entry_time=datetime.utcnow().isoformat(), sl_price=sl, tp_price=tp)
    if live and client:
        try:
            from py_clob_client.clob_types import OrderArgs
            from py_clob_client.order_builder.constants import BUY
            order_args = OrderArgs(token_id=signal.token_id, price=round(price, 2),
                                   size=round(MAX_TRADE_USD / price, 1), side=BUY)
            signed = client.create_order(order_args)
            resp = client.post_order(signed)
            logger.info(f"أمر منفذ: {resp}")
        except Exception as e:
            logger.error(f"فشل التنفيذ: {e}")
            tg(f"فشل تنفيذ صفقة: {signal.question}\n{e}")
            return False
    state.positions.append(asdict(pos))
    state.trades_today += 1
    state.total_trades += 1
    msg = (f"{'LIVE' if live else 'PAPER'} صفقة جديدة [{signal.strategy}]\n"
           f"{signal.question}\n{signal.side} @ {price:.3f}\n"
           f"السبب: {signal.reason}\nSL:{sl:.3f} TP:{tp:.3f}")
    logger.info(msg.replace("\n", " | "))
    tg(msg)
    return True

# ═══════════ إدارة المراكز ═══════════
def manage_positions(state: BotState, live: bool, client):
    if not state.positions: return
    now = datetime.utcnow()
    keep = []
    for p in state.positions:
        mdata = http_get(f"{CLOB_API}/markets/{p['market_id']}")
        if not mdata:
            keep.append(p); continue
        tokens = mdata.get("tokens") or []
        if isinstance(tokens, str):
            try: tokens = json.loads(tokens)
            except Exception: tokens = []
        current_price = None
        for t in tokens:
            tid = t.get("token_id") or t.get("tokenId") or ""
            if str(tid) == str(p["token_id"]):
                current_price = float(t.get("price", 0)); break
        if current_price is None:
            keep.append(p); continue
        entry = p["entry_price"]
        pnl_pct = (current_price - entry) / entry if entry > 0 else 0
        pnl_usd = p["size_usd"] * pnl_pct
        try:
            hold_hours = (now - datetime.fromisoformat(p["entry_time"])).total_seconds() / 3600
        except Exception:
            hold_hours = 0
        exit_reason = None
        if current_price <= p["sl_price"]: exit_reason = "STOP_LOSS"
        elif current_price >= p["tp_price"]: exit_reason = "TAKE_PROFIT"
        elif hold_hours >= MAX_HOLD_HOURS: exit_reason = "TIME_EXIT"
        if exit_reason:
            state.daily_pnl += pnl_usd
            state.paper_pnl += pnl_usd
            msg = (f"{'WIN' if pnl_usd >= 0 else 'LOSS'} إغلاق [{p['strategy']}] {exit_reason}\n"
                   f"{p['question']}\nدخول:{entry:.3f} خروج:{current_price:.3f} P&L:${pnl_usd:+.2f}")
            logger.info(msg.replace("\n", " | "))
            tg(msg)
            if live and client:
                try:
                    from py_clob_client.clob_types import OrderArgs
                    from py_clob_client.order_builder.constants import SELL
                    order_args = OrderArgs(token_id=p["token_id"], price=round(current_price, 2),
                                           size=round(p["size_usd"] / current_price, 1), side=SELL)
                    client.post_order(client.create_order(order_args))
                except Exception as e:
                    logger.error(f"فشل إغلاق: {e}")
        else:
            keep.append(p)
    state.positions = keep
    if state.daily_pnl <= -MAX_DAILY_LOSS:
        state.halted = True
        msg = f"إيقاف طوارئ — خسارة يومية ${state.daily_pnl:.2f}"
        logger.warning(msg); tg(msg)

# ═══════════ الدورة الرئيسية ═══════════
def run_cycle(state: BotState, live: bool, client, strategies: list[str]):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if state.day != today:
        state.day = today; state.trades_today = 0; state.daily_pnl = 0.0; state.halted = False
    if state.halted:
        logger.warning("النظام متوقف — تجاوز حد الخسارة"); return
    manage_positions(state, live, client)
    markets = fetch_markets(100)
    if not markets:
        logger.warning("لم يتم جلب أسواق"); return
    markets_map = {}
    for m in markets:
        mid = m.get("conditionId") or m.get("id", "")
        if mid: markets_map[mid] = m
    all_signals: list[Signal] = []
    if "whale" in strategies: all_signals.extend(strategy_whale(markets_map))
    if "momentum" in strategies: all_signals.extend(strategy_momentum(markets, state))
    if "edge" in strategies: all_signals.extend(strategy_edge(markets))
    if "volume" in strategies: all_signals.extend(strategy_volume(markets))
    all_signals.sort(key=lambda s: s.score, reverse=True)
    seen_markets, unique_signals = set(), []
    for sig in all_signals:
        if sig.market_id not in seen_markets:
            seen_markets.add(sig.market_id); unique_signals.append(sig)
    if unique_signals:
        logger.info(f"إشارات: {len(unique_signals)} (أفضل: {unique_signals[0].strategy} score={unique_signals[0].score:.0f})")
    executed = 0
    for sig in unique_signals[:3]:
        if execute_trade(sig, state, client, live): executed += 1
    if executed:
        logger.info(f"تم تنفيذ {executed} صفقات")
    save_state(state)

def cmd_check():
    state = load_state()
    print(f"""
{'='*40}
  حالة Multi-Strategy Bot
{'='*40}
  اليوم        : {state.day}
  صفقات اليوم  : {state.trades_today}/{MAX_TRADES_DAY}
  P&L اليوم    : ${state.daily_pnl:+.2f}
  P&L إجمالي   : ${state.paper_pnl:+.2f}
  مراكز مفتوحة : {len(state.positions)}/{MAX_POSITIONS}
  إجمالي صفقات : {state.total_trades}
  متوقف        : {state.halted}
{'='*40}""")
    for i, p in enumerate(state.positions, 1):
        print(f"  [{i}] {p['strategy']:8} | {p['side']} @ {p['entry_price']:.3f} | {p['question'][:40]}")
    if not state.positions:
        print("  لا توجد مراكز مفتوحة")

def main():
    ap = argparse.ArgumentParser(description="Polymarket Multi-Strategy Bot")
    ap.add_argument("--live", action="store_true", help="تداول حقيقي")
    ap.add_argument("--paper", action="store_true", default=True)
    ap.add_argument("--check", action="store_true", help="عرض الحالة")
    ap.add_argument("--strategy", type=str, default="all",
                    help="whale|momentum|edge|volume|all")
    args = ap.parse_args()
    if args.check:
        cmd_check(); return
    live = args.live
    strategies = ["whale", "momentum", "edge", "volume"] if args.strategy == "all" else [args.strategy]
    mode = "LIVE" if live else "PAPER"
    logger.info(f"بدء التشغيل — الوضع: {mode} | الاستراتيجيات: {strategies}")
    tg(f"بدء multi_strategy_bot ({mode})\nالاستراتيجيات: {', '.join(strategies)}")
    client = None
    if live:
        if not PK:
            logger.error("PK غير موجود في .env3"); return
        client = get_clob_client()
        if not client:
            logger.error("فشل الاتصال — تحويل لوضع Paper"); live = False
    state = load_state()
    cycle = 0
    try:
        while True:
            cycle += 1
            logger.info(f"── دورة #{cycle} | مراكز:{len(state.positions)} P&L:${state.daily_pnl:+.2f} ──")
            run_cycle(state, live, client, strategies)
            time.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        save_state(state)
        logger.info("تم الإيقاف")
        tg(f"إيقاف multi_strategy_bot\nP&L: ${state.paper_pnl:+.2f}")

if __name__ == "__main__":
    main()
