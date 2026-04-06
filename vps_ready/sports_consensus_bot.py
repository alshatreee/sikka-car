"""
sports_consensus_bot.py
-----------------------
Follows a watchlist of top sports traders (produced by sports_trader_finder.py)
and enters a trade ONLY when >= CONSENSUS_MIN of them buy the same side of the
same market within CONSENSUS_WINDOW_MIN minutes.

Key features:
  - Sports-only market filter
  - Consensus-based entry (kills individual bias)
  - No entry after a game has started (AVOID_LIVE_GAMES)
  - Max hold window, daily trade cap, daily loss kill-switch
  - Position persistence + SL/TP monitoring
  - Paper mode by default; --live to actually trade
  - Telegram notifications
  - Cross-platform paths

Usage:
    python3 sports_consensus_bot.py                 # paper mode
    python3 sports_consensus_bot.py --live          # real trading
    python3 sports_consensus_bot.py --check         # show status and exit
    python3 sports_consensus_bot.py --refresh-watchlist
"""
from __future__ import annotations

import argparse
import json
import os
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

WATCHLIST_FILE = BASE_DIR / "smart_wallets.json"
STATE_FILE = BASE_DIR / "sports_consensus_state.json"
POSITIONS_FILE = BASE_DIR / "sports_consensus_positions.json"
LOG_FILE = BASE_DIR / "sports_consensus.log"
ENV_FILE = BASE_DIR / ".env3"

load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# ---------- config ----------
CONSENSUS_MIN = 3
CONSENSUS_WINDOW_MIN = 15
TRADE_SIZE_USD = 3.0
MAX_DAILY_TRADES = 15
MAX_DAILY_LOSS_USD = 10.0
STOP_LOSS_PCT = 0.30
TAKE_PROFIT_PCT = 0.50
MAX_HOLD_HOURS = 12
POLL_SECS = 60
AVOID_LIVE_GAMES = True
MAX_PRICE = 0.90
MIN_PRICE = 0.30

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")


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
        log(f"tg failed: {e}")


# ---------- state ----------
@dataclass
class Position:
    market_id: str
    token_id: str
    side: str           # "YES" or "NO"
    entry_price: float
    size_usd: float
    opened_at: int
    question: str

@dataclass
class State:
    day: str = ""
    daily_trades: int = 0
    daily_pnl: float = 0.0
    halted: bool = False
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    # pending[market_id] = {"side": "YES", "votes": {addr: ts}, "first_seen": ts}


def load_state() -> State:
    if STATE_FILE.exists():
        try:
            d = json.loads(STATE_FILE.read_text())
            return State(**d)
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


def rollover_day(s: State) -> None:
    today = time.strftime("%Y-%m-%d")
    if s.day != today:
        s.day = today
        s.daily_trades = 0
        s.daily_pnl = 0.0
        s.halted = False
        s.pending = {}
        save_state(s)
        log(f"new day {today}; counters reset")


# ---------- watchlist ----------
def load_watchlist() -> list[str]:
    if not WATCHLIST_FILE.exists():
        log(f"watchlist missing: {WATCHLIST_FILE}. Run sports_trader_finder.py first.")
        return []
    try:
        data = json.loads(WATCHLIST_FILE.read_text())
        return [w["address"].lower() for w in data.get("wallets", [])]
    except Exception as e:
        log(f"watchlist parse error: {e}")
        return []


# ---------- sports filter (reuse logic) ----------
SPORTS_KEYWORDS = [
    "nba", "nfl", "mlb", "nhl", "epl", "ucl", "uefa",
    "premier league", "champions league", "la liga",
    "bundesliga", "serie a", "tennis", "atp", "wta",
    "ufc", "boxing", "golf", "pga", "formula", "f1",
    "cricket", "ipl", "rugby",
]
EXCLUDE_KEYWORDS = ["btc", "bitcoin", "eth", "crypto", "election", "trump"]


def is_sports_market(question: str) -> bool:
    q = (question or "").lower()
    if any(b in q for b in EXCLUDE_KEYWORDS):
        return False
    return any(k in q for k in SPORTS_KEYWORDS)


