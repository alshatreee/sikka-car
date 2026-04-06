"""
Latency Arbitrage Bot — Polymarket
يراقب سعر BTC/ETH على Binance عبر WebSocket
عندما يتحرك السعر بقوة، يشتري الجانب الصحيح على Polymarket
قبل أن يتحدث السوق — استغلال فارق التأخير (2-5 ثوانٍ)

الاستخدام:
    python latency_arb_bot.py              # تشغيل حقيقي
    python latency_arb_bot.py --paper      # محاكاة بدون أموال حقيقية
    python latency_arb_bot.py --check      # فحص الاتصال فقط
"""

import json
import os
import sys
import time
import threading
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ── المسارات ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = BASE_DIR / ".env"
LOG_FILE = BASE_DIR / "arb_log.json"
PAPER_MODE = "--paper" in sys.argv

# ── تحميل .env ──
def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

ENV = load_env()
PRIVATE_KEY = ENV.get("POLYGON_PRIVATE_KEY", "").strip()
if PRIVATE_KEY.startswith("0x"):
    PRIVATE_KEY = PRIVATE_KEY[2:]
FUNDER = ENV.get("FUNDER_ADDRESS", "0xbA0FeFf3B16A8cD043a6a522f74578f988924E39")
CAPITAL = float(ENV.get("CAPITAL_USD", "300"))

# ── إعدادات الاستراتيجية ──
CONFIG = {
    # حجم الصفقة — Kelly fraction محافظ
    "trade_size_pct": 0.03,           # 3% من رأس المال لكل صفقة
    "max_trade_size_usd": 25.0,       # أقصى $25 لكل صفقة
    "min_trade_size_usd": 1.0,        # أقل $1

    # حد الدخول — فرق السعر المطلوب
    "min_edge_pct": 0.04,             # 4% فرق بين Binance و Polymarket
    "strong_edge_pct": 0.08,          # 8%+ = edge قوي، حجم أكبر

    # إدارة المخاطر
    "max_trades_per_day": 50,         # أقصى 50 صفقة يومياً
    "daily_loss_limit_pct": 0.20,     # وقف خسارة يومي 20%
    "max_drawdown_pct": 0.40,         # kill switch عند 40% تراجع
    "max_positions": 3,               # أقصى 3 مراكز متزامنة

    # توقيت
    "binance_ws_symbol": "btcusdt",   # زوج التداول على Binance
    "polymarket_poll_sec": 2,         # فحص Polymarket كل 2 ثانية
    "cooldown_after_trade_sec": 5,    # انتظار 5 ثوانٍ بعد كل صفقة

    # فلتر الأسواق
    "min_liquidity": 50000,           # أقل $50K سيولة
    "min_time_to_expiry_min": 3,      # أقل 3 دقائق للانتهاء
    "max_time_to_expiry_min": 20,     # أقصى 20 دقيقة
}

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
BINANCE_WS = f"wss://stream.binance.com:9443/ws/{CONFIG['binance_ws_symbol']}@trade"

# ── الحالة العامة ──
state = {
    "binance_price": 0.0,
    "binance_price_1min_ago": 0.0,
    "binance_prices_history": [],      # آخر 60 سعر (كل ثانية)
    "trades_today": 0,
    "daily_pnl": 0.0,
    "peak_capital": CAPITAL,
    "current_capital": CAPITAL,
    "positions": [],
    "trade_log": [],
    "halted": False,
    "halt_reason": "",
    "last_trade_time": 0,
}


def log(msg, level="INFO"):
    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:12]
    icons = {"INFO": "ℹ️", "TRADE": "💰", "WIN": "✅", "LOSS": "🔴",
             "WARN": "⚠️", "ERROR": "❌", "ARB": "⚡", "KILL": "🛑"}
    print(f"[{ts}] {icons.get(level, '📌')} {msg}")


def http_get(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "latency-arb/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"HTTP error: {url[:50]} — {e}", "WARN")
        return None


def save_log():
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "trades": state["trade_log"][-200:],
                "stats": {
                    "trades_today": state["trades_today"],
                    "daily_pnl": round(state["daily_pnl"], 2),
                    "current_capital": round(state["current_capital"], 2),
                    "positions": len(state["positions"]),
                }
            }, f, indent=2, default=str)
    except Exception:
        pass


