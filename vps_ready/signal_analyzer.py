"""
signal_analyzer.py — تحليل ذاتي متقدم باستخدام VectorBT + FreqAI/ML

يستخدم المكتبات مفتوحة المصدر:
  - vectorbt: تحليل سريع للتوصيات وإيجاد أفضل توقيت
  - scikit-learn (FreqAI core): تعلم ذاتي من الأنماط
  - quantstats: تقارير أداء احترافية

    python3 signal_analyzer.py --analyze     # تحليل كامل
    python3 signal_analyzer.py --learn       # تدريب ML
    python3 signal_analyzer.py --report      # تقرير تيليجرام
    python3 signal_analyzer.py --all         # الكل

    pip install freqtrade vectorbt quantstats scikit-learn
"""
from __future__ import annotations
import json, os, sys, time, warnings
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

warnings.filterwarnings("ignore")

BASE_DIR = Path("/root/bots") if os.name != "nt" else Path(r"C:\Users\xman9\Desktop")
ENV_FILE = BASE_DIR / ".env_monthly"
TRACKER_FILE = BASE_DIR / "signal_tracker.json"
ML_MODEL_FILE = BASE_DIR / "ml_signal_model.pkl"
ML_RECOMMENDATIONS_FILE = BASE_DIR / "ml_recommendations.json"
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)
LOG_FILE = BASE_DIR / "analyzer.log"

load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

