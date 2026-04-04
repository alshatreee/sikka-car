"""
Backtesting Engine
Simulates the hedge fund strategy against historical or synthetic market data.
Runs the full pipeline: Scanner → Quant → Risk → Execution → Performance.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..config import HedgeFundConfig
from ..models.market import (
    ClosedTrade, Direction, MarketData, Position, SignalData, TradeResult,
)
from .performance import PerformanceMetrics, PerformanceTracker
from .quant_model import QuantModel
from .risk_engine import RiskEngine
from .scanner import MarketScanner
from .execution import ExecutionEngine


@dataclass
class BacktestCandle:
    """One time step in the backtest."""
    timestamp: datetime
    market_id: str
    question: str
    yes_price: float
    no_price: float
    liquidity_usd: float
    volume_24h: float
    spread: float
    expiry: datetime
    # The actual outcome (True = YES wins, False = NO wins, None = unresolved)
    outcome: Optional[bool] = None


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    start_date: datetime = field(default_factory=lambda: datetime(2025, 1, 1))
    end_date: datetime = field(default_factory=lambda: datetime(2025, 12, 31))
    step_hours: int = 24          # Time between steps (daily by default)
    num_markets: int = 20         # Markets available per step
    seed: Optional[int] = 42      # Random seed for reproducibility
    initial_capital: float = 1000.0
    # Price movement parameters
    volatility: float = 0.03      # Daily price volatility
    mean_reversion: float = 0.1   # How strongly prices revert to fair value
    # Realistic cost parameters
    taker_fee_pct: float = 0.02   # 2% taker fee (Polymarket charges fees on some markets)
    spread_cost_pct: float = 0.01 # Additional spread cost on each trade
    gas_cost_per_trade: float = 0.05  # Approx MATIC gas cost in USD per trade


@dataclass
class BacktestResult:
    """Complete backtest results."""
    config: BacktestConfig
    fund_config: HedgeFundConfig
    metrics: PerformanceMetrics
    equity_curve: list[tuple[str, float]]  # (date, equity)
    trades: list[dict]
    total_days: int
    active_days: int  # Days with at least one trade
    markets_scanned: int
    trades_proposed: int
    trades_rejected: int
    daily_pnl: list[tuple[str, float]]
    total_fees_usd: float = 0.0
    brier_score: float = 0.0  # Lower is better (0 = perfect calibration)

    def summary(self) -> str:
        m = self.metrics
        net_pnl = m.total_pnl_usd
        return f"""
══════════════════════════════════════════════
         📊 نتائج الاختبار التاريخي
══════════════════════════════════════════════

  الفترة        : {self.config.start_date.date()} → {self.config.end_date.date()}
  إجمالي الأيام : {self.total_days}
  أيام نشطة     : {self.active_days}
  أسواق ممسوحة  : {self.markets_scanned}
  صفقات مقترحة  : {self.trades_proposed}
  صفقات مرفوضة  : {self.trades_rejected}
  صفقات منفذة   : {m.total_trades}

  ── الأداء (بعد الرسوم) ──
  نسبة الفوز    : {m.win_rate:.1%}
  إجمالي P&L    : ${net_pnl:+,.2f}
  الرسوم المدفوعة: ${self.total_fees_usd:,.2f}
  متوسط العائد  : ${m.avg_pnl_usd:+,.2f}
  أقصى تراجع    : ${m.max_drawdown_usd:,.2f}
  معامل الربح   : {m.profit_factor:.2f}
  Brier Score    : {self.brier_score:.4f} (أقل = أفضل)
  دقة Edge      : {m.edge_accuracy:.1%}

  ── التكاليف ──
  Taker Fee      : {self.config.taker_fee_pct:.1%}
  Spread Cost    : {self.config.spread_cost_pct:.1%}
  Gas/Trade      : ${self.config.gas_cost_per_trade:.2f}

  ── العائد ──
  رأس المال     : ${self.config.initial_capital:,.2f}
  القيمة النهائية: ${self.config.initial_capital + net_pnl:,.2f}
  العائد الكلي  : {m.total_pnl_usd / self.config.initial_capital:.1%}
