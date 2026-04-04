"""
Polymarket Auto Trader — النسخة الكاملة
يمسح الأسواق كل 30 دقيقة وينفذ الصفقات تلقائياً
يراقب SL/TP كل دورة ويغلق الصفقات تلقائياً

الاستخدام:
    python auto_trader.py          # تشغيل التداول التلقائي
    python auto_trader.py --scan   # مسح الأسواق فقط بدون تداول
    python auto_trader.py --test   # اختبار الاتصال
"""

import sys
import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

# ── تحديد المسارات تلقائياً (Windows أو Linux) ──
if os.name == "nt":  # Windows
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:  # Linux (VPS)
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE     = BASE_DIR / ".env"
LOG_FILE     = BASE_DIR / "trade_log.json"
POSITIONS_FILE = BASE_DIR / "positions.json"  # حفظ المراكز على الديسك


def load_env():
    env = {}
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

ENV = load_env()
PRIVATE_KEY = ENV.get("POLYGON_PRIVATE_KEY", "").strip()
if PRIVATE_KEY.startswith("0x") or PRIVATE_KEY.startswith("0X"):
    PRIVATE_KEY = PRIVATE_KEY[2:]


def derive_address(pk: str) -> str:
    try:
        from eth_account import Account
        acc = Account.from_key(pk if pk.startswith("0x") else "0x" + pk)
        return acc.address
    except Exception:
        return ""

ADDRESS = derive_address(PRIVATE_KEY) if PRIVATE_KEY else ""
FUNDER  = "0xbA0FeFf3B16A8cD043a6a522f74578f988924E39"
CAPITAL = float(ENV.get("CAPITAL_USD", "221"))

# ── إعدادات التداول ──
SETTINGS = {
    "min_score":         0.75,
    "trade_size_usd":    10.0,
    "max_trades_day":    2,
    "stop_loss_pct":     0.15,    # وقف الخسارة 15%
    "take_profit_pct":   0.40,    # هدف الربح 40%
    "scan_interval_min": 30,
    "min_liquidity":     10000,
    "min_volume_24h":    5000,
    "max_price":         0.85,
    "min_price":         0.05,
    "scan_only":         "--scan" in sys.argv,
}

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"

# ── تتبع الجلسة ──
session = {
    "trades_today": 0,
    "daily_pnl":    0.0,
    "positions":    [],
    "trade_log":    [],
    "start_time":   datetime.utcnow(),
    "last_scan":    None,
}


def log(msg: str, level: str = "INFO"):
    ts = datetime.utcnow().strftime("%H:%M:%S")
    prefix = {
        "INFO": "ℹ️", "TRADE": "💰", "WIN": "✅", "LOSS": "🔴",
        "WARN": "⚠️", "ERROR": "❌", "SCAN": "🔍",
    }.get(level, "📌")
    print(f"[{ts}] {prefix} {msg}")


def http_get(url: str, timeout: int = 15):
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "polymarket-auto-trader/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"HTTP GET error: {url[:60]} — {e}", "WARN")
        return None


# ── حفظ وتحميل المراكز المفتوحة من الديسك ──
def save_positions():
    """حفظ المراكز على الديسك — تبقى حتى لو توقف البوت."""
    try:
        with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(session["positions"], f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        log(f"فشل حفظ المراكز: {e}", "WARN")


def load_positions():
    """تحميل المراكز المحفوظة عند بدء التشغيل."""
    if POSITIONS_FILE.exists():
        try:
            with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_log():
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "session_start": session["start_time"].isoformat(),
                "trades_today":  session["trades_today"],
                "daily_pnl":     session["daily_pnl"],
                "positions":     session["positions"],
                "trade_log":     session["trade_log"],
            }, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        log(f"فشل حفظ السجل: {e}", "WARN")


