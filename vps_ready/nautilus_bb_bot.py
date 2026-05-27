#!/usr/bin/env python3
"""
Nautilus Bollinger Bands Mean Reversion Bot - Bybit Spot BTC/USDT
BB(20, 2σ) على فريم 1 ساعة
"""

import os, sys, json, time, logging, argparse, platform
from datetime import datetime, date
from pathlib import Path

import ccxt
import numpy as np
import requests
from dotenv import load_dotenv

# === المسارات ===
if platform.system() == "Windows":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")

ENV_FILE = BASE_DIR / ".env_naif"
LOG_FILE = BASE_DIR / "nautilus_bb.log"
STATE_FILE = BASE_DIR / "nautilus_bb_state.json"

load_dotenv(ENV_FILE)

API_KEY = os.getenv("BYBIT_API_KEY", "")
API_SECRET = os.getenv("BYBIT_API_SECRET", "")
USE_TESTNET = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

SYMBOL = "BTC/USDT"
TRADE_AMOUNT_USD = 10
SL_PCT = -2.0
TP_PCT = 4.0
MAX_TRADES_DAY = 6
MAX_DAILY_LOSS = 10.0
CHECK_INTERVAL = 180
BB_PERIOD = 20
BB_STD_MULT = 2

# === اللوق ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger("NautilusBB")

# === الحالة ===
def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"position": None, "daily_trades": 0, "daily_loss": 0.0,
            "last_date": str(date.today()), "total_pnl": 0.0}

def save_state(st):
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, indent=2)

def reset_daily(st):
    today = str(date.today())
    if st["last_date"] != today:
        st["daily_trades"] = 0
        st["daily_loss"] = 0.0
        st["last_date"] = today
    return st

# === تيليجرام ===
def tg_send(msg):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT, "text": f"📈 BB Bot\n{msg}",
                                  "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        log.warning(f"تيليجرام فشل: {e}")

# === السعر الحالي (ورقي) ===
def get_spot_price():
    try:
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT", timeout=10)
        return float(r.json()["result"]["list"][0]["lastPrice"])
    except Exception as e:
        log.error(f"خطأ جلب السعر: {e}")
        return None

# === حساب بولينجر باند ===
def calc_bollinger(closes, period=20, mult=2):
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    sma = np.mean(window)
    std = np.std(window, ddof=0)
    upper = sma + mult * std
    lower = sma - mult * std
    return sma, upper, lower

# === التداول ===
def init_exchange():
    ex = ccxt.bybit({"apiKey": API_KEY, "secret": API_SECRET,
                      "options": {"defaultType": "spot"}})
    if USE_TESTNET:
        ex.set_sandbox_mode(True)
    return ex

def fetch_candles(exchange):
    ohlcv = exchange.fetch_ohlcv(SYMBOL, "1h", limit=30)
    closes = np.array([c[4] for c in ohlcv])
    return closes

def execute_buy(exchange, live):
    price = get_spot_price()
    if price is None:
        return None
    qty = round(TRADE_AMOUNT_USD / price, 6)
    if live:
        try:
            order = exchange.create_market_buy_order(SYMBOL, qty)
            fill = float(order.get("average", price))
            log.info(f"🟢 شراء حقيقي: {qty} BTC @ {fill}")
            return {"entry": fill, "qty": qty, "time": str(datetime.now())}
        except Exception as e:
            log.error(f"خطأ الشراء: {e}")
            return None
    else:
        log.info(f"📝 شراء ورقي: {qty} BTC @ {price}")
        return {"entry": price, "qty": qty, "time": str(datetime.now())}

def execute_sell(exchange, pos, live, reason):
    price = get_spot_price()
    if price is None:
        return 0.0
    if live:
        try:
            exchange.create_market_sell_order(SYMBOL, pos["qty"])
            log.info(f"🔴 بيع حقيقي: {pos['qty']} BTC @ {price} ({reason})")
        except Exception as e:
            log.error(f"خطأ البيع: {e}")
            return 0.0
    else:
        log.info(f"📝 بيع ورقي: {pos['qty']} BTC @ {price} ({reason})")
    pnl = (price - pos["entry"]) * pos["qty"]
    return pnl

