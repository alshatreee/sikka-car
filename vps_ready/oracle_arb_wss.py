"""
oracle_arb_wss.py — Oracle Arbitrage Bot (WebSocket edition)
============================================================

يقرأ أسعار BTC/ETH من Chainlink على Polygon عبر اتصال Alchemy WSS،
ويقارنها بأسعار عقود Polymarket لاكتشاف فرص الأربتراج.

التحسينات على النسخة السابقة:
  - WSS بدل polling (أسرع وأوثق وبدون rate limits قاسية)
  - reconnect تلقائي بدل الاعتماد على watchdog
  - قراءة latestRoundData() فعلياً (وليس الاعتماد على event AnswerUpdated
    الذي قد لا يصدر من proxy aggregator)
  - عناوين Chainlink موثّقة ومتحقّق منها على polygonscan
  - paper mode افتراضي + Telegram + state persistence
  - cross-platform paths

استخدام:
    python3 oracle_arb_wss.py              # paper mode
    python3 oracle_arb_wss.py --check      # حالة سريعة واخرج
    python3 oracle_arb_wss.py --live       # تنفيذ فعلي (خطر)

المتطلبات (على VPS):
    pip install --upgrade "web3>=6.20" python-dotenv requests websockets
"""
from __future__ import annotations

import argparse
import asyncio
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

ENV_FILE = BASE_DIR / ".env"
STATE_FILE = BASE_DIR / "oracle_arb_state.json"
LOG_FILE = BASE_DIR / "oracle_arb.log"

load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

