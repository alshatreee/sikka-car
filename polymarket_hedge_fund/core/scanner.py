"""
Market Scanner — Layer ①
Scans markets and ranks them by opportunity quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from ..config import HedgeFundConfig
from ..models.market import MarketData, SignalData


class MarketAPI(Protocol):
    """Interface for fetching market data (MCP or mock)."""

    def get_active_markets(self, limit: int = 50) -> list[dict]:
        """Fetch active markets."""
        ...

    def get_market_detail(self, market_id: str) -> dict:
        """Fetch detailed market data."""
        ...

    def get_orderbook(self, market_id: str) -> dict:
        """Fetch order book."""
        ...


@dataclass
class ScoredMarket:
    """A market with its opportunity score."""
    market: MarketData
    opportunity_score: float  # Edge × Liquidity Score
    signal: Optional[SignalData] = None


class MarketScanner:
    """
    Scans and ranks markets by (Edge × Liquidity Score).
    Filters out markets that don't meet minimum requirements.
    """

    def __init__(self, config: HedgeFundConfig, api: Optional[MarketAPI] = None):
        self.config = config
        self.api = api

    def scan_and_rank(
        self,
        markets: list[MarketData],
        signals: Optional[dict[str, SignalData]] = None,
    ) -> list[ScoredMarket]:
        """
        Score and rank markets by opportunity quality.
        Filters out markets below minimum thresholds.
        """
        scored = []
        for market in markets:
            # Pre-filter: skip markets that fail basic requirements
            if not self._passes_basic_filter(market):
                continue

            # Calculate opportunity score
            score = self._calc_opportunity_score(market)
            signal = signals.get(market.market_id) if signals else None

            # Skip if signals conflict
            if signal and signal.conflicting_signals:
                continue

            scored.append(ScoredMarket(
                market=market,
                opportunity_score=score,
                signal=signal,
            ))

        # Sort by opportunity score descending
        scored.sort(key=lambda s: s.opportunity_score, reverse=True)
        return scored

    def get_top_markets(
        self,
        markets: list[MarketData],
        signals: Optional[dict[str, SignalData]] = None,
        top_n: int = 5,
    ) -> list[ScoredMarket]:
        """Get the top N markets by opportunity score."""
        ranked = self.scan_and_rank(markets, signals)
        return ranked[:top_n]

    def _passes_basic_filter(self, market: MarketData) -> bool:
        """Check if market meets minimum requirements."""
        entry = self.config.entry

        if market.liquidity_usd < entry.min_liquidity_usd:
            return False
        if market.spread > entry.max_spread_pct:
            return False
        if market.time_to_expiry_hours < entry.min_time_to_expiry_hours:
            return False

        # Skip markets with extreme prices (too close to 0 or 1)
        if market.yes_price < 0.05 or market.yes_price > 0.95:
            return False

        return True

    def _calc_opportunity_score(self, market: MarketData) -> float:
        """
        Opportunity = potential_edge × liquidity_score

        potential_edge: how far the price is from 0.5 (more movement potential)
        liquidity_score: normalized liquidity quality
        """
        # Price distance from extremes — most opportunity near 0.3-0.7
        price = market.yes_price
        price_opportunity = 1.0 - abs(price - 0.5) * 2  # 1.0 at 0.5, 0 at 0/1

        # Liquidity quality (0-1, saturates at $100k)
        liq_score = min(1.0, market.liquidity_usd / 100_000)

        # Volume factor
        vol_score = min(1.0, market.volume_24h / 50_000)

        # Spread penalty
        spread_penalty = max(0, 1.0 - market.spread / 0.05)

        return (
            price_opportunity * 0.35
            + liq_score * 0.30
            + vol_score * 0.20
            + spread_penalty * 0.15
        )

    def format_scan_results(self, scored: list[ScoredMarket]) -> str:
        """Format scan results for display."""
        if not scored:
            return "❌ لا توجد أسواق تستوفي الشروط."

        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "       🔍 نتائج المسح",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        for i, s in enumerate(scored, 1):
            m = s.market
            lines.append(
                f"\n  #{i} | Score: {s.opportunity_score:.2f}\n"
                f"  السوق   : {m.question[:50]}\n"
                f"  السعر   : YES {m.yes_price:.3f} | NO {m.no_price:.3f}\n"
                f"  السيولة : ${m.liquidity_usd:,.0f}\n"
                f"  Spread  : {m.spread:.2%}\n"
                f"  المتبقي : {m.time_to_expiry_hours:.0f}h"
            )
        return "\n".join(lines)
