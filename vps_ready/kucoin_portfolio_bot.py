"""
portfolio_bot.py — متابع محفظة KuCoin + Bybit + تنبيهات

يراقب محفظتك في المنصتين كل ساعتين:
- يحسب سعر الدخول المتوسط من تاريخ الصفقات
- يعرض الربح/الخسارة لكل عملة
- ينبهك إذا ارتفعت عملة 10% أو أكثر
- يرسل تقرير يومي

    python3 kucoin_portfolio_bot.py              # تشغيل
    python3 kucoin_portfolio_bot.py --report     # تقرير فوري
    python3 kucoin_portfolio_bot.py --check      # فحص الاتصال

    pip install ccxt python-dotenv requests
"""
from __future__ import annotations
import json, os, sys, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(r"C:\Users\xman9\Desktop") if os.name == "nt" else Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = BASE_DIR / ".env_monthly"
STATE_FILE = BASE_DIR / "portfolio_state.json"
LOG_FILE = BASE_DIR / "portfolio.log"
load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

KUCOIN_KEY = os.getenv("KUCOIN_API_KEY", "")
KUCOIN_SECRET = os.getenv("KUCOIN_API_SECRET", "")
KUCOIN_PASS = os.getenv("KUCOIN_PASSPHRASE", "")
BYBIT_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET = os.getenv("BYBIT_API_SECRET", "")
NOTIFY_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

ALERT_UP_PCT = float(os.getenv("PORTFOLIO_ALERT_UP_PCT", "10.0"))
ALERT_DOWN_PCT = float(os.getenv("PORTFOLIO_ALERT_DOWN_PCT", "10.0"))
CHECK_INTERVAL = int(os.getenv("PORTFOLIO_CHECK_SEC", "7200"))
DAILY_REPORT_HOUR = int(os.getenv("PORTFOLIO_REPORT_HOUR", "20"))
MIN_BALANCE_USDT = float(os.getenv("PORTFOLIO_MIN_USDT", "1.0"))

_IS_TTY = sys.stdin and sys.stdin.isatty()


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    if _IS_TTY:
        print(line, flush=True)
    try:
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(msg: str) -> None:
    if not NOTIFY_TOKEN or not NOTIFY_CHAT:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{NOTIFY_TOKEN}/sendMessage",
            json={"chat_id": NOTIFY_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log(f"خطأ إشعار: {e}")


def get_kucoin_exchange():
    import ccxt
    return ccxt.kucoin({
        "apiKey": KUCOIN_KEY,
        "secret": KUCOIN_SECRET,
        "password": KUCOIN_PASS,
        "options": {"defaultType": "spot"},
    })


def get_bybit_exchange():
    import ccxt
    return ccxt.bybit({
        "apiKey": BYBIT_KEY,
        "secret": BYBIT_SECRET,
        "options": {"defaultType": "spot"},
    })


def init_exchanges() -> dict:
    exchanges = {}
    if BYBIT_KEY:
        try:
            ex = get_bybit_exchange()
            ex.load_markets()
            exchanges["Bybit"] = ex
            log(f"Bybit متصل — {len(ex.markets)} زوج")
        except Exception as e:
            log(f"خطأ Bybit: {e}")
    if KUCOIN_KEY:
        try:
            ex = get_kucoin_exchange()
            ex.load_markets()
            exchanges["KuCoin"] = ex
            log(f"KuCoin متصل — {len(ex.markets)} زوج")
        except Exception as e:
            log(f"خطأ KuCoin: {e}")
    return exchanges


@dataclass
class PortfolioState:
    entry_prices: dict[str, float] = field(default_factory=dict)
    alerted_up: dict[str, float] = field(default_factory=dict)
    alerted_down: dict[str, float] = field(default_factory=dict)
    last_report_day: str = ""


def load_state() -> PortfolioState:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return PortfolioState(**{k: v for k, v in data.items()
                                    if k in PortfolioState.__dataclass_fields__})
        except Exception:
            pass
    return PortfolioState()


def save_state(state: PortfolioState):
    STATE_FILE.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2))


def calc_avg_entry(exchange, symbol: str) -> float | None:
    """متوسط سعر الشراء من آخر 500 صفقة — يحسب فقط صفقات الشراء"""
    pair = f"{symbol}/USDT"
    try:
        trades = exchange.fetch_my_trades(pair, limit=500)
        if not trades:
            return None
        buy_qty = 0.0
        buy_cost = 0.0
        for t in trades:
            if t["side"] == "buy":
                price = float(t["price"])
                amount = float(t["amount"])
                buy_qty += amount
                buy_cost += price * amount
        if buy_qty > 0 and buy_cost > 0:
            return buy_cost / buy_qty
    except Exception as e:
        log(f"خطأ جلب صفقات {symbol}: {e}")
    return None


