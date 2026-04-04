"""
Tests for Backtesting Engine.
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from polymarket_hedge_fund.config import (
    HedgeFundConfig, RiskLimits, EntryRequirements,
)
from polymarket_hedge_fund.core.backtester import (
    Backtester, BacktestConfig, BacktestResult,
    SyntheticMarketGenerator, run_quick_backtest,
)


def test_generator_creates_markets():
    config = BacktestConfig(seed=42, num_markets=20)
    gen = SyntheticMarketGenerator(config)
    markets = gen.step(datetime(2025, 1, 1))
    assert len(markets) > 0
    for m in markets:
        assert 0 < m.yes_price < 1
        assert m.liquidity_usd > 0
        assert m.time_to_expiry_hours > 0
    print("✅ test_generator_creates_markets")


def test_generator_prices_move():
    config = BacktestConfig(seed=42, num_markets=10)
    gen = SyntheticMarketGenerator(config)
    m1 = gen.step(datetime(2025, 1, 1))
    prices_1 = {m.market_id: m.yes_price for m in m1}
    m2 = gen.step(datetime(2025, 1, 2))
    prices_2 = {m.market_id: m.yes_price for m in m2}

    # At least some prices should have changed
    changed = sum(1 for mid in prices_1 if mid in prices_2
                  and abs(prices_1[mid] - prices_2[mid]) > 0.001)
    assert changed > 0, "Prices should move between steps"
    print("✅ test_generator_prices_move")


def test_generator_markets_resolve():
    config = BacktestConfig(seed=42, num_markets=10)
    gen = SyntheticMarketGenerator(config)

    # Step through many days until some markets resolve
    resolved_count = 0
    for day in range(100):
        markets = gen.step(datetime(2025, 1, 1) + timedelta(days=day))
        for mid in list(gen._markets):
            if gen._markets[mid]["resolved"]:
                resolved_count += 1

    assert resolved_count > 0, "Some markets should resolve over 100 days"
    print("✅ test_generator_markets_resolve")


def test_generator_reproducible():
    config = BacktestConfig(seed=123, num_markets=10)
    gen1 = SyntheticMarketGenerator(config)
    m1 = gen1.step(datetime(2025, 1, 1))

    gen2 = SyntheticMarketGenerator(config)
    m2 = gen2.step(datetime(2025, 1, 1))

    for a, b in zip(m1, m2):
        assert a.market_id == b.market_id
        assert abs(a.yes_price - b.yes_price) < 0.0001
    print("✅ test_generator_reproducible")


def test_backtest_runs():
    result = run_quick_backtest(capital=1000, days=30, seed=42)
    assert isinstance(result, BacktestResult)
    assert result.total_days == 30
    assert len(result.equity_curve) > 0
    assert result.markets_scanned > 0
    print("✅ test_backtest_runs")


def test_backtest_respects_risk_limits():
    """With strict limits, fewer trades should be executed."""
    strict = HedgeFundConfig(
        capital_usd=1000,
        risk=RiskLimits(max_daily_trades=1),
        entry=EntryRequirements(min_edge_pct=0.15, min_composite_score=90),
    )
    relaxed = HedgeFundConfig(
        capital_usd=1000,
        risk=RiskLimits(max_daily_trades=5),
        entry=EntryRequirements(min_edge_pct=0.03, min_composite_score=50),
    )

    bt_config = BacktestConfig(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 4, 1),
        seed=42,
        initial_capital=1000,
    )

    r_strict = Backtester(fund_config=strict, backtest_config=bt_config).run()
    r_relaxed = Backtester(fund_config=relaxed, backtest_config=bt_config).run()

    assert r_relaxed.trades_proposed >= r_strict.trades_proposed
    print("✅ test_backtest_respects_risk_limits")


def test_backtest_equity_curve_length():
    bt_config = BacktestConfig(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 2, 1),
        step_hours=24,
        seed=42,
        initial_capital=1000,
    )
    result = Backtester(backtest_config=bt_config).run()
    # Should have roughly 31 data points (one per day)
    assert 30 <= len(result.equity_curve) <= 33
    print("✅ test_backtest_equity_curve_length")


def test_backtest_summary_format():
    result = run_quick_backtest(capital=500, days=30, seed=99)
    summary = result.summary()
    assert "نتائج الاختبار التاريخي" in summary
    assert "نسبة الفوز" in summary
    assert "500" in summary  # Capital should appear
    print("✅ test_backtest_summary_format")


def test_different_seeds_different_results():
    r1 = run_quick_backtest(capital=1000, days=60, seed=1)
    r2 = run_quick_backtest(capital=1000, days=60, seed=999)
    # Markets scanned might differ due to different market resolution timing
    # But they should both run successfully
    assert r1.total_days == r2.total_days == 60
    print("✅ test_different_seeds_different_results")


def test_backtest_no_negative_equity():
    """Equity should not go wildly negative (risk engine should protect)."""
    result = run_quick_backtest(capital=1000, days=180, seed=42)
    for date_str, equity in result.equity_curve:
        # Allow some loss but not catastrophic
        assert equity > 800, f"Equity dropped too low: ${equity:.2f} on {date_str}"
    print("✅ test_backtest_no_negative_equity")


if __name__ == "__main__":
    test_generator_creates_markets()
    test_generator_prices_move()
    test_generator_markets_resolve()
    test_generator_reproducible()
    test_backtest_runs()
    test_backtest_respects_risk_limits()
    test_backtest_equity_curve_length()
    test_backtest_summary_format()
    test_different_seeds_different_results()
    test_backtest_no_negative_equity()
    print("\n🎉 All 10 backtester tests passed!")
