"""
equity_long_short_bot.py — Equity Long/Short على S&P 500
يشتري أقوى 3 أسهم (Long) ويبيع SPY على المكشوف (Short) كتحوّط
البيانات: Financial Datasets API | التنفيذ: Alpaca API

الاستخدام:
    python equity_long_short_bot.py              # paper (افتراضي)
    python equity_long_short_bot.py --live       # تداول حقيقي عبر Alpaca
    python equity_long_short_bot.py --check      # عرض الحالة
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── المسارات ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots"); BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE   = BASE_DIR / ".env_finance"
STATE_FILE = BASE_DIR / "equity_state.json"
LOG_FILE   = BASE_DIR / "equity.log"

# ── تحميل البيئة ──
def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); env[k.strip()] = v.strip()
    return env

ENV = load_env()
FD_TOKEN       = ENV.get("FD_API_TOKEN", "")
UNIVERSE       = [s.strip() for s in ENV.get("EQUITY_UNIVERSE", "AAPL,MSFT,NVDA,GOOGL,AMZN,TSLA,META,SPY,QQQ").split(",")]
TRADE_SIZE     = float(ENV.get("EQUITY_TRADE_SIZE", "20"))
SL_PCT         = float(ENV.get("EQUITY_SL_PCT", "2.0")) / 100
TP_PCT         = float(ENV.get("EQUITY_TP_PCT", "4.0")) / 100
ALPACA_KEY     = ENV.get("ALPACA_API_KEY", "")
ALPACA_SECRET  = ENV.get("ALPACA_API_SECRET", "")
ALPACA_PAPER   = ENV.get("ALPACA_PAPER", "true").lower() == "true"
TG_TOKEN       = ENV.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT        = ENV.get("TELEGRAM_CHAT_ID", "")
FD_BASE        = "https://mcp.financialdatasets.ai/v1"
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"

# ── ثوابت الاستراتيجية ──
SCAN_INTERVAL   = 3600       # 60 دقيقة
MAX_POSITIONS   = 5          # 3 long + hedge
MAX_TRADES_DAY  = 3
MAX_DAILY_LOSS  = 20.0       # $20
MAX_HOLD_DAYS   = 7
TOP_N           = 3          # أقوى 3 أسهم
HEDGE_SYMBOL    = "SPY"
RSI_PERIOD      = 14
EMA_FAST, EMA_SLOW, EMA_SIGNAL = 12, 26, 9

# ── تسجيل الأحداث ──
logger = logging.getLogger("equity"); logger.setLevel(logging.INFO)
_fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
_sh = logging.StreamHandler(); _sh.setFormatter(_fmt); logger.addHandler(_sh)
try:
    _fh = logging.FileHandler(LOG_FILE, encoding="utf-8"); _fh.setFormatter(_fmt); logger.addHandler(_fh)
except Exception: pass

def log(msg: str, level: str = "INFO"):
    getattr(logger, level.lower(), logger.info)(msg)

# ── تيليجرام ──
def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                                    data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception: pass

# ── HTTP ──
def http_get(url: str, headers: dict | None = None, timeout: int = 15):
    try:
        hdrs = {"User-Agent": "equity-ls-bot/1.0"}
        if headers: hdrs.update(headers)
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"HTTP خطأ: {url[:60]} — {e}", "WARNING"); return None

# ── الحالة ──
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
# المؤشرات الفنية
# ═══════════════════════════════════════════════
def calc_ema(closes: list[float], period: int) -> list[float]:
    k = 2.0 / (period + 1)
    ema = [closes[0]]
    for i in range(1, len(closes)):
        ema.append(closes[i] * k + ema[-1] * (1 - k))
    return ema

def calc_rsi(closes: list[float], period: int = RSI_PERIOD) -> float:
    if len(closes) < period + 1: return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0)); losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)

def calc_macd(closes: list[float]) -> tuple[float, float, float]:
    """يرجع (macd_line, signal_line, histogram)"""
    if len(closes) < EMA_SLOW + EMA_SIGNAL:
        return 0.0, 0.0, 0.0
    ema_fast = calc_ema(closes, EMA_FAST)
    ema_slow = calc_ema(closes, EMA_SLOW)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal = calc_ema(macd_line, EMA_SIGNAL)
    return macd_line[-1], signal[-1], macd_line[-1] - signal[-1]

def momentum_score(rsi: float, histogram: float) -> float:
    """قوة الزخم: بُعد RSI عن 50 + حجم الـ histogram"""
    return (rsi - 50.0) + histogram * 1000

# ═══════════════════════════════════════════════
# جلب البيانات — Financial Datasets API
# ═══════════════════════════════════════════════
def fetch_candles(symbol: str, count: int = 30) -> list[float]:
    """جلب أسعار الإغلاق (1H candles) من Financial Datasets API"""
    # محاولة استخدام العميل أولاً
    try:
        from financial_datasets_client import FinancialDatasetsClient
        client = FinancialDatasetsClient(api_key=FD_TOKEN)
        candles = client.get_candles(symbol, interval="1h", limit=count)
        if candles and len(candles) >= count // 2:
            return [c["close"] for c in candles]
    except ImportError: pass
    except Exception as e:
        log(f"عميل FD خطأ لـ {symbol}: {e}", "WARNING")

    # HTTP مباشر
    headers = {}
    if FD_TOKEN: headers["Authorization"] = f"Bearer {FD_TOKEN}"
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=count + 10)
    url = (f"{FD_BASE}/candles?symbol={symbol}&interval=1h"
           f"&start={start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
           f"&end={end.strftime('%Y-%m-%dT%H:%M:%SZ')}&limit={count}")
    data = http_get(url, headers=headers)
    if data and isinstance(data, dict):
        candles = data.get("candles") or data.get("data") or data.get("results") or []
        if candles:
            closes = [float(c.get("close", c.get("c", 0))) for c in candles if c.get("close") or c.get("c")]
            if len(closes) >= count // 2: return closes[-count:]
    # fallback: يومية
    data2 = http_get(f"{FD_BASE}/prices?symbol={symbol}&interval=day&limit={count}", headers=headers)
    if data2 and isinstance(data2, dict):
        prices = data2.get("prices") or data2.get("data") or []
        if prices: return [float(p.get("close", p.get("c", 0))) for p in prices[-count:] if p.get("close") or p.get("c")]
    return []

def fetch_last_price(symbol: str) -> float:
    headers = {}
    if FD_TOKEN: headers["Authorization"] = f"Bearer {FD_TOKEN}"
    data = http_get(f"{FD_BASE}/quote?symbol={symbol}", headers=headers)
    if data and isinstance(data, dict):
        return float(data.get("price") or data.get("last") or data.get("close") or 0)
    return 0.0

# ═══════════════════════════════════════════════
# التنفيذ — Alpaca أو Paper
# ═══════════════════════════════════════════════
def alpaca_order(symbol: str, notional: float, side: str) -> tuple[bool, str]:
    """تنفيذ أمر عبر Alpaca API"""
    if not ALPACA_KEY: return False, "مفتاح Alpaca غير موجود"
    try:
        base = ALPACA_PAPER_URL if ALPACA_PAPER else "https://api.alpaca.markets"
        url = f"{base}/v2/orders"
        payload = json.dumps({
            "symbol": symbol, "notional": str(round(notional, 2)),
            "side": side, "type": "market", "time_in_force": "day"
        }).encode()
        req = urllib.request.Request(url, data=payload, method="POST", headers={
            "APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET,
            "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read().decode())
        return True, f"أمر {resp.get('id', '?')[:12]} — {side} ${notional:.0f} {symbol}"
    except Exception as e:
        return False, f"خطأ Alpaca: {e}"

def execute_trade(symbol: str, notional: float, side: str, mode: str) -> tuple[bool, str]:
    if mode == "live" and ALPACA_KEY:
        return alpaca_order(symbol, notional, side)
    qty = round(notional / max(fetch_last_price(symbol), 1), 4)
    return True, f"PAPER: {side.upper()} ${notional:.0f} {symbol} (~{qty} سهم)"

# ═══════════════════════════════════════════════
# تحليل الأسهم وترتيبها
# ═══════════════════════════════════════════════
def analyze_stock(symbol: str) -> dict | None:
    closes = fetch_candles(symbol, 30)
    if len(closes) < EMA_SLOW + EMA_SIGNAL:
        log(f"بيانات غير كافية لـ {symbol} ({len(closes)} شمعة)"); return None
    rsi = calc_rsi(closes)
    macd, signal, hist = calc_macd(closes)
    bullish = rsi > 50 and macd > signal
    score = momentum_score(rsi, hist)
    return {"symbol": symbol, "rsi": round(rsi, 2), "macd": round(macd, 4),
            "signal": round(signal, 4), "histogram": round(hist, 4),
            "bullish": bullish, "score": round(score, 2), "price": closes[-1]}

def rank_stocks() -> list[dict]:
    log(f"تحليل {len(UNIVERSE)} سهم...")
    results = []
    for sym in UNIVERSE:
        r = analyze_stock(sym)
        if r:
            results.append(r)
            log(f"  {sym}: RSI={r['rsi']} MACD={r['macd']} hist={r['histogram']} {'صعودي ↑' if r['bullish'] else 'هبوطي ↓'} score={r['score']}")
    bullish = sorted([r for r in results if r["bullish"]], key=lambda x: x["score"], reverse=True)
    log(f"أسهم صعودية: {len(bullish)} من {len(results)}")
    return bullish

# ═══════════════════════════════════════════════
# إدارة المراكز — SL/TP/MaxHold
# ═══════════════════════════════════════════════
def check_positions(st: dict, mode: str) -> dict:
    now, closed = datetime.now(timezone.utc), []
    for pos in st["positions"]:
        cur = fetch_last_price(pos["symbol"])
        if cur <= 0: continue
        entry = pos["entry_price"]
        pnl_pct = (cur - entry) / entry if pos["side"] == "long" else (entry - cur) / entry
        et = datetime.fromisoformat(pos["entry_time"])
        if et.tzinfo is None: et = et.replace(tzinfo=timezone.utc)
        hold_d = (now - et).total_seconds() / 86400
        reason = None
        if pnl_pct <= -SL_PCT: reason = f"وقف خسارة ({pnl_pct*100:+.1f}%)"
        elif pnl_pct >= TP_PCT: reason = f"جني أرباح ({pnl_pct*100:+.1f}%)"
        elif hold_d >= MAX_HOLD_DAYS: reason = f"أقصى مدة ({hold_d:.1f} يوم)"
        if reason:
            pnl_usd = pos["notional"] * pnl_pct
            st["daily_pnl"] += pnl_usd
            close_side = "sell" if pos["side"] == "long" else "buy"
            ok, msg = execute_trade(pos["symbol"], pos["notional"], close_side, mode)
            log(f"إغلاق: {reason} | {pos['symbol']} {pos['side']} | ${pnl_usd:+.2f}")
            tg(f"<b>إغلاق مركز</b>\n{pos['symbol']} {pos['side']}\nالسبب: {reason}\nPnL: ${pnl_usd:+.2f}")
            st["trade_log"].append({"symbol": pos["symbol"], "side": pos["side"],
                "entry": entry, "exit": cur, "pnl": round(pnl_usd, 2),
                "reason": reason, "time": now.isoformat()})
            closed.append(pos)
    for c in closed: st["positions"].remove(c)
    return st

# ═══════════════════════════════════════════════
# الدورة الرئيسية — فتح صفقات جديدة
# ═══════════════════════════════════════════════
def open_positions(st: dict, mode: str) -> dict:
    existing = {p["symbol"] for p in st["positions"]}
    bullish = rank_stocks()
    picks = [s for s in bullish if s["symbol"] != HEDGE_SYMBOL and s["symbol"] not in existing][:TOP_N]
    if not picks:
        log("لا توجد أسهم صعودية للشراء"); return st
    total_long = 0.0
    for stock in picks:
        if len(st["positions"]) >= MAX_POSITIONS: break
        if st["daily_trades"] >= MAX_TRADES_DAY: break
        ok, msg = execute_trade(stock["symbol"], TRADE_SIZE, "buy", mode)
        if ok:
            st["positions"].append({"symbol": stock["symbol"], "side": "long",
                "entry_price": stock["price"], "notional": TRADE_SIZE,
                "entry_time": datetime.now(timezone.utc).isoformat(),
                "rsi": stock["rsi"], "score": stock["score"]})
            st["daily_trades"] += 1; total_long += TRADE_SIZE
            log(f"شراء: {stock['symbol']} ${TRADE_SIZE} | RSI={stock['rsi']} score={stock['score']} | {msg}")
            tg(f"<b>شراء Long</b> 🟢\n{stock['symbol']} ${TRADE_SIZE}\nRSI: {stock['rsi']} | Score: {stock['score']}")
    # تحوّط: بيع SPY على المكشوف
    if total_long > 0 and HEDGE_SYMBOL not in existing and len(st["positions"]) < MAX_POSITIONS:
        hedge_notional = total_long
        spy_price = fetch_last_price(HEDGE_SYMBOL)
        if spy_price <= 0:
            picks_with_spy = [s for s in bullish if s["symbol"] == HEDGE_SYMBOL]
            spy_price = picks_with_spy[0]["price"] if picks_with_spy else 0
        if spy_price > 0:
            ok, msg = execute_trade(HEDGE_SYMBOL, hedge_notional, "sell", mode)
            if ok:
                st["positions"].append({"symbol": HEDGE_SYMBOL, "side": "short",
                    "entry_price": spy_price, "notional": hedge_notional,
                    "entry_time": datetime.now(timezone.utc).isoformat(),
                    "rsi": 0, "score": 0})
                st["daily_trades"] += 1
                log(f"تحوّط: بيع {HEDGE_SYMBOL} ${hedge_notional} @ {spy_price:.2f} | {msg}")
                tg(f"<b>تحوّط Short</b> 🔴\n{HEDGE_SYMBOL} ${hedge_notional:.0f}")
    return st

# ═══════════════════════════════════════════════
# عرض الحالة
# ═══════════════════════════════════════════════
def show_status(st: dict):
    st = reset_daily(st)
    print("=" * 55)
    print("  Equity Long/Short Bot — الحالة")
    print("=" * 55)
    print(f"  اليوم: {st['day']} | صفقات: {st['daily_trades']}/{MAX_TRADES_DAY}")
    print(f"  PnL اليوم: ${st['daily_pnl']:.2f} | مراكز: {len(st['positions'])}/{MAX_POSITIONS}")
    print(f"  الأسهم: {', '.join(UNIVERSE)}")
    print(f"  Alpaca: {'متصل' if ALPACA_KEY else 'غير متصل (paper)'}")
    print(f"  FD Token: {'موجود' if FD_TOKEN else 'غير موجود'}")
    if st["positions"]:
        print("-" * 55)
        for p in st["positions"]:
            cur = fetch_last_price(p["symbol"])
            pnl = ((cur - p["entry_price"]) / p["entry_price"] * 100 if p["side"] == "long"
                   else (p["entry_price"] - cur) / p["entry_price"] * 100) if cur > 0 else 0
            print(f"  {p['side'].upper():5s} {p['symbol']:5s} | دخول: {p['entry_price']:.2f} حالي: {cur:.2f} ({pnl:+.1f}%)")
    else: print("  لا توجد مراكز مفتوحة")
    if st["trade_log"]:
        print("-" * 55); print("  آخر الصفقات:")
        for t in st["trade_log"][-5:]:
            print(f"  {t['symbol']} {t['side']} | PnL: ${t['pnl']:+.2f} | {t['reason']}")
    print("=" * 55)

# ═══════════════════════════════════════════════
# الحلقة الرئيسية
# ═══════════════════════════════════════════════
def run_loop(mode: str):
    log(f"تشغيل Equity Long/Short Bot — وضع: {mode}")
    log(f"الأسهم: {', '.join(UNIVERSE)} | حجم: ${TRADE_SIZE} | SL: {SL_PCT*100:.1f}% | TP: {TP_PCT*100:.1f}%")
    tg(f"<b>Equity L/S Bot</b> شغّال\nوضع: {mode}\nأسهم: {', '.join(UNIVERSE[:5])}...\nحجم: ${TRADE_SIZE} | SL: {SL_PCT*100:.0f}% TP: {TP_PCT*100:.0f}%")
    st = reset_daily(load_state()); cycle = 0
    while True:
        try:
            cycle += 1; st = reset_daily(st)
            log(f"═══ دورة #{cycle} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC ═══")
            # فحص المراكز الحالية
            if st["positions"]:
                st = check_positions(st, mode)
            # وقف الخسارة اليومي
            if st["daily_pnl"] <= -MAX_DAILY_LOSS:
                msg = f"وقف خسارة يومي! ${st['daily_pnl']:.2f} — البوت متوقف حتى الغد"
                log(msg, "WARNING"); tg(msg); save_state(st)
                time.sleep(SCAN_INTERVAL); continue
            # حد الصفقات اليومي
            if st["daily_trades"] >= MAX_TRADES_DAY:
                log(f"الحد اليومي للصفقات ({MAX_TRADES_DAY})")
                save_state(st); time.sleep(SCAN_INTERVAL); continue
            # فتح مراكز جديدة إذا ممكن
            if len(st["positions"]) < MAX_POSITIONS:
                st = open_positions(st, mode)
            else:
                log(f"المراكز ممتلئة ({len(st['positions'])}/{MAX_POSITIONS})")
            save_state(st)
            log(f"الانتظار {SCAN_INTERVAL // 60} دقيقة...")
            time.sleep(SCAN_INTERVAL)
        except KeyboardInterrupt:
            log("إيقاف يدوي"); save_state(st); break
        except Exception as e:
            log(f"خطأ في الدورة: {e}", "ERROR")
            save_state(st); time.sleep(60)

# ═══════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Equity Long/Short Bot — S&P 500")
    parser.add_argument("--live", action="store_true", help="تداول حقيقي عبر Alpaca")
    parser.add_argument("--check", action="store_true", help="عرض الحالة فقط")
    args = parser.parse_args()

    if args.check:
        show_status(load_state())
    else:
        mode = "live" if args.live else "paper"
        run_loop(mode)
