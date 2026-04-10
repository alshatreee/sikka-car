"""
naif_signal_bot.py — Binance Futures Auto-Trader from Naif Alert Telegram Channel
==================================================================================

يراقب قناة Naif Alert على تيلجرام ويفتح صفقات تلقائياً على Binance Futures
بناءً على التوصيات.

الفلاتر:
  - قوي جداً 🔥 = تنفيذ فوري
  - قوي 💪    = تنفيذ فوري
  - متوسط ⚖️  = تجاهل (افتراضي)

استخدام:
    python3 naif_signal_bot.py              # paper mode
    python3 naif_signal_bot.py --live       # تنفيذ فعلي على Binance
    python3 naif_signal_bot.py --check      # فحص الاتصال واخرج

المتطلبات:
    pip install telethon ccxt python-dotenv requests

إعداد أول مرة:
    1. روح https://my.telegram.org → API Development Tools
       أنشئ تطبيق واحصل على api_id و api_hash
    2. أنشئ API Key من Binance (Futures مفعّل)
    3. حط كل شيء في .env_naif
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from dotenv import load_dotenv

# ---------- paths ----------
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = BASE_DIR / ".env_naif"
STATE_FILE = BASE_DIR / "naif_state.json"
LOG_FILE = BASE_DIR / "naif_bot.log"

load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# ---------- config ----------
# Telegram
TG_API_ID = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_CHANNEL = os.getenv("TG_CHANNEL", "Naif_Alert")
TG_SESSION = str(BASE_DIR / "naif_session")

# Binance
BINANCE_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "false").lower() == "true"

# Notifications
NOTIFY_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

# Trading params
TRADE_SIZE_USDT = float(os.getenv("NAIF_TRADE_SIZE", "10"))  # $ per trade
LEVERAGE = int(os.getenv("NAIF_LEVERAGE", "5"))
MAX_DAILY_TRADES = int(os.getenv("NAIF_MAX_DAILY", "15"))
MAX_DAILY_LOSS_USD = float(os.getenv("NAIF_MAX_LOSS", "20"))
MAX_OPEN_POSITIONS = int(os.getenv("NAIF_MAX_POSITIONS", "5"))

# Filters
MIN_TREND_STRENGTH = int(os.getenv("NAIF_MIN_TREND", "80"))  # % minimum
MIN_VOLUME_STRENGTH = float(os.getenv("NAIF_MIN_VOLUME", "100"))  # % minimum
ALLOWED_FRAMES = os.getenv("NAIF_FRAMES", "4h,1d").lower().split(",")

# Risk management
SL_PCT = float(os.getenv("NAIF_SL_PCT", "2.0"))   # stop loss %
TP_PCT = float(os.getenv("NAIF_TP_PCT", "4.0"))   # take profit %
TRAILING_STOP = os.getenv("NAIF_TRAILING", "false").lower() == "true"

PAPER_MODE = "--live" not in sys.argv


# ---------- logging ----------
def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(msg: str) -> None:
    """Send notification via Telegram bot."""
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
        log(f"notify failed: {e}")


# ---------- state ----------
@dataclass
class State:
    day: str = ""
    daily_trades: int = 0
    daily_pnl: float = 0.0
    halted: bool = False
    open_positions: dict[str, dict] = field(default_factory=dict)
    trade_history: list[dict] = field(default_factory=list)


def load_state() -> State:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return State(**data)
        except Exception:
            pass
    return State()


def save_state(s: State) -> None:
    STATE_FILE.write_text(json.dumps(asdict(s), indent=2))


def rollover_day(s: State) -> None:
    today = time.strftime("%Y-%m-%d")
    if s.day != today:
        s.day = today
        s.daily_trades = 0
        s.daily_pnl = 0.0
        s.halted = False
        save_state(s)
        log(f"=== new day {today} — counters reset ===")


# ---------- signal parser ----------
@dataclass
class Signal:
    direction: str       # "BUY" or "SELL"
    symbol: str          # e.g. "BTCUSDT"
    price: float         # entry price
    frame: str           # e.g. "4h"
    signal_type: str     # e.g. "إشارة لحظية"
    volume_strength: float   # e.g. 207.5
    trend_strength: int      # e.g. 99
    trend_level: str     # "قوي جداً 🔥" / "قوي 💪" / "متوسط ⚖️"
    timestamp: str       # signal time


def parse_signal(text: str) -> Signal | None:
    """Parse a Naif Alert message into a Signal object."""
    if not text:
        return None

    # Direction
    direction = None
    if "🟢" in text or "BUY" in text or "LONG" in text:
        direction = "BUY"
    elif "🔴" in text or "SELL" in text or "SHORT" in text:
        direction = "SELL"
    if not direction:
        return None

    # Symbol
    sym_match = re.search(r"العملة:\s*(\w+USDT)", text)
    if not sym_match:
        sym_match = re.search(r"([A-Z0-9]+USDT)", text)
    if not sym_match:
        return None
    symbol = sym_match.group(1).upper()

    # Price
    price_match = re.search(r"السعر:\s*([\d.]+)", text)
    if not price_match:
        return None
    price = float(price_match.group(1))

    # Frame
    frame_match = re.search(r"الفريم:\s*(\w+)", text)
    frame = frame_match.group(1).lower() if frame_match else "4h"

    # Signal type
    signal_type = "عادي"
    if "إشارة لحظية" in text:
        signal_type = "إشارة لحظية"

    # Volume strength
    vol_match = re.search(r"قوة الحجم:\s*([\d.]+)%", text)
    volume_strength = float(vol_match.group(1)) if vol_match else 0

    # Trend strength
    trend_match = re.search(r"قوة الاتجاه:\s*(\d+)%", text)
    trend_strength = int(trend_match.group(1)) if trend_match else 0

    # Trend level
    trend_level = "متوسط ⚖️"
    if "قوي جداً" in text or "🔥" in text:
        trend_level = "قوي جداً 🔥"
    elif "قوي" in text or "💪" in text:
        trend_level = "قوي 💪"

    # Time
    time_match = re.search(r"الوقت:\s*([\d:]+)", text)
    timestamp = time_match.group(1) if time_match else time.strftime("%H:%M:%S")

    return Signal(
        direction=direction,
        symbol=symbol,
        price=price,
        frame=frame,
        signal_type=signal_type,
        volume_strength=volume_strength,
        trend_strength=trend_strength,
        trend_level=trend_level,
        timestamp=timestamp,
    )


def should_trade(signal: Signal, state: State) -> tuple[bool, str]:
    """Check if we should execute this signal."""
    # Daily limits
    if state.halted:
        return False, "halted — daily loss limit"
    if state.daily_trades >= MAX_DAILY_TRADES:
        return False, f"daily trade cap ({MAX_DAILY_TRADES})"
    if state.daily_pnl <= -MAX_DAILY_LOSS_USD:
        state.halted = True
        save_state(state)
        return False, f"daily loss limit (${MAX_DAILY_LOSS_USD})"

    # Max positions
    if len(state.open_positions) >= MAX_OPEN_POSITIONS:
        return False, f"max positions ({MAX_OPEN_POSITIONS})"

    # Already in this symbol
    if signal.symbol in state.open_positions:
        return False, f"already in {signal.symbol}"

    # Frame filter
    if signal.frame not in ALLOWED_FRAMES:
        return False, f"frame {signal.frame} not in {ALLOWED_FRAMES}"

    # Trend strength filter
    if signal.trend_strength < MIN_TREND_STRENGTH:
        return False, f"trend {signal.trend_strength}% < {MIN_TREND_STRENGTH}%"

    # Volume strength filter
    if signal.volume_strength < MIN_VOLUME_STRENGTH:
        return False, f"volume {signal.volume_strength}% < {MIN_VOLUME_STRENGTH}%"

    return True, "OK"


# ---------- Binance execution ----------
def get_exchange():
    """Create ccxt Binance Futures client."""
    import ccxt

    config = {
        "apiKey": BINANCE_KEY,
        "secret": BINANCE_SECRET,
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",
            "adjustForTimeDifference": True,
        },
    }

    if BINANCE_TESTNET:
        exchange = ccxt.binanceusdm(config)
        exchange.set_sandbox_mode(True)
    else:
        exchange = ccxt.binanceusdm(config)

    # Use residential proxy to bypass Binance geo-restrictions on datacenter IPs
    proxy = os.getenv("HTTPS_PROXY", "") or os.getenv("HTTP_PROXY", "")
    if proxy:
        exchange.proxies = {"http": proxy, "https": proxy}

    return exchange


def execute_trade(signal: Signal, state: State) -> bool:
    """Execute a trade on Binance Futures."""

    # Calculate SL and TP
    if signal.direction == "BUY":
        sl_price = signal.price * (1 - SL_PCT / 100)
        tp_price = signal.price * (1 + TP_PCT / 100)
    else:
        sl_price = signal.price * (1 + SL_PCT / 100)
        tp_price = signal.price * (1 - TP_PCT / 100)

    msg = (
        f"{'🟢' if signal.direction == 'BUY' else '🔴'} {signal.direction} {signal.symbol}\n"
        f"السعر: {signal.price}\n"
        f"SL: {sl_price:.4f} ({SL_PCT}%)\n"
        f"TP: {tp_price:.4f} ({TP_PCT}%)\n"
        f"الحجم: ${TRADE_SIZE_USDT} x{LEVERAGE}\n"
        f"قوة الاتجاه: {signal.trend_strength}% {signal.trend_level}"
    )

    if PAPER_MODE:
        log(f"[PAPER] {signal.direction} {signal.symbol} @ {signal.price}")
        notify(f"📋 PAPER\n{msg}")
        state.open_positions[signal.symbol] = {
            "direction": signal.direction,
            "entry_price": signal.price,
            "sl": sl_price,
            "tp": tp_price,
            "size_usdt": TRADE_SIZE_USDT,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        state.daily_trades += 1
        save_state(state)
        return True

    try:
        exchange = get_exchange()

        # Set leverage
        try:
            exchange.set_leverage(LEVERAGE, signal.symbol)
        except Exception as e:
            log(f"set_leverage warning: {e}")

        # Set margin mode to isolated
        try:
            exchange.set_margin_mode("isolated", signal.symbol)
        except Exception as e:
            log(f"set_margin_mode warning: {e}")

        # Calculate amount
        ticker = exchange.fetch_ticker(signal.symbol)
        current_price = ticker["last"]
        notional = TRADE_SIZE_USDT * LEVERAGE
        amount = notional / current_price

        # Get market info for precision
        market = exchange.market(signal.symbol)
        amount = exchange.amount_to_precision(signal.symbol, amount)

        # Place market order
        side = "buy" if signal.direction == "BUY" else "sell"
        order = exchange.create_order(
            symbol=signal.symbol,
            type="market",
            side=side,
            amount=float(amount),
        )
        log(f"[LIVE] {side.upper()} {signal.symbol} amount={amount} | order={order.get('id', '?')}")

        # Place SL
        sl_side = "sell" if signal.direction == "BUY" else "buy"
        try:
            sl_order = exchange.create_order(
                symbol=signal.symbol,
                type="stop_market",
                side=sl_side,
                amount=float(amount),
                params={
                    "stopPrice": exchange.price_to_precision(signal.symbol, sl_price),
                    "closePosition": True,
                },
            )
            log(f"  SL set @ {sl_price:.4f}")
        except Exception as e:
            log(f"  SL failed: {e}")

        # Place TP
        try:
            tp_order = exchange.create_order(
                symbol=signal.symbol,
                type="take_profit_market",
                side=sl_side,
                amount=float(amount),
                params={
                    "stopPrice": exchange.price_to_precision(signal.symbol, tp_price),
                    "closePosition": True,
                },
            )
            log(f"  TP set @ {tp_price:.4f}")
        except Exception as e:
            log(f"  TP failed: {e}")

        notify(f"✅ LIVE\n{msg}\nOrder: {order.get('id', '?')}")

        state.open_positions[signal.symbol] = {
            "direction": signal.direction,
            "entry_price": current_price,
            "sl": sl_price,
            "tp": tp_price,
            "size_usdt": TRADE_SIZE_USDT,
            "order_id": order.get("id", ""),
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        state.daily_trades += 1
        save_state(state)
        return True

    except Exception as e:
        log(f"execute_trade error: {e}")
        notify(f"❌ Trade failed\n{signal.symbol}: {e}")
        return False


# ---------- position monitor ----------
def check_positions(state: State) -> None:
    """Check open positions and close if SL/TP hit (paper mode)."""
    if not PAPER_MODE or not state.open_positions:
        return

    import requests
    proxy = os.getenv("HTTPS_PROXY", "") or os.getenv("HTTP_PROXY", "")
    proxies = {"http": proxy, "https": proxy} if proxy else {}
    closed = []
    for symbol, pos in state.open_positions.items():
        try:
            # Get current price from Binance public API (via proxy to bypass geo-block)
            r = requests.get(
                f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}",
                proxies=proxies,
                timeout=10,
            )
            current = float(r.json()["price"])

            if pos["direction"] == "BUY":
                pnl_pct = (current - pos["entry_price"]) / pos["entry_price"] * 100
            else:
                pnl_pct = (pos["entry_price"] - current) / pos["entry_price"] * 100

            pnl_usd = pnl_pct / 100 * pos["size_usdt"] * LEVERAGE

            # Check SL/TP
            hit = None
            if pos["direction"] == "BUY":
                if current <= pos["sl"]:
                    hit = "SL"
                elif current >= pos["tp"]:
                    hit = "TP"
            else:
                if current >= pos["sl"]:
                    hit = "SL"
                elif current <= pos["tp"]:
                    hit = "TP"

            if hit:
                log(f"[PAPER] {hit} hit: {symbol} | PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})")
                notify(
                    f"{'🟢' if pnl_usd > 0 else '🔴'} {hit} {symbol}\n"
                    f"PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})"
                )
                state.daily_pnl += pnl_usd
                state.trade_history.append({
                    "symbol": symbol,
                    "direction": pos["direction"],
                    "entry": pos["entry_price"],
                    "exit": current,
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_usd": round(pnl_usd, 2),
                    "exit_reason": hit,
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                closed.append(symbol)

        except Exception as e:
            log(f"check_positions error {symbol}: {e}")

    for sym in closed:
        del state.open_positions[sym]
    if closed:
        save_state(state)


# ---------- main ----------
async def main():
    from telethon import TelegramClient, events

    if not TG_API_ID or not TG_API_HASH:
        print("ERROR: TG_API_ID and TG_API_HASH required in .env_naif")
        print("Get them from https://my.telegram.org")
        return

    state = load_state()
    mode = "LIVE" if not PAPER_MODE else "PAPER"
    log(f"naif_signal_bot starting | mode={mode}")
    log(f"Channel: {TG_CHANNEL}")
    log(f"Trade size: ${TRADE_SIZE_USDT} x{LEVERAGE} leverage")
    log(f"Filters: trend>={MIN_TREND_STRENGTH}%, volume>={MIN_VOLUME_STRENGTH}%")
    log(f"SL: {SL_PCT}% | TP: {TP_PCT}%")
    log(f"Max daily: {MAX_DAILY_TRADES} trades, ${MAX_DAILY_LOSS_USD} loss limit")
    notify(
        f"🚀 Naif Signal Bot started ({mode})\n"
        f"Size: ${TRADE_SIZE_USDT} x{LEVERAGE}\n"
        f"SL: {SL_PCT}% | TP: {TP_PCT}%"
    )

    client = TelegramClient(TG_SESSION, TG_API_ID, TG_API_HASH)
    await client.start()
    log("Telegram connected")

    # Resolve channel
    try:
        channel = await client.get_entity(TG_CHANNEL)
        log(f"Watching channel: {channel.title} (ID: {channel.id})")
    except Exception as e:
        log(f"Cannot find channel {TG_CHANNEL}: {e}")
        notify(f"❌ Cannot find channel {TG_CHANNEL}: {e}")
        return

    @client.on(events.NewMessage(chats=channel))
    async def handler(event):
        nonlocal state

        text = event.raw_text
        if not text:
            return

        signal = parse_signal(text)
        if not signal:
            return

        log(f"📡 Signal: {signal.direction} {signal.symbol} @ {signal.price} "
            f"| trend={signal.trend_strength}% | vol={signal.volume_strength}%")

        rollover_day(state)

        ok, reason = should_trade(signal, state)
        if not ok:
            log(f"  ⏭ Skip: {reason}")
            return

        log(f"  ✅ Executing {signal.direction} {signal.symbol}...")
        execute_trade(signal, state)

    # Position monitor loop
    async def monitor_loop():
        while True:
            try:
                rollover_day(state)
                check_positions(state)
            except Exception as e:
                log(f"monitor error: {e}")
            await asyncio.sleep(30)

    # Run both
    log("Listening for signals...")
    asyncio.create_task(monitor_loop())
    await client.run_until_disconnected()


def cmd_check():
    """Quick status check."""
    state = load_state()
    print(f"TG_API_ID set: {bool(TG_API_ID)}")
    print(f"BINANCE_KEY set: {bool(BINANCE_KEY)}")
    print(f"Channel: {TG_CHANNEL}")
    print(f"Mode: {'LIVE' if not PAPER_MODE else 'PAPER'}")
    print(f"Day: {state.day} | Trades: {state.daily_trades} | PnL: ${state.daily_pnl:+.2f}")
    print(f"Open positions: {len(state.open_positions)}")
    for sym, pos in state.open_positions.items():
        print(f"  {sym}: {pos['direction']} @ {pos['entry_price']} | SL={pos['sl']:.4f} TP={pos['tp']:.4f}")
    print(f"Halted: {state.halted}")


if __name__ == "__main__":
    if "--check" in sys.argv:
        cmd_check()
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            log("stopped by user")
            notify("🛑 Naif Signal Bot stopped")
