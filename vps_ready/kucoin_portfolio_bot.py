"""
kucoin_portfolio_bot.py — متابع محفظة KuCoin + تنبيهات

يراقب محفظتك في KuCoin كل 5 دقائق:
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


def get_exchange():
    import ccxt
    return ccxt.kucoin({
        "apiKey": KUCOIN_KEY,
        "secret": KUCOIN_SECRET,
        "password": KUCOIN_PASS,
        "options": {"defaultType": "spot"},
    })


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
    """حساب متوسط سعر الدخول من تاريخ الصفقات"""
    pair = f"{symbol}/USDT"
    try:
        trades = exchange.fetch_my_trades(pair, limit=100)
        if not trades:
            return None

        total_qty = 0.0
        total_cost = 0.0
        for t in trades:
            price = float(t["price"])
            amount = float(t["amount"])
            if t["side"] == "buy":
                total_qty += amount
                total_cost += price * amount
            elif t["side"] == "sell":
                total_qty -= amount
                total_cost -= price * amount

        if total_qty > 0 and total_cost > 0:
            return total_cost / total_qty
    except Exception as e:
        log(f"خطأ جلب صفقات {symbol}: {e}")
    return None


def fetch_portfolio(exchange) -> list[dict]:
    """جلب المحفظة الحالية مع الأسعار"""
    balance = exchange.fetch_balance()
    holdings = []

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

        holdings.append({
            "symbol": symbol,
            "pair": pair,
            "amount": amount,
            "price": price,
            "value": round(value, 2),
        })

    holdings.sort(key=lambda x: x["value"], reverse=True)
    return holdings


def update_entry_prices(exchange, state: PortfolioState, holdings: list[dict]):
    """تحديث أسعار الدخول من تاريخ الصفقات"""
    for h in holdings:
        sym = h["symbol"]
        if sym not in state.entry_prices:
            avg = calc_avg_entry(exchange, sym)
            if avg:
                state.entry_prices[sym] = round(avg, 8)
                log(f"سعر دخول {sym}: ${avg:.6f}")


def build_report(state: PortfolioState, holdings: list[dict]) -> str:
    """بناء تقرير المحفظة"""
    if not holdings:
        return "المحفظة فارغة"

    total_value = sum(h["value"] for h in holdings)
    total_pnl = 0.0
    lines = [f"<b>📊 محفظة KuCoin</b>\n"]

    for h in holdings:
        sym = h["symbol"]
        entry = state.entry_prices.get(sym)
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

    sign = "+" if total_pnl >= 0 else ""
    lines.append(f"\n<b>الإجمالي: ${total_value:.2f}</b>")
    lines.append(f"<b>الربح/الخسارة: {sign}${total_pnl:.2f}</b>")
    return "\n".join(lines)


def check_alerts(state: PortfolioState, holdings: list[dict]):
    """فحص التنبيهات — ارتفاع أو انخفاض"""
    for h in holdings:
        sym = h["symbol"]
        entry = state.entry_prices.get(sym)
        if not entry or entry <= 0:
            continue

        price = h["price"]
        pnl_pct = (price - entry) / entry * 100

        if pnl_pct >= ALERT_UP_PCT:
            last_alert = state.alerted_up.get(sym, 0)
            level = int(pnl_pct / ALERT_UP_PCT) * ALERT_UP_PCT
            if level > last_alert:
                msg = (
                    f"🚀 <b>تنبيه ارتفاع!</b>\n"
                    f"<b>{sym}</b> ارتفع +{pnl_pct:.1f}%\n"
                    f"دخول: ${entry:.6g} → حالي: ${price:.6g}\n"
                    f"القيمة: ${h['value']:.2f}"
                )
                log(f"تنبيه ارتفاع: {sym} +{pnl_pct:.1f}%")
                notify(msg)
                state.alerted_up[sym] = level
                save_state(state)

        elif pnl_pct <= -ALERT_DOWN_PCT:
            last_alert = state.alerted_down.get(sym, 0)
            level = int(abs(pnl_pct) / ALERT_DOWN_PCT) * ALERT_DOWN_PCT
            if level > last_alert:
                msg = (
                    f"⚠️ <b>تنبيه انخفاض!</b>\n"
                    f"<b>{sym}</b> انخفض {pnl_pct:.1f}%\n"
                    f"دخول: ${entry:.6g} → حالي: ${price:.6g}\n"
                    f"القيمة: ${h['value']:.2f}"
                )
                log(f"تنبيه انخفاض: {sym} {pnl_pct:.1f}%")
                notify(msg)
                state.alerted_down[sym] = level
                save_state(state)

        else:
            if sym in state.alerted_up:
                del state.alerted_up[sym]
            if sym in state.alerted_down:
                del state.alerted_down[sym]


def clean_stale_entries(state: PortfolioState, holdings: list[dict]):
    """حذف عملات من الحالة إذا ما عاد موجودة بالمحفظة"""
    active = {h["symbol"] for h in holdings}
    for sym in list(state.entry_prices):
        if sym not in active:
            del state.entry_prices[sym]
            state.alerted_up.pop(sym, None)
            state.alerted_down.pop(sym, None)
            log(f"حذف {sym} — ما عاد بالمحفظة")


def run_check():
    log("=== فحص الاتصال ===")
    if not KUCOIN_KEY:
        log("KUCOIN_API_KEY مفقود!")
        return
    try:
        ex = get_exchange()
        ex.load_markets()
        log(f"KuCoin متصل — {len(ex.markets)} زوج")
        bal = ex.fetch_balance()
        usdt = float(bal.get("total", {}).get("USDT", 0))
        log(f"رصيد USDT: ${usdt:.2f}")
        holdings = fetch_portfolio(ex)
        log(f"عملات بالمحفظة: {len(holdings)}")
        for h in holdings:
            log(f"  {h['symbol']}: {h['amount']:.4f} (${h['value']:.2f})")
    except Exception as e:
        log(f"خطأ: {e}")


def run_report():
    ex = get_exchange()
    ex.load_markets()
    state = load_state()
    holdings = fetch_portfolio(ex)
    update_entry_prices(ex, state, holdings)
    save_state(state)
    report = build_report(state, holdings)
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

    if not KUCOIN_KEY:
        log("KUCOIN_API_KEY مفقود! أضف المفاتيح في .env_monthly")
        return

    ex = get_exchange()
    ex.load_markets()
    log(f"KuCoin متصل — {len(ex.markets)} زوج")

    state = load_state()

    holdings = fetch_portfolio(ex)
    update_entry_prices(ex, state, holdings)
    save_state(state)
    log(f"عملات بالمحفظة: {len(holdings)}")
    for h in holdings:
        entry = state.entry_prices.get(h["symbol"], 0)
        if entry:
            pnl = (h["price"] - entry) / entry * 100
            sign = "+" if pnl >= 0 else ""
            log(f"  {h['symbol']}: ${h['value']:.2f} ({sign}{pnl:.1f}%)")
        else:
            log(f"  {h['symbol']}: ${h['value']:.2f}")

    report = build_report(state, holdings)
    notify(report)
    log(f"تنبيهات: ↑{ALERT_UP_PCT}% ↓{ALERT_DOWN_PCT}% | فحص كل {CHECK_INTERVAL}s")

    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            holdings = fetch_portfolio(ex)
            update_entry_prices(ex, state, holdings)
            check_alerts(state, holdings)
            clean_stale_entries(state, holdings)
            save_state(state)

            today = time.strftime("%Y-%m-%d")
            hour = int(time.strftime("%H"))
            if hour == DAILY_REPORT_HOUR and state.last_report_day != today:
                report = build_report(state, holdings)
                notify(f"📋 <b>تقرير يومي</b>\n\n{report}")
                state.last_report_day = today
                save_state(state)
                log("تقرير يومي أُرسل")

        except Exception as e:
            log(f"خطأ: {e}")


if __name__ == "__main__":
    main()
