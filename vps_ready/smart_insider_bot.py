"""
smart_insider_bot.py
====================

Smart Insider Trading Bot — يراقب SEC EDGAR Form 4 filings ويشتري الأسهم
عندما يقوم CEO/CFO بشراء نقدي كبير في شركة small/mid-cap.

الاستراتيجية مبنية على أبحاث أكاديمية:
  - Lakonishok & Lee (2001): insider buying يتفوق على السوق ~6% سنوياً
  - Cohen, Malloy, Pomorski (2012): "opportunistic" insiders edge أعلى
  - Cluster buying (عدة insiders خلال 30 يوم) = إشارة قوية

الفلترة:
  ✓ شراء نقدي فقط (Form 4 transaction code = "P")
  ✓ CEO أو CFO أو 10%+ Owner فقط
  ✓ حجم الصفقة ≥ MIN_VALUE_USD ($500K افتراضياً)
  ✓ Market cap بين MIN_CAP و MAX_CAP ($300M-$10B)
  ✓ ليس exercise option أو grant
  ✓ Cluster bonus: insider آخر اشترى خلال 30 يوم

التنفيذ:
  - IBKR عبر ib_insync
  - Paper account افتراضياً (port 7497)
  - Live account = port 7496 (لا تستخدمه قبل 60 يوم paper)

إدارة المخاطر:
  - حجم الصفقة: 2% من رأس المال (max 20 positions)
  - Trailing stop: 15%
  - Time exit: 90 يوم
  - Take profit: +30%
  - Daily kill-switch: -5% من رأس المال

استخدام:
    python3 smart_insider_bot.py              # paper (IBKR paper account)
    python3 smart_insider_bot.py --check      # حالة سريعة
    python3 smart_insider_bot.py --scan-once  # فحص واحد ثم خروج
    python3 smart_insider_bot.py --live       # ⚠️ live trading
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# ---------- paths ----------
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = BASE_DIR / ".env_insider"
STATE_FILE = BASE_DIR / "insider_state.json"
POSITIONS_FILE = BASE_DIR / "insider_positions.json"
SEEN_FILE = BASE_DIR / "insider_seen.json"
LOG_FILE = BASE_DIR / "insider.log"

load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# ---------- config ----------
# IBKR connection
IBKR_HOST = os.getenv("IBKR_HOST", "127.0.0.1")
IBKR_PAPER_PORT = int(os.getenv("IBKR_PAPER_PORT", "7497"))
IBKR_LIVE_PORT = int(os.getenv("IBKR_LIVE_PORT", "7496"))
IBKR_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", "17"))

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

# Strategy filters
MIN_VALUE_USD = 500_000          # حجم الصفقة الأدنى
MIN_MARKET_CAP = 300_000_000     # $300M
MAX_MARKET_CAP = 10_000_000_000  # $10B
ALLOWED_TITLES = [               # المناصب المقبولة
    "ceo", "chief executive",
    "cfo", "chief financial",
    "president",
    "10%", "10 percent",
]
CLUSTER_WINDOW_DAYS = 30         # نافذة cluster buying

# Position sizing & risk
POSITION_PCT = 0.02              # 2% من رأس المال لكل صفقة
MAX_POSITIONS = 20
TRAILING_STOP_PCT = 0.15         # 15% trailing
TAKE_PROFIT_PCT = 0.30           # 30% take profit
MAX_HOLD_DAYS = 90
DAILY_LOSS_LIMIT_PCT = 0.05      # 5% kill-switch

# Polling
SCAN_INTERVAL_SEC = 3600         # كل ساعة (لا حاجة لأسرع — Form 4 ليس HFT)
POSITION_CHECK_SEC = 300         # فحص المراكز كل 5 دقائق

# SEC EDGAR
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Insider Bot research@example.com")
EDGAR_FORM4_RSS = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcompany&type=4&dateb=&owner=include&count=100&output=atom"
)


# ---------- logging / notifications ----------
def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def tg(msg: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg},
            timeout=10,
        )
    except Exception as e:
        log(f"telegram failed: {e}")


# ---------- state ----------
@dataclass
class Position:
    symbol: str
    shares: int
    entry_price: float
    entry_date: str           # YYYY-MM-DD
    high_price: float         # for trailing stop
    insider_name: str
    insider_title: str
    filing_url: str

@dataclass
class State:
    day: str = ""
    daily_pnl: float = 0.0
    halted: bool = False
    starting_equity: float = 0.0
    recent_buys: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # recent_buys[symbol] = [{"date": "...", "insider": "...", "value": ...}, ...]


def load_state() -> State:
    if STATE_FILE.exists():
        try:
            return State(**json.loads(STATE_FILE.read_text()))
        except Exception:
            pass
    return State()


def save_state(s: State) -> None:
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2))


def load_positions() -> list[Position]:
    if not POSITIONS_FILE.exists():
        return []
    try:
        return [Position(**p) for p in json.loads(POSITIONS_FILE.read_text())]
    except Exception:
        return []


def save_positions(pos: list[Position]) -> None:
    POSITIONS_FILE.write_text(json.dumps([asdict(p) for p in pos], indent=2))


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_FILE.read_text()))
    except Exception:
        return set()


def save_seen(seen: set[str]) -> None:
    # نحتفظ بآخر 5000 فقط
    SEEN_FILE.write_text(json.dumps(list(seen)[-5000:]))


def rollover_day(s: State) -> None:
    today = time.strftime("%Y-%m-%d")
    if s.day != today:
        s.day = today
        s.daily_pnl = 0.0
        s.halted = False
        # تنظيف recent_buys الأقدم من 30 يوم
        cutoff = (datetime.utcnow() - timedelta(days=CLUSTER_WINDOW_DAYS)).strftime("%Y-%m-%d")
        for sym in list(s.recent_buys.keys()):
            s.recent_buys[sym] = [b for b in s.recent_buys[sym] if b["date"] >= cutoff]
            if not s.recent_buys[sym]:
                del s.recent_buys[sym]
        save_state(s)
        log(f"new day {today}")


# ---------- SEC EDGAR ----------
def sec_get(url: str) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception as e:
        log(f"sec_get failed {url[:60]}: {e}")
        return None


def fetch_form4_filings() -> list[dict[str, Any]]:
    """يجلب آخر Form 4 filings من EDGAR RSS."""
    text = sec_get(EDGAR_FORM4_RSS)
    if not text:
        return []
    try:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(text)
        filings = []
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            link_el = entry.find("atom:link", ns)
            link = link_el.attrib.get("href", "") if link_el is not None else ""
            updated = entry.findtext("atom:updated", default="", namespaces=ns) or ""
            filing_id = entry.findtext("atom:id", default="", namespaces=ns) or link
            filings.append({
                "title": title,
                "link": link,
                "updated": updated,
                "id": filing_id,
            })
        return filings
    except Exception as e:
        log(f"parse RSS failed: {e}")
        return []


def parse_form4_xml(filing_url: str) -> dict[str, Any] | None:
    """يستخرج تفاصيل Form 4 من صفحة الـ filing."""
    # filing_url مثل: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=...
    # نحتاج إيجاد رابط الـ XML الفعلي للـ Form 4
    text = sec_get(filing_url)
    if not text:
        return None

    # ابحث عن رابط ملف primary_doc.xml
    m = re.search(r'href="([^"]*primary_doc\.xml)"', text)
    if not m:
        # بديل: ابحث عن أي xml في الصفحة
        m = re.search(r'href="([^"]*\.xml)"', text)
        if not m:
            return None

    xml_url = m.group(1)
    if xml_url.startswith("/"):
        xml_url = "https://www.sec.gov" + xml_url

    xml_text = sec_get(xml_url)
    if not xml_text:
        return None

    try:
        root = ET.fromstring(xml_text)

        # رمز السهم
        symbol_el = root.find(".//issuerTradingSymbol")
        symbol = (symbol_el.text or "").strip().upper() if symbol_el is not None else ""

        # اسم المُبلِّغ
        name_el = root.find(".//rptOwnerName")
        insider_name = (name_el.text or "").strip() if name_el is not None else ""

        # المنصب
        title = ""
        is_officer = root.find(".//isOfficer")
        if is_officer is not None and (is_officer.text or "").strip() in ("1", "true"):
            t = root.find(".//officerTitle")
            if t is not None and t.text:
                title = t.text.strip()
        is_ten = root.find(".//isTenPercentOwner")
        if is_ten is not None and (is_ten.text or "").strip() in ("1", "true"):
            title = (title + " 10% Owner").strip()

        # الصفقات (نبحث عن non-derivative purchases فقط)
        total_value = 0.0
        total_shares = 0
        is_purchase = False
        for tx in root.findall(".//nonDerivativeTransaction"):
            code_el = tx.find(".//transactionCode")
            code = (code_el.text or "").strip() if code_el is not None else ""
            if code != "P":  # P = open market purchase
                continue
            is_purchase = True
            shares_el = tx.find(".//transactionShares/value")
            price_el = tx.find(".//transactionPricePerShare/value")
            try:
                shares = float((shares_el.text or "0") if shares_el is not None else "0")
                price = float((price_el.text or "0") if price_el is not None else "0")
                total_value += shares * price
                total_shares += int(shares)
            except (ValueError, TypeError):
                continue

        if not is_purchase or not symbol:
            return None

        return {
            "symbol": symbol,
            "insider_name": insider_name,
            "title": title,
            "total_value": total_value,
            "total_shares": total_shares,
            "filing_url": filing_url,
            "xml_url": xml_url,
        }
    except Exception as e:
        log(f"parse XML failed: {e}")
        return None


# ---------- market data ----------
def get_market_cap(symbol: str, ib=None) -> float | None:
    """يجلب market cap من yfinance (أبسط) أو IBKR."""
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info
        cap = info.get("marketCap")
        if cap:
            return float(cap)
    except Exception as e:
        log(f"yfinance market_cap failed for {symbol}: {e}")
    return None


# ---------- IBKR ----------
def connect_ibkr(live: bool):
    try:
        from ib_insync import IB
    except ImportError:
        log("ib_insync not installed. run: pip install ib_insync")
        return None
    ib = IB()
    port = IBKR_LIVE_PORT if live else IBKR_PAPER_PORT
    try:
        ib.connect(IBKR_HOST, port, clientId=IBKR_CLIENT_ID, timeout=15)
        log(f"IBKR connected ({'LIVE' if live else 'PAPER'}) on port {port}")
        return ib
    except Exception as e:
        log(f"IBKR connect failed: {e}")
        return None


def get_account_equity(ib) -> float:
    try:
        for v in ib.accountValues():
            if v.tag == "NetLiquidation" and v.currency == "USD":
                return float(v.value)
    except Exception as e:
        log(f"equity fetch failed: {e}")
    return 0.0


def get_current_price(ib, symbol: str) -> float | None:
    try:
        from ib_insync import Stock
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        ticker = ib.reqMktData(contract, "", False, False)
        ib.sleep(2)
        price = ticker.marketPrice()
        ib.cancelMktData(contract)
        if price and price > 0:
            return float(price)
    except Exception as e:
        log(f"price fetch failed {symbol}: {e}")
    return None


def place_market_buy(ib, symbol: str, shares: int) -> bool:
    try:
        from ib_insync import Stock, MarketOrder
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        order = MarketOrder("BUY", shares)
        trade = ib.placeOrder(contract, order)
        ib.sleep(3)
        log(f"BUY order placed: {symbol} x{shares}")
        return True
    except Exception as e:
        log(f"buy order failed {symbol}: {e}")
        return False


def place_market_sell(ib, symbol: str, shares: int) -> bool:
    try:
        from ib_insync import Stock, MarketOrder
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        order = MarketOrder("SELL", shares)
        ib.placeOrder(contract, order)
        ib.sleep(3)
        log(f"SELL order placed: {symbol} x{shares}")
        return True
    except Exception as e:
        log(f"sell order failed {symbol}: {e}")
        return False


# ---------- strategy ----------
def title_passes(title: str) -> bool:
    t = (title or "").lower()
    return any(kw in t for kw in ALLOWED_TITLES)


def evaluate_signal(filing: dict[str, Any], state: State) -> tuple[bool, str]:
    """يقيّم Form 4 ويعيد (مقبول، السبب)."""
    if not title_passes(filing["title"]):
        return False, f"title not allowed: {filing['title']}"
    if filing["total_value"] < MIN_VALUE_USD:
        return False, f"value too small: ${filing['total_value']:.0f}"

    cap = get_market_cap(filing["symbol"])
    if cap is None:
        return False, "market cap unknown"
    if cap < MIN_MARKET_CAP:
        return False, f"cap too small: ${cap:.0f}"
    if cap > MAX_MARKET_CAP:
        return False, f"cap too large: ${cap:.0f}"

    return True, "PASS"


def is_cluster(symbol: str, state: State) -> bool:
    buys = state.recent_buys.get(symbol, [])
    return len(buys) >= 2  # 2+ insiders خلال 30 يوم


def record_buy(symbol: str, filing: dict[str, Any], state: State) -> None:
    state.recent_buys.setdefault(symbol, []).append({
        "date": time.strftime("%Y-%m-%d"),
        "insider": filing["insider_name"],
        "value": filing["total_value"],
    })


# ---------- core loops ----------
def scan_filings(ib, state: State, positions: list[Position],
                 seen: set[str], live: bool) -> None:
    log("scanning EDGAR Form 4 filings...")
    filings = fetch_form4_filings()
    log(f"fetched {len(filings)} filings")

    new_count = 0
    for f in filings:
        if f["id"] in seen:
            continue
        seen.add(f["id"])
        new_count += 1

        details = parse_form4_xml(f["link"])
        if not details:
            continue

        ok, reason = evaluate_signal(details, state)
        if not ok:
            log(f"  skip {details['symbol']}: {reason}")
            continue

        # حدّث cluster history
        record_buy(details["symbol"], details, state)
        cluster = is_cluster(details["symbol"], state)

        # تجنب الازدواج إذا عندنا مركز
        if any(p.symbol == details["symbol"] for p in positions):
            log(f"  already holding {details['symbol']}")
            continue

        if len(positions) >= MAX_POSITIONS:
            log("max positions reached")
            break

        # احسب الحجم
        equity = get_account_equity(ib) if ib else 10000.0
        if state.starting_equity == 0:
            state.starting_equity = equity
        position_value = equity * POSITION_PCT
        price = get_current_price(ib, details["symbol"]) if ib else None
        if not price:
            log(f"  no price for {details['symbol']}")
            continue
        shares = max(1, int(position_value / price))

        msg = (
            f"💼 INSIDER BUY signal\n"
            f"{details['symbol']}  ({details['insider_name']})\n"
            f"title: {details['title']}\n"
            f"value: ${details['total_value']:,.0f}\n"
            f"price: ${price:.2f}  shares: {shares}\n"
            f"cluster: {'YES ⭐' if cluster else 'no'}\n"
            f"{details['filing_url']}"
        )
        log(msg.replace("\n", " | "))
        tg(msg)

        if ib and place_market_buy(ib, details["symbol"], shares):
            positions.append(Position(
                symbol=details["symbol"],
                shares=shares,
                entry_price=price,
                entry_date=time.strftime("%Y-%m-%d"),
                high_price=price,
                insider_name=details["insider_name"],
                insider_title=details["title"],
                filing_url=details["filing_url"],
            ))
            save_positions(positions)

        time.sleep(1)  # لطيف على EDGAR

    save_seen(seen)
    save_state(state)
    log(f"scan done. {new_count} new filings processed.")


def manage_positions(ib, state: State, positions: list[Position]) -> list[Position]:
    if not positions or not ib:
        return positions
    keep: list[Position] = []
    for p in positions:
        price = get_current_price(ib, p.symbol)
        if price is None:
            keep.append(p)
            continue

        if price > p.high_price:
            p.high_price = price

        change = (price - p.entry_price) / p.entry_price
        trail_drop = (p.high_price - price) / p.high_price
        age_days = (datetime.utcnow() - datetime.strptime(p.entry_date, "%Y-%m-%d")).days

        exit_reason = None
        if trail_drop >= TRAILING_STOP_PCT:
            exit_reason = "TRAIL_STOP"
        elif change >= TAKE_PROFIT_PCT:
            exit_reason = "TAKE_PROFIT"
        elif age_days >= MAX_HOLD_DAYS:
            exit_reason = "TIME_EXIT"

        if exit_reason:
            pnl = (price - p.entry_price) * p.shares
            state.daily_pnl += pnl
            place_market_sell(ib, p.symbol, p.shares)
            msg = (
                f"{'💰' if pnl >= 0 else '🔻'} CLOSE {exit_reason}\n"
                f"{p.symbol}  pnl=${pnl:+.2f}  ({change*100:+.1f}%)\n"
                f"held {age_days}d"
            )
            log(msg.replace("\n", " | "))
            tg(msg)
        else:
            keep.append(p)

    save_positions(keep)
    save_state(state)
    return keep


# ---------- commands ----------
def cmd_check() -> None:
    state = load_state()
    positions = load_positions()
    print(f"day:           {state.day}")
    print(f"daily_pnl:     ${state.daily_pnl:+.2f}")
    print(f"halted:        {state.halted}")
    print(f"positions:     {len(positions)}")
    for p in positions:
        print(f"  {p.symbol}  shares={p.shares}  entry=${p.entry_price:.2f}  date={p.entry_date}")
    print(f"recent_buys symbols: {len(state.recent_buys)}")
    print(f"telegram set:  {bool(TELEGRAM_TOKEN and TELEGRAM_CHAT)}")


def main_loop(live: bool, scan_once: bool = False):
    state = load_state()
    positions = load_positions()
    seen = load_seen()
    mode = "LIVE" if live else "PAPER"
    log(f"smart_insider_bot starting ({mode})")
    tg(f"🚀 smart_insider_bot started ({mode})")

    ib = connect_ibkr(live)
    if not ib:
        log("could not connect to IBKR Gateway. Make sure it's running.")
        tg("❌ insider bot: IBKR connection failed")
        return

    if state.starting_equity == 0:
        state.starting_equity = get_account_equity(ib)
        save_state(state)
    log(f"account equity: ${get_account_equity(ib):.2f}")

    last_scan = 0.0
    last_position_check = 0.0

    try:
        while True:
            rollover_day(state)

            # kill-switch
            if state.starting_equity > 0:
                loss_pct = state.daily_pnl / state.starting_equity
                if loss_pct <= -DAILY_LOSS_LIMIT_PCT and not state.halted:
                    state.halted = True
                    save_state(state)
                    tg(f"💀 daily loss limit hit ({loss_pct*100:.1f}%). halted.")

            now = time.time()

            if not state.halted and now - last_scan >= SCAN_INTERVAL_SEC:
                scan_filings(ib, state, positions, seen, live)
                last_scan = now
                if scan_once:
                    break

            if now - last_position_check >= POSITION_CHECK_SEC:
                positions = manage_positions(ib, state, positions)
                last_position_check = now

            ib.sleep(5)
    except KeyboardInterrupt:
        log("stopped by user")
        tg("🛑 smart_insider_bot stopped")
    finally:
        try:
            ib.disconnect()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="⚠️ live trading on IBKR live port")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--scan-once", action="store_true", help="one scan then exit")
    args = ap.parse_args()

    if args.check:
        cmd_check()
        return 0

    main_loop(live=args.live, scan_once=args.scan_once)
    return 0


if __name__ == "__main__":
    sys.exit(main())
