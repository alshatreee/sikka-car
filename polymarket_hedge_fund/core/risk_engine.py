"""
Risk Engine — Layer ⑤
Enforces ALL risk rules programmatically. No trade passes without approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from ..config import HedgeFundConfig
from ..models.market import (
    ClosedTrade, Direction, MarketData, Position, TradeProposal, TradeResult,
)


@dataclass
class RiskCheckResult:
    """Result of a risk check — trade is blocked if approved=False."""
    approved: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requires_confirmation: bool = False

    def __str__(self) -> str:
        status = "✅ APPROVED" if self.approved else "❌ BLOCKED"
        lines = [status]
        for r in self.reasons:
            lines.append(f"  ⛔ {r}")
        for w in self.warnings:
            lines.append(f"  ⚠️  {w}")
        if self.requires_confirmation:
            lines.append("  🔒 يتطلب تأكيد يدوي")
        return "\n".join(lines)


class RiskEngine:
    """
    Programmatic risk enforcement.
    Every trade MUST pass check_trade() before execution.
    """

    def __init__(self, config: HedgeFundConfig):
        self.config = config
        self._daily_trades: dict[str, int] = {}  # date_str -> count
        self._daily_pnl: dict[str, float] = {}   # date_str -> cumulative P&L
        self._consecutive_losses: int = 0
        self._session_halted: bool = False
        self._halt_reason: str = ""

    @property
    def is_halted(self) -> bool:
        return self._session_halted

    @property
    def halt_reason(self) -> str:
        return self._halt_reason

    def halt_session(self, reason: str) -> None:
        self._session_halted = True
        self._halt_reason = reason

    def resume_session(self) -> None:
        """Only call after manual review."""
        self._session_halted = False
        self._halt_reason = ""
        self._consecutive_losses = 0

    def check_trade(
        self,
        proposal: TradeProposal,
        market: MarketData,
        open_positions: list[Position],
    ) -> RiskCheckResult:
        """
        Run ALL risk checks on a proposed trade.
        Returns RiskCheckResult with approved/blocked + reasons.
        """
        reasons = []
        warnings = []

        # ── Session halt check ──
        if self._session_halted:
            reasons.append(f"الجلسة متوقفة: {self._halt_reason}")
            return RiskCheckResult(approved=False, reasons=reasons)

        # ── Daily trade count ──
        today = date.today().isoformat()
        daily_count = self._daily_trades.get(today, 0)
        if daily_count >= self.config.risk.max_daily_trades:
            reasons.append(
                f"تجاوز الحد اليومي: {daily_count}/{self.config.risk.max_daily_trades} صفقات"
            )

        # ── Daily loss limit ──
        daily_pnl = self._daily_pnl.get(today, 0.0)
        if daily_pnl <= -self.config.max_daily_loss_usd:
            reasons.append(
                f"تجاوز حد الخسارة اليومي: ${daily_pnl:.2f} "
                f"(الحد: -${self.config.max_daily_loss_usd:.2f})"
            )
            self.halt_session("تجاوز حد الخسارة اليومي")

        # ── Consecutive losses ──
        if self._consecutive_losses >= self.config.risk.max_consecutive_losses:
            reasons.append(
                f"خسائر متتالية: {self._consecutive_losses} "
                f"(الحد: {self.config.risk.max_consecutive_losses})"
            )
            self.halt_session("خسائر متتالية")

        # ── Position size check ──
        max_size = self.config.max_order_size_usd
        if proposal.total_size_usd > max_size:
            reasons.append(
                f"حجم الصفقة ${proposal.total_size_usd:.2f} "
                f"يتجاوز الحد ${max_size:.2f} (1% من رأس المال)"
            )

        # ── Total exposure check ──
        current_exposure = sum(p.size_usd for p in open_positions)
        new_exposure = current_exposure + proposal.total_size_usd
        max_exposure = self.config.max_total_exposure_usd
        if new_exposure > max_exposure:
            reasons.append(
                f"التعرض الكلي ${new_exposure:.2f} "
                f"يتجاوز الحد ${max_exposure:.2f} (5% من رأس المال)"
            )

        # ── Entry requirements ──
        entry = self.config.entry

        if proposal.composite_score < entry.min_composite_score:
            reasons.append(
                f"Score {proposal.composite_score:.1f} < "
                f"الحد الأدنى {entry.min_composite_score}"
            )

        if proposal.edge < entry.min_edge_pct:
            reasons.append(
                f"Edge {proposal.edge:.1%} < الحد الأدنى {entry.min_edge_pct:.1%}"
            )

        if market.liquidity_usd < entry.min_liquidity_usd:
            reasons.append(
                f"السيولة ${market.liquidity_usd:,.0f} < "
                f"الحد الأدنى ${entry.min_liquidity_usd:,.0f}"
            )

        if market.spread > entry.max_spread_pct:
            reasons.append(
                f"Spread {market.spread:.1%} > الحد {entry.max_spread_pct:.1%}"
            )

        if market.time_to_expiry_hours < entry.min_time_to_expiry_hours:
            reasons.append(
                f"الوقت المتبقي {market.time_to_expiry_hours:.1f}h < "
                f"الحد الأدنى {entry.min_time_to_expiry_hours}h"
            )

        # ── Signal conflict check ──
        if proposal.signal_data and proposal.signal_data.conflicting_signals:
            reasons.append("تعارض في الإشارات — لا يُسمح بالدخول")

        # ── Confirmation threshold ──
        requires_confirmation = (
            proposal.total_size_usd > self.config.risk.confirmation_threshold_usd
        )
        if requires_confirmation:
            warnings.append(
                f"الصفقة فوق ${self.config.risk.confirmation_threshold_usd} — "
                f"تحتاج تأكيد يدوي"
            )

        # ── Duplicate market check ──
        for pos in open_positions:
            if pos.market_id == proposal.market_id:
                warnings.append(
                    f"يوجد مركز مفتوح بالفعل في هذا السوق (#{pos.trade_id})"
                )

        approved = len(reasons) == 0
        return RiskCheckResult(
            approved=approved,
            reasons=reasons,
            warnings=warnings,
            requires_confirmation=requires_confirmation,
        )

    def record_trade_opened(self) -> None:
        """Record that a trade was opened today."""
        today = date.today().isoformat()
        self._daily_trades[today] = self._daily_trades.get(today, 0) + 1

    def record_trade_closed(self, trade: ClosedTrade) -> None:
        """Update risk state after a trade closes."""
        today = date.today().isoformat()
        self._daily_pnl[today] = self._daily_pnl.get(today, 0.0) + trade.pnl_usd

        if trade.result == TradeResult.LOSS:
            self._consecutive_losses += 1
        elif trade.result == TradeResult.WIN:
            self._consecutive_losses = 0

        # Auto-halt checks
        if self._consecutive_losses >= self.config.risk.max_consecutive_losses:
            self.halt_session(
                f"خسائر متتالية: {self._consecutive_losses}"
            )

        daily_pnl = self._daily_pnl.get(today, 0.0)
        if daily_pnl <= -self.config.max_daily_loss_usd:
            self.halt_session(
                f"تجاوز حد الخسارة اليومي: ${daily_pnl:.2f}"
            )

    def check_exit_conditions(self, position: Position) -> Optional[str]:
        """
        Check if a position should be exited.
        Returns exit reason or None.
        """
        pnl_pct = position.pnl_pct

        # Stop-Loss
        if pnl_pct <= -self.config.risk.stop_loss_pct:
            return f"STOP-LOSS: الخسارة {pnl_pct:.1%} تجاوزت -{self.config.risk.stop_loss_pct:.0%}"

        # Take-Profit
        if pnl_pct >= self.config.risk.take_profit_pct:
            return f"TAKE-PROFIT: الربح {pnl_pct:.1%} تجاوز +{self.config.risk.take_profit_pct:.0%}"

        return None

    def get_status(self, open_positions: list[Position]) -> dict:
        """Get current risk status summary."""
        today = date.today().isoformat()
        return {
            "session_halted": self._session_halted,
            "halt_reason": self._halt_reason,
            "daily_trades": self._daily_trades.get(today, 0),
            "max_daily_trades": self.config.risk.max_daily_trades,
            "daily_pnl": self._daily_pnl.get(today, 0.0),
            "max_daily_loss": -self.config.max_daily_loss_usd,
            "consecutive_losses": self._consecutive_losses,
            "total_exposure": sum(p.size_usd for p in open_positions),
            "max_exposure": self.config.max_total_exposure_usd,
            "capital": self.config.capital_usd,
        }