def check_sl_tp(state, exchange, live):
    pos = state["position"]
    if pos is None:
        return state
    price = get_spot_price()
    if price is None:
        return state
    entry = pos["entry"]
    pct = ((price - entry) / entry) * 100
    if pct <= SL_PCT:
        pnl = execute_sell(exchange, pos, live, "ستوب لوس")
        tg_send(f"⛔ ستوب لوس @ {price:.2f}\nPnL: ${pnl:.2f}")
        state["position"] = None
        state["total_pnl"] += pnl
        state["daily_loss"] += abs(pnl) if pnl < 0 else 0
    elif pct >= TP_PCT:
        pnl = execute_sell(exchange, pos, live, "تيك بروفت")
        tg_send(f"✅ تيك بروفت @ {price:.2f}\nPnL: ${pnl:.2f}")
        state["position"] = None
        state["total_pnl"] += pnl
    return state

def run_bot(live=False):
    log.info(f"=== Nautilus BB Bot | {'حقيقي' if live else 'ورقي'} ===")
    tg_send(f"تشغيل البوت - {'حقيقي' if live else 'ورقي'}")
    exchange = init_exchange()
    state = load_state()

    while True:
        try:
            state = reset_daily(state)
            state = check_sl_tp(state, exchange, live)

            closes = fetch_candles(exchange)
            sma, upper, lower = calc_bollinger(closes, BB_PERIOD, BB_STD_MULT)
            if sma is None:
                log.warning("بيانات غير كافية لحساب بولينجر")
                time.sleep(CHECK_INTERVAL)
                continue

            current_close = closes[-1]

            if state["position"] is not None and current_close >= upper:
                pnl = execute_sell(exchange, state["position"], live, "لمس الباند العلوي")
                tg_send(f"🔻 خروج - لمس الباند العلوي\nClose: {current_close:.2f} >= Upper: {upper:.2f}\nPnL: ${pnl:.2f}")
                state["position"] = None
                state["total_pnl"] += pnl
                state["daily_loss"] += abs(pnl) if pnl < 0 else 0

            if state["position"] is None and current_close <= lower:
                if state["daily_trades"] >= MAX_TRADES_DAY:
                    log.info("⚠️ وصلنا حد الصفقات اليومي")
                elif state["daily_loss"] >= MAX_DAILY_LOSS:
                    log.info("⚠️ وصلنا حد الخسارة اليومي")
                else:
                    pos = execute_buy(exchange, live)
                    if pos:
                        state["position"] = pos
                        state["daily_trades"] += 1
                        tg_send(f"🟢 شراء @ {pos['entry']:.2f}\nClose <= Lower Band ({lower:.2f})")

            log.info(f"BB: Lower={lower:.2f} SMA={sma:.2f} Upper={upper:.2f} | Close={current_close:.2f} | صفقات: {state['daily_trades']} | PnL: ${state['total_pnl']:.2f}")
            save_state(state)
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            log.info("إيقاف البوت...")
            save_state(state)
            break
        except Exception as e:
            log.error(f"خطأ: {e}")
            time.sleep(60)

def check_status():
    state = load_state()
    price = get_spot_price()
    print(f"=== Nautilus BB Bot Status ===")
    print(f"السعر الحالي: ${price:,.2f}" if price else "السعر: غير متوفر")
    print(f"صفقة مفتوحة: {'نعم' if state['position'] else 'لا'}")
    if state["position"]:
        e = state["position"]["entry"]
        pct = ((price - e) / e) * 100 if price else 0
        print(f"  دخول: ${e:,.2f} | تغير: {pct:.2f}%")
    print(f"صفقات اليوم: {state['daily_trades']}/{MAX_TRADES_DAY}")
    print(f"خسارة اليوم: ${state['daily_loss']:.2f}/{MAX_DAILY_LOSS}")
    print(f"إجمالي الربح: ${state['total_pnl']:.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nautilus Bollinger Bands Bot")
    parser.add_argument("--live", action="store_true", help="تداول حقيقي")
    parser.add_argument("--check", action="store_true", help="عرض الحالة")
    args = parser.parse_args()
    if args.check:
        check_status()
    else:
        run_bot(live=args.live)
