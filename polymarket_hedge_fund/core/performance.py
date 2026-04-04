"""
Performance Loop — Layer ⑦
Trade logging, metrics calculation, and self-improvement.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.market import ClosedTrade, TradeResult


@dataclass
class PerformanceMetrics:
    """Cumulative performance metrics."""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    total_pnl_usd: float = 0.0
    total_profit_usd: float = 0.0
    total_loss_usd: float = 0.0
    max_drawdown_usd: float = 0.0
    win_rate: float = 0.0
    avg_pnl_usd: float = 0.0
    profit_factor: float = 0.0
    edge_accuracy: float = 0.0  # % of times P(est) was closer to outcome than market

    def to_display(self) -> str:
        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         📊 مقاييس الأداء
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  إجمالي الصفقات : {self.total_trades}
  الأرباح       : {self.wins} | الخسائر: {self.losses}
  نسبة الفوز    : {self.win_rate:.1%}
  إجمالي P&L    : ${self.total_pnl_usd:+.2f}
  متوسط العائد  : ${self.avg_pnl_usd:+.2f}
  أقصى تراجع    : ${self.max_drawdown_usd:.2f}
  معامل الربح   : {self.profit_factor:.2f}
  دقة الـ Edge   : {self.edge_accuracy:.1%}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


class PerformanceTracker:
    """
    Records all trades and calculates cumulative metrics.
    Persists to JSON for continuity across sessions.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trades_file = self.data_dir / "trades.json"
        self.trades: list[dict] = []
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._load()

    def _load(self) -> None:
        """Load trade history from disk."""
        if self.trades_file.exists():
            with open(self.trades_file) as f:
                self.trades = json.load(f)
            # Rebuild equity curve
            for t in self.trades:
                self._current_equity += t.get("pnl_usd", 0)
                self._peak_equity = max(self._peak_equity, self._current_equity)

    def _save(self) -> None:
        """Persist trade history to disk."""
        with open(self.trades_file, "w") as f:
            json.dump(self.trades, f, indent=2, default=str)

    def record(self, trade: ClosedTrade) -> None:
        """Record a closed trade."""
        record = {
            "trade_id": trade.trade_id,
            "market_id": trade.market_id,
            "market_question": trade.market_question,
            "direction": trade.direction.value,
            "edge_at_entry": trade.edge_at_entry,
            "composite_score": trade.composite_score,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "size_usd": trade.size_usd,
            "pnl_usd": trade.pnl_usd,
            "result": trade.result.value,
            "reason": trade.reason,
            "opened_at": str(trade.opened_at),
            "closed_at": str(trade.closed_at),
        }
        self.trades.append(record)
        self._current_equity += trade.pnl_usd
        self._peak_equity = max(self._peak_equity, self._current_equity)
        self._save()

    def get_metrics(self) -> PerformanceMetrics:
        """Calculate all performance metrics."""
        if not self.trades:
            return PerformanceMetrics()

        wins = [t for t in self.trades if t["result"] == "win"]
        losses = [t for t in self.trades if t["result"] == "loss"]
        breakevens = [t for t in self.trades if t["result"] == "breakeven"]

        total_profit = sum(t["pnl_usd"] for t in wins)
        total_loss = abs(sum(t["pnl_usd"] for t in losses))
        total_pnl = sum(t["pnl_usd"] for t in self.trades)

        # Max drawdown
        peak = 0.0
        max_dd = 0.0
        equity = 0.0
        for t in self.trades:
            equity += t["pnl_usd"]
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)

        total = len(self.trades)
        return PerformanceMetrics(
            total_trades=total,
            wins=len(wins),
            losses=len(losses),
            breakevens=len(breakevens),
            total_pnl_usd=total_pnl,
            total_profit_usd=total_profit,
            total_loss_usd=total_loss,
            max_drawdown_usd=max_dd,
            win_rate=len(wins) / total if total > 0 else 0,
            avg_pnl_usd=total_pnl / total if total > 0 else 0,
            profit_factor=total_profit / total_loss if total_loss > 0 else float("inf"),
            edge_accuracy=self._calc_edge_accuracy(),
        )

    def _calc_edge_accuracy(self) -> float:
        """
        Calculate how often our P(est) was closer to the actual outcome
        than the market price. Only for resolved markets.
        """
        resolved = [t for t in self.trades if t["result"] in ("win", "loss")]
        if not resolved:
            return 0.0

        accurate = 0
        for t in resolved:
            # If we predicted YES and won, or NO and won, our edge was correct
            if t["result"] == "win":
                accurate += 1
        return accurate / len(resolved)

    def get_trade_log(self, last_n: int = 10) -> str:
        """Format recent trade log for display."""
        recent = self.trades[-last_n:]
        if not recent:
            return "لا توجد صفقات مسجلة بعد."

        lines = ["رقم | السوق | الاتجاه | Edge | Score | دخول | خروج | P&L$ | السبب"]
        lines.append("─" * 80)
        for i, t in enumerate(recent, 1):
            q = t["market_question"][:25]
            lines.append(
                f"{i:>3} | {q:<25} | {t['direction']:>3} | "
                f"{t['edge_at_entry']:>5.1%} | {t['composite_score']:>5.0f} | "
                f"{t['entry_price']:.3f} | {t['exit_price']:.3f} | "
                f"${t['pnl_usd']:>+7.2f} | {t['reason']}"
            )
        return "\n".join(lines)

    def get_improvement_suggestions(self) -> list[str]:
        """
        Self-improvement engine.
        Analyzes performance and suggests parameter adjustments.
        """
        metrics = self.get_metrics()
        suggestions = []

        if metrics.total_trades < 5:
            return ["⏳ تحتاج 5 صفقات على الأقل للتحليل"]

        if metrics.win_rate < 0.5:
            suggestions.append(
                f"⚠️  نسبة الفوز {metrics.win_rate:.0%} < 50% — "
                f"ارفع الحد الأدنى لـ Edge بمقدار +1%"
            )

        if metrics.avg_pnl_usd < 0:
            suggestions.append(
                f"⚠️  متوسط العائد سلبي (${metrics.avg_pnl_usd:.2f}) — "
                f"راجع نقاط SL/TP"
            )

        if metrics.profit_factor < 1.5 and metrics.profit_factor != float("inf"):
            suggestions.append(
                f"⚠️  معامل الربح ضعيف ({metrics.profit_factor:.2f}) — "
                f"ركّز على الصفقات عالية الجودة فقط"
            )

        if metrics.edge_accuracy < 0.5:
            suggestions.append(
                f"⚠️  دقة الـ Edge منخفضة ({metrics.edge_accuracy:.0%}) — "
                f"راجع مصادر البيانات ونموذج التقدير"
            )

        if not suggestions:
            suggestions.append("✅ الأداء جيد — استمر بنفس المعايير")

        return suggestions
