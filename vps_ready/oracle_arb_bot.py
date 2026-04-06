"""
Oracle Arbitrage Bot — Polymarket
يراقب أسعار Chainlink Oracle على Polygon
ويقارنها بعقود Polymarket — إذا وُجد فرق يشتري الجانب الصحيح

الاستخدام:
    python oracle_arb_bot.py             # تشغيل حقيقي
    python oracle_arb_bot.py --paper     # محاكاة
    python oracle_arb_bot.py --check     # فحص الأسعار فقط
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ── المسارات ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = BASE_DIR / ".env"
LOG_FILE = BASE_DIR / "oracle_arb_log.json"
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

# ── إعدادات ──
CONFIG = {
    "trade_size_pct": 0.04,
    "max_trade_size_usd": 30.0,
    "min_trade_size_usd": 2.0,
    "min_edge_pct": 0.03,            # 3% فرق أقل (Oracle أكثر دقة)
    "max_trades_per_day": 30,
    "daily_loss_limit_pct": 0.20,
    "max_drawdown_pct": 0.40,
    "max_positions": 3,
    "poll_interval_sec": 10,          # فحص كل 10 ثوانٍ
    "cooldown_sec": 10,
    "min_liquidity": 50000,
}

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

# Chainlink Price Feed Proxies على Polygon
CHAINLINK_FEEDS = {
    "BTC/USD": "0xc907E116054Ad103354f2D350FD2514433D57F6f",
    "ETH/USD": "0xF9680D99D6C9589e2a93a78A04A279e509205945",
}

# Chainlink AggregatorV3 ABI (latestRoundData فقط)
AGGREGATOR_ABI = [
    {
        "inputs": [],
        "name": "latestRoundData",
        "outputs": [
            {"name": "roundId", "type": "uint80"},
            {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"},
            {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]

RPCS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://polygon.llamarpc.com",
]

# ── الحالة ──
state = {
    "oracle_prices": {},       # {"BTC/USD": 67000.0, "ETH/USD": 3400.0}
    "oracle_updated_at": {},   # {"BTC/USD": timestamp}
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
    ts = datetime.utcnow().strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️", "TRADE": "💰", "WIN": "✅", "LOSS": "🔴",
             "WARN": "⚠️", "ERROR": "❌", "ORACLE": "🔮", "KILL": "🛑"}
    print(f"[{ts}] {icons.get(level, '📌')} {msg}")


def http_get(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "oracle-arb/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"HTTP error: {e}", "WARN")
        return None


def save_log():
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "oracle_prices": state["oracle_prices"],
                "trades": state["trade_log"][-200:],
                "stats": {
                    "trades_today": state["trades_today"],
                    "daily_pnl": round(state["daily_pnl"], 2),
                    "current_capital": round(state["current_capital"], 2),
                }
            }, f, indent=2, default=str)
    except Exception:
        pass


# ══════════════════════════════════════════
# Chainlink Oracle — قراءة الأسعار
# ══════════════════════════════════════════
def get_w3():
    from web3 import Web3
    for rpc in RPCS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
            if w3.is_connected():
                return w3
        except Exception:
            continue
    return None


def fetch_oracle_prices():
    """يقرأ أسعار Chainlink من البلوكتشين مباشرة."""
    from web3 import Web3
    w3 = get_w3()
    if not w3:
        log("فشل الاتصال بـ Polygon RPC", "ERROR")
        return False

    for pair, feed_addr in CHAINLINK_FEEDS.items():
        try:
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(feed_addr),
                abi=AGGREGATOR_ABI,
            )
            decimals = contract.functions.decimals().call()
            round_data = contract.functions.latestRoundData().call()

            price = round_data[1] / (10 ** decimals)
            updated_at = round_data[3]

            state["oracle_prices"][pair] = price
            state["oracle_updated_at"][pair] = updated_at

        except Exception as e:
            log(f"خطأ Oracle {pair}: {e}", "ERROR")

    return len(state["oracle_prices"]) > 0


# ══════════════════════════════════════════
# Polymarket — عقود الكريبتو
# ══════════════════════════════════════════
def fetch_crypto_contracts():
    """يجلب عقود BTC/ETH من Polymarket."""
    data = http_get(
        f"{GAMMA_API}/markets?active=true&closed=false"
        f"&limit=50&order=volume24hr&ascending=false"
    )
    if not data:
        return []

    markets = data if isinstance(data, list) else data.get("markets", data)
    contracts = []

    for m in markets:
        q = str(m.get("question", "")).lower()

        # تحديد الزوج
        pair = None
        if "bitcoin" in q or "btc" in q:
            pair = "BTC/USD"
        elif "ethereum" in q or "eth" in q:
            pair = "ETH/USD"
        else:
            continue

        # لازم يكون سؤال سعري
        has_price_ref = False
        target_price = 0
        for word in q.replace(",", "").replace("$", "").split():
            try:
                val = float(word)
                if val > 1000:  # سعر BTC أو ETH
                    target_price = val
                    has_price_ref = True
                    break
            except ValueError:
                continue

        is_direction = ("higher" in q or "lower" in q or "above" in q or
                       "below" in q or "up" in q or "down" in q)

        if not (has_price_ref or is_direction):
            continue

        # فلتر وقت الانتهاء
        end_str = m.get("endDateIso") or m.get("endDate") or ""
        mins_left = 999
        if end_str:
            try:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00")).replace(tzinfo=None)
                mins_left = (end_dt - datetime.utcnow()).total_seconds() / 60
            except Exception:
                pass
        if mins_left < 2 or mins_left > 60:
            continue

        # سيولة
        liq = float(m.get("liquidityNum") or m.get("liquidity", 0) or 0)
        if liq < CONFIG["min_liquidity"]:
            continue

        outcomes = m.get("outcomePrices") or []
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except Exception:
                continue
        if len(outcomes) < 2:
            continue

        contracts.append({
            "market": m,
            "question": m.get("question", ""),
            "pair": pair,
            "target_price": target_price,
            "yes_price": float(outcomes[0]),
            "no_price": float(outcomes[1]),
            "mins_left": round(mins_left, 1),
            "liquidity": liq,
            "market_id": m.get("conditionId") or m.get("id", ""),
        })

    return contracts


# ══════════════════════════════════════════
# محرك الأربيتراج
# ══════════════════════════════════════════
def find_oracle_edge(contract):
    """
    يقارن سعر Chainlink الحقيقي بسعر العقد على Polymarket.
    إذا Oracle يقول BTC = $67,200 لكن عقد "BTC above $67,000"
    يتداول عند YES=0.55 — فالاحتمال الحقيقي أعلى بكثير.
    """
    pair = contract["pair"]
    oracle_price = state["oracle_prices"].get(pair)
    if not oracle_price:
        return None, None, 0

    q = contract["question"].lower()
    target = contract["target_price"]
    yes_p = contract["yes_price"]
    no_p = contract["no_price"]

    if target <= 0:
        # عقود up/down بدون سعر محدد — نستخدم حركة السعر
        return None, None, 0

    # كم يبعد السعر الحالي عن الهدف
    diff_pct = (oracle_price - target) / target

    is_above_q = "above" in q or "higher" in q or "over" in q
    is_below_q = "below" in q or "lower" in q or "under" in q

    if is_above_q:
        if diff_pct > 0.001:  # Oracle أعلى من الهدف
            # YES هو الجانب الصحيح
            # كلما كان الفرق أكبر، كلما كان الاحتمال أعلى
            true_prob = min(0.95, 0.60 + abs(diff_pct) * 20)
            edge = true_prob - yes_p
            if edge >= CONFIG["min_edge_pct"]:
                return "YES", edge, true_prob
        elif diff_pct < -0.001:  # Oracle أقل من الهدف
            true_prob = min(0.95, 0.60 + abs(diff_pct) * 20)
            edge = true_prob - no_p
            if edge >= CONFIG["min_edge_pct"]:
                return "NO", edge, true_prob

    elif is_below_q:
        if diff_pct < -0.001:  # Oracle أقل من الهدف
            true_prob = min(0.95, 0.60 + abs(diff_pct) * 20)
            edge = true_prob - yes_p
            if edge >= CONFIG["min_edge_pct"]:
                return "YES", edge, true_prob
        elif diff_pct > 0.001:
            true_prob = min(0.95, 0.60 + abs(diff_pct) * 20)
            edge = true_prob - no_p
            if edge >= CONFIG["min_edge_pct"]:
                return "NO", edge, true_prob

    return None, None, 0


def risk_check():
    if state["halted"]:
        return False, state["halt_reason"]
    if state["trades_today"] >= CONFIG["max_trades_per_day"]:
        return False, "الحد اليومي"
    if state["daily_pnl"] <= -(CAPITAL * CONFIG["daily_loss_limit_pct"]):
        state["halted"] = True
        state["halt_reason"] = "خسارة يومية"
        return False, state["halt_reason"]
    drawdown = (state["peak_capital"] - state["current_capital"]) / state["peak_capital"] if state["peak_capital"] > 0 else 0
    if drawdown >= CONFIG["max_drawdown_pct"]:
        state["halted"] = True
        state["halt_reason"] = f"KILL SWITCH: drawdown {drawdown:.0%}"
        log(state["halt_reason"], "KILL")
        return False, state["halt_reason"]
    if len(state["positions"]) >= CONFIG["max_positions"]:
        return False, "أقصى مراكز"
    if time.time() - state["last_trade_time"] < CONFIG["cooldown_sec"]:
        return False, "cooldown"
    return True, "OK"


def execute_trade(contract, side, edge, true_prob):
    """ينفذ صفقة Oracle Arb."""
    price = contract["yes_price"] if side == "YES" else contract["no_price"]
    price = round(price, 2)
    if price <= 0.01 or price >= 0.99:
        return False

    size_usd = min(
        CONFIG["max_trade_size_usd"],
        max(CONFIG["min_trade_size_usd"],
            state["current_capital"] * CONFIG["trade_size_pct"])
    )
    size_usd = round(size_usd, 2)
    size_contracts = round(size_usd / price, 1)

    pair = contract["pair"]
    oracle_p = state["oracle_prices"].get(pair, 0)
    q = contract["question"][:50]

    log(f"🔮 ORACLE ARB: {side} {q}", "ORACLE")
    log(f"   Oracle {pair}: ${oracle_p:,.0f} | Target: ${contract['target_price']:,.0f}", "ORACLE")
    log(f"   Edge: {edge:.1%} | Prob: {true_prob:.0%} | ${size_usd:.2f}", "ORACLE")

    record = {
        "time": datetime.utcnow().isoformat(),
        "question": contract["question"][:60],
        "pair": pair,
        "side": side,
        "price": price,
        "size_usd": size_usd,
        "edge": round(edge, 4),
        "oracle_price": oracle_p,
        "target_price": contract["target_price"],
        "true_prob": round(true_prob, 3),
        "market_id": contract["market_id"],
    }

    if PAPER_MODE:
        log(f"   📋 [PAPER] محاكاة", "TRADE")
        record["mode"] = "paper"
        state["trade_log"].append(record)
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

        market = contract["market"]
        token_id = None
        tokens = market.get("tokens") or []
        if isinstance(tokens, str):
            try:
                tokens = json.loads(tokens)
            except Exception:
                tokens = []
        for t in tokens:
            outcome = str(t.get("outcome", "")).upper()
            tid = t.get("token_id") or t.get("tokenId") or t.get("id")
            if side == "YES" and outcome in ("YES", "1", "TRUE"):
                token_id = str(tid)
                break
            if side == "NO" and outcome in ("NO", "0", "FALSE"):
                token_id = str(tid)
                break

        if not token_id:
            cid = contract["market_id"]
            data = http_get(f"{CLOB_API}/markets/{cid}")
            if data:
                for t in (data.get("tokens") or []):
                    outcome = str(t.get("outcome", "")).upper()
                    tid = t.get("token_id") or t.get("tokenId")
                    if side == "YES" and outcome in ("YES", "1"):
                        token_id = str(tid)
                        break
                    if side == "NO" and outcome in ("NO", "0"):
                        token_id = str(tid)
                        break

        if not token_id:
            log("لم يُعثر على token_id", "ERROR")
            return False

        order = client.create_order(OrderArgs(
            token_id=token_id, price=price,
            size=size_contracts, side=BUY,
        ))
        resp = client.post_order(order)
        log(f"   ✅ تم: {resp}", "TRADE")

        record["mode"] = "live"
        record["response"] = str(resp)[:100]
        state["positions"].append(record)
        state["trade_log"].append(record)
        state["trades_today"] += 1
        state["last_trade_time"] = time.time()
        save_log()
        return True

    except Exception as e:
        log(f"   ❌ فشل: {e}", "ERROR")
        record["error"] = str(e)[:100]
        state["trade_log"].append(record)
        save_log()
        return False


# ══════════════════════════════════════════
# الحلقة الرئيسية
# ══════════════════════════════════════════
def main_loop():
    cycle = 0
    while not state["halted"]:
        cycle += 1

        # 1. قراءة Oracle
        fetch_oracle_prices()

        if not state["oracle_prices"]:
            log("لا توجد أسعار Oracle — إعادة المحاولة...", "WARN")
            time.sleep(10)
            continue

        # 2. فحص المخاطر
        ok, reason = risk_check()
        if not ok:
            if "cooldown" not in reason:
                log(f"⏸️ {reason}")
            time.sleep(CONFIG["poll_interval_sec"])
            continue

        # 3. جلب عقود Polymarket
        contracts = fetch_crypto_contracts()

        # 4. البحث عن فرصة
        best_edge = 0
        best_contract = None
        best_side = None
        best_prob = 0

        for c in contracts:
            side, edge, prob = find_oracle_edge(c)
            if side and edge and edge > best_edge:
                best_edge = edge
                best_contract = c
                best_side = side
                best_prob = prob

        if best_contract:
            execute_trade(best_contract, best_side, best_edge, best_prob)
        else:
            if cycle % 6 == 0:  # كل دقيقة
                btc = state["oracle_prices"].get("BTC/USD", 0)
                eth = state["oracle_prices"].get("ETH/USD", 0)
                log(f"🔮 Oracle: BTC ${btc:,.0f} | ETH ${eth:,.0f} | عقود: {len(contracts)} | لا فرصة")

        time.sleep(CONFIG["poll_interval_sec"])


def main():
    mode = "📋 PAPER" if PAPER_MODE else "💰 LIVE"
    print(f"""
