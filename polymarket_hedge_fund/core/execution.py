"""
Execution Engine — Layer ⑥
Handles order creation and phased execution.
LIMIT orders only. No MARKET orders.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from ..config import HedgeFundConfig, TradingMode
from ..models.market import (
    Direction, MarketData, OrderStatus, Position, TradeProposal,
)

logger = logging.getLogger(__name__)


class OrderAPI(Protocol):
    """Interface for the actual order placement (MCP or mock)."""

    def place_limit_order(
        self,
        market_id: str,
        direction: str,
        size_usd: float,
        limit_price: float,
    ) -> dict:
        """Place a LIMIT order. Returns order details."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        ...

    def get_order_status(self, order_id: str) -> dict:
        """Get current order status."""
        ...


class ExecutionEngine:
    """
    Handles trade execution with phased entry.
    Phase 1: 60% of size immediately
    Phase 2: 40% after 1 hour if price holds or improves
    """

    def __init__(self, config: HedgeFundConfig, api: Optional[OrderAPI] = None):
        self.config = config
        self.api = api

    def build_proposal(
        self,
        market: MarketData,
        direction: Direction,
        edge: float,
        composite_score: float,
        rationale: str,
        signal_data=None,
        quant_estimate=None,
    ) -> TradeProposal:
        """
        Build a trade proposal with proper sizing and SL/TP.
        """
        total_size = self.config.max_order_size_usd
        phase1 = total_size * self.config.execution.phase1_ratio
        phase2 = total_size * self.config.execution.phase2_ratio

        # Determine entry price
        if direction == Direction.YES:
            entry_price = market.yes_price
        else:
            entry_price = market.no_price

        # Calculate SL/TP based on position value, not capital
        # YES: profit when price goes UP, loss when DOWN
        # NO:  profit when price goes DOWN, loss when UP
        if direction == Direction.YES:
            sl_price = entry_price * (1 - self.config.risk.stop_loss_pct)
            tp_price = entry_price * (1 + self.config.risk.take_profit_pct)
        else:
            sl_price = entry_price * (1 + self.config.risk.stop_loss_pct)
            tp_price = entry_price * (1 - self.config.risk.take_profit_pct)

        return TradeProposal(
            market_id=market.market_id,
            market_question=market.question,
            direction=direction,
            edge=edge,
            composite_score=composite_score,
            total_size_usd=total_size,
            phase1_size_usd=phase1,
            phase2_size_usd=phase2,
            limit_price=entry_price,
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
            rationale=rationale,
            signal_data=signal_data,
            quant_estimate=quant_estimate,
        )

    def execute_phase1(self, proposal: TradeProposal) -> Optional[Position]:
        """
        Execute Phase 1 (60% of position).
        Returns Position if successful, None if no API configured.
        """
        if self.config.trading_mode == TradingMode.MANUAL:
            logger.info("📋 MANUAL MODE — عرض الصفقة فقط بدون تنفيذ")
            return self._create_simulated_position(proposal, phase=1)

        if self.api is None:
            logger.warning("⚠️  لا يوجد API متصل — تشغيل محاكاة")
            return self._create_simulated_position(proposal, phase=1)

        # Enforce LIMIT only
        if self.config.execution.order_type != "LIMIT":
            raise ValueError("⛔ MARKET orders are FORBIDDEN — LIMIT only")

        result = self.api.place_limit_order(
            market_id=proposal.market_id,
            direction=proposal.direction.value,
            size_usd=proposal.phase1_size_usd,
            limit_price=proposal.limit_price,
        )

        logger.info(f"✅ Phase 1 executed: ${proposal.phase1_size_usd:.2f}")
        return Position(
            trade_id=proposal.id,
            market_id=proposal.market_id,
            market_question=proposal.market_question,
            direction=proposal.direction,
            entry_price=proposal.limit_price,
            current_price=proposal.limit_price,
            size_usd=proposal.phase1_size_usd,
            phase=1,
            status=OrderStatus.PHASE1_FILLED,
            edge_at_entry=proposal.edge,
            stop_loss_price=proposal.stop_loss_price,
            take_profit_price=proposal.take_profit_price,
        )

    def should_execute_phase2(
        self,
        position: Position,
        current_market: MarketData,
    ) -> bool:
        """
        Check if Phase 2 should execute.
        Conditions: price held or improved after waiting period.
        """
        elapsed = (datetime.utcnow() - position.opened_at).total_seconds() / 60
        if elapsed < self.config.execution.phase2_wait_minutes:
            return False

        # Price must hold or improve
        # YES: price should not have risen too much (still cheap to add)
        # NO: price should not have dropped too much (still cheap to add)
        if position.direction == Direction.YES:
            return current_market.yes_price <= position.entry_price * 1.02
        else:
            return current_market.no_price >= position.entry_price * 0.98

    def _create_simulated_position(
        self, proposal: TradeProposal, phase: int
    ) -> Position:
        """Create a simulated position for paper trading."""
        size = proposal.phase1_size_usd if phase == 1 else proposal.total_size_usd
        return Position(
            trade_id=proposal.id,
            market_id=proposal.market_id,
            market_question=proposal.market_question,
            direction=proposal.direction,
            entry_price=proposal.limit_price,
            current_price=proposal.limit_price,
            size_usd=size,
            phase=phase,
            status=OrderStatus.PHASE1_FILLED if phase == 1 else OrderStatus.FULLY_FILLED,
            edge_at_entry=proposal.edge,
            stop_loss_price=proposal.stop_loss_price,
            take_profit_price=proposal.take_profit_price,
        )

    def format_proposal(self, proposal: TradeProposal) -> str:
        """Format proposal for display."""
        return f"""
┌─────────────────────────────────────────┐
│ السوق    : {proposal.market_question[:40]}
│ الاتجاه  : {proposal.direction.value}
│ Edge     : {proposal.edge:.1%}
│ Score    : {proposal.composite_score:.0f}/100
│ الحجم    : ${proposal.total_size_usd:.2f} (م1: ${proposal.phase1_size_usd:.2f} | م2: ${proposal.phase2_size_usd:.2f})
│ سعر الدخول: {proposal.limit_price:.4f}
│ SL       : {proposal.stop_loss_price:.4f} (-20% من المركز)
│ TP       : {proposal.take_profit_price:.4f} (+40% من المركز)
│ المبرر   : {proposal.rationale[:60]}
└─────────────────────────────────────────┘"""
