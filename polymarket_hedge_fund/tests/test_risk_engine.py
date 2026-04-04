"""
Tests for Risk Engine — ensures rules cannot be bypassed.
"""

import sys
import os
from datetime import datetime, timedelta

# Add repo root to path so the package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from polymarket_hedge_fund.config import HedgeFundConfig
from polymarket_hedge_fund.models.market import (
    Direction, MarketData, Position, SignalData, TradeProposal, ClosedTrade, TradeResult,
)
from polymarket_hedge_fund.core.risk_engine import RiskEngine


def make_market(**kwargs) -> MarketData:
    defaults = dict(
        market_id="test-1",
        question="Test Market?",
        yes_price=0.60,
        no_price=0.40,
        liquidity_usd=50_000,
        volume_24h=10_000,
        spread=0.02,
        expiry=datetime.utcnow() + timedelta(days=7),
    )
    defaults.update(kwargs)
    return MarketData(**defaults)


def make_proposal(**kwargs) -> TradeProposal:
    defaults = dict(
        market_id="test-1",
        market_question="Test Market?",
        direction=Direction.YES,
        edge=0.10,
        composite_score=80.0,
        total_size_usd=10.0,
        phase1_size_usd=6.0,
        phase2_size_usd=4.0,
        limit_price=0.60,
        stop_loss_price=0.48,
        take_profit_price=0.84,
        rationale="Test trade",
    )
    defaults.update(kwargs)
    return TradeProposal(**defaults)


def test_approves_valid_trade():
    config = HedgeFundConfig(capital_usd=1000)
    engine = RiskEngine(config)
    market = make_market()
    proposal = make_proposal()
    result = engine.check_trade(proposal, market, [])
    assert result.approved, f"Should approve valid trade: {result.reasons}"
    print("✅ test_approves_valid_trade")


def test_blocks_oversized_trade():
    config = HedgeFundConfig(capital_usd=1000)  # max = $10
    engine = RiskEngine(config)
    market = make_market()
    proposal = make_proposal(total_size_usd=50.0)  # Way over limit
    result = engine.check_trade(proposal, market, [])
    assert not result.approved
    assert any("حجم الصفقة" in r for r in result.reasons)
    print("✅ test_blocks_oversized_trade")


def test_blocks_low_edge():
    config = HedgeFundConfig(capital_usd=1000)
    engine = RiskEngine(config)
    market = make_market()
    proposal = make_proposal(edge=0.03)  # Below 7% minimum
    result = engine.check_trade(proposal, market, [])
    assert not result.approved
    assert any("Edge" in r for r in result.reasons)
    print("✅ test_blocks_low_edge")


def test_blocks_low_score():
    config = HedgeFundConfig(capital_usd=1000)
    engine = RiskEngine(config)
    market = make_market()
    proposal = make_proposal(composite_score=60.0)  # Below 75
    result = engine.check_trade(proposal, market, [])
    assert not result.approved
    assert any("Score" in r for r in result.reasons)
    print("✅ test_blocks_low_score")


def test_blocks_low_liquidity():
    config = HedgeFundConfig(capital_usd=1000)
    engine = RiskEngine(config)
    market = make_market(liquidity_usd=5000)  # Below $10,000
    proposal = make_proposal()
    result = engine.check_trade(proposal, market, [])
    assert not result.approved
    assert any("السيولة" in r for r in result.reasons)
    print("✅ test_blocks_low_liquidity")


def test_blocks_after_daily_limit():
    config = HedgeFundConfig(capital_usd=1000)
    engine = RiskEngine(config)
    market = make_market()
    proposal = make_proposal()

    engine.record_trade_opened()
    engine.record_trade_opened()  # 2 trades

    result = engine.check_trade(proposal, market, [])
    assert not result.approved
    assert any("الحد اليومي" in r for r in result.reasons)
    print("✅ test_blocks_after_daily_limit")


def test_halts_after_consecutive_losses():
    config = HedgeFundConfig(capital_usd=1000)
    engine = RiskEngine(config)

    for _ in range(2):
        engine.record_trade_closed(ClosedTrade(
            trade_id="t", market_id="m", market_question="Q",
            direction=Direction.YES, edge_at_entry=0.1, composite_score=80,
            entry_price=0.6, exit_price=0.48, size_usd=10,
            pnl_usd=-2.0, result=TradeResult.LOSS,
            reason="SL", opened_at=datetime.utcnow(),
        ))

    assert engine.is_halted
    print("✅ test_halts_after_consecutive_losses")


def test_blocks_exposure_limit():
    config = HedgeFundConfig(capital_usd=1000)  # max exposure = $50
    engine = RiskEngine(config)
    market = make_market()
    proposal = make_proposal(total_size_usd=10.0)

    # Existing positions totaling $45
    existing = [Position(
        trade_id="x", market_id="other", market_question="Q",
        direction=Direction.YES, entry_price=0.5, current_price=0.5,
        size_usd=45.0, edge_at_entry=0.1,
        stop_loss_price=0.4, take_profit_price=0.7,
    )]

    result = engine.check_trade(proposal, market, existing)
    assert not result.approved
    assert any("التعرض الكلي" in r for r in result.reasons)
    print("✅ test_blocks_exposure_limit")


def test_stop_loss_detection():
    config = HedgeFundConfig(capital_usd=1000)
    engine = RiskEngine(config)

    pos = Position(
        trade_id="t", market_id="m", market_question="Q",
        direction=Direction.YES, entry_price=0.60, current_price=0.45,
        size_usd=10.0, edge_at_entry=0.1,
        stop_loss_price=0.48, take_profit_price=0.84,
    )

    reason = engine.check_exit_conditions(pos)
    assert reason is not None
    assert "STOP-LOSS" in reason
    print("✅ test_stop_loss_detection")


def test_conflicting_signals_blocked():
    config = HedgeFundConfig(capital_usd=1000)
    engine = RiskEngine(config)
    market = make_market()
    signal = SignalData(market_id="test-1", conflicting_signals=True)
    proposal = make_proposal(signal_data=signal)
    result = engine.check_trade(proposal, market, [])
    assert not result.approved
    assert any("تعارض" in r for r in result.reasons)
    print("✅ test_conflicting_signals_blocked")


if __name__ == "__main__":
    test_approves_valid_trade()
    test_blocks_oversized_trade()
    test_blocks_low_edge()
    test_blocks_low_score()
    test_blocks_low_liquidity()
    test_blocks_after_daily_limit()
    test_halts_after_consecutive_losses()
    test_blocks_exposure_limit()
    test_stop_loss_detection()
    test_conflicting_signals_blocked()
    print("\n🎉 All 10 tests passed!")