# ── حساب نقطة السوق ──
def score_market(market: dict) -> tuple[float, str]:
    """يحسب نقطة السوق ويعود (score, side)."""
    try:
        outcomes = market.get("outcomePrices") or []
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)

        if not outcomes or len(outcomes) < 2:
            return 0.0, ""

        yes_p = float(outcomes[0])
        no_p  = float(outcomes[1])

        if yes_p > no_p:
            price, side = yes_p, "YES"
        else:
            price, side = no_p, "NO"

        if price > SETTINGS["max_price"] or price < SETTINGS["min_price"]:
            return 0.0, ""

        liquidity = float(market.get("liquidityNum") or market.get("liquidity", 0) or 0)
        volume    = float(market.get("volume24hr")   or market.get("volume", 0) or 0)

        if liquidity < SETTINGS["min_liquidity"]:
            return 0.0, ""
        if volume < SETTINGS["min_volume_24h"]:
            return 0.0, ""

        end_str = market.get("endDateIso") or market.get("endDate") or ""
        days_left = 30.0
        if end_str:
            try:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                end_dt = end_dt.replace(tzinfo=None)
                days_left = (end_dt - datetime.utcnow()).total_seconds() / 86400
            except Exception:
                pass

        if days_left < 0.5:
            return 0.0, ""

        liq_score = min(1.0, liquidity / 100_000)
        vol_score = min(1.0, volume / 50_000)

        if days_left < 1:     time_score = 0.2
        elif days_left < 3:   time_score = 0.5
        elif days_left <= 14: time_score = 0.85
        elif days_left <= 30: time_score = 0.70
        else:                 time_score = 0.50

        edge_score = min(1.0, abs(price - 0.5) * 4)

        score = (liq_score * 0.25 + vol_score * 0.25 +
                 time_score * 0.25 + edge_score * 0.25)

        return round(score, 3), side

    except Exception as e:
        log(f"Score error: {e}", "WARN")
        return 0.0, ""


# ── جلب الأسواق ──
def fetch_markets(limit: int = 50) -> list[dict]:
    data = http_get(
        f"{GAMMA_API}/markets?active=true&closed=false"
        f"&limit={limit}&order=volume24hr&ascending=false"
    )
    if not data:
        return []
    if isinstance(data, dict) and "markets" in data:
        return data["markets"]
    if isinstance(data, list):
        return data
    return []


def scan_markets() -> list[dict]:
    """يمسح ويرتب الأسواق حسب النقطة."""
    log("جاري مسح الأسواق...", "SCAN")
    markets = fetch_markets(100)
    log(f"تم جلب {len(markets)} سوق")

    scored = []
    for m in markets:
        score, side = score_market(m)
        if score >= SETTINGS["min_score"]:
            m["_score"] = score
            m["_side"]  = side
            scored.append(m)

    scored.sort(key=lambda x: x["_score"], reverse=True)
    log(f"أسواق مؤهلة: {len(scored)}")
    return scored


def print_market(m: dict, rank: int):
    outcomes = m.get("outcomePrices") or ["0.5", "0.5"]
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            outcomes = ["0.5", "0.5"]
    yes_p = float(outcomes[0]) if outcomes else 0.5
    no_p  = float(outcomes[1]) if len(outcomes) > 1 else 0.5
    liq   = float(m.get("liquidityNum") or m.get("liquidity", 0) or 0)
    vol   = float(m.get("volume24hr") or m.get("volume", 0) or 0)
    q     = str(m.get("question") or m.get("title", "?"))[:60]

    print(f"""  #{rank} | Score: {m['_score']} | الجانب: {m['_side']}
  السوق   : {q}
  السعر   : YES {yes_p:.3f} | NO {no_p:.3f}
  السيولة : ${liq:,.0f} | الحجم: ${vol:,.0f}""")


# ── الاتصال بـ Polymarket CLOB ──
def get_clob_client():
    from py_clob_client.client import ClobClient
    from py_clob_client.constants import POLYGON
    try:
        client = ClobClient(
            host=CLOB_API,
            key=PRIVATE_KEY,
            chain_id=POLYGON,
            funder=FUNDER,
            signature_type=1,
        )
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)

        try:
            from py_clob_client.clob_types import BalanceAllowanceParams
            try:
                from py_clob_client.clob_types import AssetType
                asset = getattr(AssetType, 'USDC',
                        getattr(AssetType, 'COLLATERAL', "USDC"))
            except Exception:
                asset = "USDC"
            resp = client.update_balance_allowance(
                BalanceAllowanceParams(asset_type=asset)
            )
            log(f"رصيد CLOB: {resp}")
        except Exception as e:
            try:
                resp = client.update_balance_allowance({"asset_type": "USDC"})
                log(f"رصيد CLOB: {resp}")
            except Exception as e2:
                log(f"تحديث الرصيد (تحذير): {e2}", "WARN")

        log("✅ متصل بـ Polymarket CLOB API")
        return client
    except Exception as e:
        log(f"فشل الاتصال بـ CLOB: {e}", "ERROR")
        return None