# ---------- config ----------
WSS_URL = os.getenv("POLYGON_WSS_URL", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

# عناوين Chainlink الصحيحة على Polygon Mainnet (تحقق منها على polygonscan.com)
CHAINLINK_FEEDS = {
    "BTC": "0xc907E116054Ad103354f2D350FD2514433D57F6f",
    "ETH": "0xF9680D99D6C9589e2a93a78A04A279e509205945",
}

POLL_INTERVAL_SEC = 15           # كل كم ثانية نقرأ السعر من العقد
MIN_EDGE_PCT = 3.0               # الحد الأدنى للانحراف لاعتباره فرصة (%)
TRADE_SIZE_USD = 4.0
MAX_DAILY_TRADES = 20
MAX_DAILY_LOSS_USD = 10.0

GAMMA_API = "https://gamma-api.polymarket.com"

# Chainlink AggregatorV3 ABI (الحقول التي نحتاجها فقط)
AGGREGATOR_ABI = [
    {
        "inputs": [],
        "name": "latestRoundData",
        "outputs": [
            {"name": "roundId", "type": "uint80"},
            {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"},
            {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]


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
class State:
    day: str = ""
    daily_trades: int = 0
    daily_pnl: float = 0.0
    halted: bool = False
    last_signals: dict[str, float] = field(default_factory=dict)


def load_state() -> State:
    if STATE_FILE.exists():
        try:
            return State(**json.loads(STATE_FILE.read_text()))
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
        s.last_signals = {}
        save_state(s)
        log(f"new day {today}; counters reset")


# ---------- web3 / chainlink ----------
async def make_w3():
    """ينشئ AsyncWeb3 مع WebSocketProvider. يدعم web3.py >= 6.20"""
    try:
        from web3 import AsyncWeb3
        from web3.providers.persistent import WebSocketProvider  # web3 >= 6.20
    except ImportError:
        from web3 import AsyncWeb3
        from web3 import WebSocketProvider  # type: ignore

    if not WSS_URL:
        raise RuntimeError("POLYGON_WSS_URL غير محدد في .env")

    provider = WebSocketProvider(WSS_URL)
    w3 = AsyncWeb3(provider)
    await provider.connect()
    if not await w3.is_connected():
        raise RuntimeError("فشل الاتصال بـ Polygon WSS")
    return w3


async def read_chainlink_price(w3, address: str) -> tuple[float, int] | None:
    """يقرأ السعر الفعلي مباشرة من latestRoundData (موثوق أكثر من الاستماع للأحداث)."""
    try:
        from web3 import Web3
        contract = w3.eth.contract(address=Web3.to_checksum_address(address), abi=AGGREGATOR_ABI)
        data = await contract.functions.latestRoundData().call()
        decimals = await contract.functions.decimals().call()
        # data = (roundId, answer, startedAt, updatedAt, answeredInRound)
        price = float(data[1]) / (10 ** decimals)
        updated_at = int(data[3])
        return price, updated_at
    except Exception as e:
        log(f"read_chainlink_price failed for {address[:10]}: {e}")
        return None


# ---------- polymarket ----------
def fetch_polymarket_crypto_markets(asset: str) -> list[dict[str, Any]]:
    """يجلب أسواق Polymarket النشطة لـ BTC/ETH (أسواق up/down قصيرة المدى)."""
    try:
        r = requests.get(
            f"{GAMMA_API}/markets",
            params={"active": "true", "closed": "false", "limit": 100},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        markets = data if isinstance(data, list) else data.get("markets", [])
        keyword = "bitcoin" if asset == "BTC" else "ethereum"
        return [m for m in markets if keyword in (m.get("question") or "").lower()]
    except Exception as e:
        log(f"polymarket fetch failed: {e}")
        return []


def parse_target_price(question: str) -> float | None:
    """يستخرج السعر المستهدف من سؤال السوق (مثال: 'Will BTC reach $70,000 by ...')."""
    import re
    m = re.search(r"\$?([\d,]{4,})", question)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def compute_edge(oracle_price: float, market: dict[str, Any]) -> tuple[float, str] | None:
    """يحسب الفجوة بين سعر oracle وسعر السوق على Polymarket.
    يرجع (edge_pct, side) أو None."""
    target = parse_target_price(market.get("question", ""))
    if not target:
        return None
    tokens = market.get("tokens") or market.get("outcomes") or []
    if len(tokens) < 2:
        return None

    # سعر السوق الحالي لليس (YES)
    yes_price = None
    for t in tokens:
        name = (t.get("outcome") or t.get("name") or "").upper()
        if name == "YES":
            yes_price = float(t.get("price", 0) or 0)
            break
    if yes_price is None or yes_price <= 0 or yes_price >= 1:
        return None

    # حقيقة بسيطة: إذا oracle أعلى من target بكثير، YES مقوّمة بأقل من قيمتها
    diff_pct = (oracle_price - target) / target * 100
    if diff_pct > MIN_EDGE_PCT and yes_price < 0.85:
        return (diff_pct, "YES")
    if diff_pct < -MIN_EDGE_PCT and yes_price > 0.15:
        return (-diff_pct, "NO")
    return None


# ---------- trade execution ----------
async def execute_trade(asset: str, oracle_price: float, market: dict[str, Any],
                        side: str, edge: float, live: bool) -> bool:
    q = market.get("question", "")[:70]
    msg = f"🔮 {asset} oracle={oracle_price:.2f}\n{q}\n{side}  edge={edge:.2f}%"
    if not live:
        log(f"[PAPER] {msg}")
        tg(f"📋 PAPER\n{msg}")
        return True

    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OrderArgs, OrderType
        host = "https://clob.polymarket.com"
        key = os.getenv("PK") or os.getenv("PRIVATE_KEY")
        funder = os.getenv("FUNDER")
        client = ClobClient(host, key=key, chain_id=137, signature_type=1, funder=funder)
        client.set_api_creds(client.create_or_derive_api_creds())

        tokens = market.get("tokens") or market.get("outcomes") or []
        token_id = None
        price = None
        for t in tokens:
            if (t.get("outcome") or t.get("name") or "").upper() == side:
                token_id = t.get("token_id") or t.get("id")
                price = float(t.get("price", 0) or 0)
                break
        if not token_id or not price:
            log("token resolution failed")
            return False

        args = OrderArgs(price=price, size=TRADE_SIZE_USD / price, side="BUY", token_id=str(token_id))
        signed = client.create_order(args)
        resp = client.post_order(signed, OrderType.GTC)
        if resp and resp.get("success"):
            log(f"[LIVE] BUY {side} ok | {resp.get('orderID','?')[:12]}")
            tg(f"✅ LIVE BUY\n{msg}")
            return True
        log(f"order failed: {resp}")
        return False
    except Exception as e:
        log(f"execute_trade error: {e}")
        tg(f"❌ {asset} order error: {e}")
        return False


# ---------- main loop ----------
async def main_loop(live: bool):
    state = load_state()
    log(f"oracle_arb_wss starting | mode={'LIVE' if live else 'PAPER'}")
    tg(f"🚀 oracle_arb_wss started ({'LIVE' if live else 'PAPER'})")

    while True:
        w3 = None
        try:
            w3 = await make_w3()
            log("WSS connected")
            tg("🟢 oracle_arb WSS connected")

            while True:
                rollover_day(state)
                if state.halted:
                    await asyncio.sleep(POLL_INTERVAL_SEC)
                    continue
                if state.daily_pnl <= -MAX_DAILY_LOSS_USD:
                    state.halted = True
                    save_state(state)
                    tg(f"💀 oracle_arb daily loss limit hit ({state.daily_pnl:.2f}$)")
                    continue
                if state.daily_trades >= MAX_DAILY_TRADES:
                    log("daily trade cap reached; sleeping")
                    await asyncio.sleep(POLL_INTERVAL_SEC * 4)
                    continue

                for asset, addr in CHAINLINK_FEEDS.items():
                    res = await read_chainlink_price(w3, addr)
                    if not res:
                        continue
                    oracle_price, updated_at = res
                    age = int(time.time()) - updated_at
                    log(f"{asset} oracle={oracle_price:.2f} (age {age}s)")

                    markets = fetch_polymarket_crypto_markets(asset)
                    for m in markets:
                        edge_info = compute_edge(oracle_price, m)
                        if not edge_info:
                            continue
                        edge, side = edge_info
                        key = f"{m.get('id') or m.get('conditionId')}:{side}"
                        # cooldown 30 دقيقة لنفس الفرصة
                        last = state.last_signals.get(key, 0)
                        if time.time() - last < 1800:
                            continue
                        state.last_signals[key] = time.time()
                        ok = await execute_trade(asset, oracle_price, m, side, edge, live)
                        if ok:
                            state.daily_trades += 1
                            save_state(state)

                await asyncio.sleep(POLL_INTERVAL_SEC)

        except Exception as e:
            log(f"main loop error, reconnecting in 5s: {e}")
            tg(f"⚠️ oracle_arb reconnecting: {e}")
            try:
                if w3 is not None:
                    await w3.provider.disconnect()  # type: ignore
            except Exception:
                pass
            await asyncio.sleep(5)


def cmd_check():
    state = load_state()
    print(f"WSS_URL set: {bool(WSS_URL)}")
    print(f"day={state.day}  trades={state.daily_trades}  pnl={state.daily_pnl:+.2f}  halted={state.halted}")
    print(f"cached signals: {len(state.last_signals)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        cmd_check()
        return 0
    try:
        asyncio.run(main_loop(live=args.live))
    except KeyboardInterrupt:
        log("stopped by user")
        tg("🛑 oracle_arb_wss stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
