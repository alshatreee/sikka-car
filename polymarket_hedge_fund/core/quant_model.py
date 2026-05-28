"""
Quant Layer — Layer ③
Probability estimation and Edge calculation.
Includes: category-aware fees, edge skepticism, time-decay market pull.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import HedgeFundConfig, QuantWeights, SignalWeights
from ..models.market import Direction, MarketData, QuantEstimate, SignalData

# Polymarket fee schedule by category (taker fee %)
# Source: SharkFlow research — fees vary significantly by market type
CATEGORY_FEES = {
    "crypto": 0.072,
    "btc": 0.072,
    "bitcoin": 0.072,
    "ethereum": 0.072,
    "sports": 0.030,
    "nba": 0.030,
    "nfl": 0.030,
    "mlb": 0.030,
    "soccer": 0.030,
    "ufc": 0.030,
    "politics": 0.000,
    "geopolitics": 0.000,
    "election": 0.000,
    "economy": 0.015,
    "fed": 0.015,
    "weather": 0.020,
    "tech": 0.015,
    "ai": 0.015,
    "entertainment": 0.020,
}
DEFAULT_FEE = 0.020


def get_category_fee(market: MarketData) -> float:
    """Return taker fee % for a market based on its category/question."""
    cat = market.category.lower().strip() if market.category else ""
    if cat in CATEGORY_FEES:
        return CATEGORY_FEES[cat]
    q = market.question.lower() if market.question else ""
    for keyword, fee in CATEGORY_FEES.items():
        if keyword in q:
            return fee
    return DEFAULT_FEE


class QuantModel:
    """
    Composite probability model with 3 SharkFlow-inspired corrections:

    1. Category-aware fees (crypto 7.2%, sports 3%, politics 0%)
    2. Edge skepticism discount (edges > 12% are likely noise)
    3. Time-decay market pull (P(est) → market price near expiry)

    P(est) = (P_historical × 0.25) + (P_news × 0.25) + (P_sentiment × 0.20)
           + (P_structure × 0.15) + (P_time × 0.15)

    Edge = P(est) − market_price − fee_adjustment
    """

    def __init__(self, config: HedgeFundConfig):
        self.weights = config.quant_weights
        self.signal_weights = config.signal_weights

    def _calc_news_proxy(self, market: MarketData) -> float:
        """Derive news signal from volume spike and price momentum."""
        vol_signal = min(1.0, market.volume_24h / 80_000)
        price = market.yes_price
        price_conviction = abs(price - 0.50) * 2
        if price > 0.50:
            news_score = 0.50 + (vol_signal * 0.3 + price_conviction * 0.2)
        else:
            news_score = 0.50 - (vol_signal * 0.3 + price_conviction * 0.2)
        return max(0.05, min(0.95, news_score))

    def _calc_sentiment_proxy(self, market: MarketData) -> float:
        """Derive sentiment from liquidity flow direction."""
        liq_vol_ratio = (market.liquidity_usd / max(market.volume_24h, 1))
        patience_score = min(1.0, liq_vol_ratio / 5.0)
        consensus_score = max(0.0, 1.0 - market.spread / 0.08)
        price = market.yes_price
        if price > 0.50:
            return 0.50 + (patience_score * 0.15 + consensus_score * 0.15)
        else:
            return 0.50 - (patience_score * 0.15 + consensus_score * 0.15)

    def _apply_time_decay_pull(self, p_est: float, market_price: float,
                                market: MarketData) -> float:
        """Pull P(est) toward market price as expiry approaches.
        <6h: 80% market weight. <24h: 50%. <72h: 20%. Otherwise: 0%."""
        hours = market.time_to_expiry_hours
        if hours < 6:
            market_weight = 0.80
        elif hours < 24:
            market_weight = 0.50
        elif hours < 72:
            market_weight = 0.20
        else:
            return p_est
        return p_est * (1 - market_weight) + market_price * market_weight

    def _apply_edge_skepticism(self, edge: float) -> float:
        """Discount edges > 12% — large edges on Polymarket are usually noise.
        12-20%: linear discount to 60%. >20%: cap at 60% of raw edge."""
        abs_edge = abs(edge)
        if abs_edge <= 0.12:
            return edge
        if abs_edge <= 0.20:
            discount = 1.0 - 0.40 * ((abs_edge - 0.12) / 0.08)
        else:
            discount = 0.60
        sign = 1.0 if edge >= 0 else -1.0
        return sign * abs_edge * discount

    def estimate(
        self,
        market: MarketData,
        signal: SignalData,
        p_historical: float,
        direction: Direction = None,
    ) -> QuantEstimate:
        """Calculate estimated probability and edge with all corrections."""
        p_news = self._calc_news_proxy(market)
        p_sentiment = self._calc_sentiment_proxy(market)
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

        if direction == Direction.NO:
            market_price = market.no_price
            p_est = 1 - p_est
        else:
            market_price = market.yes_price

        # Correction 1: time-decay pull toward market price near expiry
        p_est = self._apply_time_decay_pull(p_est, market_price, market)

        # Raw edge
        edge = p_est - market_price

        # Correction 2: edge skepticism discount
        edge = self._apply_edge_skepticism(edge)

        # Correction 3: subtract category-specific fees from edge
        fee = get_category_fee(market)
        net_edge = edge - fee

        # Composite score (0-100)
        composite_score = self._calc_composite_score(
            edge=net_edge,
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
            edge=net_edge,
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