══════════════════════════════════════��═══════"""


class SyntheticMarketGenerator:
    """
    Generates realistic synthetic market data for backtesting.
    Each market has a hidden "true probability" that the price eventually converges to.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.rng = random.Random(config.seed)
        self._markets: dict[str, dict] = {}
        self._init_markets()

    def _init_markets(self) -> None:
        """Create a pool of synthetic markets."""
        categories = ["Politics", "Sports", "Crypto", "Tech", "Economy"]
        subjects = [
            "BTC reach $150k", "ETH reach $10k", "Trump win election",
            "Fed cut rates", "AI regulation pass", "SpaceX Mars landing",
            "Netflix hit 400M subs", "Gold exceed $3000", "Oil below $50",
            "DOGE reach $1", "Apple hit $4T", "Inflation below 2%",
            "US recession", "China GDP above 6%", "UFC 350 main event",
            "World Cup qualifier", "Champions League final",
            "AWS outage this month", "New COVID variant", "Solar eclipse visible",
            "Interest rates hold", "Housing crash", "Quantum breakthrough",
            "AGI announced", "Major cyber attack",
        ]

        for i in range(max(self.config.num_markets * 2, 30)):
            mid = f"synth-{i:04d}"
            true_prob = self.rng.uniform(0.15, 0.85)
            days_to_expiry = self.rng.randint(5, 60)
            subject = subjects[i % len(subjects)]
            category = categories[i % len(categories)]

            self._markets[mid] = {
                "id": mid,
                "question": f"{subject}?",
                "true_prob": true_prob,
                "current_price": true_prob + self.rng.uniform(-0.15, 0.15),
                "liquidity": self.rng.uniform(15000, 200000),
                "volume": self.rng.uniform(5000, 80000),
                "category": category,
                "days_to_expiry": days_to_expiry,
                "start_expiry_days": days_to_expiry,
                "resolved": False,
                "outcome": self.rng.random() < true_prob,
            }
            # Clamp price
            self._markets[mid]["current_price"] = max(
                0.05, min(0.95, self._markets[mid]["current_price"])
            )

    def step(self, current_date: datetime) -> list[MarketData]:
        """
        Advance one time step. Prices move with noise + mean reversion.
        Returns available (unresolved) markets.
        """
        available = []
        for mid, m in self._markets.items():
            if m["resolved"]:
                continue

            m["days_to_expiry"] -= self.config.step_hours / 24

            # Resolve if expired
            if m["days_to_expiry"] <= 0:
                m["resolved"] = True
                m["current_price"] = 1.0 if m["outcome"] else 0.0
                continue

            # Price movement: noise + mean reversion to true probability
            noise = self.rng.gauss(0, self.config.volatility)
            reversion = self.config.mean_reversion * (m["true_prob"] - m["current_price"])
            m["current_price"] += noise + reversion
            m["current_price"] = max(0.03, min(0.97, m["current_price"]))

            # Volume/liquidity fluctuation
            m["volume"] *= self.rng.uniform(0.8, 1.2)
            m["liquidity"] *= self.rng.uniform(0.95, 1.05)

            spread = abs(self.rng.gauss(0.02, 0.01))
            price = m["current_price"]

            # Set expiry relative to utcnow() so MarketData.time_to_expiry_hours works
            available.append(MarketData(
                market_id=mid,
                question=m["question"],
                yes_price=price,
                no_price=1 - price,
                liquidity_usd=m["liquidity"],
                volume_24h=m["volume"],
                spread=spread,
                expiry=datetime.utcnow() + timedelta(days=m["days_to_expiry"]),
                category=m["category"],
            ))

        return available

    def get_outcome(self, market_id: str) -> Optional[bool]:
        """Get the actual outcome for a resolved market."""
        m = self._markets.get(market_id)
        if m and m["resolved"]:
            return m["outcome"]
        return None

    def get_true_prob(self, market_id: str) -> float:
        """Get the hidden true probability (for edge accuracy calc)."""
        return self._markets.get(market_id, {}).get("true_prob", 0.5)

    def get_current_price(self, market_id: str) -> float:
        """Get current price for a market."""
        return self._markets.get(market_id, {}).get("current_price", 0.5)