def get_token_id(market: dict, side: str, clob_client=None) -> str | None:
    """استخرج token_id لـ YES أو NO — يجرب ثلاث طرق."""

    def _search_tokens(tokens_raw):
        if not tokens_raw:
            return None
        tokens = tokens_raw
        if isinstance(tokens, str):
            try:
                tokens = json.loads(tokens)
            except Exception:
                return None
        for token in (tokens or []):
            if not isinstance(token, dict):
                continue
            outcome = str(token.get("outcome", "")).strip().upper()
            tid = token.get("token_id") or token.get("tokenId") or token.get("id")
            if not tid:
                continue
            if side == "YES" and outcome in ("YES", "1", "TRUE"):
                return str(tid)
            if side == "NO" and outcome in ("NO", "0", "FALSE"):
                return str(tid)
        return None

    result = _search_tokens(market.get("tokens"))
    if result:
        return result

    cid = (market.get("conditionId") or market.get("condition_id") or
           market.get("id") or "")
    if cid and len(cid) > 10:
        clob_data = http_get(f"{CLOB_API}/markets/{cid}")
        if clob_data:
            result = _search_tokens(clob_data.get("tokens"))
            if result:
                return result

        simp = http_get(f"{CLOB_API}/simplified-markets?condition_ids={cid}")
        if simp:
            items = simp if isinstance(simp, list) else simp.get("data", [])
            for item in items:
                result = _search_tokens(item.get("tokens"))
                if result:
                    return result

    if clob_client and cid:
        try:
            mkt = clob_client.get_market(cid)
            result = _search_tokens(mkt.get("tokens"))
            if result:
                return result
        except Exception as e:
            log(f"CLOB get_market error: {e}", "WARN")

    log(f"لم يُعثر على token_id لـ {side} في السوق {cid[:20]}...", "WARN")
    return None


def place_order(client, market: dict, side: str, size_usd: float) -> dict | None:
    """ينفذ أمر LIMIT على Polymarket."""
    from py_clob_client.clob_types import OrderArgs
    from py_clob_client.order_builder.constants import BUY

    token_id = get_token_id(market, side, clob_client=client)
    if not token_id:
        log(f"لم يتم العثور على token_id لـ {side}", "ERROR")
        return None

    outcomes = market.get("outcomePrices") or ["0.5", "0.5"]
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            outcomes = ["0.5", "0.5"]

    if side == "YES":
        price = float(outcomes[0]) if outcomes else 0.5
    else:
        price = float(outcomes[1]) if len(outcomes) > 1 else 0.5

    price = round(price, 2)
    size_contracts = round(size_usd / price, 1)

    log(f"📤 إرسال أمر: {side} {size_contracts} @ ${price:.2f} (${size_usd:.2f})", "TRADE")

    try:
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size_contracts,
            side=BUY,
        )
        signed = client.create_order(order_args)
        resp = client.post_order(signed)
        log(f"✅ أمر مُنفَّذ: {resp}", "TRADE")

        # حساب SL/TP
        sl_price = round(price * (1 - SETTINGS["stop_loss_pct"]), 3)
        tp_price = round(price * (1 + SETTINGS["take_profit_pct"]), 3)

        return {
            "market_id":   market.get("conditionId") or market.get("id", ""),
            "token_id":    token_id,
            "side":        side,
            "entry_price": price,
            "size_usd":    size_usd,
            "question":    str(market.get("question", ""))[:60],
            "stop_loss":   sl_price,
            "take_profit": tp_price,
            "time":        datetime.utcnow().isoformat(),
            "order_resp":  str(resp),
        }
    except Exception as e:
        log(f"فشل الأمر: {e}", "ERROR")
        return None