def fetch_portfolio(exchanges: dict) -> list[dict]:
    holdings = []
    seen = set()
    usdt_balances = {}

    for ex_name, exchange in exchanges.items():
        try:
            balance = exchange.fetch_balance()
        except Exception as e:
            log(f"خطأ جلب رصيد {ex_name}: {e}")
            continue

        # رصيد USDT النقدي
        for stable in ("USDT", "USD", "USDC", "BUSD"):
            usdt_amt = float(balance.get("total", {}).get(stable, 0) or 0)
            if usdt_amt >= 1:
                usdt_balances[ex_name] = usdt_balances.get(ex_name, 0) + usdt_amt

        for symbol, info in balance.get("total", {}).items():
            amount = float(info) if info else 0.0
            if amount <= 0 or symbol in ("USDT", "USD", "USDC", "BUSD"):
                continue

            pair = f"{symbol}/USDT"
            try:
                ticker = exchange.fetch_ticker(pair)
                price = ticker.get("last")
                if not price:
                    continue
                price = float(price)
            except Exception:
                continue

            value = amount * price
            if value < MIN_BALANCE_USDT:
                continue

            key = f"{symbol}_{ex_name}"
            if key in seen:
                continue
            seen.add(key)

            holdings.append({
                "symbol": symbol,
                "pair": pair,
                "amount": amount,
                "price": price,
                "value": round(value, 2),
                "exchange": ex_name,
            })

    holdings.sort(key=lambda x: x["value"], reverse=True)
    return holdings, usdt_balances


def update_entry_prices(exchanges: dict, state: PortfolioState, holdings: list[dict]):
    for h in holdings:
        key = f"{h['symbol']}@{h['exchange']}"
        # أعد الحساب دائماً — عشان يعكس أي شراء جديد
        exchange = exchanges.get(h["exchange"])
        if not exchange:
            continue
        avg = calc_avg_entry(exchange, h["symbol"])
        if avg:
            if state.entry_prices.get(key) != round(avg, 8):
                log(f"سعر دخول {h['symbol']} [{h['exchange']}]: ${avg:.6f}")
            state.entry_prices[key] = round(avg, 8)
        elif key not in state.entry_prices:
            pass  # لا تمسح السعر المحفوظ يدوياً (مثل NIL)


def build_report(state: PortfolioState, holdings: list[dict], usdt_balances: dict) -> str:
    if not holdings and not usdt_balances:
        return "المحفظة فارغة"

    total_pnl = 0.0
    by_exchange = {}
    for h in holdings:
        by_exchange.setdefault(h["exchange"], []).append(h)

    # اجمع كل المنصات (عملات + USDT)
    all_exchanges = set(list(by_exchange.keys()) + list(usdt_balances.keys()))
    lines = ["<b>📊 تقرير المحفظة</b>\n"]
    grand_total = 0.0

    for ex_name in sorted(all_exchanges):
        ex_holdings = by_exchange.get(ex_name, [])
        ex_coins_value = sum(h["value"] for h in ex_holdings)
        ex_usdt = usdt_balances.get(ex_name, 0)
        ex_total = ex_coins_value + ex_usdt
        grand_total += ex_total

        lines.append(f"<b>━━ {ex_name} (${ex_total:.2f}) ━━</b>")

        # رصيد USDT النقدي أولاً
        if ex_usdt >= 1:
            lines.append(f"💵 <b>USDT</b>: ${ex_usdt:.2f}  (نقدي جاهز)")

        for h in ex_holdings:
            sym = h["symbol"]
            key = f"{sym}@{ex_name}"
            entry = state.entry_prices.get(key)
            price = h["price"]
            value = h["value"]

            if entry and entry > 0:
                pnl_pct = (price - entry) / entry * 100
                pnl_usdt = (price - entry) * h["amount"]
                total_pnl += pnl_usdt
                sign = "+" if pnl_pct >= 0 else ""
                emoji = "🟢" if pnl_pct >= 0 else "🔴"
                lines.append(
                    f"{emoji} <b>{sym}</b>: ${value:.2f}\n"
                    f"   دخول: ${entry:.6g} → حالي: ${price:.6g}\n"
                    f"   {sign}{pnl_pct:.1f}% ({sign}${pnl_usdt:.2f})"
                )
            else:
                lines.append(
                    f"⚪ <b>{sym}</b>: ${value:.2f}\n"
                    f"   سعر: ${price:.6g} (بدون سعر دخول)"
                )
        lines.append("")

    sign = "+" if total_pnl >= 0 else ""
    lines.append(f"<b>الإجمالي: ${grand_total:.2f}</b>")
    lines.append(f"<b>ربح/خسارة العملات: {sign}${total_pnl:.2f}</b>")
    return "\n".join(lines)


