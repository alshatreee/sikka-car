"""
channel_analyzer.py — تحليل سنة كاملة من توصيات القنوات

يمسح رسائل القناتين لمدة سنة، يحاكي كل توصية باستخدام بيانات OHLCV الحقيقية،
ويحسب: نسبة النجاح، التوقع الرياضي، أفضل/أسوأ العملات، الأداء الشهري.

    python3 channel_analyzer.py              # تحليل سنة كاملة
    python3 channel_analyzer.py --days 90   # آخر 90 يوم
    python3 channel_analyzer.py --notify    # أرسل التقرير على تيليجرام

pip install telethon python-dotenv ccxt requests
"""
from __future__ import annotations
import asyncio, json, os, re, sys, time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path("/root/bots") if os.name != "nt" else Path(r"C:\Users\xman9\Desktop")
load_dotenv(BASE_DIR / ".env_monthly")

TG_API_ID   = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_SESSION  = str(BASE_DIR / "monthly_session")
TG_CHANNELS = [c.strip() for c in os.getenv("MONTHLY_CHANNELS", "").split(",") if c.strip()]

BYBIT_KEY    = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET = os.getenv("BYBIT_API_SECRET", "")
KUCOIN_KEY    = os.getenv("KUCOIN_API_KEY", "")
KUCOIN_SECRET = os.getenv("KUCOIN_API_SECRET", "")
KUCOIN_PASS   = os.getenv("KUCOIN_PASSPHRASE", "")

ANALYSIS_DAYS   = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 365
SL_PCT          = 30.0   # وقف الخسارة الكارثي المستخدم في المحاكاة
MAX_HOLD_DAYS   = 45     # أقصى مدة للصفقة
MAX_TP_PCT      = 100.0  # تجاهل توصيات بهدف أعلى من 100%
NOTIFY_RESULTS  = "--notify" in sys.argv
NOTIFY_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT     = os.getenv("TELEGRAM_CHAT_ID", "")


# ─── هياكل البيانات ───────────────────────────────────────────────

@dataclass
class SignalRec:
    channel:   str
    symbol:    str
    trade_num: int
    date:      datetime
    entry:     float
    tp:        float
    sl:        float
    tp_pct:    float
    outcome:   str   = ""    # WIN / LOSS / EXPIRED / OPEN / NO_DATA
    pnl_pct:   float = 0.0
    days_held: int   = 0


# ─── محلل التوصيات (نسخة مستقلة) ──────────────────────────────────

def _parse_signal(text: str) -> dict | None:
    """يحلل رسالة التوصية — يدعم صيغتي القناة الشهرية والقناة العامة"""

    # تجاهل الأسهم الأمريكية
    if re.search(r"NYSE|NASDAQ|أسهم\s*أمريكية", text, re.IGNORECASE):
        return None
    type_m = re.search(r"النوع[:\s]+(\S+)", text)
    if type_m and "USDT" not in type_m.group(1).upper():
        return None

    # رقم الصفقة — يدعم "رقم الصفقة:(15)" و "صفقة #5"
    num_m = re.search(r"رقم\s*الصفقة\s*[:(]?\s*(\d+)|(?:صفقة|توصية)\s*#?\s*(\d+)", text)
    trade_num = int((num_m.group(1) or num_m.group(2))) if num_m else 0

    # اسم العملة — يدعم "العملة: WARD" و "WARD/USDT"
    sym_m = re.search(r"\b([A-Z]{2,10})\s*/\s*USDT\b|ال?عملة[:\s]+([A-Z]{2,10})", text)
    if not sym_m:
        sym_m = re.search(r"^\s*([A-Z]{2,10})\s*:", text, re.MULTILINE)
    if not sym_m:
        return None
    symbol = (sym_m.group(1) or sym_m.group(2)).strip().upper()

    lines = text.splitlines()

    # سعر الشراء — صيغة 1: "سعر الشراء: 0.123"
    buy_p: float | None = None
    buy_m = re.search(r"(?:سعر\s*)?الشراء[:\s]+([\d.]+)", text)
    if buy_m:
        buy_p = float(buy_m.group(1))
    else:
        # صيغة 2: أول سعر في قائمة "الشراء والتعزيز:"
        in_section = False
        for line in lines:
            if re.search(r"الشراء\s*(?:والتعزيز)?", line) and ":" in line:
                in_section = True
                continue
            if in_section:
                pm = re.search(r"[-–]\s*([\d]+\.[\d]+)", line)
                if pm:
                    buy_p = float(pm.group(1))
                    break
    if not buy_p or buy_p <= 0:
        return None

    # سعر البيع / الهدف — صيغة 1: "سعر البيع  0.14" أو "الهدف: 0.14"
    sell_p: float | None = None
    sell_m = re.search(r"(?:سعر\s*)?البيع[:\s]*([\d.]+)", text)
    if sell_m:
        sell_p = float(sell_m.group(1))
    else:
        sell_m2 = re.search(r"الهدف[:\s]*([\d.]+)", text)
        if sell_m2:
            sell_p = float(sell_m2.group(1))

    if not sell_p:
        # صيغة 2: أول هدف من قائمة "أهداف الصفقة:"
        in_targets = False
        for line in lines:
            if "أهداف" in line and ("صفقة" in line or "الصفقة" in line):
                in_targets = True
                continue
            if in_targets:
                pm = re.search(r"[-–]\s*([\d]+\.[\d]+)", line)
                if pm:
                    sell_p = float(pm.group(1))
                    break

    if not sell_p:
        sell_p = buy_p * 1.20

    if sell_p <= buy_p:
        return None
    tp_pct = round((sell_p - buy_p) / buy_p * 100, 2)
    return {"symbol": symbol, "num": trade_num,
            "buy": buy_p, "sell": sell_p, "tp_pct": tp_pct}