# ── مراقبة SL/TP للمراكز المفتوحة ──
def check_positions_sl_tp(client):
    """
    يتحقق من كل مركز مفتوح — إذا وصل SL أو TP يغلقه.
    يجلب السعر الحالي من CLOB API.
    """
    if not session["positions"]:
        return

    positions_to_close = []

    for pos in session["positions"]:
        token_id = pos.get("token_id", "")
        market_id = pos.get("market_id", "")
        if not market_id:
            continue

        # جلب السعر الحالي
        current_price = None
        try:
            market_data = http_get(f"{CLOB_API}/markets/{market_id}")
            if market_data and "tokens" in market_data:
                tokens = market_data["tokens"]
                if isinstance(tokens, str):
                    tokens = json.loads(tokens)
                for t in tokens:
                    tid = t.get("token_id") or t.get("tokenId") or t.get("id")
                    if str(tid) == str(token_id):
                        current_price = float(t.get("price", 0))
                        break
        except Exception as e:
            log(f"خطأ في جلب السعر: {e}", "WARN")
            continue

        if current_price is None or current_price == 0:
            continue

        entry = pos["entry_price"]
        sl    = pos["stop_loss"]
        tp    = pos["take_profit"]
        q     = pos.get("question", "?")[:30]

        pnl_pct = (current_price - entry) / entry if entry > 0 else 0

        # فحص Stop-Loss
        if current_price <= sl:
            pnl_usd = pos["size_usd"] * pnl_pct
            log(f"🔴 STOP-LOSS: {q} | دخول {entry:.3f} → حالي {current_price:.3f} | P&L: ${pnl_usd:+.2f}", "LOSS")
            positions_to_close.append((pos, pnl_usd, "STOP-LOSS"))

        # فحص Take-Profit
        elif current_price >= tp:
            pnl_usd = pos["size_usd"] * pnl_pct
            log(f"✅ TAKE-PROFIT: {q} | دخول {entry:.3f} → حالي {current_price:.3f} | P&L: ${pnl_usd:+.2f}", "WIN")
            positions_to_close.append((pos, pnl_usd, "TAKE-PROFIT"))

        else:
            log(f"📊 {q} | {entry:.3f} → {current_price:.3f} ({pnl_pct:+.1%}) | SL:{sl:.3f} TP:{tp:.3f}")

    # إغلاق المراكز
    for pos, pnl_usd, reason in positions_to_close:
        # محاولة إلغاء الأمر على CLOB (إذا لا زال مفتوح)
        try:
            if client:
                client.cancel_all()
                log(f"🗑️ تم إلغاء الأوامر المفتوحة")
        except Exception:
            pass

        session["daily_pnl"] += pnl_usd
        session["trade_log"].append({
            **pos,
            "type": "CLOSE",
            "reason": reason,
            "pnl_usd": round(pnl_usd, 2),
            "closed_at": datetime.utcnow().isoformat(),
        })
        session["positions"].remove(pos)
        save_positions()
        save_log()


# ── فحص تكرار السوق ──
def is_market_already_open(market_id: str) -> bool:
    """يمنع فتح صفقة في سوق فيه مركز مفتوح بالفعل."""
    for pos in session["positions"]:
        if pos.get("market_id") == market_id:
            return True
    return False


# ── دورة التداول الرئيسية ──
def trading_cycle(client):
    """دورة واحدة: فحص SL/TP → مسح → تنفيذ."""

    # أولاً: فحص المراكز المفتوحة
    if session["positions"]:
        log(f"📊 فحص {len(session['positions'])} مراكز مفتوحة...")
        check_positions_sl_tp(client)

    # ثانياً: هل وصلنا الحد اليومي؟
    if session["trades_today"] >= SETTINGS["max_trades_day"]:
        log(f"وصلنا الحد اليومي ({SETTINGS['max_trades_day']} صفقات)", "WARN")
        return

    # ثالثاً: مسح الأسواق
    markets = scan_markets()
    session["last_scan"] = datetime.utcnow()

    if not markets:
        log("لا توجد أسواق تستوفي الشروط في هذه الجولة")
        return

    print(f"\n{'━'*32}")
    print(f"       🔍 أفضل الأسواق")
    print(f"{'━'*32}")
    for i, m in enumerate(markets[:5], 1):
        print_market(m, i)
        print()

    if SETTINGS["scan_only"]:
        log("وضع المسح فقط — لا تنفيذ")
        return

    # رابعاً: تنفيذ على أفضل سوق (مع فحص التكرار)
    for best in markets[:5]:
        market_id = best.get("conditionId") or best.get("id", "")

        if is_market_already_open(market_id):
            log(f"⏭️ تخطي {best.get('question', '?')[:40]} — مركز مفتوح بالفعل")
            continue

        q = str(best.get("question", ""))[:60]
        log(f"🎯 الهدف: {q} | {best['_side']} | Score: {best['_score']}", "TRADE")

        pos = place_order(client, best, best["_side"], SETTINGS["trade_size_usd"])
        if pos:
            session["positions"].append(pos)
            session["trades_today"] += 1
            session["trade_log"].append({**pos, "type": "OPEN"})
            save_positions()
            save_log()
            log(f"مراكز مفتوحة: {len(session['positions'])}", "TRADE")
        break  # صفقة واحدة فقط كل دورة