class Backtester:
    """
    Runs a full backtest simulation.

    For each time step:
    1. Generate/update market prices
    2. Check open positions for SL/TP
    3. Scan markets for opportunities
    4. Propose trades via Quant model
    5. Risk-check and execute
    6. Record results
    """

    def __init__(
        self,
        fund_config: Optional[HedgeFundConfig] = None,
        backtest_config: Optional[BacktestConfig] = None,
    ):
        self.fund_config = fund_config or HedgeFundConfig()
        self.bt_config = backtest_config or BacktestConfig(
            initial_capital=self.fund_config.capital_usd
        )
        # Sync capital from backtest config without overwriting risk/entry settings
        if self.fund_config.capital_usd != self.bt_config.initial_capital:
            self.fund_config.capital_usd = self.bt_config.initial_capital

    def run(self) -> BacktestResult:
        """Execute the backtest. Returns BacktestResult."""
        # Initialize components
        risk = RiskEngine(self.fund_config)
        quant = QuantModel(self.fund_config)
        scanner = MarketScanner(self.fund_config)
        execution = ExecutionEngine(self.fund_config)
        import tempfile
        _bt_tmpdir = tempfile.mkdtemp(prefix="bt_")
        tracker = PerformanceTracker(data_dir=_bt_tmpdir)
        generator = SyntheticMarketGenerator(self.bt_config)
        rng = random.Random(self.bt_config.seed)

        positions: list[Position] = []
        equity = self.bt_config.initial_capital
        equity_curve: list[tuple[str, float]] = []
        daily_pnl: list[tuple[str, float]] = []
        markets_scanned = 0
        trades_proposed = 0
        trades_rejected = 0
        active_days = 0
        total_fees = 0.0
        # Brier score tracking: (estimated_prob, actual_outcome)
        brier_samples: list[tuple[float, float]] = []

        current = self.bt_config.start_date
        step_delta = timedelta(hours=self.bt_config.step_hours)

        while current <= self.bt_config.end_date:
            date_str = current.strftime("%Y-%m-%d")
            day_pnl = 0.0

            # 1. Get market data
            markets = generator.step(current)
            markets_scanned += len(markets)

            # 2. Check open positions for SL/TP and resolved markets
            closed_this_step = []
            for pos in list(positions):
                new_price = generator.get_current_price(pos.market_id)
                pos.current_price = new_price

                exit_reason = risk.check_exit_conditions(pos)
                outcome = generator.get_outcome(pos.market_id)

                if outcome is not None:
                    # Market resolved
                    if pos.direction == Direction.YES:
                        final_price = 1.0 if outcome else 0.0
                    else:
                        final_price = 0.0 if outcome else 1.0
                    exit_reason = f"RESOLVED: {'YES' if outcome else 'NO'}"
                    pos.current_price = final_price

                if exit_reason:
                    pnl_pct = pos.pnl_pct
                    pnl_usd = pos.pnl_usd

                    # Deduct exit fees (taker fee + spread + gas)
                    exit_fee = (
                        pos.size_usd * self.bt_config.taker_fee_pct
                        + pos.size_usd * self.bt_config.spread_cost_pct
                        + self.bt_config.gas_cost_per_trade
                    )
                    pnl_usd -= exit_fee
                    total_fees += exit_fee

                    # Brier score: track estimated prob vs actual outcome
                    if outcome is not None:
                        est_prob = pos.edge_at_entry + pos.entry_price
                        actual = 1.0 if outcome else 0.0
                        if pos.direction == Direction.NO:
                            est_prob = 1 - est_prob
                            actual = 1 - actual
                        est_prob = max(0, min(1, est_prob))
                        brier_samples.append((est_prob, actual))

                    result = TradeResult.WIN if pnl_usd > 0 else (
                        TradeResult.LOSS if pnl_usd < 0 else TradeResult.BREAKEVEN
                    )

                    closed = ClosedTrade(
                        trade_id=pos.trade_id,
                        market_id=pos.market_id,
                        market_question=pos.market_question,
                        direction=pos.direction,
                        edge_at_entry=pos.edge_at_entry,
                        composite_score=0.0,
                        entry_price=pos.entry_price,
                        exit_price=pos.current_price,
                        size_usd=pos.size_usd,
                        pnl_usd=pnl_usd,
                        result=result,
                        reason=exit_reason,
                        opened_at=pos.opened_at,
                        closed_at=current,
                    )
                    tracker.record(closed)
                    risk.record_trade_closed(closed)
                    day_pnl += pnl_usd
                    equity += pnl_usd
                    positions = [p for p in positions if p.trade_id != pos.trade_id]

            # 3. Skip if halted
            if risk.is_halted:
                equity_curve.append((date_str, equity))
                daily_pnl.append((date_str, day_pnl))
                # Reset halt for next day (simulating manual review)
                risk.resume_session()
                current += step_delta
                continue

            # 4. Scan and rank markets
            top_markets = scanner.get_top_markets(markets, top_n=5)

            if not top_markets:
                equity_curve.append((date_str, equity))
                daily_pnl.append((date_str, day_pnl))
                current += step_delta
                continue

            # 5. Propose trades (max 2 per day)
            traded_today = False
            for scored in top_markets[:2]:
                market = scored.market

                # Build synthetic signal
                true_prob = generator.get_true_prob(market.market_id)
                signal = SignalData(
                    market_id=market.market_id,
                    news_score=true_prob + rng.uniform(-0.1, 0.1),
                    sentiment_score=0.5 + rng.uniform(-0.2, 0.2),
                    market_data_score=min(1.0, market.liquidity_usd / 100000),
                    time_factor_score=min(1.0, market.time_to_expiry_hours / (14 * 24)),
                    conflicting_signals=False,
                )
                # Clamp scores
                signal.news_score = max(0, min(1, signal.news_score))
                signal.sentiment_score = max(0, min(1, signal.sentiment_score))

                # Historical probability estimate (with noise)
                p_hist = true_prob + rng.uniform(-0.08, 0.08)
                p_hist = max(0.05, min(0.95, p_hist))

                # Quant estimate
                estimate = quant.estimate(market, signal, p_hist)

                # Determine direction
                if estimate.edge > 0:
                    direction = Direction.YES
                else:
                    direction = Direction.NO
                    estimate = quant.estimate(
                        MarketData(
                            market_id=market.market_id,
                            question=market.question,
                            yes_price=market.no_price,
                            no_price=market.yes_price,
                            liquidity_usd=market.liquidity_usd,
                            volume_24h=market.volume_24h,
                            spread=market.spread,
                            expiry=market.expiry,
                        ),
                        signal, 1 - p_hist,
                    )

                if estimate.edge < self.fund_config.entry.min_edge_pct:
                    continue

                # Build proposal
                proposal = execution.build_proposal(
                    market=market,
                    direction=direction,
                    edge=estimate.edge,
                    composite_score=estimate.composite_score,
                    rationale="Backtest auto-trade",
                    signal_data=signal,
                    quant_estimate=estimate,
                )
                trades_proposed += 1

                # Risk check
                risk_result = risk.check_trade(proposal, market, positions)
                if not risk_result.approved:
                    trades_rejected += 1
                    continue

                # Execute (deduct entry fees: taker + spread + gas)
                position = execution.execute_phase1(proposal)
                if position:
                    entry_fee = (
                        position.size_usd * self.bt_config.taker_fee_pct
                        + position.size_usd * self.bt_config.spread_cost_pct
                        + self.bt_config.gas_cost_per_trade
                    )
                    total_fees += entry_fee
                    equity -= entry_fee
                    position.opened_at = current
                    positions.append(position)
                    risk.record_trade_opened()
                    traded_today = True

            if traded_today:
                active_days += 1

            equity_curve.append((date_str, equity))
            daily_pnl.append((date_str, day_pnl))
            current += step_delta

        # Close remaining positions at current price (with exit fees)
        for pos in list(positions):
            exit_fee = (
                pos.size_usd * self.bt_config.taker_fee_pct
                + pos.size_usd * self.bt_config.spread_cost_pct
                + self.bt_config.gas_cost_per_trade
            )
            total_fees += exit_fee
            pnl_usd = pos.pnl_usd - exit_fee
            result = TradeResult.WIN if pnl_usd > 0 else (
                TradeResult.LOSS if pnl_usd < 0 else TradeResult.BREAKEVEN
            )
            closed = ClosedTrade(
                trade_id=pos.trade_id,
                market_id=pos.market_id,
                market_question=pos.market_question,
                direction=pos.direction,
                edge_at_entry=pos.edge_at_entry,
                composite_score=0.0,
                entry_price=pos.entry_price,
                exit_price=pos.current_price,
                size_usd=pos.size_usd,
                pnl_usd=pnl_usd,
                result=result,
                reason="BACKTEST_END",
                opened_at=pos.opened_at,
                closed_at=self.bt_config.end_date,
            )
            tracker.record(closed)
            equity += pnl_usd

        total_days = (self.bt_config.end_date - self.bt_config.start_date).days

        # Calculate Brier score: mean squared error of probability estimates
        brier = 0.0
        if brier_samples:
            brier = sum((p - a) ** 2 for p, a in brier_samples) / len(brier_samples)

        return BacktestResult(
            config=self.bt_config,
            fund_config=self.fund_config,
            metrics=tracker.get_metrics(),
            equity_curve=equity_curve,
            trades=tracker.trades,
            total_days=total_days,
            active_days=active_days,
            markets_scanned=markets_scanned,
            trades_proposed=trades_proposed,
            trades_rejected=trades_rejected,
            daily_pnl=daily_pnl,
            total_fees_usd=total_fees,
            brier_score=brier,
        )


def run_quick_backtest(
    capital: float = 1000,
    days: int = 90,
    seed: int = 42,
) -> BacktestResult:
    """Convenience function for a quick backtest."""
    bt_config = BacktestConfig(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 1) + timedelta(days=days),
        seed=seed,
        initial_capital=capital,
    )
    backtester = Backtester(backtest_config=bt_config)
    return backtester.run()


if __name__ == "__main__":
    print("Running 90-day backtest...")
    result = run_quick_backtest(capital=1000, days=90, seed=42)
    print(result.summary())