# ══════════════════════════════════════════
# Binance WebSocket — سعر BTC لحظياً
# ══════════════════════════════════════════
def binance_ws_thread():
    """يتصل بـ Binance WebSocket ويحدّث السعر لحظياً."""
    import websocket

    def on_message(ws, message):
        try:
            data = json.loads(message)
            price = float(data["p"])
            state["binance_price"] = price

            # سجل تاريخ الأسعار (كل ثانية تقريباً)
            now = time.time()
            state["binance_prices_history"].append((now, price))
            # احتفظ بآخر 120 قراءة فقط
            if len(state["binance_prices_history"]) > 120:
                state["binance_prices_history"] = state["binance_prices_history"][-120:]

            # سعر قبل دقيقة
            one_min_ago = now - 60
            old_prices = [p for t, p in state["binance_prices_history"] if t <= one_min_ago]
            if old_prices:
                state["binance_price_1min_ago"] = old_prices[-1]

        except Exception:
            pass

    def on_error(ws, error):
        log(f"Binance WS error: {error}", "WARN")

    def on_close(ws, code, reason):
        log("Binance WS disconnected — reconnecting in 3s...", "WARN")
        time.sleep(3)
        start_binance_ws()

    def on_open(ws):
        log(f"✅ Binance WebSocket connected ({CONFIG['binance_ws_symbol']})")

    ws = websocket.WebSocketApp(
        BINANCE_WS,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )
    ws.run_forever()


def start_binance_ws():
    t = threading.Thread(target=binance_ws_thread, daemon=True)
    t.start()


# ══════════════════════════════════════════
# Polymarket — جلب عقود BTC قصيرة المدة
# ══════════════════════════════════════════
def fetch_btc_contracts():
    """يجلب عقود BTC up/down قصيرة المدة من Polymarket."""
    data = http_get(
        f"{GAMMA_API}/markets?active=true&closed=false"
        f"&limit=50&order=endDate&ascending=true"
    )
    if not data:
        return []

    markets = data if isinstance(data, list) else data.get("markets", data)
    btc_contracts = []

    for m in markets:
        q = str(m.get("question", "")).lower()
        # فلتر: عقود BTC up/down فقط
        if "bitcoin" not in q and "btc" not in q:
            continue
        if "higher" not in q and "lower" not in q and "above" not in q and "below" not in q:
            continue

        # فلتر: وقت الانتهاء
        end_str = m.get("endDateIso") or m.get("endDate") or ""
        if not end_str:
            continue
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).replace(tzinfo=None)
            mins_left = (end_dt - datetime.utcnow()).total_seconds() / 60
        except Exception:
            continue

        if mins_left < CONFIG["min_time_to_expiry_min"]:
            continue
        if mins_left > CONFIG["max_time_to_expiry_min"]:
            continue

        # فلتر: السيولة
        liq = float(m.get("liquidityNum") or m.get("liquidity", 0) or 0)
        if liq < CONFIG["min_liquidity"]:
            continue

        # استخراج الأسعار
        outcomes = m.get("outcomePrices") or []
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except Exception:
                continue
        if len(outcomes) < 2:
            continue

        yes_p = float(outcomes[0])
        no_p = float(outcomes[1])

        btc_contracts.append({
            "market": m,
            "question": m.get("question", ""),
            "yes_price": yes_p,
            "no_price": no_p,
            "mins_left": round(mins_left, 1),
            "liquidity": liq,
            "market_id": m.get("conditionId") or m.get("id", ""),
        })

    return btc_contracts