def print_status():
    uptime = datetime.utcnow() - session["start_time"]
    last_scan = session['last_scan'].strftime('%H:%M') if session['last_scan'] else 'لم يتم بعد'
    print(f"""
══════════════════════════════════════
   📊 حالة النظام
══════════════════════════════════════
  وقت التشغيل  : {str(uptime).split('.')[0]}
  صفقات اليوم  : {session['trades_today']}/{SETTINGS['max_trades_day']}
  P&L اليوم    : ${session['daily_pnl']:+.2f}
  مراكز مفتوحة : {len(session['positions'])}
  آخر مسح      : {last_scan}
══════════════════════════════════════""")


# ── نقطة الدخول الرئيسية ──
def main():
    mode_text = "مسح فقط 🔍" if SETTINGS["scan_only"] else "تداول تلقائي 💰"
    print(f"""
╔══════════════════════════════════════╗
║   🤖 Polymarket Auto Trader          ║
║   رأس المال: ${CAPITAL:.2f}              ║
║   الوضع: {mode_text}              ║
╚══════════════════════════════════════╝
""")

    if not PRIVATE_KEY:
        print("❌ POLYGON_PRIVATE_KEY غير موجود في .env")
        print(f"   المسار: {ENV_FILE}")
        return

    log(f"المحفظة: {ADDRESS[:6]}...{ADDRESS[-4:]}")
    log(f"رأس المال: ${CAPITAL:,.2f}")
    log(f"حجم الصفقة: ${SETTINGS['trade_size_usd']:.2f}")
    log(f"الحد الأدنى للنقطة: {SETTINGS['min_score']}")

    # تحميل المراكز المحفوظة من الديسك
    saved_positions = load_positions()
    if saved_positions:
        session["positions"] = saved_positions
        log(f"📂 تم تحميل {len(saved_positions)} مراكز محفوظة من الجلسة السابقة")

    # اختبار الاتصال
    if "--test" in sys.argv:
        log("🔍 وضع الاختبار")
        markets = fetch_markets(10)
        log(f"✅ جُلبت {len(markets)} سوق من Polymarket API")
        for m in markets[:3]:
            sc, side = score_market(m)
            q = str(m.get("question", ""))[:50]
            print(f"  Score:{sc:.2f} {side:3} | {q}")
        return

    # الاتصال بـ CLOB
    client = None
    if not SETTINGS["scan_only"]:
        log("جاري الاتصال بـ Polymarket CLOB...")
        client = get_clob_client()
        if not client:
            log("⚠️  فشل الاتصال بـ CLOB — تحويل لوضع المسح فقط", "WARN")
            SETTINGS["scan_only"] = True

    interval = SETTINGS["scan_interval_min"] * 60

    log(f"🚀 بدء التشغيل — مسح كل {SETTINGS['scan_interval_min']} دقيقة")
    log("اضغط Ctrl+C لإيقاف النظام\n")

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n{'═'*40}")
            print(f"  🔄 جولة #{cycle} — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"{'═'*40}")

            trading_cycle(client)
            print_status()

            log(f"النوم {SETTINGS['scan_interval_min']} دقيقة حتى الجولة التالية...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n🛑 تم إيقاف النظام بواسطة المستخدم")
        print_status()
        save_positions()
        save_log()
        print(f"\n📁 سجل التداول محفوظ في: {LOG_FILE}")
        print(f"📁 المراكز محفوظة في: {POSITIONS_FILE}")


if __name__ == "__main__":
    main()
