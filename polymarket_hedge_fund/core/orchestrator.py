"""
Main Orchestrator — ties all layers together.
Implements the mandatory session sequence.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..config import HedgeFundConfig, TradingMode
from ..models.market import (
    ClosedTrade, Direction, MarketData, OrderStatus, Position, SignalData,
    TradeProposal, TradeResult,
)
from .api_market import PolymarketMarketAPI
from .api_trading import PolymarketPortfolioAPI, PolymarketTradingAPI
from .execution import ExecutionEngine
from .mcp_client import MCPClient, MCPConfig
from .performance import PerformanceTracker
from .quant_model import QuantModel
from .risk_engine import RiskEngine
from .safety import (
    EnhancedKillSwitch, KillSwitchConfig, PreLaunchChecklist, SecureConfig,
)
from .scanner import MarketScanner

logger = logging.getLogger(__name__)


class HedgeFundOrchestrator:
    """
    Main entry point for the hedge fund system.
    Enforces the mandatory session sequence:
    ① Portfolio status
    ② Market scan (top 5)
    ③ Propose up to 2 trades
    """

    def __init__(
        self,
        config: Optional[HedgeFundConfig] = None,
        mcp_config: Optional[MCPConfig] = None,
    ):
        self.config = config or HedgeFundConfig()
        self.risk = RiskEngine(self.config)
        self.quant = QuantModel(self.config)
        self.execution = ExecutionEngine(self.config)
        self.scanner = MarketScanner(self.config)
        self.performance = PerformanceTracker()
        self.positions: list[Position] = []
        self._pending_proposals: dict[str, TradeProposal] = {}
        self.kill_switch = EnhancedKillSwitch(KillSwitchConfig(), self.config)

        # MCP API layer (optional — works offline without it)
        self.mcp: Optional[MCPClient] = None
        self.market_api: Optional[PolymarketMarketAPI] = None
        self.trading_api: Optional[PolymarketTradingAPI] = None
        self.portfolio_api: Optional[PolymarketPortfolioAPI] = None
        self._mcp_config = mcp_config

    async def connect(self) -> str:
        """Connect to Polymarket MCP Server."""
        if not self._mcp_config:
            return "⚠️  لا يوجد إعدادات MCP — يعمل في وضع المحاكاة"

        self.mcp = MCPClient(self._mcp_config)
        await self.mcp.connect()

        self.market_api = PolymarketMarketAPI(self.mcp)
        self.trading_api = PolymarketTradingAPI(self.mcp)
        self.portfolio_api = PolymarketPortfolioAPI(self.mcp)

        # Wire trading API into execution engine
        self.execution = ExecutionEngine(self.config, api=self.trading_api)

        return "✅ متصل بـ Polymarket MCP Server"

    async def disconnect(self) -> None:
        """Disconnect from MCP Server."""
        if self.mcp:
            await self.mcp.disconnect()

    def run_safety_checklist(
        self,
        secure_config: Optional[SecureConfig] = None,
        backtest_result: Optional[object] = None,
        trading_days: int = 0,
    ) -> str:
        """
        Run pre-launch safety checklist.
        Must pass ALL critical items before real trading.
        """
        checklist = PreLaunchChecklist(self.config)
        checklist.run(
            secure_config=secure_config,
            mcp_connected=self.is_connected,
            backtest_result=backtest_result,
            trading_days_completed=trading_days,
        )
        return checklist.format_report()

    @property
    def is_connected(self) -> bool:
        return self.mcp is not None and self.mcp.is_connected

    # ── Session Start ──

    async def start_session(self) -> str:
        """
        Mandatory session start sequence.
        Returns formatted status string.
        """
        lines = [
            "══════════════════════════════════════",
            "   🏦 POLYMARKET HEDGE FUND — Session",
            "══════════════════════════════════════",
        ]

        # If connected, fetch live portfolio data
        if self.is_connected and self.portfolio_api:
            try:
                wallet_summary = await self.portfolio_api.get_wallet_summary()
                lines.append("")
                lines.append(wallet_summary)
            except Exception as e:
                lines.append(f"\n⚠️  خطأ في جلب بيانات المحفظة: {e}")
                lines.append(self._format_portfolio_status())
        else:
            lines.append("")
            lines.append(self._format_portfolio_status())

        lines.append("")
        lines.append(self._format_risk_status())

        # Performance summary if trades exist
        metrics = self.performance.get_metrics()
        if metrics.total_trades > 0:
            lines.append("")
            lines.append(metrics.to_display())

            suggestions = self.performance.get_improvement_suggestions()
            if suggestions:
                lines.append("\n📈 توصيات التحسين:")
                for s in suggestions:
                    lines.append(f"  {s}")

        return "\n".join(lines)

    # ── Market Analysis ──

    async def scan_live_markets(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        top_n: int = 5,
    ) -> str:
        """
        Step ②: Fetch live markets from Polymarket and rank them.
        Uses MCP API if connected, otherwise requires manual market data.
        """
        if self.risk.is_halted:
            return f"⛔ الجلسة متوقفة: {self.risk.halt_reason}"

        if not self.is_connected or not self.market_api:
            return "⚠️  غير متصل بـ MCP — استخدم analyze_markets() مع بيانات يدوية"

        markets = []
        if query:
            markets = await self.market_api.search_markets(query, limit=30)
        elif category:
            markets = await self.market_api.get_markets_by_category(category, limit=30)
        else:
            markets = await self.market_api.get_trending_markets(
                timeframe="24h", limit=30
            )

        if not markets:
            return "❌ لم يتم العثور على أسواق"

        top = self.scanner.get_top_markets(markets, top_n=top_n)
        return self.scanner.format_scan_results(top)

    def analyze_markets(self, markets: list[MarketData]) -> str:
        """
        Step ②: Scan and rank top 5 markets (offline mode).
        """
        if self.risk.is_halted:
            return f"⛔ الجلسة متوقفة: {self.risk.halt_reason}"

        top = self.scanner.get_top_markets(markets, top_n=5)
        return self.scanner.format_scan_results(top)

    # ── Trade Proposal ──

    async def propose_live_trade(
        self,
        market_id: str,
        direction: Direction,
        p_historical: float,
        rationale: str,
        news_score: float = 0.5,
    ) -> str:
        """
        Full pipeline: fetch live data → build signal → quant analysis →
        risk check → format proposal.
        """
        if not self.is_connected or not self.market_api:
            return "⚠️  غير متصل بـ MCP"

        # Fetch live market data
        market = await self.market_api.get_market_detail(market_id)
        if not market:
            return f"❌ لم يتم العثور على السوق: {market_id}"

        # Build signal from live data
        signal = await self.market_api.build_signal(market)
        signal.news_score = news_score  # Must be provided externally

        return self.propose_trade(market, signal, p_historical, direction, rationale)

    def propose_trade(
        self,
        market: MarketData,
        signal: SignalData,
        p_historical: float,
        direction: Direction,
        rationale: str,
    ) -> str:
        """
        Analyze a market and build a trade proposal.
        Runs through KillSwitch → Quant → Risk → format for display.
        """
        # Kill switch pre-check
        ks_ok, ks_issues = self.kill_switch.check_pre_trade(
            market, self.positions, self.is_connected,
        )
        if not ks_ok:
            return "⛔ Kill Switch:\n" + "\n".join(ks_issues)

        # Quant analysis (direction-aware edge calculation)
        estimate = self.quant.estimate(market, signal, p_historical, direction=direction)

        # Build proposal
        proposal = self.execution.build_proposal(
            market=market,
            direction=direction,
            edge=estimate.edge,
            composite_score=estimate.composite_score,
            rationale=rationale,
            signal_data=signal,
            quant_estimate=estimate,
        )

        # Risk check
        risk_result = self.risk.check_trade(proposal, market, self.positions)

        # Format output
        lines = [
            self.execution.format_proposal(proposal),
            "",
            "── فحص المخاطر ──",
            str(risk_result),
        ]

        if risk_result.approved:
            self._pending_proposals[proposal.id] = proposal
            if self.config.trading_mode == TradingMode.MANUAL:
                lines.append(
                    f"\n💡 الوضع: يدوي — نفّذ بالأمر: execute('{proposal.id}')"
                )
            elif risk_result.requires_confirmation:
                lines.append(
                    f"\n🔒 تحتاج تأكيد — نفّذ بالأمر: execute('{proposal.id}')"
                )
        else:
            lines.append("\n❌ الصفقة مرفوضة — لا يمكن التنفيذ")

        return "\n".join(lines)

    # ── Execution ──

    async def execute(self, proposal_id: str) -> str:
        """
        Execute an approved trade (Phase 1) via MCP API or simulation.
        """
        from datetime import datetime, timedelta

        proposal = self._pending_proposals.get(proposal_id)
        if not proposal:
            return f"❌ لم يتم العثور على الاقتراح: {proposal_id}"

        # Kill switch check
        if self.kill_switch.is_halted:
            return f"⛔ Kill switch مُفعَّل:\n" + "\n".join(self.kill_switch.halt_reasons)

        # Re-validate with risk engine using live data if available
        if self.is_connected and self.market_api:
            try:
                live_market = await self.market_api.get_market_detail(proposal.market_id)
                if live_market:
                    risk_market = live_market
                else:
                    logger.warning("⚠️ تعذر جلب بيانات حية — استخدام بيانات الاقتراح")
                    risk_market = MarketData(
                        market_id=proposal.market_id,
                        question=proposal.market_question,
                        yes_price=proposal.limit_price,
                        no_price=1 - proposal.limit_price,
                        liquidity_usd=self.config.entry.min_liquidity_usd,
                        volume_24h=0, spread=0,
                        expiry=datetime.utcnow() + timedelta(days=7),
                    )
            except Exception as e:
                logger.warning(f"⚠️ خطأ في جلب بيانات حية: {e}")
                risk_market = MarketData(
                    market_id=proposal.market_id,
                    question=proposal.market_question,
                    yes_price=proposal.limit_price,
                    no_price=1 - proposal.limit_price,
                    liquidity_usd=self.config.entry.min_liquidity_usd,
                    volume_24h=0, spread=0,
                    expiry=datetime.utcnow() + timedelta(days=7),
                )
        else:
            risk_market = MarketData(
                market_id=proposal.market_id,
                question=proposal.market_question,
                yes_price=proposal.limit_price,
                no_price=1 - proposal.limit_price,
                liquidity_usd=self.config.entry.min_liquidity_usd,
                volume_24h=0, spread=0,
                expiry=datetime.utcnow() + timedelta(days=7),
            )
        risk_result = self.risk.check_trade(proposal, risk_market, self.positions)
        if not risk_result.approved:
            return f"❌ فشل فحص المخاطر:\n{risk_result}"

        # Live execution via MCP
        if self.is_connected and self.trading_api:
            try:
                # Both YES and NO are BUY orders on their respective tokens
                suggested = await self.trading_api.suggest_price(
                    market_id=proposal.market_id,
                    side="BUY",
                    size=proposal.phase1_size_usd,
                    strategy="mid",
                )
                exec_price = proposal.limit_price
                if isinstance(suggested, dict) and "price" in suggested:
                    exec_price = float(suggested["price"])

                order_result = await self.trading_api.place_limit_order(
                    market_id=proposal.market_id,
                    direction=proposal.direction.value,
                    size_usd=proposal.phase1_size_usd,
                    limit_price=exec_price,
                )

                # Verify order was accepted
                if isinstance(order_result, dict):
                    if order_result.get("error") or not order_result.get("success", True):
                        error_msg = order_result.get("error", order_result.get("errorMsg", "Unknown"))
                        return f"❌ الأمر مرفوض: {error_msg}"

                # Order placed — status is PENDING (not filled yet for LIMIT orders)
                order_id = ""
                if isinstance(order_result, dict):
                    order_id = order_result.get("orderID", order_result.get("order_id", ""))

                position = Position(
                    trade_id=proposal.id,
                    market_id=proposal.market_id,
                    market_question=proposal.market_question,
                    direction=proposal.direction,
                    entry_price=exec_price,
                    current_price=exec_price,
                    size_usd=proposal.phase1_size_usd,
                    phase=1,
                    status=OrderStatus.PHASE1_FILLED,
                    edge_at_entry=proposal.edge,
                    stop_loss_price=proposal.stop_loss_price,
                    take_profit_price=proposal.take_profit_price,
                )
                self.positions.append(position)
                self.risk.record_trade_opened()
                del self._pending_proposals[proposal_id]

                return (
                    f"✅ Phase 1 نُفِّذت: ${proposal.phase1_size_usd:.2f} "
                    f"@ {exec_price:.4f} (Order: {order_id[:16]}...)\n"
                    f"   Phase 2 (${proposal.phase2_size_usd:.2f}) "
                    f"خلال {self.config.execution.phase2_wait_minutes} دقيقة"
                )
            except Exception as e:
                return f"❌ خطأ في التنفيذ: {e}"

        # Simulation mode
        position = self.execution.execute_phase1(proposal)
        if position:
            self.positions.append(position)
            self.risk.record_trade_opened()
            del self._pending_proposals[proposal_id]
            return (
                f"📋 [محاكاة] Phase 1: ${proposal.phase1_size_usd:.2f} "
                f"@ {proposal.limit_price:.4f}"
            )
        return "❌ فشل التنفيذ"

    # ── Position Management ──

    def check_positions(self, current_prices: dict[str, float]) -> list[str]:
        """
        Check all open positions for exit conditions.
        Auto-closes positions that hit SL/TP.
        current_prices: dict of market_id -> YES token price.
        For NO positions, we derive the NO token price as (1 - yes_price).
        Returns list of actions taken.
        """
        actions = []
        positions_to_close = []

        for pos in self.positions:
            if pos.market_id in current_prices:
                yes_price = current_prices[pos.market_id]
                # Set direction-specific token price
                if pos.direction == Direction.NO:
                    pos.current_price = 1.0 - yes_price
                else:
                    pos.current_price = yes_price

            exit_reason = self.risk.check_exit_conditions(pos)
            if exit_reason:
                positions_to_close.append((pos, exit_reason))

        # Close outside the loop to avoid mutating self.positions during iteration
        for pos, reason in positions_to_close:
            result = self.close_position(pos, pos.current_price, reason)
            actions.append(f"🚨 {result}")

        return actions

    def close_position(
        self,
        position: Position,
        exit_price: float,
        reason: str,
    ) -> str:
        """Close a position and record it."""
        # Determine result — same formula for YES and NO
        # exit_price and entry_price are always for the same token (direction-specific)
        if position.entry_price == 0:
            pnl_pct = 0.0
        else:
            pnl_pct = (exit_price - position.entry_price) / position.entry_price
        pnl_usd = position.size_usd * pnl_pct

        if pnl_usd > 0:
            result = TradeResult.WIN
        elif pnl_usd < 0:
            result = TradeResult.LOSS
        else:
            result = TradeResult.BREAKEVEN

        closed = ClosedTrade(
            trade_id=position.trade_id,
            market_id=position.market_id,
            market_question=position.market_question,
            direction=position.direction,
            edge_at_entry=position.edge_at_entry,
            composite_score=0.0,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size_usd=position.size_usd,
            pnl_usd=pnl_usd,
            result=result,
            reason=reason,
            opened_at=position.opened_at,
        )

        # Record in performance tracker and risk engine
        self.performance.record(closed)
        self.risk.record_trade_closed(closed)

        # Remove from open positions
        self.positions = [p for p in self.positions if p.trade_id != position.trade_id]

        return (
            f"{'✅' if pnl_usd >= 0 else '❌'} "
            f"{position.market_question[:30]} — "
            f"P&L: ${pnl_usd:+.2f} ({reason})"
        )

    # ── Helpers ──

    def _format_portfolio_status(self) -> str:
        total_exposure = sum(p.size_usd for p in self.positions)
        total_pnl = sum(p.pnl_usd for p in self.positions)
        return f"""
── 💼 المحفظة ──
  رأس المال     : ${self.config.capital_usd:,.2f}
  التعرض الحالي  : ${total_exposure:,.2f} / ${self.config.max_total_exposure_usd:,.2f}
  P&L المفتوح   : ${total_pnl:+,.2f}
  المراكز المفتوحة: {len(self.positions)}
  الوضع         : {self.config.trading_mode.value}"""

    def _format_risk_status(self) -> str:
        status = self.risk.get_status(self.positions)
        return f"""
── 🛡️  حالة المخاطر ──
  الجلسة       : {'⛔ متوقفة — ' + status['halt_reason'] if status['session_halted'] else '✅ نشطة'}
  صفقات اليوم  : {status['daily_trades']}/{status['max_daily_trades']}
  P&L اليوم    : ${status['daily_pnl']:+,.2f} (الحد: ${status['max_daily_loss']:,.2f})
  خسائر متتالية: {status['consecutive_losses']}/{self.config.risk.max_consecutive_losses}"""