# ─── جلب التوصيات من تيليجرام ──────────────────────────────────────

async def scan_channels() -> list[SignalRec]:
    from telethon import TelegramClient
    results: list[SignalRec] = []
    since = datetime.now(timezone.utc) - timedelta(days=ANALYSIS_DAYS)

    async with TelegramClient(TG_SESSION, TG_API_ID, TG_API_HASH) as client:
        for channel in TG_CHANNELS:
            try:
                entity = await client.get_entity(channel)
                print(f"\nمسح قناة: {channel} (آخر {ANALYSIS_DAYS} يوم)...")
                total_msgs = 0
                found = 0
                async for msg in client.iter_messages(entity, offset_date=since, reverse=True):
                    if not msg.text:
                        continue
                    total_msgs += 1
                    sig = _parse_signal(msg.text)
                    if not sig:
                        continue
                    if sig["tp_pct"] > MAX_TP_PCT:
                        continue
                    found += 1
                    sl_price = sig["buy"] * (1 - SL_PCT / 100)
                    results.append(SignalRec(
                        channel=channel,
                        symbol=sig["symbol"],
                        trade_num=sig["num"],
                        date=msg.date,
                        entry=sig["buy"],
                        tp=sig["sell"],
                        sl=sl_price,
                        tp_pct=sig["tp_pct"],
                    ))
                print(f"  {total_msgs} رسالة | {found} توصية مُعرَّفة")
            except Exception as e:
                print(f"  خطأ {channel}: {e}")
    return results


# ─── محاكاة الصفقات بـ OHLCV ────────────────────────────────────────

def get_exchanges() -> list:
    import ccxt
    exchanges = []
    try:
        bybit = ccxt.bybit({"apiKey": BYBIT_KEY, "secret": BYBIT_SECRET})
        bybit.load_markets()
        exchanges.append(bybit)
        print(f"  Bybit: {len(bybit.markets)} زوج")
    except Exception as e:
        print(f"  خطأ Bybit: {e}")
    try:
        kucoin = ccxt.kucoin({"apiKey": KUCOIN_KEY, "secret": KUCOIN_SECRET,
                              "password": KUCOIN_PASS})
        kucoin.load_markets()
        exchanges.append(kucoin)
        print(f"  KuCoin: {len(kucoin.markets)} زوج")
    except Exception as e:
        print(f"  خطأ KuCoin: {e}")
    try:
        binance = ccxt.binance()
        binance.load_markets()
        exchanges.append(binance)
        print(f"  Binance: {len(binance.markets)} زوج")
    except Exception as e:
        print(f"  خطأ Binance: {e}")
    return exchanges


def _find_exchange(symbol: str, exchanges: list):
    pair = f"{symbol}/USDT"
    for ex in exchanges:
        if pair in ex.markets:
            return ex, pair
    return None, None


