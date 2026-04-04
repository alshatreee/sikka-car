"""
Quant Layer — Layer ③
Probability estimation and Edge calculation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import HedgeFundConfig, QuantWeights, SignalWeights
from ..models.market import Direction, MarketData, QuantEstimate, SignalData


class QuantModel:
    """
    Composite probability model.

    P(est) = (P_historical × 0.25) + (P_news × 0.25) + (P_sentiment × 0.20)
           + (P_structure × 0.15) + (P_time × 0.15)

    Edge = P(est) − market_price
    """

    def __init__(self, config: HedgeFundConfig):
        self.weights = config.quant_weights
        self.signal_weights = config.signal_weights

    def estimate(
        self,
        market: MarketData,
        signal: SignalData,
        p_historical: float,
        direction: Direction = None,
    ) -> QuantEstimate:
        """
        Calculate estimated probability and edge for a market.

        Args:
            market: Current market data
            signal: Aggregated signal data
            p_historical: Historical probability from similar events (0-1)

        Returns:
            QuantEstimate with all components
        """
        # Derive component probabilities
        p_news = signal.news_score
        p_sentiment = signal.sentiment_score
        p_structure = self._calc_structure_score(market)
        p_time = self._calc_time_score(market)

        # Weighted composite probability
        p_est = (
            p_historical * self.weights.historical
            + p_news * self.weights.news
            + p_sentiment * self.weights.sentiment
            + p_structure * self.weights.structure
            + p_time * self.weights.time_decay
        )

        # Edge = estimated probability - market price (direction-aware)
        # YES: edge = P(est) - yes_price (profit when event happens)
        # NO:  edge = (1 - P(est)) - no_price (profit when event doesn't happen)
        if direction == Direction.NO:
            market_price = market.no_price
            edge = (1 - p_est) - market_price
        else:
            market_price = market.yes_price
            edge = p_est - market_price

        # Composite score (0-100)
        composite_score = self._calc_composite_score(
            edge=edge,
            signal=signal,
            market=market,
        )

        return QuantEstimate(
            market_id=market.market_id,
            p_historical=p_historical,
            p_news=p_news,
            p_sentiment=p_sentiment,
            p_structure=p_structure,
            p_time=p_time,
            estimated_probability=p_est,
            market_price=market_price,
            edge=edge,
            composite_score=composite_score,
        )

    def calc_signal_strength(self, signal: SignalData) -> float:
        """
        Calculate overall signal strength (0-1).

        Signal = (news × 0.30) + (sentiment × 0.25)
               + (market_data × 0.25) + (time × 0.20)
        """
        return (
            signal.news_score * self.signal_weights.news
            + signal.sentiment_score * self.signal_weights.market_sentiment
            + signal.market_data_score * self.signal_weights.market_data
            + signal.time_factor_score * self.signal_weights.time_factor
        )

    def _calc_structure_score(self, market: MarketData) -> float:
        """
        Score market structure (liquidity, volume, spread).
        Higher liquidity + volume and lower spread = higher score.
        """
        # Liquidity score: 0-1 (saturates at $100k)
        liq_score = min(1.0, market.liquidity_usd / 100_000)

        # Volume score: 0-1 (saturates at $50k daily)
        vol_score = min(1.0, market.volume_24h / 50_000)

        # Spread score: 1.0 at 0% spread, 0.0 at 10% spread
        spread_score = max(0.0, 1.0 - market.spread / 0.10)

        return liq_score * 0.4 + vol_score * 0.3 + spread_score * 0.3

    def _calc_time_score(self, market: MarketData) -> float:
        """
        Time decay factor.
        Markets very close to expiry get lower scores (less time to recover).
        Markets very far out also get lower scores (more uncertainty).
        Sweet spot: 2-14 days.
        """
        hours = market.time_to_expiry_hours
        days = hours / 24

        if days < 1:
            return 0.2  # Too close to expiry
        elif days < 2:
            return 0.5
        elif days <= 14:
            return 0.8 + 0.2 * min(1.0, (days - 2) / 12)  # Sweet spot
        elif days <= 30:
            return 0.7
        else:
            return 0.5  # Too far out, high uncertainty

    def _calc_composite_score(
        self,
        edge: float,
        signal: SignalData,
        market: MarketData,
    ) -> float:
        """
        Composite score (0-100) combining edge, signal strength,
        and market quality.
        """
        # Edge component (0-40 points): 7% edge = 20pts, 15%+ = 40pts
        edge_pts = min(40.0, max(0.0, edge / 0.15 * 40))

        # Signal strength (0-30 points)
        signal_strength = self.calc_signal_strength(signal)
        signal_pts = signal_strength * 30

        # Market quality (0-30 points)
        structure = self._calc_structure_score(market)
        time_score = self._calc_time_score(market)
        quality_pts = (structure * 0.6 + time_score * 0.4) * 30

        return min(100.0, edge_pts + signal_pts + quality_pts)
