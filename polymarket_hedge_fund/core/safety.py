"""
Safety Module — Hardened security, geoblock, kill switches, and pre-launch checklist.
This module must pass ALL checks before any real trade is executed.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import HedgeFundConfig
from ..models.market import MarketData, Position

logger = logging.getLogger(__name__)


# ══════════════════════════════════════
# 1. Secret Management — env-only, never hardcoded
# ══════════════════════════════════════

@dataclass
class SecureConfig:
    """
    Loads secrets from environment variables ONLY.
    Never accepts hardcoded keys. Validates format.
    """
    polygon_private_key: str = ""
    polygon_address: str = ""

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "SecureConfig":
        """
        Load secrets from environment variables.
        Optionally load a .env file first.
        """
        if env_file:
            _load_dotenv(env_file)

        key = os.environ.get("POLYGON_PRIVATE_KEY", "")
        address = os.environ.get("POLYGON_ADDRESS", "")

        config = cls(polygon_private_key=key, polygon_address=address)
        return config

    def validate(self) -> list[str]:
        """Validate secret format. Returns list of errors."""
        errors = []

        if not self.polygon_private_key:
            errors.append("POLYGON_PRIVATE_KEY غير موجود في متغيرات البيئة")
        elif self.polygon_private_key.startswith("0x"):
            errors.append("POLYGON_PRIVATE_KEY يجب أن يكون بدون 0x")
        elif len(self.polygon_private_key) < 32:
            errors.append("POLYGON_PRIVATE_KEY قصير جداً — تحقق من المفتاح")

        if not self.polygon_address:
            errors.append("POLYGON_ADDRESS غير موجود في متغيرات البيئة")
        elif not self.polygon_address.startswith("0x"):
            errors.append("POLYGON_ADDRESS يجب أن يبدأ بـ 0x")
        elif len(self.polygon_address) != 42:
            errors.append(f"POLYGON_ADDRESS طوله {len(self.polygon_address)} — يجب أن يكون 42 حرف")

        # Check if key looks like it was left as placeholder
        placeholders = ["your_private_key", "YOUR_PRIVATE_KEY", "abc123", "xxx", "test"]
        for ph in placeholders:
            if ph in self.polygon_private_key.lower():
                errors.append("POLYGON_PRIVATE_KEY يبدو كقيمة تجريبية — استخدم المفتاح الحقيقي")
                break

        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    def masked_key(self) -> str:
        """Return masked key for logging (never log full key)."""
        if len(self.polygon_private_key) > 8:
            return self.polygon_private_key[:4] + "..." + self.polygon_private_key[-4:]
        return "***"

    def masked_address(self) -> str:
        """Return masked address for logging."""
        if len(self.polygon_address) > 10:
            return self.polygon_address[:6] + "..." + self.polygon_address[-4:]
        return "***"


def _load_dotenv(path: str) -> None:
    """Simple .env loader without external dependencies."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)


# ══════════════════════════════════════
# 2. Geoblock Check
# ══════════════════════════════════════