NOTIFY_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
BYBIT_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET = os.getenv("BYBIT_API_SECRET", "")
KUCOIN_KEY = os.getenv("KUCOIN_API_KEY", "")
KUCOIN_SECRET = os.getenv("KUCOIN_API_SECRET", "")
KUCOIN_PASS = os.getenv("KUCOIN_PASSPHRASE", "")
GATE_KEY = os.getenv("GATE_API_KEY", "")
GATE_SECRET = os.getenv("GATE_API_SECRET", "")


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(msg: str):
    if not NOTIFY_TOKEN or not NOTIFY_CHAT:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{NOTIFY_TOKEN}/sendMessage",
            json={"chat_id": NOTIFY_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


def init_exchanges() -> dict:
    import ccxt
    exchanges = {}
    if BYBIT_KEY:
        try:
            ex = ccxt.bybit({"apiKey": BYBIT_KEY, "secret": BYBIT_SECRET,
                             "options": {"defaultType": "spot"}})
            ex.load_markets()
            exchanges["bybit"] = ex
        except Exception:
            pass
    if KUCOIN_KEY:
        try:
            ex = ccxt.kucoin({"apiKey": KUCOIN_KEY, "secret": KUCOIN_SECRET,
                              "password": KUCOIN_PASS, "options": {"defaultType": "spot"}})
            ex.load_markets()
            exchanges["kucoin"] = ex
        except Exception:
            pass
    if GATE_KEY:
        try:
            ex = ccxt.gateio({"apiKey": GATE_KEY, "secret": GATE_SECRET,
                              "options": {"defaultType": "spot"}})
            ex.load_markets()
            exchanges["gateio"] = ex
        except Exception:
            pass
    return exchanges


def fetch_ohlcv(exchanges: dict, pair: str, ex_name: str, since_ts: float, days: int = 3) -> pd.DataFrame:
    ex = exchanges.get(ex_name)
    if not ex:
        for e in exchanges.values():
            if pair in getattr(e, "markets", {}):
                ex = e
                break
    if not ex:
        return pd.DataFrame()
    try:
        since_ms = int(since_ts * 1000)
        candles = ex.fetch_ohlcv(pair, "15m", since=since_ms, limit=days * 96)
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("datetime", inplace=True)
        return df
    except Exception:
        return pd.DataFrame()


# ─── VectorBT: تحليل التوقيت الأمثل ───

def vbt_analyze_signals(exchanges: dict):
    """يستخدم VectorBT لتحليل أفضل وقت دخول وخروج بعد كل توصية"""
    import vectorbt as vbt

    if not TRACKER_FILE.exists():
        log("لا توجد بيانات تتبع"); return None

    tracker = json.loads(TRACKER_FILE.read_text())

    _STABLECOINS = {"USDC", "USDT", "BUSD", "DAI", "TUSD", "FDUSD"}
    tracker = [r for r in tracker if r.get("symbol", "").upper() not in _STABLECOINS]

    seen_keys = set()
    unique_tracker = []
    for r in tracker:
        key = (r.get("symbol", ""), r.get("exchange", ""), round(r.get("signal_time", 0), -2))
        if key not in seen_keys:
            seen_keys.add(key)
            unique_tracker.append(r)
    tracker = unique_tracker

    if len(tracker) < 2:
        log(f"بيانات غير كافية ({len(tracker)} توصية — نحتاج 2+)"); return None

    results = []
    for rec in tracker:
        pair = rec.get("pair", "")
        if not pair:
            continue
        df = fetch_ohlcv(exchanges, pair, rec.get("exchange", ""), rec["signal_time"])
        if df.empty or len(df) < 10:
            continue

        entry_price = rec["signal_price"]
        close = df["close"]

        returns_pct = ((close - entry_price) / entry_price * 100).values
        minutes = ((df["timestamp"] - rec["signal_time"] * 1000) / 60000).values

        best_exit_idx = np.argmax(returns_pct)
        worst_idx = np.argmin(returns_pct)
        best_entry_idx = np.argmin(close.values[:max(best_exit_idx, 1)])

        results.append({
            "symbol": rec["symbol"],
            "pair": pair,
            "source": rec.get("source", "bot"),
            "exchange": rec.get("exchange", ""),
            "entry_price": entry_price,
            "best_entry_price": float(close.values[best_entry_idx]),
            "best_entry_min": float(minutes[best_entry_idx]),
            "best_entry_saving_pct": round((entry_price - close.values[best_entry_idx]) / entry_price * 100, 2),
            "best_exit_price": float(close.values[best_exit_idx]),
            "best_exit_min": float(minutes[best_exit_idx]),
            "max_profit_pct": round(float(returns_pct[best_exit_idx]), 2),
            "max_drawdown_pct": round(float(returns_pct[worst_idx]), 2),
            "volatility": round(float(np.std(returns_pct)), 2),
            "price_30m": float(close.iloc[min(2, len(close)-1)]),
            "price_1h": float(close.iloc[min(4, len(close)-1)]),
            "price_4h": float(close.iloc[min(16, len(close)-1)]),
            "price_24h": float(close.iloc[min(96, len(close)-1)]) if len(close) > 96 else None,
        })

    if not results:
        log("لا نتائج تحليل"); return None

    df_results = pd.DataFrame(results)

    log("\n═══ VectorBT: تحليل التوقيت ═══")
    avg_saving = df_results["best_entry_saving_pct"].mean()
    avg_delay = df_results["best_entry_min"].mean()
    avg_max_profit = df_results["max_profit_pct"].mean()
    avg_drawdown = df_results["max_drawdown_pct"].mean()

    log(f"عدد التوصيات: {len(df_results)}")
    log(f"متوسط التوفير بالدخول المتأخر: {avg_saving:+.2f}%")
    log(f"أفضل وقت دخول: بعد {avg_delay:.0f} دقيقة من التوصية")
    log(f"متوسط أقصى ربح: {avg_max_profit:+.2f}%")
    log(f"متوسط أقصى انخفاض: {avg_drawdown:+.2f}%")

    if df_results["source"].nunique() > 1:
        for src in ["bot", "manual"]:
            sub = df_results[df_results["source"] == src]
            if len(sub) > 0:
                label = "🤖 بوت" if src == "bot" else "👤 يدوي"
                log(f"\n  {label} ({len(sub)} صفقة):")
                log(f"    توفير الدخول: {sub['best_entry_saving_pct'].mean():+.2f}%")
                log(f"    أقصى ربح: {sub['max_profit_pct'].mean():+.2f}%")
                log(f"    أقصى انخفاض: {sub['max_drawdown_pct'].mean():+.2f}%")

    for _, r in df_results.iterrows():
        log(f"  {r['symbol']} [{r['exchange']}]: "
            f"أفضل دخول بعد {r['best_entry_min']:.0f}د (توفير {r['best_entry_saving_pct']:+.1f}%) | "
            f"أقصى ربح {r['max_profit_pct']:+.1f}% | انخفاض {r['max_drawdown_pct']:+.1f}%")

    return df_results


# ─── ML: تعلم ذاتي (FreqAI-style) ───

def ml_train(df_results: pd.DataFrame):
    """يدرّب نموذج ML لتوقع أفضل توقيت دخول — مستوحى من FreqAI"""
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import cross_val_score
    import joblib

    if df_results is None or len(df_results) < 5:
        log(f"بيانات غير كافية للتدريب ({0 if df_results is None else len(df_results)} — نحتاج 5+)")
        return None

    features = []
    targets = []
    for _, r in df_results.iterrows():
        features.append({
            "volatility": r["volatility"],
            "max_drawdown": abs(r["max_drawdown_pct"]),
            "entry_price": r["entry_price"],
            "is_manual": 1 if r["source"] == "manual" else 0,
        })
        targets.append(r["best_entry_min"])

    X = pd.DataFrame(features)
    y = np.array(targets)

    model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)

    if len(X) >= 5:
        cv_folds = min(5, len(X))
        scores = cross_val_score(model, X, y, cv=cv_folds, scoring="neg_mean_absolute_error")
        log(f"\nML: دقة التوقع (MAE): {-scores.mean():.1f} دقيقة (±{scores.std():.1f})")

    model.fit(X, y)
    joblib.dump(model, ML_MODEL_FILE)
    log(f"ML: تم حفظ النموذج → {ML_MODEL_FILE}")

    importances = dict(zip(X.columns, model.feature_importances_))
    log("ML: أهمية المتغيرات:")
    for feat, imp in sorted(importances.items(), key=lambda x: -x[1]):
        log(f"  {feat}: {imp:.1%}")

    return model


