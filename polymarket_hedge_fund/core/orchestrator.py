"""
Main Orchestrator — ties all layers together.
Implements the mandatory session sequence.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..config import HedgeFundConfig, TradingMode
from ..models.market import (
    ClosedTrade, Direction, MarketData, Position, SignalData, TradeResult,
)
from .execution import ExecutionEngine
from .performance import PerformanceTracker
from .quant_model import QuantModel
from .risk_engine import RiskEngine
from .scanner import MarketScanner

logger = logging.getLogger(__name__)


class HedgeFundOrchestrator:
    """
    Main entry point for the hedge fund system.
    Enforces the mandatory session sequence:
    ① Portfolio status
    ② Market scan (top 5)
    ③ Propose up to 2 trades
    """

    def __init__(self, config: Optional[HedgeFundConfig] = None):
        self.config = config or HedgeFundConfig()
        self.risk = RiskEngine(self.config)
        self.quant = QuantModel(self.config)
        self.execution = ExecutionEngine(self.config)
        self.scanner = MarketScanner(self.config)
        self.performance = PerformanceTracker()
        self.positions: list[Position] = []

    # ── Session Start ──

    def start_session(self) -> str:
        """
        Mandatory session start sequence.
        Returns formatted status string.
        """
        lines = [
            "══════════════════════════════════════",
            "   🏦 POLYMARKET HEDGE FUND — Session",
            "══════════════════════════════════════",
            "",
            self._format_portfolio_status(),
            "",
            self._format_risk_status(),
        ]

        # Performance summary if trades exist
        metrics = self.performance.get_metrics()
        if metrics.total_trades > 0:
            lines.append("")
            lines.append(metrics.to_display())

            # Improvement suggestions
            suggestions = self.performance.get_improvement_suggestions()
            if suggestions:
                lines.append("\n📈 توصيات التحسين:")
                for s in suggestions:
                    lines.append(f"  {s}")

        return "\n".join(lines)

    # ── Market Analysis ──

    def analyze_markets(self, markets: list[MarketData]) -> str:
        """
        Step ②: Scan and rank top 5 markets.
        """
        if self.risk.is_halted:
            return f"⛔ الجلسة متوقفة: {self.risk.halt_reason}"

        top = self.scanner.get_top_markets(markets, top_n=5)
        return self.scanner.format_scan_results(top)

    # ── Trade Proposal ──

    def propose_trade(
        self,
        market: MarketData,
        signal: SignalData,
        p_historical: float,
        direction: Direction,
        rationale: str,
    ) -> str:
        """
        Analyze a market and build a trade proposal.
        Runs through Quant → Risk → format for display.
        """
        # Quant analysis
        estimate = self.quant.estimate(market, signal, p_historical)

        # Build proposal
        proposal = self.execution.build_proposal(
            market=market,
            direction=direction,
            edge=estimate.edge,
            composite_score=estimate.composite_score,
            rationale=rationale,
            signal_data=signal,
            quant_estimate=estimate,
        )

        # Risk check
        risk_result = self.risk.check_trade(proposal, market, self.positions)

        # Format output
        lines = [
            self.execution.format_proposal(proposal),
            "",
            "── فحص المخاطر ──",
            str(risk_result),
        ]

        if risk_result.approved:
            if self.config.trading_mode == TradingMode.MANUAL:
                lines.append("\n💡 الوضع: يدوي — اكتب 'نفّذ' لتأكيد الصفقة")
            elif risk_result.requires_confirmation:
                lines.append("\n🔒 الصفقة تحتاج تأكيد يدوي (فوق الحد)")
        else:
            lines.append("\n❌ الصفقة مرفوضة — لا يمكن التنفيذ")

        return "\n".join(lines)

    # ── Execution ──

    def execute_trade(self, proposal_id: str) -> str:
        """Execute an approved trade (Phase 1)."""
        # In a real system, look up the proposal by ID
        # For now, this is called after manual confirmation
        return "⚠️  التنفيذ يحتاج ربط API — استخدم MCP Server"

    # ── Position Management ──

    def check_positions(self, current_prices: dict[str, float]) -> list[str]:
        """
        Check all open positions for exit conditions.
        Returns list of actions taken.
        """
        actions = []
        for pos in self.positions:
            if pos.market_id in current_prices:
                pos.current_price = current_prices[pos.market_id]

            exit_reason = self.risk.check_exit_conditions(pos)
            if exit_reason:
                actions.append(f"🚨 {pos.market_question[:30]}: {exit_reason}")

        return actions

    def close_position(
        self,
        position: Position,
        exit_price: float,
        reason: str,
    ) -> str:
        """Close a position and record it."""
        # Determine result
        pnl_pct = (exit_price - position.entry_price) / position.entry_price
        if position.direction == Direction.NO:
            pnl_pct = -pnl_pct
        pnl_usd = position.size_usd * pnl_pct

        if pnl_usd > 0:
            result = TradeResult.WIN
        elif pnl_usd < 0:
            result = TradeResult.LOSS
        else:
            result = TradeResult.BREAKEVEN

        closed = ClosedTrade(
            trade_id=position.trade_id,
            market_id=position.market_id,
            market_question=position.market_question,
            direction=position.direction,
            edge_at_entry=position.edge_at_entry,
            composite_score=0.0,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size_usd=position.size_usd,
            pnl_usd=pnl_usd,
            result=result,
            reason=reason,
            opened_at=position.opened_at,
        )

        # Record in performance tracker and risk engine
        self.performance.record(closed)
        self.risk.record_trade_closed(closed)

        # Remove from open positions
        self.positions = [p for p in self.positions if p.trade_id != position.trade_id]

        return (
            f"{'✅' if pnl_usd >= 0 else '❌'} "
            f"{position.market_question[:30]} — "
            f"P&L: ${pnl_usd:+.2f} ({reason})"
        )

    # ── Helpers ──

    def _format_portfolio_status(self) -> str:
        total_exposure = sum(p.size_usd for p in self.positions)
        total_pnl = sum(p.pnl_usd for p in self.positions)
        return f"""
── 💼 المحفظة ──
  رأس المال     : ${self.config.capital_usd:,.2f}
  التعرض الحالي  : ${total_exposure:,.2f} / ${self.config.max_total_exposure_usd:,.2f}
  P&L المفتوح   : ${total_pnl:+,.2f}
  المراكز المفتوحة: {len(self.positions)}
  الوضع         : {self.config.trading_mode.value}"""

    def _format_risk_status(self) -> str:
        status = self.risk.get_status(self.positions)
        return f"""
── 🛡️  حالة المخاطر ──
  الجلسة       : {'⛔ متوقفة — ' + status['halt_reason'] if status['session_halted'] else '✅ نشطة'}
  صفقات اليوم  : {status['daily_trades']}/{status['max_daily_trades']}
  P&L اليوم    : ${status['daily_pnl']:+,.2f} (الحد: ${status['max_daily_loss']:,.2f})
  خسائر متتالية: {status['consecutive_losses']}/{self.config.risk.max_consecutive_losses}"""
