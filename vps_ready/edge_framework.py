import sqlite3, os, platform, time, statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = (
    Path(r"C:\Users\xman9\Desktop\trades.db")
    if platform.system() == "Windows"
    else Path("/root/bots/trades.db")
)


def stability_check(prices: list[float], threshold: float = 0.15) -> bool:
    if len(prices) < 2:
        return True
    mean = statistics.mean(prices)
    if mean == 0:
        return False
    return (statistics.stdev(prices) / mean) <= threshold


def ev_kelly_gate(edge_pct: float, win_rate: float, base_size: float) -> float:
    if edge_pct == 0:
        return 0.0
    odds = edge_pct / 100
    kelly_fraction = (win_rate * (1 + odds) - 1) / odds
    if kelly_fraction <= 0:
        return 0.0
    return base_size * min(kelly_fraction / 4, 1.0)


class MarketLock:
    def __init__(self):
        self._locks: dict[str, float] = {}

    def lock(self, market_id: str, minutes: int = 30):
        self._locks[market_id] = time.time() + minutes * 60

    def is_locked(self, market_id: str) -> bool:
        expiry = self._locks.get(market_id)
        if expiry is None:
            return False
        if time.time() >= expiry:
            del self._locks[market_id]
            return False
        return True


def check_risk_limits(
    daily_trades: int,
    daily_pnl: float,
    open_positions: int,
    max_trades: int = 20,
    max_loss: float = 20.0,
    max_positions: int = 10,
) -> tuple[bool, str]:
    if daily_trades >= max_trades:
        return False, f"max trades reached ({daily_trades}/{max_trades})"
    if daily_pnl <= -max_loss:
        return False, f"daily loss limit hit (${daily_pnl:.2f})"
    if open_positions >= max_positions:
        return False, f"max positions reached ({open_positions}/{max_positions})"
    return True, "ok"


def calc_fee(price: float) -> float:
    return 2 * min(price, 1 - price) * 0.02 * 100


def net_edge(entry: float, target: float) -> float:
    gross = (target - entry) * 100
    return gross - calc_fee(entry) - calc_fee(target)


class TradeDB:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot TEXT, market_id TEXT, side TEXT,
                    entry_price REAL, exit_price REAL,
                    pnl_usd REAL, pnl_pct REAL, size_usd REAL,
                    opened_at TEXT, closed_at TEXT,
                    exit_reason TEXT, strategy TEXT
                )
            """)

    def record_trade(self, bot: str, market_id: str, side: str,
                     entry_price: float, exit_price: float,
                     pnl_usd: float, pnl_pct: float, size_usd: float,
                     opened_at: str, closed_at: str,
                     exit_reason: str = "", strategy: str = ""):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO trades (bot,market_id,side,entry_price,exit_price,"
                "pnl_usd,pnl_pct,size_usd,opened_at,closed_at,exit_reason,strategy) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (bot, market_id, side, entry_price, exit_price,
                 pnl_usd, pnl_pct, size_usd, opened_at, closed_at,
                 exit_reason, strategy),
            )

    def get_trades(self, bot: str | None = None, days: int = 7) -> list[dict]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q = "SELECT * FROM trades WHERE opened_at >= ?"
        params: list = [since]
        if bot:
            q += " AND bot = ?"
            params.append(bot)
        q += " ORDER BY id DESC"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def metrics(trades: list[dict]) -> dict:
    if not trades:
        return dict(win_rate=0, profit_factor=0, sharpe=0, max_drawdown=0,
                    total_pnl=0, num_trades=0, best_hour=0)
    wins = [t for t in trades if t.get("pnl_usd", 0) > 0]
    losses = [t for t in trades if t.get("pnl_usd", 0) < 0]
    total_pnl = sum(t.get("pnl_usd", 0) for t in trades)
    win_rate = len(wins) / len(trades) if trades else 0
    gross_profit = sum(t["pnl_usd"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["pnl_usd"] for t in losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss else float("inf")

    daily_pnl: dict[str, float] = {}
    hour_pnl: dict[int, float] = {}
    for t in trades:
        dt_str = t.get("closed_at") or t.get("opened_at", "")
        try:
            dt = datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            continue
        day_key = dt.strftime("%Y-%m-%d")
        daily_pnl[day_key] = daily_pnl.get(day_key, 0) + t.get("pnl_usd", 0)
        hour_pnl[dt.hour] = hour_pnl.get(dt.hour, 0) + t.get("pnl_usd", 0)

    daily_returns = list(daily_pnl.values())
    if len(daily_returns) >= 2:
        sharpe = (statistics.mean(daily_returns) / statistics.stdev(daily_returns)) * (365 ** 0.5)
    else:
        sharpe = 0.0

    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for d in sorted(daily_pnl):
        cumulative += daily_pnl[d]
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)

    best_hour = max(hour_pnl, key=hour_pnl.get) if hour_pnl else 0

    return dict(
        win_rate=round(win_rate, 4),
        profit_factor=round(profit_factor, 4),
        sharpe=round(sharpe, 4),
        max_drawdown=round(max_dd, 2),
        total_pnl=round(total_pnl, 2),
        num_trades=len(trades),
        best_hour=best_hour,
    )