def ml_predict(df_results: pd.DataFrame, model):
    """يولّد توصيات للبوت بناءً على النموذج"""
    if model is None or df_results is None:
        return

    recommendations = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "signals_analyzed": len(df_results),
        "avg_optimal_delay_min": round(float(df_results["best_entry_min"].mean()), 1),
        "avg_entry_saving_pct": round(float(df_results["best_entry_saving_pct"].mean()), 2),
        "avg_max_drawdown_pct": round(float(df_results["max_drawdown_pct"].mean()), 2),
        "suggestion": "",
        "per_symbol": {},
    }

    avg_delay = df_results["best_entry_min"].mean()
    avg_saving = df_results["best_entry_saving_pct"].mean()
    avg_dd = df_results["max_drawdown_pct"].mean()

    suggestions = []
    if avg_saving > 1.0:
        suggestions.append(f"تأخير الدخول {avg_delay:.0f} دقيقة يوفر ~{avg_saving:.1f}%")
    if avg_dd < -5:
        suggestions.append(f"وقف خسارة ديناميكي عند {abs(avg_dd):.1f}% أفضل من الثابت")
    if not suggestions:
        suggestions.append("البيانات الحالية لا تُظهر نمط واضح — استمر بالتجميع")

    recommendations["suggestion"] = " | ".join(suggestions)

    for _, r in df_results.iterrows():
        recommendations["per_symbol"][r["symbol"]] = {
            "optimal_delay_min": round(r["best_entry_min"], 1),
            "entry_saving_pct": round(r["best_entry_saving_pct"], 2),
            "max_profit_pct": round(r["max_profit_pct"], 2),
            "max_drawdown_pct": round(r["max_drawdown_pct"], 2),
        }

    ML_RECOMMENDATIONS_FILE.write_text(json.dumps(recommendations, indent=2, ensure_ascii=False))
    log(f"\nتوصيات ML محفوظة → {ML_RECOMMENDATIONS_FILE}")
    log(f"💡 {recommendations['suggestion']}")

    return recommendations


# ─── QuantStats: تقرير أداء ───

def generate_quantstats_report():
    """يولّد تقرير أداء احترافي من تاريخ الصفقات"""
    import quantstats as qs

    state_file = BASE_DIR / "monthly_state.json"
    if not state_file.exists():
        log("لا يوجد ملف حالة"); return

    state = json.loads(state_file.read_text())
    history = state.get("trade_history", [])
    if len(history) < 2:
        log(f"صفقات غير كافية للتقرير ({len(history)})"); return

    dates = []
    returns = []
    for t in history:
        closed = t.get("closed", "")
        if not closed:
            continue
        try:
            dt = pd.to_datetime(closed)
            dates.append(dt)
            returns.append(t.get("pnl_pct", 0) / 100)
        except Exception:
            continue

    if len(dates) < 2:
        log("بيانات غير كافية"); return

    series = pd.Series(returns, index=pd.DatetimeIndex(dates), name="البوت")

    report_file = REPORT_DIR / f"performance_{time.strftime('%Y%m%d')}.html"
    try:
        qs.reports.html(series, output=str(report_file), title="أداء البوت")
        log(f"تقرير QuantStats → {report_file}")
    except Exception as e:
        log(f"خطأ QuantStats HTML: {e}")

    log("\n═══ QuantStats: ملخص الأداء ═══")
    try:
        metrics = {
            "إجمالي العائد": f"{qs.stats.comp(series):.2%}",
            "أفضل صفقة": f"{series.max():.2%}",
            "أسوأ صفقة": f"{series.min():.2%}",
            "نسبة الربح": f"{(series > 0).mean():.0%}",
            "متوسط الربح": f"{series[series > 0].mean():.2%}" if (series > 0).any() else "N/A",
            "متوسط الخسارة": f"{series[series < 0].mean():.2%}" if (series < 0).any() else "N/A",
        }
        for k, v in metrics.items():
            log(f"  {k}: {v}")
    except Exception as e:
        log(f"خطأ في الإحصائيات: {e}")