async def check_geoblock() -> tuple[bool, str]:
    """
    Check if the current IP is geoblocked by Polymarket.
    Uses Polymarket's own endpoint.
    Returns (allowed, message).
    """
    import urllib.request
    import json

    try:
        # Polymarket geo check endpoint
        req = urllib.request.Request(
            "https://gamma-api.polymarket.com/geo",
            headers={"User-Agent": "polymarket-hedge-fund/3.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        # If the response indicates blocking
        if data.get("blocked", False) or data.get("restricted", False):
            country = data.get("country", "unknown")
            return False, f"⛔ GEOBLOCKED: Polymarket غير متاح في {country}"

        return True, "✅ الموقع الجغرافي مسموح"

    except urllib.error.HTTPError as e:
        if e.code == 403:
            return False, "⛔ GEOBLOCKED: طلب مرفوض (403)"
        return False, f"⚠️  خطأ في فحص الموقع: HTTP {e.code}"
    except Exception as e:
        # If we can't check, warn but don't block
        return True, f"⚠️  تعذر فحص الموقع الجغرافي: {e} — تابع بحذر"


def check_geoblock_sync() -> tuple[bool, str]:
    """Synchronous wrapper for geoblock check."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't nest async — do a simple HTTP check
            return _sync_geocheck()
        return loop.run_until_complete(check_geoblock())
    except RuntimeError:
        return _sync_geocheck()


def _sync_geocheck() -> tuple[bool, str]:
    """Fallback synchronous geoblock check."""
    import urllib.request
    import json
    try:
        req = urllib.request.Request(
            "https://gamma-api.polymarket.com/geo",
            headers={"User-Agent": "polymarket-hedge-fund/3.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("blocked", False) or data.get("restricted", False):
            return False, f"⛔ GEOBLOCKED: {data.get('country', 'unknown')}"
        return True, "✅ الموقع الجغرافي مسموح"
    except Exception as e:
        return True, f"⚠️  تعذر الفحص: {e}"


# ══════════════════════════════════════
# 3. Enhanced Kill Switches
# ══════════════════════════════════════

@dataclass
class KillSwitchConfig:
    """Extended kill switch configuration."""
    # Existing limits (from RiskLimits)
    max_daily_loss_pct: float = 0.015
    max_consecutive_losses: int = 2
    # New: per-market exposure limit
    max_exposure_per_market_pct: float = 0.03  # 3% of capital per single market
    # New: spread guard — block if spread is too wide
    max_spread_for_execution: float = 0.05  # 5% — wider than entry requirement
    # New: connection guard — block if MCP disconnected
    require_mcp_connection: bool = True
    # New: price staleness guard
    max_price_staleness_seconds: int = 300  # 5 minutes
    # New: minimum MATIC balance for gas
    min_matic_balance: float = 1.0  # $1 worth of MATIC minimum
    # New: auto-halt on API errors
    max_api_errors_per_session: int = 5


class EnhancedKillSwitch:
    """
    Enhanced kill switches beyond basic risk limits.
    Runs BEFORE the risk engine — if any switch triggers, everything stops.
    """

    def __init__(self, config: KillSwitchConfig, fund_config: HedgeFundConfig):
        self.config = config
        self.fund_config = fund_config
        self._api_error_count: int = 0
        self._halted: bool = False
        self._halt_reasons: list[str] = []

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def halt_reasons(self) -> list[str]:
        return self._halt_reasons

    def check_pre_trade(
        self,
        market: MarketData,
        positions: list[Position],
        mcp_connected: bool = True,
    ) -> tuple[bool, list[str]]:
        """
        Run all kill switch checks before a trade.
        Returns (allowed, list_of_issues).
        """
        issues = []

        # 1. Connection guard
        if self.config.require_mcp_connection and not mcp_connected:
            issues.append("⛔ MCP غير متصل — التداول محظور")

        # 2. Spread guard
        if market.spread > self.config.max_spread_for_execution:
            issues.append(
                f"⛔ Spread واسع جداً: {market.spread:.2%} > "
                f"{self.config.max_spread_for_execution:.2%}"
            )

        # 3. Per-market exposure
        market_exposure = sum(
            p.size_usd for p in positions if p.market_id == market.market_id
        )
        max_market_exposure = self.fund_config.capital_usd * self.config.max_exposure_per_market_pct
        if market_exposure >= max_market_exposure:
            issues.append(
                f"⛔ تعرض مفرط في هذا السوق: ${market_exposure:.2f} >= "
                f"${max_market_exposure:.2f} ({self.config.max_exposure_per_market_pct:.0%} من رأس المال)"
            )

        # 4. Time to expiry (stricter than entry requirements)
        if market.time_to_expiry_hours < 12:
            issues.append(
                f"⛔ قريب جداً من الانتهاء: {market.time_to_expiry_hours:.0f}h"
            )

        # 5. API error count
        if self._api_error_count >= self.config.max_api_errors_per_session:
            issues.append(
                f"⛔ أخطاء API كثيرة: {self._api_error_count} >= "
                f"{self.config.max_api_errors_per_session}"
            )

        if issues:
            self._halted = True
            self._halt_reasons = issues

        return len(issues) == 0, issues

    def record_api_error(self) -> None:
        """Record an API error."""
        self._api_error_count += 1
        if self._api_error_count >= self.config.max_api_errors_per_session:
            self._halted = True
            self._halt_reasons.append(
                f"⛔ تجاوز عدد أخطاء API: {self._api_error_count}"
            )

    def reset(self) -> None:
        """Reset after manual review."""
        self._halted = False
        self._halt_reasons = []
        self._api_error_count = 0


# ══════════════════════════════════════
# 4. Pre-Launch Safety Checklist
# ══════════════════════════════════════

@dataclass
class ChecklistItem:
    name: str
    passed: bool
    message: str
    critical: bool = True  # If critical and failed, blocks launch


class PreLaunchChecklist:
    """
    Programmatic pre-launch checklist.
    ALL critical items must pass before first real trade.
    """

    def __init__(self, fund_config: HedgeFundConfig):
        self.fund_config = fund_config
        self.items: list[ChecklistItem] = []

    def run(
        self,
        secure_config: Optional[SecureConfig] = None,
        mcp_connected: bool = False,
        backtest_result: Optional[object] = None,
        trading_days_completed: int = 0,
    ) -> list[ChecklistItem]:
        """Run all checklist items and return results."""
        self.items = []

        # 1. Secret validation
        if secure_config:
            errors = secure_config.validate()
            self.items.append(ChecklistItem(
                name="1. التحقق من المفاتيح",
                passed=len(errors) == 0,
                message="✅ المفاتيح صالحة" if not errors else f"❌ {'; '.join(errors)}",
                critical=True,
            ))
        else:
            self.items.append(ChecklistItem(
                name="1. التحقق من المفاتيح",
                passed=False,
                message="❌ لم يتم تحميل SecureConfig",
                critical=True,
            ))

        # 2. Geoblock check
        try:
            allowed, geo_msg = check_geoblock_sync()
            self.items.append(ChecklistItem(
                name="2. فحص الموقع الجغرافي",
                passed=allowed,
                message=geo_msg,
                critical=True,
            ))
        except Exception as e:
            self.items.append(ChecklistItem(
                name="2. فحص الموقع الجغرافي",
                passed=False,
                message=f"❌ خطأ: {e}",
                critical=True,
            ))

        # 3. MCP connection
        self.items.append(ChecklistItem(
            name="3. اتصال MCP Server",
            passed=mcp_connected,
            message="✅ متصل" if mcp_connected else "❌ غير متصل",
            critical=True,
        ))

        # 4. Capital configured
        has_capital = self.fund_config.capital_usd >= 100
        self.items.append(ChecklistItem(
            name="4. رأس المال",
            passed=has_capital,
            message=f"✅ ${self.fund_config.capital_usd:,.0f}" if has_capital
                    else f"❌ ${self.fund_config.capital_usd} — الحد الأدنى $100",
            critical=True,
        ))

        # 5. Risk limits configured
        risk_ok = (
            self.fund_config.risk.max_position_pct <= 0.02
            and self.fund_config.risk.max_total_exposure_pct <= 0.10
            and self.fund_config.risk.max_daily_loss_pct <= 0.03
        )
        self.items.append(ChecklistItem(
            name="5. حدود المخاطرة",
            passed=risk_ok,
            message="✅ حدود معقولة" if risk_ok else "⚠️  حدود مرتفعة — تحقق",
            critical=False,
        ))

        # 6. Backtesting completed
        bt_done = backtest_result is not None
        self.items.append(ChecklistItem(
            name="6. اختبار تاريخي",
            passed=bt_done,
            message="✅ تم" if bt_done else "❌ لم يتم — شغّل backtest أولاً",
            critical=True,
        ))

        # 7. Minimum practice days (60-90 recommended)
        min_days = 60
        days_ok = trading_days_completed >= min_days
        self.items.append(ChecklistItem(
            name="7. فترة التدريب",
            passed=days_ok,
            message=f"✅ {trading_days_completed} يوم" if days_ok
                    else f"⚠️  {trading_days_completed}/{min_days} يوم — استمر بالتدريب",
            critical=False,
        ))

        # 8. .env file not in git
        env_in_git = Path(".env").exists() and not self._is_gitignored(".env")
        self.items.append(ChecklistItem(
            name="8. أمان .env",
            passed=not env_in_git,
            message="✅ .env محمي" if not env_in_git
                    else "❌ .env غير مضاف لـ .gitignore!",
            critical=True,
        ))

        # 9. USDC.e (not generic USDC)
        self.items.append(ChecklistItem(
            name="9. نوع العملة",
            passed=True,  # Can't check programmatically, remind user
            message="⚠️  تأكد من استخدام USDC.e على Polygon (وليس أي USDC عادي)",
            critical=False,
        ))

        # 10. MATIC gas
        self.items.append(ChecklistItem(
            name="10. رصيد MATIC",
            passed=True,  # Can't check without API, remind user
            message="⚠️  تأكد من وجود 2-5$ MATIC في المحفظة للغاز",
            critical=False,
        ))

        return self.items

    def is_ready(self) -> bool:
        """Check if all CRITICAL items pass."""
        return all(item.passed for item in self.items if item.critical)

    def format_report(self) -> str:
        """Format the checklist as a report."""
        lines = [
            "══════════════════════════════════════",
            "   ✅ قائمة التحقق قبل الإطلاق",
            "══════════════════════════════════════",
        ]
        critical_pass = 0
        critical_total = 0
        for item in self.items:
            status = "✅" if item.passed else ("❌" if item.critical else "⚠️ ")
            lines.append(f"  {status} {item.name}")
            lines.append(f"     {item.message}")
            if item.critical:
                critical_total += 1
                if item.passed:
                    critical_pass += 1

        lines.append("")
        if self.is_ready():
            lines.append(f"  🟢 جاهز للإطلاق ({critical_pass}/{critical_total} حرج)")
        else:
            lines.append(
                f"  🔴 غير جاهز ({critical_pass}/{critical_total} حرج) — "
                f"أصلح البنود الحمراء أولاً"
            )
        return "\n".join(lines)

    @staticmethod
    def _is_gitignored(path: str) -> bool:
        """Check if a file is in .gitignore."""
        gitignore = Path(".gitignore")
        if gitignore.exists():
            return path in gitignore.read_text()
        return False