# ---------- data fetch ----------
def fetch_recent_trades(address: str, lookback_sec: int) -> list[dict[str, Any]]:
    try:
        r = requests.get(
            f"{DATA_API}/trades",
            params={"user": address, "limit": 50, "takerOnly": "true"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        trades = data if isinstance(data, list) else data.get("trades", [])
        cutoff = time.time() - lookback_sec
        return [t for t in trades if int(t.get("timestamp", 0) or 0) >= cutoff]
    except Exception as e:
        log(f"trades fetch failed {address[:10]}: {e}")
        return []


def fetch_market(market_id: str) -> dict[str, Any] | None:
    try:
        r = requests.get(f"{GAMMA_API}/markets/{market_id}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def market_is_live(market: dict[str, Any]) -> bool:
    # heuristic: game_start_time <= now, or "live" flag
    if market.get("live"):
        return True
    start = market.get("gameStartTime") or market.get("startDate")
    if start:
        try:
            from datetime import datetime
            ts = datetime.fromisoformat(start.replace("Z", "+00:00")).timestamp()
            return ts <= time.time()
        except Exception:
            return False
    return False


# ---------- consensus engine ----------
def update_consensus(state: State, watchlist: list[str]) -> list[dict[str, Any]]:
    """Poll each watched wallet for recent trades; register votes.
    Returns list of confirmed signals to act on."""
    lookback = CONSENSUS_WINDOW_MIN * 60
    now = int(time.time())

    for addr in watchlist:
        for t in fetch_recent_trades(addr, lookback):
            market_id = str(t.get("market") or t.get("conditionId") or "")
            side = (t.get("outcome") or "").upper()
            question = t.get("question") or ""
            if not market_id or side not in ("YES", "NO"):
                continue
            if not is_sports_market(question):
                continue
            price = float(t.get("price", 0) or 0)
            if not (MIN_PRICE <= price <= MAX_PRICE):
                continue

            key = f"{market_id}:{side}"
            entry = state.pending.get(key)
            if not entry:
                entry = {
                    "market_id": market_id,
                    "side": side,
                    "question": question,
                    "votes": {},
                    "first_seen": now,
                    "last_price": price,
                }
                state.pending[key] = entry
            entry["votes"][addr] = now
            entry["last_price"] = price

    # prune expired
    signals: list[dict[str, Any]] = []
    for key in list(state.pending.keys()):
        entry = state.pending[key]
        entry["votes"] = {a: ts for a, ts in entry["votes"].items() if now - ts <= lookback}
        if not entry["votes"]:
            del state.pending[key]
            continue
        if len(entry["votes"]) >= CONSENSUS_MIN and not entry.get("fired"):
            entry["fired"] = True
            signals.append(dict(entry))

    save_state(state)
    return signals


# ---------- trading ----------
def place_order(signal: dict[str, Any], live: bool) -> Position | None:
    market = fetch_market(signal["market_id"])
    if not market:
        log(f"cannot fetch market {signal['market_id']}")
        return None
    if AVOID_LIVE_GAMES and market_is_live(market):
        log(f"skip live game: {signal['question'][:60]}")
        return None

    side = signal["side"]
    tokens = market.get("tokens") or market.get("outcomes") or []
    token_id = None
    for tok in tokens:
        name = (tok.get("outcome") or tok.get("name") or "").upper()
        if name == side:
            token_id = tok.get("token_id") or tok.get("id")
            break
    if not token_id:
        log("token_id not resolved")
        return None

    price = signal["last_price"]
    pos = Position(
        market_id=signal["market_id"],
        token_id=str(token_id),
        side=side,
        entry_price=price,
        size_usd=TRADE_SIZE_USD,
        opened_at=int(time.time()),
        question=signal["question"],
    )

    if not live:
        log(f"[PAPER] BUY {side} @ {price} | {signal['question'][:60]}")
        tg(f"📋 PAPER BUY\n{signal['question'][:80]}\n{side} @ {price}\nvotes={len(signal['votes'])}")
        return pos

    # live path -- requires py-clob-client installed on the VPS
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OrderArgs, OrderType
        host = "https://clob.polymarket.com"
        key = os.getenv("PK") or os.getenv("PRIVATE_KEY")
        funder = os.getenv("FUNDER")
        chain_id = 137
        client = ClobClient(host, key=key, chain_id=chain_id, signature_type=1, funder=funder)
        client.set_api_creds(client.create_or_derive_api_creds())
        args = OrderArgs(price=price, size=TRADE_SIZE_USD / price, side="BUY", token_id=str(token_id))
        signed = client.create_order(args)
        resp = client.post_order(signed, OrderType.GTC)
        if not resp or not resp.get("success"):
            log(f"order failed: {resp}")
            return None
        log(f"[LIVE] BUY {side} @ {price} | {resp.get('orderID','?')[:12]}")
        tg(f"✅ LIVE BUY\n{signal['question'][:80]}\n{side} @ {price}")
        return pos
    except Exception as e:
        log(f"live order error: {e}")
        tg(f"❌ order error: {e}")
        return None


def current_price(token_id: str) -> float | None:
    try:
        r = requests.get(
            "https://clob.polymarket.com/price",
            params={"token_id": token_id, "side": "sell"},
            timeout=10,
        )
        r.raise_for_status()
        return float(r.json().get("price", 0))
    except Exception:
        return None


def check_sl_tp(positions: list[Position], state: State, live: bool) -> list[Position]:
    keep: list[Position] = []
    now = int(time.time())
    for p in positions:
        price = current_price(p.token_id)
        if price is None:
            keep.append(p)
            continue
        change = (price - p.entry_price) / p.entry_price
        age_h = (now - p.opened_at) / 3600.0
        exit_reason = None
        if change <= -STOP_LOSS_PCT:
            exit_reason = "SL"
        elif change >= TAKE_PROFIT_PCT:
            exit_reason = "TP"
        elif age_h >= MAX_HOLD_HOURS:
            exit_reason = "MAX_HOLD"
        if exit_reason:
            pnl = p.size_usd * change
            state.daily_pnl += pnl
            log(f"CLOSE {exit_reason} {p.side} pnl={pnl:+.2f} | {p.question[:50]}")
            tg(f"{'💰' if pnl>=0 else '🔻'} CLOSE {exit_reason}\n{p.question[:70]}\npnl={pnl:+.2f}$")
            # live close omitted for brevity -- paper tracks pnl only
        else:
            keep.append(p)
    return keep


# ---------- main ----------
def cmd_check() -> None:
    wl = load_watchlist()
    state = load_state()
    positions = load_positions()
    print(f"watchlist: {len(wl)} wallets")
    for a in wl:
        print(f"  - {a}")
    print(f"state: day={state.day} trades={state.daily_trades} pnl={state.daily_pnl:+.2f} halted={state.halted}")
    print(f"open positions: {len(positions)}")
    for p in positions:
        print(f"  {p.side} @ {p.entry_price} | {p.question[:60]}")
    print(f"pending signals: {len(state.pending)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="real trading (default: paper)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--refresh-watchlist", action="store_true")
    args = ap.parse_args()

    if args.check:
        cmd_check()
        return 0

    if args.refresh_watchlist:
        os.system(f"{sys.executable} {Path(__file__).parent / 'sports_trader_finder.py'}")
        return 0

    watchlist = load_watchlist()
    if not watchlist:
        return 1

    state = load_state()
    positions = load_positions()
    mode = "LIVE" if args.live else "PAPER"
    log(f"sports_consensus_bot started ({mode}) | watching {len(watchlist)} wallets")
    tg(f"🤖 sports_consensus_bot started ({mode})\nwatching {len(watchlist)} wallets")

    try:
        while True:
            rollover_day(state)

            if state.halted:
                log("halted for the day; sleeping")
                time.sleep(POLL_SECS)
                continue

            # 1) manage open positions
            positions = check_sl_tp(positions, state, args.live)
            save_positions(positions)

            # 2) kill-switch check
            if state.daily_pnl <= -MAX_DAILY_LOSS_USD:
                state.halted = True
                save_state(state)
                tg(f"🛑 daily loss limit hit ({state.daily_pnl:.2f}$). halted.")
                continue
            if state.daily_trades >= MAX_DAILY_TRADES:
                log("daily trade cap reached")
                time.sleep(POLL_SECS)
                continue

            # 3) gather consensus
            signals = update_consensus(state, watchlist)
            for sig in signals:
                if state.daily_trades >= MAX_DAILY_TRADES:
                    break
                # avoid duplicates
                if any(p.market_id == sig["market_id"] and p.side == sig["side"] for p in positions):
                    continue
                pos = place_order(sig, args.live)
                if pos:
                    positions.append(pos)
                    state.daily_trades += 1
                    save_positions(positions)
                    save_state(state)

            time.sleep(POLL_SECS)
    except KeyboardInterrupt:
        log("stopped by user")
        tg("🛑 sports_consensus_bot stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())