# ══════════════════════════════════════════
# محرك الأربيتراج — حساب الفرصة
# ══════════════════════════════════════════
def calc_edge(contract):
    """
    يحسب الفرق بين ما يقوله Binance وما يقوله Polymarket.
    إذا BTC تحرك بقوة على Binance لكن Polymarket لم يتحدث بعد = فرصة.
    """
    if state["binance_price"] == 0 or state["binance_price_1min_ago"] == 0:
        return None, None, 0

    # حركة BTC في آخر دقيقة (أو أقل)
    price_now = state["binance_price"]
    price_before = state["binance_price_1min_ago"]
    move_pct = (price_now - price_before) / price_before

    q = contract["question"].lower()
    yes_p = contract["yes_price"]
    no_p = contract["no_price"]

    # تحديد الاتجاه من السؤال
    is_higher_q = "higher" in q or "above" in q or "up" in q
    is_lower_q = "lower" in q or "below" in q or "down" in q

    if not (is_higher_q or is_lower_q):
        return None, None, 0

    # حساب الاحتمال الحقيقي بناءً على حركة Binance
    # حركة قوية = احتمال عالي أن الاتجاه يستمر
    if is_higher_q:
        if move_pct > 0.002:  # BTC ارتفع 0.2%+
            # "will be higher" = أغلب الظن YES
            true_prob = min(0.95, 0.50 + move_pct * 30)  # كل 1% حركة = +30% احتمال
            edge = true_prob - yes_p
            if edge >= CONFIG["min_edge_pct"]:
                return "YES", edge, true_prob
        elif move_pct < -0.002:  # BTC انخفض
            # "will be higher" = أغلب الظن NO
            true_prob = min(0.95, 0.50 + abs(move_pct) * 30)
            edge = true_prob - no_p
            if edge >= CONFIG["min_edge_pct"]:
                return "NO", edge, true_prob

    elif is_lower_q:
        if move_pct < -0.002:  # BTC انخفض
            # "will be lower" = أغلب الظن YES
            true_prob = min(0.95, 0.50 + abs(move_pct) * 30)
            edge = true_prob - yes_p
            if edge >= CONFIG["min_edge_pct"]:
                return "YES", edge, true_prob
        elif move_pct > 0.002:  # BTC ارتفع
            # "will be lower" = أغلب الظن NO
            true_prob = min(0.95, 0.50 + move_pct * 30)
            edge = true_prob - no_p
            if edge >= CONFIG["min_edge_pct"]:
                return "NO", edge, true_prob

    return None, None, 0


# ══════════════════════════════════════════
# إدارة المخاطر
# ══════════════════════════════════════════
def risk_check():
    """يتحقق من كل قواعد المخاطرة قبل الدخول."""
    if state["halted"]:
        return False, f"HALTED: {state['halt_reason']}"

    if state["trades_today"] >= CONFIG["max_trades_per_day"]:
        return False, "الحد اليومي للصفقات"

    # خسارة يومية
    if state["daily_pnl"] <= -(CAPITAL * CONFIG["daily_loss_limit_pct"]):
        state["halted"] = True
        state["halt_reason"] = f"خسارة يومية ${state['daily_pnl']:.2f}"
        return False, state["halt_reason"]

    # drawdown كلي
    drawdown = (state["peak_capital"] - state["current_capital"]) / state["peak_capital"]
    if drawdown >= CONFIG["max_drawdown_pct"]:
        state["halted"] = True
        state["halt_reason"] = f"KILL SWITCH: drawdown {drawdown:.0%}"
        log(state["halt_reason"], "KILL")
        return False, state["halt_reason"]

    # عدد المراكز
    if len(state["positions"]) >= CONFIG["max_positions"]:
        return False, "أقصى عدد مراكز"

    # cooldown
    if time.time() - state["last_trade_time"] < CONFIG["cooldown_after_trade_sec"]:
        return False, "cooldown"

    return True, "OK"


def calc_position_size(edge):
    """حجم الصفقة بناءً على Kelly محافظ."""
    base = state["current_capital"] * CONFIG["trade_size_pct"]

    # إذا edge قوي، زد الحجم قليلاً
    if edge >= CONFIG["strong_edge_pct"]:
        base *= 1.5

    # حدود
    size = max(CONFIG["min_trade_size_usd"], min(CONFIG["max_trade_size_usd"], base))
    return round(size, 2)


