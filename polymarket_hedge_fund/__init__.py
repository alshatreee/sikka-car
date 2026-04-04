"""
Polymarket Hedge Fund System v3.0
Professional trading system with programmatic risk enforcement.
"""

from .config import HedgeFundConfig, TradingMode
from .core.orchestrator import HedgeFundOrchestrator

__version__ = "3.0.0"
__all__ = ["HedgeFundConfig", "HedgeFundOrchestrator", "TradingMode"]