def check_alerts(state: PortfolioState, holdings: list[dict]):
    for h in holdings:
        sym = h["symbol"]
        key = f"{sym}@{h['exchange']}"
        entry = state.entry_prices.get(key)
        if not entry or entry <= 0:
            continue

        price = h["price"]
        pnl_pct = (price - entry) / entry * 100

        if pnl_pct >= ALERT_UP_PCT:
            last_alert = state.alerted_up.get(key, 0)
            level = int(pnl_pct / ALERT_UP_PCT) * ALERT_UP_PCT
            if level > last_alert:
                msg = (
                    f"🚀 <b>تنبيه ارتفاع!</b>\n"
                    f"<b>{sym}</b> [{h['exchange']}] ارتفع +{pnl_pct:.1f}%\n"
                    f"دخول: ${entry:.6g} → حالي: ${price:.6g}\n"
                    f"القيمة: ${h['value']:.2f}"
                )
                log(f"تنبيه ارتفاع: {sym} [{h['exchange']}] +{pnl_pct:.1f}%")
                notify(msg)
                state.alerted_up[key] = level
                save_state(state)

        elif pnl_pct <= -ALERT_DOWN_PCT:
            last_alert = state.alerted_down.get(key, 0)
            level = int(abs(pnl_pct) / ALERT_DOWN_PCT) * ALERT_DOWN_PCT
            if level > last_alert:
                msg = (
                    f"⚠️ <b>تنبيه انخفاض!</b>\n"
                    f"<b>{sym}</b> [{h['exchange']}] انخفض {pnl_pct:.1f}%\n"
                    f"دخول: ${entry:.6g} → حالي: ${price:.6g}\n"
                    f"القيمة: ${h['value']:.2f}"
                )
                log(f"تنبيه انخفاض: {sym} [{h['exchange']}] {pnl_pct:.1f}%")
                notify(msg)
                state.alerted_down[key] = level
                save_state(state)

        else:
            state.alerted_up.pop(key, None)
            state.alerted_down.pop(key, None)


def clean_stale_entries(state: PortfolioState, holdings: list[dict]):
    active = {f"{h['symbol']}@{h['exchange']}" for h in holdings}
    for key in list(state.entry_prices):
        if key not in active:
            del state.entry_prices[key]
            state.alerted_up.pop(key, None)
            state.alerted_down.pop(key, None)
            log(f"حذف {key} — ما عاد بالمحفظة")


def run_check():
    log("=== فحص الاتصال ===")
    exchanges = init_exchanges()
    if not exchanges:
        log("لا يوجد منصات متصلة!")
        return
    for ex_name, ex in exchanges.items():
        try:
            bal = ex.fetch_balance()
            usdt = float(bal.get("total", {}).get("USDT", 0))
            log(f"[{ex_name}] رصيد USDT: ${usdt:.2f}")
        except Exception as e:
            log(f"[{ex_name}] خطأ: {e}")
    holdings, usdt_balances = fetch_portfolio(exchanges)
    log(f"عملات بالمحفظة: {len(holdings)}")
    for h in holdings:
        log(f"  [{h['exchange']}] {h['symbol']}: {h['amount']:.4f} (${h['value']:.2f})")
    for ex, usdt in usdt_balances.items():
        log(f"  [{ex}] USDT نقدي: ${usdt:.2f}")


def run_report():
    exchanges = init_exchanges()
    state = load_state()
    holdings, usdt_balances = fetch_portfolio(exchanges)
    update_entry_prices(exchanges, state, holdings)
    save_state(state)
    report = build_report(state, holdings, usdt_balances)
    log(report.replace("<b>", "").replace("</b>", ""))
    notify(report)


def main():
    if "--check" in sys.argv:
        run_check()
        return
    if "--report" in sys.argv:
        run_report()
        return

    log("بدء متابع المحفظة...")
    exchanges = init_exchanges()
    if not exchanges:
        log("لا يوجد منصات! أضف المفاتيح في .env_monthly")
        return

    log(f"المنصات: {', '.join(exchanges.keys())}")
    state = load_state()

    holdings, usdt_balances = fetch_portfolio(exchanges)
    update_entry_prices(exchanges, state, holdings)
    save_state(state)
    log(f"عملات بالمحفظة: {len(holdings)}")
    for h in holdings:
        entry = state.entry_prices.get(f"{h['symbol']}@{h['exchange']}", 0)
        if entry:
            pnl = (h["price"] - entry) / entry * 100
            sign = "+" if pnl >= 0 else ""
            log(f"  [{h['exchange']}] {h['symbol']}: ${h['value']:.2f} ({sign}{pnl:.1f}%)")
        else:
            log(f"  [{h['exchange']}] {h['symbol']}: ${h['value']:.2f}")
    for ex, usdt in usdt_balances.items():
        log(f"  [{ex}] USDT نقدي: ${usdt:.2f}")

    report = build_report(state, holdings, usdt_balances)
    notify(report)
    log(f"تنبيهات: ↑{ALERT_UP_PCT}% ↓{ALERT_DOWN_PCT}% | فحص كل {CHECK_INTERVAL}s")

    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            holdings, usdt_balances = fetch_portfolio(exchanges)
            update_entry_prices(exchanges, state, holdings)
            check_alerts(state, holdings)
            clean_stale_entries(state, holdings)
            save_state(state)

            today = time.strftime("%Y-%m-%d")
            hour = int(time.strftime("%H"))
            if hour == DAILY_REPORT_HOUR and state.last_report_day != today:
                report = build_report(state, holdings, usdt_balances)
                notify(f"📋 <b>تقرير يومي</b>\n\n{report}")
                state.last_report_day = today
                save_state(state)
                log("تقرير يومي أُرسل")

        except Exception as e:
            log(f"خطأ: {e}")


if __name__ == "__main__":
    main()
