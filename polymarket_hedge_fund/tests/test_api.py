"""
Tests for API layer — uses mock MCP client.
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from polymarket_hedge_fund.core.mcp_client import MCPConfig
from polymarket_hedge_fund.core.api_market import PolymarketMarketAPI
from polymarket_hedge_fund.core.api_trading import (
    PolymarketTradingAPI,
    PolymarketPortfolioAPI,
)


def make_mock_mcp():
    """Create a mock MCP client."""
    mcp = MagicMock()
    mcp.call_tool = AsyncMock()
    mcp.is_connected = True
    return mcp


def make_market_result(markets):
    """Wrap market data in MCP result format."""
    return {"content": [{"type": "text", "text": json.dumps(markets)}]}


# ── MCP Config Validation ──

def test_config_validates_keys():
    config = MCPConfig()
    errors = config.validate()
    assert len(errors) > 0, "Empty config should have errors"
    print("✅ test_config_validates_keys")


def test_config_rejects_0x_private_key():
    config = MCPConfig(
        python_path="/usr/bin/python",
        server_cwd="/tmp",
        polygon_private_key="0xabc123",
        polygon_address="0xdef456",
    )
    errors = config.validate()
    assert any("0x" in e for e in errors)
    print("✅ test_config_rejects_0x_private_key")


def test_config_rejects_missing_0x_address():
    config = MCPConfig(
        python_path="/usr/bin/python",
        server_cwd="/tmp",
        polygon_private_key="abc123",
        polygon_address="def456",
    )
    errors = config.validate()
    assert any("0x" in e for e in errors)
    print("✅ test_config_rejects_missing_0x_address")


def test_valid_config():
    config = MCPConfig(
        python_path="/usr/bin/python",
        server_cwd="/tmp",
        polygon_private_key="abc123def",
        polygon_address="0xabc123def",
    )
    errors = config.validate()
    assert len(errors) == 0, f"Valid config should have no errors: {errors}"
    print("✅ test_valid_config")


# ── Market API ──

def test_parse_markets():
    mcp = make_mock_mcp()
    api = PolymarketMarketAPI(mcp)

    mcp.call_tool.return_value = make_market_result([
        {
            "id": "market-1",
            "question": "Will BTC reach $100k?",
            "outcomePrices": [0.65, 0.35],
            "liquidityNum": 50000,
            "volumeNum": 12000,
            "spread": 0.02,
            "endDate": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        },
        {
            "id": "market-2",
            "question": "US Election 2024?",
            "outcomePrices": [0.52, 0.48],
            "liquidityNum": 200000,
            "volumeNum": 80000,
            "spread": 0.01,
            "endDate": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        },
    ])

    markets = asyncio.get_event_loop().run_until_complete(
        api.search_markets("test")
    )
    assert len(markets) == 2
    assert markets[0].market_id == "market-1"
    assert markets[0].yes_price == 0.65
    assert markets[1].liquidity_usd == 200000
    print("✅ test_parse_markets")


def test_build_signal():
    mcp = make_mock_mcp()
    api = PolymarketMarketAPI(mcp)

    from polymarket_hedge_fund.models.market import MarketData

    market = MarketData(
        market_id="test-1",
        question="Test?",
        yes_price=0.6,
        no_price=0.4,
        liquidity_usd=50000,
        volume_24h=10000,
        spread=0.02,
        expiry=datetime.utcnow() + timedelta(days=7),
    )

    # Mock price history
    history = [{"close": 0.55}, {"close": 0.57}, {"close": 0.60}, {"close": 0.62}]
    orderbook = {"bids": [{"p": 0.59}] * 10, "asks": [{"p": 0.61}] * 10}
    volume = {"24h": 25000}

    mcp.call_tool.side_effect = [
        make_market_result(history),
        make_market_result(orderbook),
        make_market_result(volume),
    ]

    signal = asyncio.get_event_loop().run_until_complete(
        api.build_signal(market)
    )

    assert signal.market_id == "test-1"
    assert 0.0 <= signal.sentiment_score <= 1.0
    assert 0.0 <= signal.market_data_score <= 1.0
    assert 0.0 <= signal.time_factor_score <= 1.0
    print("✅ test_build_signal")


# ── Trading API ──

def test_place_limit_order():
    mcp = make_mock_mcp()
    api = PolymarketTradingAPI(mcp)

    mcp.call_tool.return_value = make_market_result({
        "order_id": "ord-123",
        "status": "pending",
    })

    result = asyncio.get_event_loop().run_until_complete(
        api.place_limit_order("market-1", "YES", 10.0, 0.65)
    )
    assert mcp.call_tool.called
    call_args = mcp.call_tool.call_args
    assert call_args[0][0] == "create_limit_order"
    assert call_args[0][1]["side"] == "BUY"
    assert call_args[0][1]["price"] == 0.65
    print("✅ test_place_limit_order")


def test_market_order_blocked():
    mcp = make_mock_mcp()
    api = PolymarketTradingAPI(mcp)

    try:
        asyncio.get_event_loop().run_until_complete(
            api.place_market_order("market-1", "BUY", 10.0)
        )
        assert False, "Should have raised PermissionError"
    except PermissionError as e:
        assert "FORBIDDEN" in str(e)
    print("✅ test_market_order_blocked")


# ── Portfolio API ──

def test_get_portfolio_value():
    mcp = make_mock_mcp()
    api = PolymarketPortfolioAPI(mcp)

    mcp.call_tool.return_value = make_market_result({
        "total_value": 1250.50,
        "usdc_balance": 800.00,
    })

    result = asyncio.get_event_loop().run_until_complete(
        api.get_portfolio_value()
    )
    assert result["total_value"] == 1250.50
    print("✅ test_get_portfolio_value")


def test_wallet_summary():
    mcp = make_mock_mcp()
    api = PolymarketPortfolioAPI(mcp)

    mcp.call_tool.side_effect = [
        make_market_result({"total_value": 1000, "usdc_balance": 500}),
        make_market_result([
            {"question": "BTC $100k?", "currentValue": 200},
            {"question": "ETH $5k?", "currentValue": 150},
        ]),
        make_market_result({"pnl_24h": 25.50}),
    ]

    summary = asyncio.get_event_loop().run_until_complete(
        api.get_wallet_summary()
    )
    assert "المحفظة" in summary
    assert "1000" in summary or "1,000" in summary
    print("✅ test_wallet_summary")


if __name__ == "__main__":
    test_config_validates_keys()
    test_config_rejects_0x_private_key()
    test_config_rejects_missing_0x_address()
    test_valid_config()
    test_parse_markets()
    test_build_signal()
    test_place_limit_order()
    test_market_order_blocked()
    test_get_portfolio_value()
    test_wallet_summary()
    print("\n🎉 All 10 API tests passed!")