# ─── التقرير الشامل ───

def send_full_report(df_results, recommendations):
    """يرسل ملخص شامل عبر تيليجرام"""
    if df_results is None:
        return

    lines = ["<b>📊 تقرير التحليل الذاتي</b>\n"]

    lines.append(f"توصيات محللة: {len(df_results)}")
    lines.append(f"أفضل وقت دخول: بعد {df_results['best_entry_min'].mean():.0f} دقيقة")
    lines.append(f"توفير متوسط: {df_results['best_entry_saving_pct'].mean():+.1f}%")
    lines.append(f"أقصى ربح متوسط: {df_results['max_profit_pct'].mean():+.1f}%")
    lines.append(f"أقصى انخفاض متوسط: {df_results['max_drawdown_pct'].mean():+.1f}%")

    if recommendations and recommendations.get("suggestion"):
        lines.append(f"\n💡 {recommendations['suggestion']}")

    lines.append("\n<b>تفاصيل:</b>")
    for _, r in df_results.iterrows():
        src = "🤖" if r["source"] == "bot" else "👤"
        lines.append(
            f"{src} {r['symbol']}: دخول بعد {r['best_entry_min']:.0f}د "
            f"({r['best_entry_saving_pct']:+.1f}%) | "
            f"ربح {r['max_profit_pct']:+.1f}%"
        )

    notify("\n".join(lines))
    log("تم إرسال التقرير عبر تيليجرام")


# ─── تحليل استراتيجية السوينج ───

