"""
Polymarket Hedge Fund — Dashboard
Interactive Streamlit dashboard for monitoring performance and running backtests.

Usage:
    pip install streamlit plotly
    streamlit run polymarket_hedge_fund/dashboard.py
"""

import sys
import os

# Ensure package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from datetime import datetime, timedelta
from pathlib import Path

try:
    import streamlit as st
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
except ImportError:
    print("Dashboard requires: pip install streamlit plotly")
    print("Then run: streamlit run polymarket_hedge_fund/dashboard.py")
    sys.exit(1)

from polymarket_hedge_fund.config import (
    HedgeFundConfig, RiskLimits, EntryRequirements,
)
from polymarket_hedge_fund.core.backtester import (
    Backtester, BacktestConfig, BacktestResult,
)
from polymarket_hedge_fund.core.performance import PerformanceTracker

# ══════════════════════════════════════
# Page Config
# ══════════════════════════════════════

st.set_page_config(
    page_title="Polymarket Hedge Fund",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏦 Polymarket Hedge Fund Dashboard")


# ══════════════════════════════════════
# Sidebar — Configuration
# ══════════════════════════════════════

st.sidebar.header("⚙️ إعدادات النظام")

tab = st.sidebar.radio("القسم", ["📊 الأداء الحي", "🧪 الاختبار التاريخي", "📈 تحليل المعايير"])

# ══════════════════════════════════════
# Tab 1: Live Performance
# ══════════════════════════════════════

if tab == "📊 الأداء الحي":
    st.header("📊 الأداء الحي")

    # Load trade history
    data_dir = Path("data")
    trades_file = data_dir / "trades.json"

    if trades_file.exists():
        with open(trades_file) as f:
            trades = json.load(f)

        if trades:
            tracker = PerformanceTracker(data_dir=str(data_dir))
            metrics = tracker.get_metrics()

            # ── KPI Cards ──
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("إجمالي الصفقات", metrics.total_trades)
            col2.metric("نسبة الفوز", f"{metrics.win_rate:.0%}")
            col3.metric("إجمالي P&L", f"${metrics.total_pnl_usd:+,.2f}")
            col4.metric("أقصى تراجع", f"${metrics.max_drawdown_usd:,.2f}")
            col5.metric("معامل الربح", f"{metrics.profit_factor:.2f}")

            # ── Equity Curve ──
            st.subheader("منحنى رأس المال")
            equity = [0]
            dates = []
            for t in trades:
                equity.append(equity[-1] + t["pnl_usd"])
                dates.append(t.get("closed_at", ""))

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(len(equity))),
                y=equity,
                mode="lines+markers",
                name="Equity",
                line=dict(color="#2ecc71", width=2),
                fill="tozeroy",
                fillcolor="rgba(46,204,113,0.1)",
            ))
            fig.update_layout(
                xaxis_title="عدد الصفقات",
                yaxis_title="P&L ($)",
                template="plotly_dark",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            # ── Trade Distribution ──
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("توزيع الأرباح والخسائر")
                pnls = [t["pnl_usd"] for t in trades]
                colors = ["#2ecc71" if p >= 0 else "#e74c3c" for p in pnls]
                fig = go.Figure(go.Bar(
                    x=list(range(1, len(pnls) + 1)),
                    y=pnls,
                    marker_color=colors,
                ))
                fig.update_layout(
                    xaxis_title="رقم الصفقة",
                    yaxis_title="P&L ($)",
                    template="plotly_dark",
                    height=350,
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("نسبة الفوز/الخسارة")
                fig = go.Figure(go.Pie(
                    labels=["ربح", "خسارة", "تعادل"],
                    values=[metrics.wins, metrics.losses, metrics.breakevens],
                    marker_colors=["#2ecc71", "#e74c3c", "#f39c12"],
                    hole=0.4,
                ))
                fig.update_layout(template="plotly_dark", height=350)
                st.plotly_chart(fig, use_container_width=True)

            # ── Trade Log ──
            st.subheader("سجل الصفقات")
            st.dataframe(
                [{
                    "#": i + 1,
                    "السوق": t["market_question"][:40],
                    "الاتجاه": t["direction"],
                    "Edge": f"{t['edge_at_entry']:.1%}",
                    "Score": f"{t['composite_score']:.0f}",
                    "دخول": f"{t['entry_price']:.3f}",
                    "خروج": f"{t['exit_price']:.3f}",
                    "P&L": f"${t['pnl_usd']:+.2f}",
                    "النتيج��": t["result"],
                    "السبب": t["reason"],
                } for i, t in enumerate(trades)],
                use_container_width=True,
            )

            # ── Improvement Suggestions ──
            suggestions = tracker.get_improvement_suggestions()
            st.subheader("📈 توصيات التحسين")
            for s in suggestions:
                st.info(s)
        else:
            st.info("لا توجد صفقات مسجلة بعد. ابدأ التداول أو شغّل الاختبار التاريخي.")
    else:
        st.info("لا يوجد ملف بيانات. ابدأ التداول أو شغّل الاختبار التاريخي.")


# ══════════════════════════════════════
# Tab 2: Backtesting
# ══════════════════════════════════════

elif tab == "🧪 الاختبار التاريخي":
    st.header("🧪 الاختبار التاريخي")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("إعدادات الاختبار")
        capital = st.number_input("رأس المال ($)", 100, 100000, 1000, step=100)
        days = st.slider("عدد الأيام", 30, 365, 90)
        seed = st.number_input("Random Seed", 1, 9999, 42)
        num_markets = st.slider("عدد الأسواق", 10, 50, 20)
        volatility = st.slider("تقلب الأسعار", 0.01, 0.10, 0.03, 0.005)

    with col2:
        st.subheader("معايير الدخول")
        min_edge = st.slider("الحد الأدنى لـ Edge %", 1, 20, 7) / 100
        min_score = st.slider("الحد الأدنى لـ Score", 50, 95, 75)
        max_daily = st.slider("أقصى صفقات يومياً", 1, 10, 2)
        max_pos_pct = st.slider("حجم الصفقة % من رأس المال", 1, 10, 1) / 100
        sl_pct = st.slider("Stop Loss %", 5, 40, 20)
        tp_pct = st.slider("Take Profit %", 10, 80, 40)

    if st.button("🚀 تشغيل الاختبار", type="primary", use_container_width=True):
        with st.spinner("جاري تشغيل الاختبار التاريخي..."):
            fund_config = HedgeFundConfig(
                capital_usd=capital,
                risk=RiskLimits(
                    max_daily_trades=max_daily,
                    max_position_pct=max_pos_pct,
                    stop_loss_pct=sl_pct / 100,
                    take_profit_pct=tp_pct / 100,
                ),
                entry=EntryRequirements(
                    min_edge_pct=min_edge,
                    min_composite_score=min_score,
                ),
            )
            bt_config = BacktestConfig(
                start_date=datetime(2025, 1, 1),
                end_date=datetime(2025, 1, 1) + timedelta(days=days),
                seed=seed,
                initial_capital=capital,
                num_markets=num_markets,
                volatility=volatility,
            )
            backtester = Backtester(fund_config=fund_config, backtest_config=bt_config)
            result = backtester.run()

        # Store in session
        st.session_state["backtest_result"] = result

    # Display results
    if "backtest_result" in st.session_state:
        result = st.session_state["backtest_result"]
        m = result.metrics

        # ── KPI Cards ──
        st.divider()
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("صفقات منفذة", m.total_trades)
        col2.metric("نسبة الفوز", f"{m.win_rate:.0%}")
        col3.metric("إجمالي P&L", f"${m.total_pnl_usd:+,.2f}")
        col4.metric("أقصى تراجع", f"${m.max_drawdown_usd:,.2f}")
        col5.metric("معامل الربح", f"{m.profit_factor:.2f}")
        roi = m.total_pnl_usd / result.config.initial_capital * 100
        col6.metric("العائد", f"{roi:+.1f}%")

        # ── Stats Row ─��
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("أسواق ممسوحة", f"{result.markets_scanned:,}")
        col2.metric("صفقات مقترحة", result.trades_proposed)
        col3.metric("صفقات مرفوضة", result.trades_rejected)
        col4.metric("أيام نشطة", result.active_days)

        # ── Equity Curve ──
        st.subheader("📈 منحنى رأس المال")
        dates = [e[0] for e in result.equity_curve]
        values = [e[1] for e in result.equity_curve]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=values,
            mode="lines",
            name="رأس المال",
            line=dict(color="#3498db", width=2),
            fill="tozeroy",
            fillcolor="rgba(52,152,219,0.1)",
        ))
        fig.add_hline(
            y=result.config.initial_capital,
            line_dash="dash",
            line_color="gray",
            annotation_text="رأس المال الأصلي",
        )
        fig.update_layout(
            xaxis_title="التاريخ",
            yaxis_title="رأس المال ($)",
            template="plotly_dark",
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Daily P&L ──
        if result.daily_pnl:
            non_zero = [(d, p) for d, p in result.daily_pnl if p != 0]
            if non_zero:
                st.subheader("📊 P&L اليومي")
                d_dates = [x[0] for x in non_zero]
                d_pnl = [x[1] for x in non_zero]
                colors = ["#2ecc71" if p >= 0 else "#e74c3c" for p in d_pnl]
                fig = go.Figure(go.Bar(x=d_dates, y=d_pnl, marker_color=colors))
                fig.update_layout(
                    xaxis_title="التاريخ",
                    yaxis_title="P&L ($)",
                    template="plotly_dark",
                    height=300,
                )
                st.plotly_chart(fig, use_container_width=True)

        # ── Trades Table ──
        if result.trades:
            st.subheader("📋 سجل الصفقات")
            st.dataframe(
                [{
                    "#": i + 1,
                    "السوق": t["market_question"][:35],
                    "الاتجاه": t["direction"],
                    "Edge": f"{t['edge_at_entry']:.1%}",
                    "دخول": f"{t['entry_price']:.3f}",
                    "خروج": f"{t['exit_price']:.3f}",
                    "P&L": f"${t['pnl_usd']:+.2f}",
                    "النتيجة": "✅" if t["result"] == "win" else "❌" if t["result"] == "loss" else "➖",
                    "السبب": t["reason"][:25],
                } for i, t in enumerate(result.trades)],
                use_container_width=True,
            )

        # ── Win/Loss Pie ──
        if m.total_trades > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("نسبة الفوز/الخسارة")
                fig = go.Figure(go.Pie(
                    labels=["ربح", "خسارة", "تعادل"],
                    values=[m.wins, m.losses, m.breakevens],
                    marker_colors=["#2ecc71", "#e74c3c", "#f39c12"],
                    hole=0.4,
                ))
                fig.update_layout(template="plotly_dark", height=300)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("توزيع P&L")
                pnls = [t["pnl_usd"] for t in result.trades]
                fig = go.Figure(go.Histogram(
                    x=pnls,
                    nbinsx=20,
                    marker_color="#3498db",
                ))
                fig.update_layout(
                    xaxis_title="P&L ($)",
                    yaxis_title="العدد",
                    template="plotly_dark",
                    height=300,
                )
                st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════
# Tab 3: Parameter Analysis
# ══════════════════════════════════════

elif tab == "📈 تحليل المعايير":
    st.header("📈 تحليل حساسية المعايير")
    st.write("يشغّل عدة اختبارات مع تغيير معيار واحد لمعرفة تأثيره.")

    param = st.selectbox("المعيار المراد تحليله", [
        "min_edge_pct",
        "min_composite_score",
        "stop_loss_pct",
        "take_profit_pct",
        "max_daily_trades",
        "volatility",
    ])

    param_ranges = {
        "min_edge_pct": (0.03, 0.15, 0.01),
        "min_composite_score": (50, 90, 5),
        "stop_loss_pct": (0.10, 0.40, 0.05),
        "take_profit_pct": (0.20, 0.80, 0.10),
        "max_daily_trades": (1, 8, 1),
        "volatility": (0.01, 0.08, 0.01),
    }

    start, end, step = param_ranges[param]
    base_capital = st.number_input("رأس المال", 100, 100000, 1000, key="sens_cap")
    base_days = st.slider("أيام الاختبار", 30, 365, 90, key="sens_days")
    base_seed = st.number_input("Seed", 1, 9999, 42, key="sens_seed")

    if st.button("🔬 تشغيل التحليل", type="primary", use_container_width=True):
        values = []
        v = start
        while v <= end + 0.0001:
            values.append(round(v, 4))
            v += step

        results = []
        progress = st.progress(0)

        for i, val in enumerate(values):
            risk_kwargs = {}
            entry_kwargs = {}
            bt_kwargs = {"volatility": 0.03}

            if param == "min_edge_pct":
                entry_kwargs["min_edge_pct"] = val
            elif param == "min_composite_score":
                entry_kwargs["min_composite_score"] = val
            elif param == "stop_loss_pct":
                risk_kwargs["stop_loss_pct"] = val
            elif param == "take_profit_pct":
                risk_kwargs["take_profit_pct"] = val
            elif param == "max_daily_trades":
                risk_kwargs["max_daily_trades"] = int(val)
            elif param == "volatility":
                bt_kwargs["volatility"] = val

            fund_config = HedgeFundConfig(
                capital_usd=base_capital,
                risk=RiskLimits(**risk_kwargs),
                entry=EntryRequirements(**entry_kwargs),
            )
            bt_config = BacktestConfig(
                start_date=datetime(2025, 1, 1),
                end_date=datetime(2025, 1, 1) + timedelta(days=base_days),
                seed=base_seed,
                initial_capital=base_capital,
                **bt_kwargs,
            )
            backtester = Backtester(fund_config=fund_config, backtest_config=bt_config)
            r = backtester.run()
            m = r.metrics

            results.append({
                "param_value": val,
                "total_trades": m.total_trades,
                "win_rate": m.win_rate,
                "total_pnl": m.total_pnl_usd,
                "max_drawdown": m.max_drawdown_usd,
                "profit_factor": min(m.profit_factor, 20),  # Cap for display
                "roi": m.total_pnl_usd / base_capital * 100,
            })

            progress.progress((i + 1) / len(values))

        # ── Plot Results ──
        if results:
            param_vals = [r["param_value"] for r in results]

            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=["العائد (%)", "نسبة الفوز", "عدد الصفقات", "أقصى تراجع ($)"],
            )

            fig.add_trace(go.Scatter(
                x=param_vals, y=[r["roi"] for r in results],
                mode="lines+markers", name="العائد",
                line=dict(color="#2ecc71"),
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=param_vals, y=[r["win_rate"] * 100 for r in results],
                mode="lines+markers", name="نسبة الفوز",
                line=dict(color="#3498db"),
            ), row=1, col=2)

            fig.add_trace(go.Bar(
                x=param_vals, y=[r["total_trades"] for r in results],
                name="الصفقات",
                marker_color="#9b59b6",
            ), row=2, col=1)

            fig.add_trace(go.Scatter(
                x=param_vals, y=[r["max_drawdown"] for r in results],
                mode="lines+markers", name="التراجع",
                line=dict(color="#e74c3c"),
            ), row=2, col=2)

            fig.update_layout(
                template="plotly_dark",
                height=600,
                showlegend=False,
                title_text=f"تحليل حساسية: {param}",
            )
            st.plotly_chart(fig, use_container_width=True)

            # Table
            st.dataframe(
                [{
                    param: r["param_value"],
                    "صفقات": r["total_trades"],
                    "فوز %": f"{r['win_rate']:.0%}",
                    "P&L $": f"${r['total_pnl']:+.2f}",
                    "عائد %": f"{r['roi']:+.1f}%",
                    "تراجع $": f"${r['max_drawdown']:.2f}",
                } for r in results],
                use_container_width=True,
            )


# ══════════════════════════════════════
# Footer
# ══════════════════════════════════════

st.sidebar.divider()
st.sidebar.caption("Polymarket Hedge Fund v3.0")
st.sidebar.caption("البقاء > الانضباط > الجودة > الربح")