def simulate(rec: SignalRec, exchanges: list) -> SignalRec:
    """محاكاة نتيجة الصفقة باستخدام بيانات OHLCV الحقيقية"""
    exchange, pair = _find_exchange(rec.symbol, exchanges)
    if not exchange:
        rec.outcome = "NO_DATA"
        return rec

    since_ms = int(rec.date.timestamp() * 1000)
    deadline_ms = since_ms + MAX_HOLD_DAYS * 86400 * 1000

    try:
        ohlcv = exchange.fetch_ohlcv(pair, "1h", since=since_ms, limit=1080)
        if not ohlcv:
            rec.outcome = "NO_DATA"
            return rec

        for candle in ohlcv:
            ts, _, high, low, close = candle[0], candle[1], candle[2], candle[3], candle[4]

            if ts > deadline_ms:
                rec.outcome = "EXPIRED"
                rec.pnl_pct = round((close - rec.entry) / rec.entry * 100, 2)
                rec.days_held = MAX_HOLD_DAYS
                return rec

            if high >= rec.tp:
                rec.outcome = "WIN"
                rec.pnl_pct = round(rec.tp_pct, 2)
                rec.days_held = round((ts - since_ms) / (86400 * 1000))
                return rec

            if low <= rec.sl:
                rec.outcome = "LOSS"
                rec.pnl_pct = -SL_PCT
                rec.days_held = round((ts - since_ms) / (86400 * 1000))
                return rec

        # توصية حديثة لم تنته بعد
        last_close = ohlcv[-1][4]
        rec.outcome = "OPEN"
        rec.pnl_pct = round((last_close - rec.entry) / rec.entry * 100, 2)
        rec.days_held = round((ohlcv[-1][0] - since_ms) / (86400 * 1000))

    except Exception as e:
        rec.outcome = "NO_DATA"
    return rec


# ─── بناء التقرير ───────────────────────────────────────────────────

def build_report(records: list[SignalRec]) -> str:
    closed = [r for r in records if r.outcome in ("WIN", "LOSS", "EXPIRED")]
    wins   = [r for r in closed if r.outcome == "WIN"]
    losses = [r for r in closed if r.outcome == "LOSS"]
    expired= [r for r in closed if r.outcome == "EXPIRED"]
    open_  = [r for r in records if r.outcome == "OPEN"]
    no_data= [r for r in records if r.outcome == "NO_DATA"]

    n = len(closed)
    if n == 0:
        return "لا توجد صفقات مغلقة لتحليلها"

    wr = len(wins) / n * 100
    avg_win  = sum(r.pnl_pct for r in wins)   / len(wins)   if wins   else 0
    avg_loss = sum(r.pnl_pct for r in losses) / len(losses) if losses else 0
    avg_exp  = sum(r.pnl_pct for r in expired)/ len(expired)if expired else 0
    expectancy = (wr/100 * avg_win) + ((1-wr/100) * avg_loss)
    verdict = "✅ إيجابي" if expectancy > 0 else "⚠️ سلبي"

    # أداء كل عملة
    by_symbol: dict[str, list] = {}
    for r in closed:
        by_symbol.setdefault(r.symbol, []).append(r.pnl_pct)
    sym_perf = sorted(by_symbol.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True)

    # أداء شهري
    by_month: dict[str, list] = {}
    for r in closed:
        month = r.date.strftime("%Y-%m")
        by_month.setdefault(month, []).append(r.pnl_pct)

    lines = [
        f"<b>📊 تقرير تحليل القنوات — آخر {ANALYSIS_DAYS} يوم</b>",
        f"وقف الخسارة المحاكى: -{SL_PCT}% | مدة قصوى: {MAX_HOLD_DAYS} يوم\n",

        f"<b>إجمالي التوصيات:</b> {len(records)}",
        f"  ✅ ربح (وصل الهدف): {len(wins)}",
        f"  ❌ خسارة (وقف الخسارة): {len(losses)}",
        f"  ⏰ منتهية (30 يوم): {len(expired)}",
        f"  🔄 لا تزال مفتوحة: {len(open_)}",
        f"  ❓ لا بيانات: {len(no_data)}\n",

        f"<b>الأداء (الصفقات المغلقة {n}):</b>",
        f"  نسبة الربح: {wr:.1f}%",
        f"  متوسط الربح: {avg_win:+.1f}%",
        f"  متوسط الخسارة: {avg_loss:+.1f}%",
        f"  متوسط المنتهية: {avg_exp:+.1f}%",
        f"  التوقع الرياضي: {expectancy:+.1f}% / صفقة ({verdict})\n",
    ]

    # أفضل 5 عملات
    lines.append("<b>أفضل العملات:</b>")
    for sym, pnls in sym_perf[:5]:
        avg = sum(pnls) / len(pnls)
        lines.append(f"  {sym}: {avg:+.1f}% متوسط ({len(pnls)} صفقة)")

    # أسوأ 3 عملات
    lines.append("\n<b>أسوأ العملات:</b>")
    for sym, pnls in sym_perf[-3:]:
        avg = sum(pnls) / len(pnls)
        lines.append(f"  {sym}: {avg:+.1f}% متوسط ({len(pnls)} صفقة)")

    # أداء شهري
    lines.append("\n<b>الأداء الشهري:</b>")
    for month in sorted(by_month.keys()):
        pnls = by_month[month]
        avg = sum(pnls) / len(pnls)
        wins_m = sum(1 for p in pnls if p > 0)
        lines.append(f"  {month}: {avg:+.1f}% | {wins_m}/{len(pnls)} ربح")

    # أفضل وأسوأ صفقة
    if wins:
        best = max(wins, key=lambda r: r.pnl_pct)
        lines.append(f"\n🏆 أفضل صفقة: {best.symbol} {best.pnl_pct:+.1f}% ({best.date.strftime('%Y-%m-%d')})")
    if losses:
        worst = min(losses, key=lambda r: r.pnl_pct)
        lines.append(f"💀 أسوأ صفقة: {worst.symbol} {worst.pnl_pct:+.1f}% ({worst.date.strftime('%Y-%m-%d')})")

    return "\n".join(lines)


