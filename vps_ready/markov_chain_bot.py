"""
markov_chain_bot.py — Markov Chain Forecaster for Polymarket
يبني مصفوفة انتقال ماركوف من تاريخ الأسعار (60 يوم)
يحاكي 10,000 مسار عشوائي حتى انتهاء السوق ويقارن الاحتمال المحسوب بسعر السوق

الاستخدام:
    python markov_chain_bot.py              # paper trading (افتراضي)
    python markov_chain_bot.py --live       # تداول حقيقي
    python markov_chain_bot.py --check      # عرض الحالة
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time, random, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
try:
    import numpy as np; HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots"); BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE, STATE_FILE = BASE_DIR / ".env3", BASE_DIR / "markov_state.json"
LOG_FILE = BASE_DIR / "markov.log"
GAMMA_API, CLOB_API = "https://gamma-api.polymarket.com", "https://clob.polymarket.com"

N_BUCKETS, N_SIMULATIONS, LOOKBACK_DAYS = 10, 10_000, 60
MIN_EDGE, MIN_PRICE, MAX_PRICE, MIN_VOLUME = 0.10, 0.15, 0.85, 5000
MIN_HOURS_LEFT, MAX_DAYS_LEFT = 24, 30
TRADE_SIZE, SCAN_INTERVAL = 3.0, 600
MAX_TRADES_DAY, MAX_POSITIONS, MAX_DAILY_LOSS = 8, 6, 12.0
SL_PCT, TP_PCT, MAX_HOLD_HOURS = 0.25, 0.40, 72

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

logger = logging.getLogger("markov"); logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception: pass

def log(msg: str, level: str = "INFO"):
    getattr(logger, level.lower(), logger.info)(msg)

def tg_send(msg: str):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                                    data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception: pass

def http_get(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "markov-bot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"HTTP خطأ: {url[:60]} — {e}", "WARNING"); return None

def load_state() -> dict:
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text())
        except Exception: pass
    return {"positions": [], "daily_trades": 0, "daily_pnl": 0.0, "day": "", "trade_log": []}

def save_state(st: dict):
    st["trade_log"] = st["trade_log"][-200:]
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2))

def reset_daily(st: dict) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if st.get("day") != today:
        st["day"], st["daily_trades"], st["daily_pnl"] = today, 0, 0.0
    return st

# ═══════════════════════════════════════════════
# جلب الأسواق النشطة
# ═══════════════════════════════════════════════
def fetch_active_markets() -> list[dict]:
    data = http_get(f"{GAMMA_API}/markets?active=true&closed=false&limit=100")
    if not data: return []
    markets = data if isinstance(data, list) else data.get("markets", [])
    result, now = [], datetime.now(timezone.utc)
    for m in markets:
        vol = float(m.get("volume", 0) or m.get("volumeNum", 0) or 0)
        if vol < MIN_VOLUME: continue
        end_str = m.get("endDateIso") or m.get("end_date_iso") or m.get("endDate") or ""
        if not end_str: continue
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            if end_dt.tzinfo is None: end_dt = end_dt.replace(tzinfo=timezone.utc)
            hours_left = (end_dt - now).total_seconds() / 3600
        except Exception: continue
        if hours_left < MIN_HOURS_LEFT or hours_left > MAX_DAYS_LEFT * 24: continue
        outcomes = m.get("outcomePrices") or []
        if isinstance(outcomes, str):
            try: outcomes = json.loads(outcomes)
            except Exception: continue
        if len(outcomes) < 2: continue
        yes_p = float(outcomes[0])
        if not (MIN_PRICE <= yes_p <= MAX_PRICE): continue
        tokens = m.get("clobTokenIds") or m.get("tokens") or []
        if isinstance(tokens, str):
            try: tokens = json.loads(tokens)
            except Exception: tokens = []
        yes_token, no_token = "", ""
        if isinstance(tokens, list) and len(tokens) >= 2:
            if isinstance(tokens[0], str):
                yes_token, no_token = tokens[0], tokens[1]
            elif isinstance(tokens[0], dict):
                for t in tokens:
                    out = str(t.get("outcome", "")).upper()
                    tid = t.get("token_id") or t.get("tokenId") or ""
                    if out in ("YES", "1"): yes_token = str(tid)
                    elif out in ("NO", "0"): no_token = str(tid)
        result.append({"market_id": m.get("conditionId") or m.get("id", ""),
            "question": m.get("question", m.get("title", "")),
            "yes_price": yes_p, "no_price": float(outcomes[1]), "volume": vol,
            "hours_left": round(hours_left, 1), "yes_token": yes_token,
            "no_token": no_token, "market": m})
    return result

# ═══════════════════════════════════════════════
# تاريخ الأسعار + مصفوفة ماركوف + محاكاة
# ═══════════════════════════════════════════════
def fetch_price_history(token_id: str) -> list[float]:
    if not token_id: return []
    for params in [f"interval=1h&fidelity=60", f"interval=max&fidelity={LOOKBACK_DAYS*24}"]:
        data = http_get(f"{CLOB_API}/prices-history?market={token_id}&{params}")
        if data and isinstance(data, dict):
            hist = data.get("history", [])
            if isinstance(hist, list) and len(hist) >= 24:
                prices = [float(pt.get("p", 0) or pt.get("price", 0))
                          for pt in hist if 0 < float(pt.get("p", 0) or pt.get("price", 0) or 0) < 1]
                if len(prices) >= 24: return prices
    return []

def synthesize_history(current_price: float, hours: int = LOOKBACK_DAYS * 24) -> list[float]:
    rng, p = random.Random(int(current_price * 10000)), current_price
    prices = [p]
    for _ in range(hours - 1):
        p = max(0.01, min(0.99, p + rng.gauss(0, 0.008)))
        prices.append(round(p, 4))
    return prices

def price_to_bucket(price: float) -> int:
    return max(0, min(N_BUCKETS - 1, int(price * N_BUCKETS)))

def build_transition_matrix(prices: list[float]):
    if HAS_NUMPY:
        matrix = np.zeros((N_BUCKETS, N_BUCKETS), dtype=np.float64)
        for i in range(len(prices) - 1):
            matrix[price_to_bucket(prices[i]), price_to_bucket(prices[i + 1])] += 1.0
        for r in range(N_BUCKETS):
            s = matrix[r].sum()
            matrix[r] = np.ones(N_BUCKETS) / N_BUCKETS if s == 0 else (matrix[r] + 0.01) / (s + 0.01 * N_BUCKETS)
    else:
        matrix = [[0.0] * N_BUCKETS for _ in range(N_BUCKETS)]
        for i in range(len(prices) - 1):
            matrix[price_to_bucket(prices[i])][price_to_bucket(prices[i + 1])] += 1.0
        for r in range(N_BUCKETS):
            s = sum(matrix[r])
            if s == 0: matrix[r] = [1.0 / N_BUCKETS] * N_BUCKETS
            else:
                total = s + 0.01 * N_BUCKETS
                matrix[r] = [(matrix[r][c] + 0.01) / total for c in range(N_BUCKETS)]
    return matrix

def simulate_paths(matrix, start_bucket: int, steps: int) -> float:
    steps = max(1, steps)
    yes_bucket = N_BUCKETS - 1
    if HAS_NUMPY:
        cdf = np.cumsum(matrix, axis=1)
        buckets = np.full(N_SIMULATIONS, start_bucket, dtype=np.int32)
        for _ in range(steps):
            rands = np.random.random(N_SIMULATIONS)
            for i in range(N_SIMULATIONS):
                buckets[i] = min(np.searchsorted(cdf[buckets[i]], rands[i]), N_BUCKETS - 1)
        return int(np.sum(buckets == yes_bucket)) / N_SIMULATIONS
    cdf = []
    for r in range(N_BUCKETS):
        row, cumul = [], 0.0
        for c in range(N_BUCKETS): cumul += matrix[r][c]; row.append(cumul)
        cdf.append(row)
    counts = 0
    for _ in range(N_SIMULATIONS):
        bucket = start_bucket
        for __ in range(steps):
            rv = random.random()
            for c in range(N_BUCKETS):
                if rv <= cdf[bucket][c]: bucket = c; break
        if bucket == yes_bucket: counts += 1
    return counts / N_SIMULATIONS

def analyze_market(mkt: dict) -> dict | None:
    prices = fetch_price_history(mkt["yes_token"])
    synthetic = len(prices) < 24
    if synthetic: prices = synthesize_history(mkt["yes_price"])
    matrix = build_transition_matrix(prices)
    p_yes = simulate_paths(matrix, price_to_bucket(mkt["yes_price"]), max(1, int(mkt["hours_left"])))
    edge_yes, edge_no = p_yes - mkt["yes_price"], (1 - p_yes) - mkt["no_price"]
    if edge_yes >= MIN_EDGE:
        sig = {"side": "YES", "edge": edge_yes, "p_calc": p_yes}
    elif edge_no >= MIN_EDGE:
        sig = {"side": "NO", "edge": edge_no, "p_calc": 1 - p_yes}
    else: return None
    return {"market_id": mkt["market_id"], "question": mkt["question"], "side": sig["side"],
        "edge": round(sig["edge"], 4), "p_calculated": round(sig["p_calc"], 4),
        "market_price": round(mkt["yes_price"] if sig["side"] == "YES" else mkt["no_price"], 4),
        "yes_price": mkt["yes_price"], "no_price": mkt["no_price"], "hours_left": mkt["hours_left"],
        "volume": mkt["volume"], "yes_token": mkt["yes_token"], "no_token": mkt["no_token"],
        "synthetic": synthetic, "data_points": len(prices)}

# ═══════════════════════════════════════════════
# تنفيذ + إدارة المراكز
# ═══════════════════════════════════════════════
def execute_trade(sig: dict, mode: str) -> tuple[bool, str]:
    token_id = sig["yes_token"] if sig["side"] == "YES" else sig["no_token"]
    price = sig["market_price"]
    size = round(TRADE_SIZE / price, 2) if price > 0 else 0
    if mode == "paper": return True, f"PAPER: {size} shares @ {price:.3f}"
    if not PK: return False, "PK مفقود في .env3"
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON
        from py_clob_client.clob_types import OrderArgs
        try:
            from py_clob_client.clob_types import BUY
        except ImportError: BUY = "BUY"
        client = ClobClient(host=CLOB_API, key=PK, chain_id=POLYGON, funder=FUNDER, signature_type=0)
        creds = client.create_or_derive_api_creds(); client.set_api_creds(creds)
        order = client.create_and_post_order(OrderArgs(
            token_id=token_id, price=round(price, 4), size=size, side=BUY))
        return True, str(order)[:120]
    except Exception as e: return False, str(e)[:150]

def get_token_price(token_id: str) -> float:
    data = http_get(f"{CLOB_API}/price?token_id={token_id}&side=sell")
    return float(data.get("price", 0)) if data else 0.0

def check_positions(st: dict) -> dict:
    now, closed = datetime.now(timezone.utc), []
    for pos in st["positions"]:
        tid = pos["yes_token"] if pos["side"] == "YES" else pos["no_token"]
        cur = get_token_price(tid)
        if cur <= 0: continue
        entry = pos["entry_price"]
        pnl_pct = (cur - entry) / entry if entry > 0 else 0
        et = datetime.fromisoformat(pos["entry_time"])
        if et.tzinfo is None: et = et.replace(tzinfo=timezone.utc)
        hold_h = (now - et).total_seconds() / 3600
        reason = None
        if pnl_pct <= -SL_PCT: reason = f"SL ({pnl_pct*100:.1f}%)"
        elif pnl_pct >= TP_PCT: reason = f"TP ({pnl_pct*100:.1f}%)"
        elif hold_h >= MAX_HOLD_HOURS: reason = f"MAX_HOLD ({hold_h:.0f}h)"
        if reason:
            pnl_usd = TRADE_SIZE * pnl_pct; st["daily_pnl"] += pnl_usd
            log(f"EXIT: {reason} | {pos['question'][:35]} | ${pnl_usd:+.2f}")
            tg_send(f"<b>EXIT</b> | {pos['question'][:40]}\nسبب: {reason} | PnL: ${pnl_usd:+.2f}\n"
                    f"دخول: {entry:.3f} خروج: {cur:.3f}")
            closed.append(pos)
    for c in closed: st["positions"].remove(c)
    return st

# ═══════════════════════════════════════════════
# عرض الحالة + الحلقة الرئيسية
# ═══════════════════════════════════════════════
def show_status(st: dict):
    st = reset_daily(st)
    print("=" * 55)
    print("  Markov Chain Forecaster — الحالة")
    print("=" * 55)
    print(f"  اليوم: {st['day']} | صفقات: {st['daily_trades']}/{MAX_TRADES_DAY}")
    print(f"  PnL: ${st['daily_pnl']:.2f} | مراكز: {len(st['positions'])}/{MAX_POSITIONS}")
    print(f"  numpy: {'متوفر' if HAS_NUMPY else 'غير متوفر (fallback)'}")
    if st["positions"]:
        for p in st["positions"]:
            tid = p["yes_token"] if p["side"] == "YES" else p["no_token"]
            cur = get_token_price(tid)
            pnl = ((cur - p["entry_price"]) / p["entry_price"] * 100) if cur > 0 else 0
            print(f"  {p['side']} {p['question'][:30]} | {p['entry_price']:.3f}->{cur:.3f} ({pnl:+.1f}%)")
    else: print("  لا توجد مراكز مفتوحة")
    print("=" * 55)

def run_loop(mode: str):
    log(f"تشغيل Markov Bot — وضع: {mode} | buckets={N_BUCKETS} sims={N_SIMULATIONS:,}")
    log(f"min_edge={MIN_EDGE:.0%} | trade=${TRADE_SIZE} | scan={SCAN_INTERVAL}s")
    tg_send(f"<b>Markov Bot</b> شغّال | وضع: {mode}\nsims={N_SIMULATIONS:,} | edge>={MIN_EDGE:.0%}")
    st = reset_daily(load_state()); cycle = 0
    while True:
        cycle += 1; st = reset_daily(st)
        if st["positions"]:
            st = check_positions(st)
            if st["daily_pnl"] <= -MAX_DAILY_LOSS:
                msg = f"وقف الخسارة اليومي! ${st['daily_pnl']:.2f} — البوت متوقف"
                log(msg, "WARNING"); tg_send(msg); save_state(st); return
        if st["daily_trades"] >= MAX_TRADES_DAY:
            log("الحد اليومي للصفقات"); time.sleep(SCAN_INTERVAL); continue
        if len(st["positions"]) >= MAX_POSITIONS:
            log("الحد الأقصى للمراكز"); time.sleep(SCAN_INTERVAL); continue
        log(f"[{datetime.now().strftime('%H:%M:%S')}] فحص #{cycle} — جلب الأسواق...")
        markets = fetch_active_markets()
        if not markets:
            log("لا توجد أسواق مؤهلة"); time.sleep(SCAN_INTERVAL); continue
        log(f"تحليل {len(markets)} سوق بمصفوفة ماركوف...")
        signals = []
        for mkt in markets:
            if any(p["market_id"] == mkt["market_id"] for p in st["positions"]): continue
            try:
                sig = analyze_market(mkt)
                if sig: signals.append(sig)
            except Exception as e: log(f"خطأ تحليل {mkt['question'][:30]}: {e}", "WARNING")
            time.sleep(0.3)
        if not signals:
            log(f"لا إشارات — {len(markets)} سوق بدون فجوة كافية"); time.sleep(SCAN_INTERVAL); continue
        signals.sort(key=lambda s: s["edge"], reverse=True)
        log(f"وُجدت {len(signals)} إشارة — أقوى فجوة: {signals[0]['edge']:.1%}")
        for sig in signals:
            if st["daily_trades"] >= MAX_TRADES_DAY or len(st["positions"]) >= MAX_POSITIONS: break
            q = sig["question"][:40]
            htag = "حقيقي" if not sig["synthetic"] else "اصطناعي"
            log(f"SIGNAL: {sig['side']} {q} | edge={sig['edge']:.1%} | calc={sig['p_calculated']:.2f} vs mkt={sig['market_price']:.2f}")
            tg_send(f"<b>SIGNAL</b> | {sig['side']} {q}\nP(محسوب)={sig['p_calculated']:.1%} vs "
                    f"سوق={sig['market_price']:.1%}\nفجوة: {sig['edge']:.1%} | "
                    f"بيانات: {sig['data_points']} ({htag})\nحجم: ${sig['volume']:,.0f} | متبقي: {sig['hours_left']:.0f}h")
            ok, result = execute_trade(sig, mode)
            if ok:
                pos = {"market_id": sig["market_id"], "question": sig["question"],
                    "side": sig["side"], "entry_price": sig["market_price"],
                    "p_calculated": sig["p_calculated"], "edge": sig["edge"],
                    "size_usd": TRADE_SIZE, "yes_token": sig["yes_token"],
                    "no_token": sig["no_token"], "entry_time": datetime.now(timezone.utc).isoformat()}
                st["positions"].append(pos); st["daily_trades"] += 1
                st["trade_log"].append({**pos, "result": result[:80], "mode": mode, "cycle": cycle})
                log(f"TRADE: {sig['side']} {q} | ${TRADE_SIZE} | {result[:50]}")
                tg_send(f"<b>TRADE</b> | {sig['side']} {q}\n${TRADE_SIZE} @ {sig['market_price']:.3f}\n{result[:60]}")
            else: log(f"فشل التنفيذ: {result[:80]}", "WARNING")
            time.sleep(1)
        save_state(st)
        log(f"انتظار {SCAN_INTERVAL}s حتى الفحص التالي...\n"); time.sleep(SCAN_INTERVAL)

def main():
    ap = argparse.ArgumentParser(description="Markov Chain Forecaster — Polymarket")
    ap.add_argument("--live", action="store_true", help="تداول حقيقي")
    ap.add_argument("--check", action="store_true", help="عرض الحالة")
    args = ap.parse_args()
    if args.check: show_status(load_state()); return
    if args.live:
        if not PK: print("PK مفقود في .env3 — لا يمكن التداول الحقيقي"); return
        mode = "live"
    else: mode = "paper"
    print(f"\n{'='*55}\n  Markov Chain Forecaster — Polymarket\n"
          f"  الوضع: {'تجريبي' if mode == 'paper' else 'حقيقي'}\n"
          f"  Buckets: {N_BUCKETS} | Simulations: {N_SIMULATIONS:,}\n"
          f"  Lookback: {LOOKBACK_DAYS} days | Min Edge: {MIN_EDGE:.0%}\n"
          f"  numpy: {'YES' if HAS_NUMPY else 'NO (pure Python fallback)'}\n{'='*55}\n")
    try: run_loop(mode)
    except KeyboardInterrupt:
        print(f"\nتم الإيقاف — صفقات اليوم: {load_state().get('daily_trades', 0)}")

if __name__ == "__main__":
    main()