def analyze_swing_strategy(exchanges: dict, sell_pct: float = 3.0, rebuy_drop_pct: float = 5.0,
                            max_cycles: int = 10, days: int = 14):
    """يحلل استراتيجية: بيع عند +sell_pct% → إعادة شراء عند -rebuy_drop_pct% من سعر البيع → تكرار
    ويقارنها بالاحتفاظ (HODL)"""
    if not TRACKER_FILE.exists():
        log("لا توجد بيانات تتبع"); return None

    tracker = json.loads(TRACKER_FILE.read_text())
    _STABLECOINS = {"USDC", "USDT", "BUSD", "DAI", "TUSD", "FDUSD"}
    tracker = [r for r in tracker if r.get("symbol", "").upper() not in _STABLECOINS and r.get("pair")]

    if not tracker:
        log("لا توجد بيانات كافية"); return None

    results = []
    for rec in tracker:
        pair = rec["pair"]
        df = fetch_ohlcv(exchanges, pair, rec.get("exchange", ""), rec["signal_time"], days=days)
        if df.empty or len(df) < 20:
            continue

        closes = df["close"].values
        entry_price = rec.get("entry_price", rec["signal_price"])

        qty = 1.0
        cash = 0.0
        buy_price = entry_price
        cycles = 0
        cycle_details = []
        holding = True

        for price in closes:
            if holding:
                sell_trigger = buy_price * (1 + sell_pct / 100)
                if price >= sell_trigger:
                    cash = qty * price
                    sell_price = price
                    holding = False
                    pnl = (price - buy_price) / buy_price * 100
                    cycle_details.append({"buy": round(buy_price, 6), "sell": round(price, 6), "pnl_pct": round(pnl, 2)})
            else:
                rebuy_trigger = sell_price * (1 - rebuy_drop_pct / 100)
                if price <= rebuy_trigger:
                    qty = cash / price
                    buy_price = price
                    cash = 0.0
                    holding = True
                    cycles += 1
                    if cycles >= max_cycles:
                        break

        if holding:
            final_value = qty * closes[-1]
        else:
            final_value = cash

        initial_value = entry_price
        swing_return = (final_value - initial_value) / initial_value * 100
        hodl_return = (closes[-1] - entry_price) / entry_price * 100

        results.append({
            "symbol": rec["symbol"],
            "source": rec.get("source", "bot"),
            "entry": entry_price,
            "cycles": cycles,
            "swing_return_pct": round(swing_return, 2),
            "hodl_return_pct": round(hodl_return, 2),
            "advantage_pct": round(swing_return - hodl_return, 2),
            "details": cycle_details,
        })

    if not results:
        log("لا نتائج"); return None

    df_r = pd.DataFrame(results)
    avg_swing = df_r["swing_return_pct"].mean()
    avg_hodl = df_r["hodl_return_pct"].mean()
    avg_cycles = df_r["cycles"].mean()
    avg_advantage = df_r["advantage_pct"].mean()
    coins_with_cycles = len(df_r[df_r["cycles"] >= 2])

    log(f"\n═══ تحليل السوينج: بيع +{sell_pct}% → شراء -{rebuy_drop_pct}% ═══")
    log(f"عدد العملات: {len(df_r)}")
    log(f"متوسط الدورات (بيع+شراء): {avg_cycles:.1f}")
    log(f"عملات حققت دورتين+: {coins_with_cycles}/{len(df_r)}")
    log(f"عائد السوينج: {avg_swing:+.2f}%")
    log(f"عائد الاحتفاظ (HODL): {avg_hodl:+.2f}%")
    log(f"ميزة السوينج: {avg_advantage:+.2f}%")

    for _, r in df_r.iterrows():
        src = "🤖" if r["source"] == "bot" else "👤"
        winner = "✅" if r["advantage_pct"] > 0 else "❌"
        log(f"  {src} {r['symbol']}: {r['cycles']} دورات | "
            f"سوينج {r['swing_return_pct']:+.1f}% vs HODL {r['hodl_return_pct']:+.1f}% {winner}")

    report_lines = [f"<b>🔄 تحليل السوينج: بيع +{sell_pct}% → شراء -{rebuy_drop_pct}%</b>\n"]
    report_lines.append(f"عملات محللة: {len(df_r)}")
    report_lines.append(f"متوسط الدورات: {avg_cycles:.1f}")
    report_lines.append(f"عملات حققت دورتين+: {coins_with_cycles}/{len(df_r)}")
    report_lines.append(f"عائد السوينج: {avg_swing:+.1f}%")
    report_lines.append(f"عائد الاحتفاظ HODL: {avg_hodl:+.1f}%")
    verdict = f"✅ السوينج أفضل بـ {avg_advantage:+.1f}%" if avg_advantage > 0 else f"❌ الاحتفاظ أفضل بـ {abs(avg_advantage):.1f}%"
    report_lines.append(f"\n💡 النتيجة: {verdict}")

    report_lines.append("\n<b>تفاصيل:</b>")
    for _, r in df_r.iterrows():
        src = "🤖" if r["source"] == "bot" else "👤"
        winner = "✅" if r["advantage_pct"] > 0 else "❌"
        report_lines.append(
            f"{src} {r['symbol']}: {r['cycles']} دورات | "
            f"سوينج {r['swing_return_pct']:+.1f}% vs HODL {r['hodl_return_pct']:+.1f}% {winner}")

    notify("\n".join(report_lines))
    return df_r


# ─── main ───

def main():
    args = set(sys.argv[1:])
    do_all = "--all" in args

    log("═══ بدء التحليل الذاتي المتقدم ═══")
    log("المكتبات: VectorBT + scikit-learn (FreqAI) + QuantStats")

    exchanges = init_exchanges()
    log(f"المنصات: {', '.join(exchanges.keys()) or 'لا يوجد'}")

    df_results = None
    recommendations = None

    if "--analyze" in args or do_all:
        log("\n── VectorBT: تحليل التوقيت ──")
        df_results = vbt_analyze_signals(exchanges)

    if "--swing" in args or do_all:
        log("\n── تحليل استراتيجية السوينج ──")
        analyze_swing_strategy(exchanges)

    if "--learn" in args or do_all:
        log("\n── ML: تدريب النموذج ──")
        if df_results is None:
            df_results = vbt_analyze_signals(exchanges)
        model = ml_train(df_results)
        if model and df_results is not None:
            recommendations = ml_predict(df_results, model)

    if "--report" in args or do_all:
        log("\n── QuantStats: تقرير الأداء ──")
        generate_quantstats_report()
        if df_results is not None:
            send_full_report(df_results, recommendations)

    log("\n═══ انتهى التحليل ═══")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("الاستخدام:")
        print("  python3 signal_analyzer.py --analyze   # تحليل VectorBT")
        print("  python3 signal_analyzer.py --swing     # تحليل السوينج")
        print("  python3 signal_analyzer.py --learn     # تدريب ML")
        print("  python3 signal_analyzer.py --report    # تقرير QuantStats")
        print("  python3 signal_analyzer.py --all       # الكل")
        sys.exit(0)
    main()
