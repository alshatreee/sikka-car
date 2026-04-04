"""
Market API — Wraps Polymarket MCP Server market discovery & analysis tools.
Implements the MarketAPI and provides data conversion to our models.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from ..models.market import MarketData, SignalData
from .mcp_client import MCPClient

logger = logging.getLogger(__name__)


class PolymarketMarketAPI:
    """
    Market data API backed by Polymarket MCP Server.

    Tools used:
    - search_markets(query, limit, filters)
    - get_trending_markets(timeframe, limit)
    - filter_markets_by_category(category, active_only, limit)
    - get_closing_soon_markets(hours, limit)
    - get_market_details(market_id)
    - get_current_price(token_id, side)
    - get_orderbook(token_id, depth)
    - get_spread(token_id)
    - get_liquidity(market_id)
    - get_market_volume(market_id, timeframes)
    - get_price_history(token_id, start_date, end_date, resolution)
    - analyze_market_opportunity(market_id)
    """

    def __init__(self, mcp: MCPClient):
        self.mcp = mcp

    # ── Market Discovery ──

    async def search_markets(
        self, query: str, limit: int = 20
    ) -> list[MarketData]:
        """Search markets by keyword."""
        result = await self.mcp.call_tool("search_markets", {
            "query": query,
            "limit": limit,
        })
        return self._parse_markets(result)

    async def get_trending_markets(
        self, timeframe: str = "24h", limit: int = 10
    ) -> list[MarketData]:
        """Get trending markets by volume."""
        result = await self.mcp.call_tool("get_trending_markets", {
            "timeframe": timeframe,
            "limit": limit,
        })
        return self._parse_markets(result)

    async def get_markets_by_category(
        self, category: str, limit: int = 20
    ) -> list[MarketData]:
        """Filter markets by category (Politics, Sports, Crypto, etc)."""
        result = await self.mcp.call_tool("filter_markets_by_category", {
            "category": category,
            "active_only": True,
            "limit": limit,
        })
        return self._parse_markets(result)

    async def get_closing_soon(
        self, hours: int = 48, limit: int = 20
    ) -> list[MarketData]:
        """Get markets closing within N hours."""
        result = await self.mcp.call_tool("get_closing_soon_markets", {
            "hours": hours,
            "limit": limit,
        })
        return self._parse_markets(result)

    # ── Market Analysis ──

    async def get_market_detail(self, market_id: str) -> Optional[MarketData]:
        """Get detailed data for a single market."""
        result = await self.mcp.call_tool("get_market_details", {
            "market_id": market_id,
        })
        markets = self._parse_markets(result)
        return markets[0] if markets else None

    async def get_orderbook(self, token_id: str, depth: int = 20) -> dict:
        """Get order book for a token."""
        return await self.mcp.call_tool("get_orderbook", {
            "token_id": token_id,
            "depth": depth,
        })

    async def get_spread(self, token_id: str) -> dict:
        """Get current spread data."""
        return await self.mcp.call_tool("get_spread", {
            "token_id": token_id,
        })

    async def get_liquidity(self, market_id: str) -> dict:
        """Get liquidity data for a market."""
        return await self.mcp.call_tool("get_liquidity", {
            "market_id": market_id,
        })

    async def get_price_history(
        self,
        token_id: str,
        hours_back: int = 48,
        resolution: str = "1h",
    ) -> list[dict]:
        """Get price history for sentiment analysis."""
        end = datetime.utcnow()
        start = end - timedelta(hours=hours_back)
        result = await self.mcp.call_tool("get_price_history", {
            "token_id": token_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "resolution": resolution,
        })
        return self._extract_content(result)

    async def analyze_opportunity(self, market_id: str) -> dict:
        """Get AI-powered opportunity analysis from MCP server."""
        return await self.mcp.call_tool("analyze_market_opportunity", {
            "market_id": market_id,
        })

    async def get_volume(
        self, market_id: str, timeframes: Optional[list[str]] = None
    ) -> dict:
        """Get volume data across timeframes."""
        return await self.mcp.call_tool("get_market_volume", {
            "market_id": market_id,
            "timeframes": timeframes or ["24h", "7d", "30d"],
        })

    # ── Signal Building ──

    async def build_signal(self, market: MarketData) -> SignalData:
        """
        Build a SignalData object from market analysis.
        Combines price history, orderbook, and volume data.
        """
        signal = SignalData(market_id=market.market_id)

        # Polymarket uses market_id for some tools and token_id for others.
        # For orderbook/price tools, token_id = market_id (the condition token).
        # The MCP server handles the mapping internally.
        token_id = market.market_id

        try:
            # Price history → sentiment score
            history = await self.get_price_history(token_id, hours_back=48)
            signal.sentiment_score = self._calc_sentiment_from_history(history)

            # Orderbook → market data score
            orderbook = await self.get_orderbook(token_id)
            signal.market_data_score = self._calc_orderbook_score(orderbook)

            # Volume → part of market data
            volume = await self.get_volume(market.market_id)
            vol_score = self._calc_volume_score(volume)
            signal.market_data_score = (signal.market_data_score + vol_score) / 2

            # Time factor
            signal.time_factor_score = self._calc_time_factor(market)

            # Detect conflicting signals
            scores = [signal.sentiment_score, signal.market_data_score]
            if max(scores) - min(scores) > 0.5:
                signal.conflicting_signals = True

        except Exception as e:
            logger.warning(f"Error building signal for {market.market_id}: {e}")

        return signal

    # ── Data Conversion ──

    def _parse_markets(self, result: Any) -> list[MarketData]:
        """Convert MCP tool result to list of MarketData."""
        content = self._extract_content(result)
        if not isinstance(content, list):
            content = [content] if content else []

        markets = []
        for item in content:
            if not isinstance(item, dict):
                continue
            try:
                markets.append(MarketData(
                    market_id=str(item.get("id", item.get("condition_id", ""))),
                    question=item.get("question", item.get("title", "")),
                    yes_price=float(item.get("yes_price", item.get("outcomePrices", [0.5, 0.5])[0])),
                    no_price=float(item.get("no_price", item.get("outcomePrices", [0.5, 0.5])[1])),
                    liquidity_usd=float(item.get("liquidity", item.get("liquidityNum", 0))),
                    volume_24h=float(item.get("volume_24h", item.get("volumeNum", 0))),
                    spread=float(item.get("spread", 0.02)),
                    expiry=self._parse_expiry(item.get("end_date_iso", item.get("endDate", ""))),
                    category=item.get("category", item.get("groupItemTitle", "")),
                ))
            except (ValueError, KeyError, IndexError) as e:
                logger.debug(f"Skipping market due to parse error: {e}")
        return markets

    def _extract_content(self, result: Any) -> Any:
        """Extract actual content from MCP tool result wrapper."""
        if isinstance(result, dict):
            # MCP results often wrapped in {"content": [{"type": "text", "text": "..."}]}
            if "content" in result:
                contents = result["content"]
                if isinstance(contents, list) and contents:
                    text = contents[0].get("text", "")
                    try:
                        import json
                        return json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        return text
            return result
        return result

    def _parse_expiry(self, date_str: str) -> datetime:
        """Parse expiry date from various formats. Returns naive UTC datetime."""
        if not date_str:
            return datetime.utcnow() + timedelta(days=30)
        try:
            # Normalize timezone to parse, then strip tz for naive UTC
            normalized = date_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            # Convert to naive UTC for consistency with the rest of the codebase
            if dt.tzinfo is not None:
                from datetime import timezone
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            return datetime.utcnow() + timedelta(days=30)

    def _calc_sentiment_from_history(self, history: Any) -> float:
        """Calculate sentiment (0-1) from price history."""
        if not history or not isinstance(history, list):
            return 0.5
        try:
            prices = [float(h.get("close", h.get("price", 0.5))) for h in history if isinstance(h, dict)]
            if len(prices) < 2:
                return 0.5
            recent = prices[-min(6, len(prices)):]
            older = prices[:max(1, len(prices) // 2)]
            trend = (sum(recent) / len(recent)) - (sum(older) / len(older))
            return max(0.0, min(1.0, 0.5 + trend * 5))
        except (ValueError, ZeroDivisionError):
            return 0.5

    def _calc_orderbook_score(self, orderbook: Any) -> float:
        """Score orderbook health (0-1)."""
        if not isinstance(orderbook, dict):
            return 0.5
        try:
            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])
            if not bids or not asks:
                return 0.3
            depth = len(bids) + len(asks)
            return min(1.0, depth / 40)
        except (TypeError, ValueError):
            return 0.5

    def _calc_volume_score(self, volume: Any) -> float:
        """Score trading volume (0-1)."""
        if not isinstance(volume, dict):
            return 0.5
        try:
            vol_24h = float(volume.get("24h", volume.get("volume_24h", 0)))
            return min(1.0, vol_24h / 50_000)
        except (ValueError, TypeError):
            return 0.5

    def _calc_time_factor(self, market: MarketData) -> float:
        """Time factor score matching our quant model."""
        hours = market.time_to_expiry_hours
        days = hours / 24
        if days < 1:
            return 0.2
        elif days < 2:
            return 0.5
        elif days <= 14:
            return 0.8 + 0.2 * min(1.0, (days - 2) / 12)
        elif days <= 30:
            return 0.7
        else:
            return 0.5
