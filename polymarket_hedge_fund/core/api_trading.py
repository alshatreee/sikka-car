"""
Trading & Portfolio API — Wraps Polymarket MCP Server trading + portfolio tools.
Implements OrderAPI protocol and adds portfolio management.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .mcp_client import MCPClient

logger = logging.getLogger(__name__)


class PolymarketTradingAPI:
    """
    Trading API backed by Polymarket MCP Server.

    Order tools:
    - create_limit_order(market_id, side, price, size, order_type, expiration)
    - create_market_order(market_id, side, size)  ← BLOCKED by our system
    - suggest_order_price(market_id, side, size, strategy)
    - get_order_status(order_id)
    - get_open_orders(market_id?)
    - cancel_order(order_id)
    - cancel_market_orders(market_id)
    - cancel_all_orders()
    """

    def __init__(self, mcp: MCPClient):
        self.mcp = mcp

    # ── Order Placement (LIMIT ONLY) ──

    async def place_limit_order(
        self,
        market_id: str,
        direction: str,
        size_usd: float,
        limit_price: float,
        order_type: str = "GTC",
    ) -> dict:
        """
        Place a LIMIT order via MCP.
        direction: "YES" or "NO" → mapped to side: "BUY" on appropriate token
        """
        # Map YES/NO to the correct side
        side = "BUY" if direction in ("YES", "BUY") else "SELL"

        logger.info(
            f"📤 Placing LIMIT order: {direction} ${size_usd:.2f} @ {limit_price:.4f} "
            f"on market {market_id}"
        )

        result = await self.mcp.call_tool("create_limit_order", {
            "market_id": market_id,
            "side": side,
            "price": limit_price,
            "size": size_usd,
            "order_type": order_type,
        })

        content = self._extract_content(result)
        logger.info(f"✅ Order placed: {content}")
        return content

    async def suggest_price(
        self,
        market_id: str,
        side: str = "BUY",
        size: float = 10.0,
        strategy: str = "mid",
    ) -> dict:
        """
        Get AI-suggested price for an order.
        strategy: 'aggressive', 'passive', or 'mid'
        """
        result = await self.mcp.call_tool("suggest_order_price", {
            "market_id": market_id,
            "side": side,
            "size": size,
            "strategy": strategy,
        })
        return self._extract_content(result)

    # ── Order Management ──

    async def get_order_status(self, order_id: str) -> dict:
        """Get status of a specific order."""
        result = await self.mcp.call_tool("get_order_status", {
            "order_id": order_id,
        })
        return self._extract_content(result)

    async def get_open_orders(self, market_id: Optional[str] = None) -> list:
        """Get all open orders, optionally filtered by market."""
        args = {}
        if market_id:
            args["market_id"] = market_id
        result = await self.mcp.call_tool("get_open_orders", args)
        content = self._extract_content(result)
        return content if isinstance(content, list) else [content]

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order."""
        try:
            await self.mcp.call_tool("cancel_order", {"order_id": order_id})
            logger.info(f"🗑️ Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def cancel_market_orders(self, market_id: str) -> bool:
        """Cancel all orders in a specific market."""
        try:
            await self.mcp.call_tool("cancel_market_orders", {
                "market_id": market_id,
            })
            logger.info(f"🗑️ All orders cancelled for market {market_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel market orders: {e}")
            return False

    async def cancel_all_orders(self) -> bool:
        """Cancel ALL open orders across all markets."""
        try:
            await self.mcp.call_tool("cancel_all_orders", {})
            logger.info("🗑️ All orders cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return False

    # ── BLOCKED: Market Orders ──

    async def place_market_order(self, *args, **kwargs) -> None:
        """BLOCKED — Market orders are forbidden by system rules."""
        raise PermissionError(
            "⛔ MARKET orders are FORBIDDEN. Use LIMIT orders only. "
            "This is a core system rule that cannot be overridden."
        )

    # ── Helpers ──

    def _extract_content(self, result: Any) -> Any:
        """Extract content from MCP tool result."""
        if isinstance(result, dict) and "content" in result:
            contents = result["content"]
            if isinstance(contents, list) and contents:
                text = contents[0].get("text", "")
                try:
                    import json
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return text
        return result


class PolymarketPortfolioAPI:
    """
    Portfolio API backed by Polymarket MCP Server.

    Tools:
    - get_all_positions(include_closed, min_value, sort_by)
    - get_position_details(market_id)
    - get_portfolio_value(include_breakdown)
    - get_pnl_summary(timeframe)
    - get_trade_history(market_id, start_date, end_date, limit, side)
    - analyze_portfolio_risk()
    """

    def __init__(self, mcp: MCPClient):
        self.mcp = mcp

    async def get_positions(
        self,
        include_closed: bool = False,
        min_value: float = 1.0,
        sort_by: str = "value",
    ) -> list[dict]:
        """Get all portfolio positions."""
        result = await self.mcp.call_tool("get_all_positions", {
            "include_closed": include_closed,
            "min_value": min_value,
            "sort_by": sort_by,
        })
        content = self._extract_content(result)
        return content if isinstance(content, list) else [content]

    async def get_position_detail(self, market_id: str) -> dict:
        """Get detailed position info for a specific market."""
        result = await self.mcp.call_tool("get_position_details", {
            "market_id": market_id,
        })
        return self._extract_content(result)

    async def get_portfolio_value(self, include_breakdown: bool = True) -> dict:
        """Get total portfolio valuation."""
        result = await self.mcp.call_tool("get_portfolio_value", {
            "include_breakdown": include_breakdown,
        })
        return self._extract_content(result)

    async def get_pnl(self, timeframe: str = "all") -> dict:
        """Get P&L summary. timeframe: '24h', '7d', '30d', 'all'."""
        result = await self.mcp.call_tool("get_pnl_summary", {
            "timeframe": timeframe,
        })
        return self._extract_content(result)

    async def get_trade_history(
        self,
        market_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get trade history."""
        args: dict[str, Any] = {"limit": limit, "side": "BOTH"}
        if market_id:
            args["market_id"] = market_id
        result = await self.mcp.call_tool("get_trade_history", args)
        content = self._extract_content(result)
        return content if isinstance(content, list) else [content]

    async def analyze_risk(self) -> dict:
        """Get portfolio risk analysis."""
        result = await self.mcp.call_tool("analyze_portfolio_risk", {})
        return self._extract_content(result)

    async def get_wallet_summary(self) -> str:
        """
        Build a complete wallet summary string.
        Combines portfolio value + positions + P&L.
        """
        try:
            value = await self.get_portfolio_value()
            positions = await self.get_positions()
            pnl = await self.get_pnl(timeframe="24h")

            lines = ["── 💰 ملخص المحفظة ──"]

            if isinstance(value, dict):
                lines.append(f"  القيمة الإجمالية: ${value.get('total_value', 'N/A')}")
                lines.append(f"  USDC المتاح    : ${value.get('usdc_balance', 'N/A')}")

            if isinstance(pnl, dict):
                lines.append(f"  P&L اليوم      : ${pnl.get('pnl_24h', 'N/A')}")

            if isinstance(positions, list):
                lines.append(f"  المراكز المفتوحة: {len(positions)}")
                for p in positions[:5]:
                    if isinstance(p, dict):
                        q = p.get("question", p.get("title", "?"))[:35]
                        val = p.get("value", p.get("currentValue", "?"))
                        lines.append(f"    • {q} — ${val}")

            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ تعذر جلب بيانات المحفظة: {e}"

    def _extract_content(self, result: Any) -> Any:
        """Extract content from MCP tool result."""
        if isinstance(result, dict) and "content" in result:
            contents = result["content"]
            if isinstance(contents, list) and contents:
                text = contents[0].get("text", "")
                try:
                    import json
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return text
        return result