╔══════════════════════════════════════════╗
║   🔮 Polymarket Oracle Arbitrage Bot     ║
║   رأس المال: ${CAPITAL:.2f}                  ║
║   الوضع: {mode}                         ║
║   المصدر: Chainlink Oracle (on-chain)   ║
╚══════════════════════════════════════════╝
""")

    if not PRIVATE_KEY and not PAPER_MODE:
        print("❌ POLYGON_PRIVATE_KEY مطلوب")
        print("   أو: python oracle_arb_bot.py --paper")
        return

    if "--check" in sys.argv:
        log("🔍 فحص Oracle...")
        ok = fetch_oracle_prices()
        if ok:
            for pair, price in state["oracle_prices"].items():
                log(f"   {pair}: ${price:,.2f}")
        contracts = fetch_crypto_contracts()
        log(f"✅ Polymarket: {len(contracts)} عقود كريبتو")
        for c in contracts[:5]:
            log(f"   {c['question'][:50]} | YES:{c['yes_price']:.2f}")
        return

    # تحقق من web3
    try:
        from web3 import Web3
    except ImportError:
        os.system(f"{sys.executable} -m pip install web3 -q")

    log(f"Edge الأدنى: {CONFIG['min_edge_pct']:.0%}")
    log(f"Kill switch: {CONFIG['max_drawdown_pct']:.0%}")

    # فحص أولي
    log("🔌 قراءة Chainlink Oracle...")
    if fetch_oracle_prices():
        for pair, price in state["oracle_prices"].items():
            log(f"   ✅ {pair}: ${price:,.2f}")
    else:
        log("❌ فشل قراءة Oracle", "ERROR")
        return

    log("🚀 بدء البحث عن فرص Oracle Arbitrage...\n")

    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n🛑 تم الإيقاف")
        print(f"   صفقات: {state['trades_today']} | P&L: ${state['daily_pnl']:+.2f}")
        save_log()


if __name__ == "__main__":
    main()