def notify(msg: str):
    if not NOTIFY_TOKEN or not NOTIFY_CHAT:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{NOTIFY_TOKEN}/sendMessage",
            json={"chat_id": NOTIFY_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=15,
        )
    except Exception as e:
        print(f"خطأ الإرسال: {e}")


# ─── نقطة الدخول ─────────────────────────────────────────────────────

async def main():
    print(f"=== تحليل القنوات — آخر {ANALYSIS_DAYS} يوم ===")
    print(f"وقف كارثي: -{SL_PCT}% | مدة قصوى: {MAX_HOLD_DAYS} يوم | حد الهدف: {MAX_TP_PCT}%\n")

    if not TG_API_ID or not TG_API_HASH:
        print("خطأ: TG_API_ID و TG_API_HASH غير مضبوطين في .env_monthly")
        return
    if not TG_CHANNELS:
        print("خطأ: MONTHLY_CHANNELS فارغ في .env_monthly")
        return

    # 1) مسح القنوات
    records = await scan_channels()
    print(f"\nإجمالي التوصيات المُعرَّفة: {len(records)}")
    if not records:
        print("لا توصيات — تأكد من صيغة الرسائل")
        return

    # 2) محاكاة كل توصية
    print("\nالاتصال بالمنصات...")
    exchanges = get_exchanges()
    if not exchanges:
        print("خطأ: لا منصة متصلة!")
        return

    print(f"\nجلب البيانات التاريخية ومحاكاة الصفقات...")
    for i, rec in enumerate(records):
        records[i] = simulate(rec, exchanges)
        outcome_ar = {"WIN":"ربح","LOSS":"خسارة","EXPIRED":"منتهية","OPEN":"مفتوحة","NO_DATA":"لا بيانات"}.get(rec.outcome, rec.outcome)
        print(f"  [{i+1}/{len(records)}] {rec.symbol} {rec.date.strftime('%Y-%m-%d')} → {outcome_ar} {rec.pnl_pct:+.1f}%")
        time.sleep(0.3)  # تجنب rate limit

    # 3) حفظ النتائج
    out_file = BASE_DIR / "channel_analysis.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump([{
            "channel": r.channel, "symbol": r.symbol, "date": r.date.isoformat(),
            "entry": r.entry, "tp": r.tp, "sl": r.sl, "tp_pct": r.tp_pct,
            "outcome": r.outcome, "pnl_pct": r.pnl_pct, "days_held": r.days_held,
        } for r in records], f, ensure_ascii=False, indent=2)
    print(f"\nالنتائج محفوظة: {out_file}")

    # 4) التقرير
    report = build_report(records)
    clean = report.replace("<b>","").replace("</b>","")
    print("\n" + "="*50)
    print(clean)
    print("="*50)

    if NOTIFY_RESULTS:
        notify(report)
        print("\nتم إرسال التقرير على تيليجرام")


if __name__ == "__main__":
    asyncio.run(main())
