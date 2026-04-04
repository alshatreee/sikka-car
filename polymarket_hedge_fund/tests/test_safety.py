"""
Tests for Safety Module — secrets, kill switches, and pre-launch checklist.
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from polymarket_hedge_fund.config import HedgeFundConfig
from polymarket_hedge_fund.models.market import Direction, MarketData, Position
from polymarket_hedge_fund.core.safety import (
    SecureConfig,
    EnhancedKillSwitch,
    KillSwitchConfig,
    PreLaunchChecklist,
)


# ── SecureConfig Tests ──

def test_secure_config_from_env():
    os.environ["POLYGON_PRIVATE_KEY"] = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    os.environ["POLYGON_ADDRESS"] = "0x1234567890abcdef1234567890abcdef12345678"
    config = SecureConfig.from_env()
    assert config.is_valid, f"Should be valid: {config.validate()}"
    print("✅ test_secure_config_from_env")


def test_secure_config_rejects_0x_key():
    config = SecureConfig(
        polygon_private_key="0xabc123abc123abc123abc123abc123abc123",
        polygon_address="0x1234567890abcdef1234567890abcdef12345678",
    )
    errors = config.validate()
    assert any("0x" in e for e in errors)
    print("✅ test_secure_config_rejects_0x_key")


def test_secure_config_rejects_placeholder():
    config = SecureConfig(
        polygon_private_key="your_private_key_here_replace_this",
        polygon_address="0x1234567890abcdef1234567890abcdef12345678",
    )
    errors = config.validate()
    assert any("تجريبية" in e for e in errors)
    print("✅ test_secure_config_rejects_placeholder")


def test_secure_config_masks_key():
    config = SecureConfig(
        polygon_private_key="a1b2c3d4e5f6g7h8i9j0",
        polygon_address="0x1234567890abcdef1234567890abcdef12345678",
    )
    masked = config.masked_key()
    assert "a1b2" in masked
    assert "i9j0" in masked
    assert "e5f6" not in masked  # Middle should be hidden
    print("✅ test_secure_config_masks_key")


# ── Kill Switch Tests ──

def make_market(**kwargs) -> MarketData:
    defaults = dict(
        market_id="test-1", question="Test?",
        yes_price=0.6, no_price=0.4,
        liquidity_usd=50000, volume_24h=10000,
        spread=0.02, expiry=datetime.utcnow() + timedelta(days=7),
    )
    defaults.update(kwargs)
    return MarketData(**defaults)


def test_kill_switch_blocks_wide_spread():
    ks = EnhancedKillSwitch(KillSwitchConfig(), HedgeFundConfig(capital_usd=1000))
    market = make_market(spread=0.08)  # 8% spread
    allowed, issues = ks.check_pre_trade(market, [])
    assert not allowed
    assert any("Spread" in i for i in issues)
    print("✅ test_kill_switch_blocks_wide_spread")


def test_kill_switch_blocks_disconnected():
    ks = EnhancedKillSwitch(
        KillSwitchConfig(require_mcp_connection=True),
        HedgeFundConfig(capital_usd=1000),
    )
    market = make_market()
    allowed, issues = ks.check_pre_trade(market, [], mcp_connected=False)
    assert not allowed
    assert any("MCP" in i for i in issues)
    print("✅ test_kill_switch_blocks_disconnected")


def test_kill_switch_blocks_per_market_exposure():
    config = HedgeFundConfig(capital_usd=1000)
    ks = EnhancedKillSwitch(
        KillSwitchConfig(max_exposure_per_market_pct=0.03),
        config,
    )
    market = make_market(market_id="same-market")
    existing = [Position(
        trade_id="t1", market_id="same-market", market_question="Q",
        direction=Direction.YES, entry_price=0.5, current_price=0.5,
        size_usd=35.0, edge_at_entry=0.1,  # Already $35 in this market
        stop_loss_price=0.4, take_profit_price=0.7,
    )]
    allowed, issues = ks.check_pre_trade(market, existing, mcp_connected=True)
    assert not allowed
    assert any("تعرض مفرط" in i for i in issues)
    print("✅ test_kill_switch_blocks_per_market_exposure")


def test_kill_switch_blocks_near_expiry():
    ks = EnhancedKillSwitch(KillSwitchConfig(), HedgeFundConfig(capital_usd=1000))
    market = make_market(expiry=datetime.utcnow() + timedelta(hours=6))
    allowed, issues = ks.check_pre_trade(market, [], mcp_connected=True)
    assert not allowed
    assert any("الانتهاء" in i for i in issues)
    print("✅ test_kill_switch_blocks_near_expiry")


def test_kill_switch_allows_valid_trade():
    ks = EnhancedKillSwitch(KillSwitchConfig(), HedgeFundConfig(capital_usd=1000))
    market = make_market()
    allowed, issues = ks.check_pre_trade(market, [], mcp_connected=True)
    assert allowed, f"Should allow valid trade: {issues}"
    print("✅ test_kill_switch_allows_valid_trade")


def test_kill_switch_api_errors():
    ks = EnhancedKillSwitch(
        KillSwitchConfig(max_api_errors_per_session=3),
        HedgeFundConfig(capital_usd=1000),
    )
    ks.record_api_error()
    ks.record_api_error()
    assert not ks.is_halted
    ks.record_api_error()
    assert ks.is_halted
    print("✅ test_kill_switch_api_errors")


# ── Pre-Launch Checklist Tests ──

def test_checklist_fails_without_config():
    checklist = PreLaunchChecklist(HedgeFundConfig(capital_usd=1000))
    items = checklist.run()
    assert not checklist.is_ready()  # Should fail without secrets
    print("✅ test_checklist_fails_without_config")


def test_checklist_format():
    checklist = PreLaunchChecklist(HedgeFundConfig(capital_usd=1000))
    checklist.run()
    report = checklist.format_report()
    assert "قائمة التحقق" in report
    assert "غير جاهز" in report  # Should show not ready
    print("✅ test_checklist_format")


if __name__ == "__main__":
    test_secure_config_from_env()
    test_secure_config_rejects_0x_key()
    test_secure_config_rejects_placeholder()
    test_secure_config_masks_key()
    test_kill_switch_blocks_wide_spread()
    test_kill_switch_blocks_disconnected()
    test_kill_switch_blocks_per_market_exposure()
    test_kill_switch_blocks_near_expiry()
    test_kill_switch_allows_valid_trade()
    test_kill_switch_api_errors()
    test_checklist_fails_without_config()
    test_checklist_format()
    print("\n🎉 All 12 safety tests passed!")
