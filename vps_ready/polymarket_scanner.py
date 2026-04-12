"""
polymarket_scanner.py — Polymarket Smart Scanner & Selective Auto-Trader
========================================================================
يمسح كل أسواق Polymarket النشطة، يكتشف الفرص، يرسل تنبيهات تيليجرام،
ويتداول تلقائياً فقط لمّا الشروط الصارمة كلها تتحقق.

الإشارات:
  1. تحرك سعر مفاجئ >10% (هبوط = فرصة شراء)
  2. ارتفاع حجم غير عادي (3x المعدل)
  3. فرق بين سعر العملة الحقيقي وسعر Polymarket (أسواق كريبتو)

شروط التداول التلقائي (كلها لازم تتحقق):
  - Edge > 5% بعد الرسوم
  - السعر بين 0.10 و 0.85
  - السوق فيه سيولة كافية (>$5000)
  - السوق ما ينتهي خلال 24 ساعة
  - ما عندنا صفقة مفتوحة بنفس السوق
  - ما تجاوزنا الحد اليومي
  - وقف خسارة 25% + جني أرباح 40%

استخدام:
    python3 polymarket_scanner.py                # مسح + paper trade
    python3 polymarket_scanner.py --scan-only    # تنبيهات فقط بدون تداول
    python3 polymarket_scanner.py --live         # تداول حقيقي
    python3 polymarket_scanner.py --check        # عرض الحالة

المتطلبات:
    pip install requests python-dotenv
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
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

STATE_FILE = BASE_DIR / "scanner_state.json"
PRICES_FILE = BASE_DIR / "scanner_prices.json"
LOG_FILE = BASE_DIR / "scanner.log"
ENV_FILE = BASE_DIR / ".env3"

load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# ---------- config ----------
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Scanner
SCAN_INTERVAL_SEC = 300          # مسح كل 5 دقائق
ALERT_MOVE_PCT = 10.0            # تنبيه لو السعر تحرك >10%
VOLUME_SPIKE_MULT = 3.0          # تنبيه لو الحجم 3x المعدل

# شروط التداول التلقائي (كل الشروط لازم تتحقق)
MIN_EDGE_PCT = 5.0               # أقل edge بعد الرسوم
MIN_PRICE = 0.10                 # لا تشتري تحت هذا
MAX_PRICE = 0.85                 # لا تشتري فوق هذا
MIN_MARKET_VOLUME = 5000         # أقل حجم سوق $
MIN_HOURS_TO_EXPIRY = 24         # تجنب الأسواق اللي تنتهي قريب
TRADE_SIZE_USD = 3.0             # حجم الصفقة
MAX_OPEN_POSITIONS = 5           # أقصى صفقات مفتوحة
MAX_DAILY_TRADES = 10            # أقصى صفقات يومية
MAX_DAILY_LOSS_USD = 10.0        # وقف خسارة يومي

# إدارة المخاطر
STOP_LOSS_PCT = 25.0             # وقف خسارة لكل صفقة
TAKE_PROFIT_PCT = 40.0           # جني أرباح لكل صفقة
MAX_HOLD_HOURS = 48              # أقصى مدة احتفاظ

# تقدير الرسوم
FEE_RATE = 0.02                  # معدل رسوم تقريبي 2%

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

# Proxy
_PROXY = os.getenv("HTTPS_PROXY", "") or os.getenv("HTTP_PROXY", "")
PROXIES = {"http": _PROXY, "https": _PROXY} if _PROXY else {}


# ---------- logging ----------
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
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log(f"tg error: {e}")


# ---------- fees ----------
def fee_pct(price: float) -> float:
    """تقدير رسوم Polymarket كنسبة مئوية."""
    return 2 * min(price, 1 - price) * FEE_RATE * 100


def net_edge(entry: float, target: float) -> float:
    """حساب الـedge الصافي بعد رسوم الدخول والخروج."""
    if target <= entry:
        return 0.0
    gross = (target - entry) / entry * 100
    return gross - fee_pct(entry) - fee_pct(target)


# ---------- state ----------
@dataclass
class State:
    day: str = ""
    daily_trades: int = 0
    daily_pnl: float = 0.0
    halted: bool = False
    positions: list[dict] = field(default_factory=list)
    scan_count: int = 0


def load_state() -> State:
    if STATE_FILE.exists():
        try:
            return State(**json.loads(STATE_FILE.read_text()))
        except Exception:
            pass
    return State()


def save_state(s: State) -> None:
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2))


def load_prices() -> dict:
    if PRICES_FILE.exists():
        try:
            return json.loads(PRICES_FILE.read_text())
        except Exception:
            pass
    return {}


def save_prices(p: dict) -> None:
    PRICES_FILE.write_text(json.dumps(p, indent=2))


def rollover_day(s: State) -> None:
    today = time.strftime("%Y-%m-%d")
    if s.day != today:
        s.day = today
        s.daily_trades = 0
        s.daily_pnl = 0.0
        s.halted = False
        save_state(s)
        log(f"=== new day {today} ===")


# ---------- market data ----------
def fetch_markets(limit: int = 1000) -> list[dict]:
    """جلب كافة الأسواق النشطة (حتى 1000 سوق) لتغطية شاملة."""
    markets = []
    offset = 0
    while offset < limit:
        try:
            r = requests.get(
                f"{GAMMA_API}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": 100,
                    "offset": offset,
                },
                proxies=PROXIES,
                timeout=15,
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            markets.extend(batch)
            offset += len(batch)
            if len(batch) < 100:
                break
        except Exception as e:
            log(f"fetch_markets error: {e}")
            break
    log(f"✅ تم مسح {len(markets)} سوق نشط حالياً.")
    return markets


def fetch_midpoint(token_id: str) -> float | None:
    """جلب السعر الحالي (midpoint)."""
    try:
        r = requests.get(
            f"{CLOB_API}/midpoint",
            params={"token_id": token_id},
            proxies=PROXIES,
            timeout=10,
        )
        r.raise_for_status()
        return float(r.json().get("mid", 0))
    except Exception:
        return None


def fetch_crypto_price(symbol: str) -> float | None:
    """جلب سعر العملة الرقمية من CoinGecko."""
    coin_map = {
        "BTC": "bitcoin", "BITCOIN": "bitcoin",
        "ETH": "ethereum", "ETHEREUM": "ethereum",
        "SOL": "solana", "SOLANA": "solana",
        "BNB": "binancecoin", "XRP": "ripple",
        "DOGE": "dogecoin",
    }
    coin_id = coin_map.get(symbol.upper())
    if not coin_id:
        return None
    try:
        r = requests.get(
            f"{COINGECKO_API}/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get(coin_id, {}).get("usd")
    except Exception:
        return None


# ---------- market parsing ----------
def parse_market(market: dict) -> dict | None:
    """استخراج بيانات السوق الموحّدة."""
    market_id = market.get("id", "")
    question = market.get("question", "")
    if not market_id or not question:
        return None

    yes_price = no_price = 0.0
    yes_tid = no_tid = ""

    # tokens array
    tokens = market.get("tokens", [])
    if tokens and len(tokens) >= 2:
        for tok in tokens:
            outcome = (tok.get("outcome") or tok.get("name") or "").upper()
            tid = str(tok.get("token_id") or tok.get("id", ""))
            tp = float(tok.get("price", 0) or 0)
            if outcome == "YES":
                yes_tid, yes_price = tid, tp
            elif outcome == "NO":
                no_tid, no_price = tid, tp
    else:
        # outcomePrices fallback
        op = market.get("outcomePrices", "")
        ct = market.get("clobTokenIds", "")
        try:
            prices = json.loads(op) if isinstance(op, str) else op
            tids = json.loads(ct) if isinstance(ct, str) else ct
            if prices and len(prices) >= 2 and tids and len(tids) >= 2:
                yes_price = float(prices[0])
                no_price = float(prices[1])
                yes_tid = str(tids[0])
                no_tid = str(tids[1])
        except Exception:
            return None

    if not yes_tid or yes_price <= 0:
        return None

    return {
        "market_id": market_id,
        "question": question,
        "yes_price": yes_price,
        "no_price": no_price,
        "yes_tid": yes_tid,
        "no_tid": no_tid,
        "volume": float(market.get("volume", 0) or 0),
        "liquidity": float(market.get("liquidity", 0) or 0),
        "end_date": market.get("endDate", ""),
    }


def parse_crypto_target(question: str) -> tuple[str, float] | None:
    """استخراج العملة والسعر المستهدف من سؤال السوق."""
    q = (question or "").upper()
    symbol = None
    for s in ["BITCOIN", "BTC", "ETHEREUM", "ETH", "SOLANA", "SOL", "BNB", "XRP", "DOGE"]:
        if s in q:
            symbol = s
            break
    if not symbol:
        return None

    # $70,000 format
    m = re.search(r"\$?\s*([\d]{1,3}(?:,\d{3})+(?:\.\d+)?)", question)
    if m:
        return (symbol, float(m.group(1).replace(",", "")))
    # 70k format
    m = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*[kK]\b", question)
    if m:
        return (symbol, float(m.group(1)) * 1000)
    # plain number >= 4 digits
    m = re.search(r"\$?\s*(\d{4,}(?:\.\d+)?)", question)
    if m:
        return (symbol, float(m.group(1)))
    return None


def hours_to_expiry(end_date: str) -> float:
    """حساب عدد الساعات حتى انتهاء السوق."""
    if not end_date:
        return 9999
    try:
        from datetime import datetime
        ts = datetime.fromisoformat(end_date.replace("Z", "+00:00")).timestamp()
        return max(0, (ts - time.time()) / 3600)
    except Exception:
        return 9999


# ---------- signal detection ----------
@dataclass
class Signal:
    market_id: str
    token_id: str
    question: str
    side: str
    price: float
    edge_pct: float
    signal_type: str
    strength: str
    details: str


def detect_signals(markets: list[dict], prev_prices: dict) -> tuple[list[Signal], dict]:
    """تحليل الأسواق واكتشاف الإشارات."""
    signals: list[Signal] = []
    current: dict = {}
    crypto_cache: dict[str, float | None] = {}

    for raw in markets:
        m = parse_market(raw)
        if not m:
            continue

        mid = m["market_id"]
        current[mid] = {
            "yes_price": m["yes_price"],
            "no_price": m["no_price"],
            "yes_tid": m["yes_tid"],
            "no_tid": m["no_tid"],
            "question": m["question"],
            "volume": m["volume"],
            "end_date": m["end_date"],
            "ts": int(time.time()),
        }

        # --- Signal 1: Price Movement ---
        prev = prev_prices.get(mid)
        if prev and prev.get("yes_price", 0) > 0:
            prev_yes = prev["yes_price"]
            change = (m["yes_price"] - prev_yes) / prev_yes * 100

            if abs(change) >= ALERT_MOVE_PCT:
                if change < 0 and m["yes_price"] >= MIN_PRICE:
                    edge = abs(change) - fee_pct(m["yes_price"]) * 2
                    strength = "strong" if edge > 10 else "medium" if edge > 5 else "weak"
                    signals.append(Signal(
                        market_id=mid, token_id=m["yes_tid"],
                        question=m["question"], side="YES",
                        price=m["yes_price"], edge_pct=edge,
                        signal_type="price_drop", strength=strength,
                        details=f"YES {change:+.1f}% ({prev_yes:.2f} -> {m['yes_price']:.2f})",
                    ))
                elif change > 0 and m["no_price"] >= MIN_PRICE:
                    edge = abs(change) - fee_pct(m["no_price"]) * 2
                    strength = "strong" if edge > 10 else "medium" if edge > 5 else "weak"
                    signals.append(Signal(
                        market_id=mid, token_id=m["no_tid"],
                        question=m["question"], side="NO",
                        price=m["no_price"], edge_pct=edge,
                        signal_type="price_spike", strength=strength,
                        details=f"YES {change:+.1f}%, NO now {m['no_price']:.2f}",
                    ))

            # Volume spike
            prev_vol = prev.get("volume", 0)
            if prev_vol > 0 and m["volume"] > MIN_MARKET_VOLUME:
                ratio = m["volume"] / prev_vol
                if ratio >= VOLUME_SPIKE_MULT:
                    signals.append(Signal(
                        market_id=mid, token_id=m["yes_tid"],
                        question=m["question"], side="INFO",
                        price=m["yes_price"], edge_pct=0,
                        signal_type="volume_spike", strength="medium",
                        details=f"Volume {ratio:.1f}x (${prev_vol:,.0f} -> ${m['volume']:,.0f})",
                    ))

        # --- Signal 2: Oracle Mismatch (crypto markets) ---
        crypto = parse_crypto_target(m["question"])
        if crypto:
            symbol, target = crypto
            if symbol not in crypto_cache:
                crypto_cache[symbol] = fetch_crypto_price(symbol)
            real_price = crypto_cache[symbol]
            if real_price and target > 0:
                diff = (real_price - target) / target * 100

                if diff > 5 and m["yes_price"] < 0.80:
                    edge = net_edge(m["yes_price"], 0.90)
                    if edge > 0:
                        strength = "strong" if edge > 10 else "medium" if edge > 5 else "weak"
                        signals.append(Signal(
                            market_id=mid, token_id=m["yes_tid"],
                            question=m["question"], side="YES",
                            price=m["yes_price"], edge_pct=edge,
                            signal_type="oracle_mismatch", strength=strength,
                            details=f"{symbol} ${real_price:,.0f} above target ${target:,.0f} ({diff:+.1f}%)",
                        ))
                elif diff < -5 and m["no_price"] < 0.80:
                    edge = net_edge(m["no_price"], 0.90)
                    if edge > 0:
                        strength = "strong" if edge > 10 else "medium" if edge > 5 else "weak"
                        signals.append(Signal(
                            market_id=mid, token_id=m["no_tid"],
                            question=m["question"], side="NO",
                            price=m["no_price"], edge_pct=edge,
                            signal_type="oracle_mismatch", strength=strength,
                            details=f"{symbol} ${real_price:,.0f} below target ${target:,.0f} ({diff:+.1f}%)",
                        ))

    return signals, current


# ---------- trading ----------
def should_trade(sig: Signal, state: State, prices: dict) -> tuple[bool, str]:
    """فحص كل الشروط الصارمة قبل التداول."""
    if state.halted:
        return False, "daily loss limit"
    if state.daily_trades >= MAX_DAILY_TRADES:
        return False, f"daily cap {MAX_DAILY_TRADES}"
    if len(state.positions) >= MAX_OPEN_POSITIONS:
        return False, f"max positions {MAX_OPEN_POSITIONS}"
    if any(p["market_id"] == sig.market_id for p in state.positions):
        return False, "already in market"
    if sig.price < MIN_PRICE or sig.price > MAX_PRICE:
        return False, f"price {sig.price:.2f} outside [{MIN_PRICE}, {MAX_PRICE}]"
    if sig.edge_pct < MIN_EDGE_PCT:
        return False, f"edge {sig.edge_pct:.1f}% < {MIN_EDGE_PCT}%"
    if sig.strength == "weak":
        return False, "weak signal"
    if sig.signal_type == "volume_spike":
        return False, "volume = alert only"

    # check market volume
    mdata = prices.get(sig.market_id, {})
    vol = mdata.get("volume", 0)
    if vol < MIN_MARKET_VOLUME:
        return False, f"volume ${vol:.0f} < ${MIN_MARKET_VOLUME}"

    # check expiry
    end = mdata.get("end_date", "")
    hrs = hours_to_expiry(end)
    if hrs < MIN_HOURS_TO_EXPIRY:
        return False, f"expires in {hrs:.0f}h < {MIN_HOURS_TO_EXPIRY}h"

    return True, "OK"


def place_order(sig: Signal, live: bool) -> dict | None:
    """تنفيذ الصفقة (paper أو live)."""
    pos = {
        "market_id": sig.market_id,
        "token_id": sig.token_id,
        "side": sig.side,
        "entry_price": sig.price,
        "size_usd": TRADE_SIZE_USD,
        "opened_at": int(time.time()),
        "question": sig.question,
    }

    if not live:
        log(f"[PAPER] BUY {sig.side} @ {sig.price:.2f} | {sig.question[:60]}")
        tg(f"📋 PAPER BUY\n{sig.question[:80]}\n{sig.side} @ {sig.price:.2f}\nedge={sig.edge_pct:+.1f}%")
        return pos

    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OrderArgs, OrderType

        key = os.getenv("PK") or os.getenv("PRIVATE_KEY")
        funder = os.getenv("FUNDER")
        client = ClobClient(
            "https://clob.polymarket.com",
            key=key, chain_id=137,
            signature_type=1, funder=funder,
        )
        client.set_api_creds(client.create_or_derive_api_creds())
        order_args = OrderArgs(
            price=sig.price,
            size=TRADE_SIZE_USD / sig.price,
            side="BUY",
            token_id=sig.token_id,
        )
        signed = client.create_order(order_args)
        resp = client.post_order(signed, OrderType.GTC)
        if not resp or not resp.get("success"):
            log(f"order failed: {resp}")
            return None
        log(f"[LIVE] BUY {sig.side} @ {sig.price:.2f} | order={resp.get('orderID', '?')[:12]}")
        tg(f"✅ LIVE BUY\n{sig.question[:80]}\n{sig.side} @ {sig.price:.2f}")
        return pos
    except Exception as e:
        log(f"order error: {e}")
        tg(f"❌ order error: {e}")
        return None


# ---------- position management ----------
def check_positions(state: State) -> None:
    """فحص الصفقات المفتوحة: وقف خسارة / جني أرباح / مدة قصوى."""
    if not state.positions:
        return

    now = int(time.time())
    keep: list[dict] = []

    for pos in state.positions:
        price = fetch_midpoint(pos["token_id"])
        if price is None:
            keep.append(pos)
            continue

        entry = pos["entry_price"]
        change = (price - entry) / entry * 100
        age_h = (now - pos["opened_at"]) / 3600

        exit_reason = None
        if change <= -STOP_LOSS_PCT:
            exit_reason = "SL"
        elif change >= TAKE_PROFIT_PCT:
            exit_reason = "TP"
        elif age_h >= MAX_HOLD_HOURS:
            exit_reason = "MAX_HOLD"

        if exit_reason:
            pnl = pos["size_usd"] * change / 100
            state.daily_pnl += pnl
            q = pos["question"][:50]
            log(f"CLOSE {exit_reason} {pos['side']} pnl={pnl:+.2f} | {q}")
            icon = "💰" if pnl >= 0 else "🔻"
            tg(f"{icon} CLOSE {exit_reason}\n{pos['question'][:70]}\npnl={pnl:+.2f}$\nprice: {entry:.2f} -> {price:.2f}")

            if state.daily_pnl <= -MAX_DAILY_LOSS_USD:
                state.halted = True
                tg(f"🛑 Daily loss limit (${state.daily_pnl:.2f})")
        else:
            keep.append(pos)

    state.positions = keep
    save_state(state)


# ---------- alert ----------
def format_alert(sig: Signal) -> str:
    """تنسيق التنبيه لتيليجرام."""
    icons = {"strong": "🔴", "medium": "🟡", "weak": "⚪"}
    types = {
        "price_drop": "📉", "price_spike": "📈",
        "volume_spike": "📊", "oracle_mismatch": "🔮",
    }
    i = icons.get(sig.strength, "⚪")
    t = types.get(sig.signal_type, "📡")

    return (
        f"{i}{t} <b>{sig.signal_type.replace('_', ' ').upper()}</b>\n"
        f"<b>{sig.question[:80]}</b>\n"
        f"Side: {sig.side} @ {sig.price:.2f}\n"
        f"Edge: {sig.edge_pct:+.1f}%\n"
        f"{sig.details}"
    )


# ---------- main ----------
def cmd_check():
    state = load_state()
    prices = load_prices()
    print(f"Day: {state.day} | Trades: {state.daily_trades} | PnL: ${state.daily_pnl:+.2f}")
    print(f"Positions: {len(state.positions)}")
    for p in state.positions:
        print(f"  {p['side']} @ {p['entry_price']:.2f} | {p['question'][:60]}")
    print(f"Markets tracked: {len(prices)}")
    print(f"Scans: {state.scan_count} | Halted: {state.halted}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="real trading")
    ap.add_argument("--scan-only", action="store_true", help="alerts only")
    ap.add_argument("--check", action="store_true", help="show status")
    args = ap.parse_args()

    if args.check:
        cmd_check()
        return 0

    state = load_state()
    prev_prices = load_prices()
    live = args.live
    scan_only = args.scan_only
    mode = "LIVE" if live else ("SCAN" if scan_only else "PAPER")

    log(f"polymarket_scanner started | mode={mode}")
    log(f"edge>{MIN_EDGE_PCT}% | SL={STOP_LOSS_PCT}% | TP={TAKE_PROFIT_PCT}% | size=${TRADE_SIZE_USD}")
    log(f"max_positions={MAX_OPEN_POSITIONS} | max_daily={MAX_DAILY_TRADES} | max_loss=${MAX_DAILY_LOSS_USD}")
    tg(
        f"🔍 Scanner started ({mode})\n"
        f"Edge: >{MIN_EDGE_PCT}% | Size: ${TRADE_SIZE_USD}\n"
        f"SL: {STOP_LOSS_PCT}% | TP: {TAKE_PROFIT_PCT}%"
    )

    try:
        while True:
            rollover_day(state)

            if state.halted:
                log("halted; sleeping")
                time.sleep(SCAN_INTERVAL_SEC)
                continue

            # 1) manage positions
            if not scan_only:
                check_positions(state)

            # 2) scan
            log("scanning...")
            markets = fetch_markets()
            if not markets:
                log("no markets fetched")
                time.sleep(SCAN_INTERVAL_SEC)
                continue

            log(f"fetched {len(markets)} markets")
            state.scan_count += 1

            # 3) detect signals
            signals, current_prices = detect_signals(markets, prev_prices)

            # 4) process signals
            for sig in sorted(signals, key=lambda s: s.edge_pct, reverse=True):
                log(f"  {sig.signal_type} | {sig.side} {sig.price:.2f} | edge={sig.edge_pct:+.1f}% | {sig.question[:50]}")
                tg(format_alert(sig))

                if not scan_only and not state.halted:
                    ok, reason = should_trade(sig, state, current_prices)
                    if ok:
                        pos = place_order(sig, live)
                        if pos:
                            state.positions.append(pos)
                            state.daily_trades += 1
                            save_state(state)
                    else:
                        log(f"    skip: {reason}")

            if not signals:
                log("no signals")

            # 5) save
            prev_prices = current_prices
            save_prices(prev_prices)
            save_state(state)

            time.sleep(SCAN_INTERVAL_SEC)

    except KeyboardInterrupt:
        log("stopped by user")
        tg("🛑 Scanner stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())