# ══════════════════════════════════════════
# تنفيذ الصفقة
# ══════════════════════════════════════════
def get_token_id(market, side):
    """يستخرج token_id."""
    tokens = market.get("tokens") or []
    if isinstance(tokens, str):
        try:
            tokens = json.loads(tokens)
        except Exception:
            tokens = []

    for t in tokens:
        outcome = str(t.get("outcome", "")).upper()
        tid = t.get("token_id") or t.get("tokenId") or t.get("id")
        if not tid:
            continue
        if side == "YES" and outcome in ("YES", "1", "TRUE"):
            return str(tid)
        if side == "NO" and outcome in ("NO", "0", "FALSE"):
            return str(tid)

    # محاولة من CLOB API
    cid = market.get("conditionId") or market.get("id", "")
    if cid:
        data = http_get(f"{CLOB_API}/markets/{cid}")
        if data:
            tokens = data.get("tokens", [])
            if isinstance(tokens, str):
                try:
                    tokens = json.loads(tokens)
                except Exception:
                    tokens = []
            for t in tokens:
                outcome = str(t.get("outcome", "")).upper()
                tid = t.get("token_id") or t.get("tokenId") or t.get("id")
                if side == "YES" and outcome in ("YES", "1", "TRUE"):
                    return str(tid)
                if side == "NO" and outcome in ("NO", "0", "FALSE"):
                    return str(tid)
    return None


def execute_trade(contract, side, edge, size_usd):
    """ينفذ الصفقة على Polymarket أو يسجلها في المحاكاة."""
    market = contract["market"]
    price = contract["yes_price"] if side == "YES" else contract["no_price"]
    price = round(price, 2)

    if price <= 0.01 or price >= 0.99:
        log(f"سعر غير منطقي: {price}", "WARN")
        return False

    size_contracts = round(size_usd / price, 1)
    q = contract["question"][:50]

    log(f"⚡ ARB: {side} {q}", "ARB")
    log(f"   Edge: {edge:.1%} | ${size_usd:.2f} | {size_contracts} عقد @ {price:.2f}", "ARB")
    log(f"   BTC: ${state['binance_price']:,.0f} | Polymarket: {side}={price:.2f}", "ARB")

    trade_record = {
        "time": datetime.utcnow().isoformat(),
        "question": contract["question"][:60],
        "side": side,
        "price": price,
        "size_usd": size_usd,
        "edge": round(edge, 4),
        "btc_price": state["binance_price"],
        "market_id": contract["market_id"],
        "mins_left": contract["mins_left"],
    }

    if PAPER_MODE:
        log(f"   📋 [PAPER] صفقة محاكاة — لا تنفيذ حقيقي", "TRADE")
        trade_record["mode"] = "paper"
        trade_record["status"] = "simulated"
        state["trade_log"].append(trade_record)
        state["trades_today"] += 1
        state["last_trade_time"] = time.time()
        save_log()
        return True

    # تنفيذ حقيقي
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON
        from py_clob_client.clob_types import OrderArgs
        from py_clob_client.order_builder.constants import BUY

        client = ClobClient(
            host=CLOB_API, key=PRIVATE_KEY,
            chain_id=POLYGON, funder=FUNDER, signature_type=1,
        )
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)

        token_id = get_token_id(market, side)
        if not token_id:
            log("لم يُعثر على token_id", "ERROR")
            return False

        order = client.create_order(OrderArgs(
            token_id=token_id, price=price,
            size=size_contracts, side=BUY,
        ))
        resp = client.post_order(order)
        log(f"   ✅ تم: {resp}", "TRADE")

        trade_record["mode"] = "live"
        trade_record["status"] = "executed"
        trade_record["response"] = str(resp)[:100]

        state["positions"].append(trade_record)
        state["trade_log"].append(trade_record)
        state["trades_today"] += 1
        state["last_trade_time"] = time.time()
        save_log()
        return True

    except Exception as e:
        log(f"   ❌ فشل: {e}", "ERROR")
        trade_record["status"] = "failed"
        trade_record["error"] = str(e)[:100]
        state["trade_log"].append(trade_record)
        save_log()
        return False


