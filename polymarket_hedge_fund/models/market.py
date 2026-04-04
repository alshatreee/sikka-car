"""
Data models for markets, trades, and positions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(Enum):
    YES = "YES"
    NO = "NO"


class OrderStatus(Enum):
    PENDING = "pending"
    PHASE1_FILLED = "phase1_filled"
    FULLY_FILLED = "fully_filled"
    CANCELLED = "cancelled"
    STOPPED_OUT = "stopped_out"
    TAKE_PROFIT = "take_profit"


class TradeResult(Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"


@dataclass
class MarketData:
    """Raw market data from Polymarket."""
    market_id: str
    question: str
    yes_price: float
    no_price: float
    liquidity_usd: float
    volume_24h: float
    spread: float
    expiry: datetime
    category: str = ""

    @property
    def time_to_expiry_hours(self) -> float:
        delta = self.expiry - datetime.utcnow()
        return max(0, delta.total_seconds() / 3600)


@dataclass
class SignalData:
    """Aggregated signal data for a market."""
    market_id: str
    news_score: float = 0.0        # 0-1: bullish signal from news
    sentiment_score: float = 0.0   # 0-1: market sentiment
    market_data_score: float = 0.0 # 0-1: structural analysis
    time_factor_score: float = 0.0 # 0-1: time decay factor
    news_summary: str = ""
    conflicting_signals: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QuantEstimate:
    """Output of the Quant Layer."""
    market_id: str
    p_historical: float = 0.0
    p_news: float = 0.0
    p_sentiment: float = 0.0
    p_structure: float = 0.0
    p_time: float = 0.0
    estimated_probability: float = 0.0
    market_price: float = 0.0
    edge: float = 0.0
    composite_score: float = 0.0


@dataclass
class TradeProposal:
    """A proposed trade — must pass Risk Engine before execution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    market_id: str = ""
    market_question: str = ""
    direction: Direction = Direction.YES
    edge: float = 0.0
    composite_score: float = 0.0
    total_size_usd: float = 0.0
    phase1_size_usd: float = 0.0
    phase2_size_usd: float = 0.0
    limit_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    rationale: str = ""
    quant_estimate: Optional[QuantEstimate] = None
    signal_data: Optional[SignalData] = None


@dataclass
class Position:
    """An open position."""
    trade_id: str
    market_id: str
    market_question: str
    direction: Direction
    entry_price: float
    current_price: float
    size_usd: float
    phase: int = 1  # 1 or 2
    status: OrderStatus = OrderStatus.PHASE1_FILLED
    opened_at: datetime = field(default_factory=datetime.utcnow)
    edge_at_entry: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0

    @property
    def pnl_usd(self) -> float:
        if self.direction == Direction.YES:
            return self.size_usd * (self.current_price - self.entry_price) / self.entry_price
        else:
            return self.size_usd * (self.entry_price - self.current_price) / self.entry_price

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        if self.direction == Direction.YES:
            return (self.current_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.current_price) / self.entry_price


@dataclass
class ClosedTrade:
    """Record of a completed trade for performance tracking."""
    trade_id: str
    market_id: str
    market_question: str
    direction: Direction
    edge_at_entry: float
    composite_score: float
    entry_price: float
    exit_price: float
    size_usd: float
    pnl_usd: float
    result: TradeResult
    reason: str  # SL, TP, manual, expiry
    opened_at: datetime
    closed_at: datetime = field(default_factory=datetime.utcnow)
