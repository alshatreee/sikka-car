"""
sports_trader_finder.py
-----------------------
Scans Polymarket data API for top-performing SPORTS traders and writes
the best candidates to `smart_wallets.json` for use by sports_consensus_bot.

Filters:
  - Sports markets only (NBA/NFL/EPL/MLB/UCL/...)
  - >= MIN_TRADES resolved trades over the lookback window
  - Win rate >= MIN_WIN_RATE
  - ROI >= MIN_ROI
  - Average trade size within [MIN_AVG_SIZE, MAX_AVG_SIZE]
  - Active in the last ACTIVE_DAYS

Usage:
    python3 sports_trader_finder.py                # scan + save top 10
    python3 sports_trader_finder.py --top 20       # custom top N
    python3 sports_trader_finder.py --dry-run      # print, don't save
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import requests

# ---------- paths (cross-platform) ----------
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = BASE_DIR / "smart_wallets.json"
HISTORY_FILE = BASE_DIR / "smart_wallets_history.json"

# ---------- data sources ----------
DATA_API = "https://data-api.polymarket.com"
LEADERBOARD_URL = f"{DATA_API}/leaderboard"   # monthly by default
TRADES_URL = f"{DATA_API}/trades"
POSITIONS_URL = f"{DATA_API}/positions"

SPORTS_KEYWORDS = [
    "nba", "nfl", "mlb", "nhl", "epl", "ucl", "uefa",
    "premier league", "champions league", "la liga",
    "bundesliga", "serie a", "tennis", "atp", "wta",
    "ufc", "boxing", "golf", "pga", "formula", "f1",
    "cricket", "ipl", "rugby",
]
EXCLUDE_KEYWORDS = [
    "btc", "bitcoin", "eth", "ethereum", "crypto",
    "election", "trump", "biden", "president",
    "fed", "cpi", "inflation",
]

# ---------- thresholds ----------
MIN_TRADES = 100
MIN_WIN_RATE = 0.60
MIN_ROI = 0.25
MIN_AVG_SIZE = 50.0
MAX_AVG_SIZE = 2000.0
MAX_DRAWDOWN = 0.30
ACTIVE_DAYS = 3
LOOKBACK_DAYS = 90


@dataclass
class WalletStats:
    address: str
    trades: int
    wins: int
    win_rate: float
    roi: float
    avg_size: float
    max_drawdown: float
    sharpe: float
    last_trade_ts: int
    sports_ratio: float

    def passes(self) -> bool:
        return (
            self.trades >= MIN_TRADES
            and self.win_rate >= MIN_WIN_RATE
            and self.roi >= MIN_ROI
            and MIN_AVG_SIZE <= self.avg_size <= MAX_AVG_SIZE
            and self.max_drawdown <= MAX_DRAWDOWN
            and self.sports_ratio >= 0.70
            and (time.time() - self.last_trade_ts) <= ACTIVE_DAYS * 86400
        )


def is_sports_market(question: str) -> bool:
    q = (question or "").lower()
    if any(bad in q for bad in EXCLUDE_KEYWORDS):
        return False
    return any(kw in q for kw in SPORTS_KEYWORDS)


def fetch_leaderboard(limit: int = 500) -> list[str]:
    try:
        r = requests.get(LEADERBOARD_URL, params={"window": "month", "limit": limit}, timeout=20)
        r.raise_for_status()
        data = r.json()
        addrs: list[str] = []
        for row in data if isinstance(data, list) else data.get("users", []):
            addr = row.get("proxyWallet") or row.get("address") or row.get("user")
            if addr:
                addrs.append(addr.lower())
        return addrs
    except Exception as e:
        print(f"[finder] leaderboard fetch failed: {e}")
        return []


def fetch_user_trades(address: str, limit: int = 500) -> list[dict[str, Any]]:
    try:
        r = requests.get(
            TRADES_URL,
            params={"user": address, "limit": limit, "takerOnly": "true"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("trades", [])
    except Exception as e:
        print(f"[finder] trades fetch failed for {address[:10]}: {e}")
        return []


def analyze_wallet(address: str) -> WalletStats | None:
    trades = fetch_user_trades(address)
    if not trades:
        return None

    cutoff = time.time() - LOOKBACK_DAYS * 86400
    sports_count = 0
    total = 0
    wins = 0
    sizes: list[float] = []
    pnls: list[float] = []
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    last_ts = 0

    for t in trades:
        ts = int(t.get("timestamp", 0) or 0)
        if ts and ts < cutoff:
            continue
        question = t.get("question") or t.get("title") or ""
        if not question:
            continue
        total += 1
        last_ts = max(last_ts, ts)
        if is_sports_market(question):
            sports_count += 1
        size = float(t.get("size", 0) or 0) * float(t.get("price", 0) or 0)
        if size > 0:
            sizes.append(size)
        pnl = float(t.get("pnl", 0) or 0)
        pnls.append(pnl)
        if pnl > 0:
            wins += 1
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)

    if total == 0 or not sizes:
        return None

    win_rate = wins / total if total else 0.0
    avg_size = sum(sizes) / len(sizes)
    total_staked = sum(sizes) or 1.0
    roi = equity / total_staked
    mean = sum(pnls) / len(pnls) if pnls else 0.0
    var = sum((p - mean) ** 2 for p in pnls) / len(pnls) if pnls else 0.0
    std = math.sqrt(var) or 1e-9
    sharpe = mean / std * math.sqrt(len(pnls))
    sports_ratio = sports_count / total

    return WalletStats(
        address=address,
        trades=total,
        wins=wins,
        win_rate=round(win_rate, 4),
        roi=round(roi, 4),
        avg_size=round(avg_size, 2),
        max_drawdown=round(max_dd, 4),
        sharpe=round(sharpe, 4),
        last_trade_ts=last_ts,
        sports_ratio=round(sports_ratio, 4),
    )


def save_results(top: list[WalletStats]) -> None:
    payload = {
        "generated_at": int(time.time()),
        "criteria": {
            "min_trades": MIN_TRADES,
            "min_win_rate": MIN_WIN_RATE,
            "min_roi": MIN_ROI,
            "min_sports_ratio": 0.70,
            "lookback_days": LOOKBACK_DAYS,
        },
        "wallets": [asdict(w) for w in top],
    }
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2))

    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except Exception:
            history = []
    history.append(payload)
    history = history[-20:]
    HISTORY_FILE.write_text(json.dumps(history, indent=2))
    print(f"[finder] saved {len(top)} wallets -> {OUTPUT_FILE}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--limit", type=int, default=500, help="leaderboard scan size")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"[finder] fetching top {args.limit} leaderboard wallets...")
    addrs = fetch_leaderboard(args.limit)
    if not addrs:
        print("[finder] leaderboard empty; abort")
        return 1
    print(f"[finder] analyzing {len(addrs)} wallets (this takes a while)...")

    results: list[WalletStats] = []
    for i, a in enumerate(addrs, 1):
        stats = analyze_wallet(a)
        if stats and stats.passes():
            results.append(stats)
            print(f"  [{i}/{len(addrs)}] PASS {a[:10]}  wr={stats.win_rate}  roi={stats.roi}  sports={stats.sports_ratio}")
        time.sleep(0.25)  # rate-limit friendly

    # rank by Sharpe, tie-break ROI
    results.sort(key=lambda w: (w.sharpe, w.roi), reverse=True)
    top = results[: args.top]

    print(f"\n[finder] {len(results)} wallets passed filters. Top {len(top)}:")
    for i, w in enumerate(top, 1):
        print(f"  {i}. {w.address}  sharpe={w.sharpe}  wr={w.win_rate}  roi={w.roi}  trades={w.trades}")

    if args.dry_run:
        print("[finder] dry-run; not saving")
        return 0
    save_results(top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