# ══════════════════════════════════════════
# الحلقة الرئيسية
# ══════════════════════════════════════════
def arb_loop():
    """الحلقة الرئيسية — تبحث عن فرص أربيتراج."""
    cycle = 0

    while not state["halted"]:
        cycle += 1

        # انتظر حتى يتصل Binance
        if state["binance_price"] == 0:
            time.sleep(1)
            continue

        # فحص المخاطر
        ok, reason = risk_check()
        if not ok:
            if "cooldown" not in reason:
                log(f"⏸️ {reason}")
            time.sleep(CONFIG["polymarket_poll_sec"])
            continue

        # جلب عقود BTC
        contracts = fetch_btc_contracts()
        if not contracts:
            time.sleep(CONFIG["polymarket_poll_sec"])
            continue

        # البحث عن فرصة
        best_edge = 0
        best_contract = None
        best_side = None

        for c in contracts:
            side, edge, true_prob = calc_edge(c)
            if side and edge and edge > best_edge:
                best_edge = edge
                best_contract = c
                best_side = side

        if best_contract and best_edge >= CONFIG["min_edge_pct"]:
            size = calc_position_size(best_edge)
            execute_trade(best_contract, best_side, best_edge, size)
        else:
            if cycle % 30 == 0:  # كل دقيقة تقريباً
                move = 0
                if state["binance_price_1min_ago"] > 0:
                    move = (state["binance_price"] - state["binance_price_1min_ago"]) / state["binance_price_1min_ago"]
                log(f"📊 BTC: ${state['binance_price']:,.0f} | حركة: {move:+.2%} | عقود: {len(contracts)} | لا فرصة")

        time.sleep(CONFIG["polymarket_poll_sec"])


# ══════════════════════════════════════════
# نقطة الدخول
# ══════════════════════════════════════════
def main():
    mode = "📋 PAPER MODE" if PAPER_MODE else "💰 LIVE"
    print(f"""
╔══════════════════════════════════════════╗
║   ⚡ Polymarket Latency Arbitrage Bot    ║
║   رأس المال: ${CAPITAL:.2f}                  ║
║   الوضع: {mode}                    ║
║   الزوج: BTC/USDT (Binance → Polymarket)║
╚══════════════════════════════════════════╝
""")

    if not PRIVATE_KEY and not PAPER_MODE:
        print("❌ POLYGON_PRIVATE_KEY مطلوب للتداول الحقيقي")
        print(f"   ملف: {ENV_FILE}")
        print("   أو شغّل بالمحاكاة: python latency_arb_bot.py --paper")
        return

    if "--check" in sys.argv:
        log("🔍 فحص الاتصالات...")
        contracts = fetch_btc_contracts()
        log(f"✅ Polymarket: {len(contracts)} عقود BTC نشطة")
        for c in contracts[:3]:
            log(f"   {c['question'][:50]} | YES:{c['yes_price']:.2f} | {c['mins_left']}min")
        return

    log(f"Edge الأدنى: {CONFIG['min_edge_pct']:.0%}")
    log(f"حجم الصفقة: {CONFIG['trade_size_pct']:.0%} من رأس المال (max ${CONFIG['max_trade_size_usd']})")
    log(f"Kill switch: {CONFIG['max_drawdown_pct']:.0%} drawdown")
    log(f"أقصى صفقات يومية: {CONFIG['max_trades_per_day']}")

    # تشغيل Binance WebSocket
    try:
        import websocket
    except ImportError:
        log("تثبيت websocket-client...", "INFO")
        os.system(f"{sys.executable} -m pip install websocket-client -q")
        import websocket

    log("🔌 الاتصال بـ Binance WebSocket...")
    start_binance_ws()

    # انتظر اتصال Binance
    for i in range(15):
        if state["binance_price"] > 0:
            break
        time.sleep(1)

    if state["binance_price"] == 0:
        log("❌ فشل الاتصال بـ Binance", "ERROR")
        return

    log(f"✅ BTC: ${state['binance_price']:,.0f}")
    log("🚀 بدء البحث عن فرص الأربيتراج...\n")

    try:
        arb_loop()
    except KeyboardInterrupt:
        print("\n🛑 تم الإيقاف")
        print(f"   صفقات اليوم: {state['trades_today']}")
        print(f"   P&L: ${state['daily_pnl']:+.2f}")
        save_log()


if __name__ == "__main__":
    main()
