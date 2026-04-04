"""
Polymarket Hedge Fund — Configuration
All trading limits are enforced programmatically. No override without code change.
"""

from dataclasses import dataclass, field
from enum import Enum


class TradingMode(Enum):
    MANUAL = "manual"        # كل صفقة تحتاج تأكيد يدوي
    SEMI_AUTO = "semi_auto"  # تنفيذ آلي مع تأكيد فوق الحد
    FULL_AUTO = "full_auto"  # تنفيذ آلي كامل — لا تفعّله قبل 30 يوم


@dataclass(frozen=True)
class RiskLimits:
    """Immutable risk limits — cannot be changed at runtime."""
    max_position_pct: float = 0.01        # 1% من رأس المال للصفقة الواحدة
    max_total_exposure_pct: float = 0.05  # 5% حد إجمالي مفتوح
    max_daily_loss_pct: float = 0.015     # 1.5% حد خسارة يومي
    max_daily_trades: int = 2             # صفقتان يومياً فقط
    confirmation_threshold_usd: float = 100.0
    stop_loss_pct: float = 0.20           # -20% من قيمة المركز
    take_profit_pct: float = 0.40         # +40% من قيمة المركز
    max_consecutive_losses: int = 2       # إيقاف بعد خسارتين متتاليتين


@dataclass(frozen=True)
class EntryRequirements:
    """Minimum thresholds for entering a trade — ALL must be met."""
    min_composite_score: float = 75.0     # Score ≥ 75/100
    min_edge_pct: float = 0.07            # Edge ≥ 7%
    min_liquidity_usd: float = 10_000.0   # Liquidity ≥ $10,000
    max_spread_pct: float = 0.03          # Spread ≤ 3%
    min_time_to_expiry_hours: float = 24  # ≥ 24 ساعة للانتهاء


@dataclass(frozen=True)
class ExecutionConfig:
    """Execution rules."""
    phase1_ratio: float = 0.60   # المرحلة 1: 60%
    phase2_ratio: float = 0.40   # المرحلة 2: 40%
    phase2_wait_minutes: int = 60  # انتظار ساعة قبل المرحلة 2
    order_type: str = "LIMIT"    # LIMIT فقط — MARKET محظور
    max_slippage_pct: float = 0.01


@dataclass(frozen=True)
class QuantWeights:
    """Probability model weights — must sum to 1.0."""
    historical: float = 0.25
    news: float = 0.25
    sentiment: float = 0.20
    structure: float = 0.15
    time_decay: float = 0.15

    def __post_init__(self):
        total = (self.historical + self.news + self.sentiment
                 + self.structure + self.time_decay)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Quant weights must sum to 1.0, got {total}")


@dataclass(frozen=True)
class SignalWeights:
    """Signal strength weights — must sum to 1.0."""
    news: float = 0.30
    market_sentiment: float = 0.25
    market_data: float = 0.25
    time_factor: float = 0.20

    def __post_init__(self):
        total = self.news + self.market_sentiment + self.market_data + self.time_factor
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Signal weights must sum to 1.0, got {total}")


@dataclass
class HedgeFundConfig:
    """Master configuration."""
    capital_usd: float = 1000.0
    trading_mode: TradingMode = TradingMode.MANUAL
    risk: RiskLimits = field(default_factory=RiskLimits)
    entry: EntryRequirements = field(default_factory=EntryRequirements)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    quant_weights: QuantWeights = field(default_factory=QuantWeights)
    signal_weights: SignalWeights = field(default_factory=SignalWeights)

    @property
    def max_order_size_usd(self) -> float:
        return self.capital_usd * self.risk.max_position_pct

    @property
    def max_total_exposure_usd(self) -> float:
        return self.capital_usd * self.risk.max_total_exposure_pct

    @property
    def max_daily_loss_usd(self) -> float:
        return self.capital_usd * self.risk.max_daily_loss_pct
