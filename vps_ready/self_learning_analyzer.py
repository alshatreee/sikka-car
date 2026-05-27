#!/usr/bin/env python3
"""
Daily Self-Learning Analyzer
Reads all bot logs, calculates performance metrics, outputs learning parameters.
Optionally calls Claude API for strategy review and sends summary to Telegram.
Usage: python3 self_learning_analyzer.py --days 7 --send
"""
import os
import sys
import re
import json
import glob
import argparse
import platform
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# ---------- paths ----------
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    BOTS_DIR = r"C:\Users\xman9\Desktop"
    LOG_PATTERN = os.path.join(BOTS_DIR, "*.log")
else:
    BOTS_DIR = "/root/bots"
    LOG_PATTERN = os.path.join(BOTS_DIR, "*.log")

OUTPUT_FILE = os.path.join(BOTS_DIR, "learning_params.json")

# ---------- env helpers ----------

def find_env_value(key: str) -> str | None:
    """Search available .env files for a key."""
    env_files = [".env3", ".env2", ".env_naif", ".env", ".env_monthly", ".env_finance"]
    for fname in env_files:
        fpath = os.path.join(BOTS_DIR, fname)
        if os.path.isfile(fpath):
            with open(fpath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{key}="):
                        val = line.split("=", 1)[1].strip().strip("'\"")
                        if val:
                            return val
    return os.environ.get(key)

# ---------- log parsing ----------

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
PNL_RE = re.compile(r"PnL[:\s]*([+-]?\d+\.?\d*)", re.IGNORECASE)
TRADE_BUY_RE = re.compile(r"\[PAPER\]\s*BUY|\bBUY\b.*(?:open|entry)", re.IGNORECASE)
CLOSE_TP_RE = re.compile(r"CLOSE\s*TP|take.?profit|TP\s*hit", re.IGNORECASE)
CLOSE_SL_RE = re.compile(r"CLOSE\s*SL|stop.?loss|SL\s*hit", re.IGNORECASE)
HOUR_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}):")


def parse_log(filepath: str, cutoff: datetime) -> dict:
    """Parse a single log file and return raw stats."""
    stats = {
        "wins": 0, "losses": 0, "total_trades": 0,
        "pnl_list": [], "total_pnl": 0.0,
        "hours": defaultdict(int),
        "equity_curve": [],
    }
    try:
        with open(filepath, "r", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return stats

    for line in lines:
        # filter by date
        dm = DATE_RE.search(line)
        if dm:
            try:
                line_date = datetime.strptime(dm.group(1), "%Y-%m-%d")
                if line_date < cutoff:
                    continue
            except ValueError:
                pass

        # trades
        if TRADE_BUY_RE.search(line):
            stats["total_trades"] += 1
            hm = HOUR_RE.search(line)
            if hm:
                stats["hours"][int(hm.group(2))] += 1

        # wins / losses
        if CLOSE_TP_RE.search(line):
            stats["wins"] += 1
        if CLOSE_SL_RE.search(line):
            stats["losses"] += 1

        # pnl
        pm = PNL_RE.search(line)
        if pm:
            val = float(pm.group(1))
            stats["pnl_list"].append(val)
            stats["total_pnl"] += val
            stats["equity_curve"].append(stats["total_pnl"])

    return stats

# ---------- metrics ----------

def calc_metrics(stats: dict) -> dict:
    total = stats["wins"] + stats["losses"]
    win_rate = (stats["wins"] / total * 100) if total else 0.0

    gains = [p for p in stats["pnl_list"] if p > 0]
    losses_abs = [abs(p) for p in stats["pnl_list"] if p < 0]
    profit_factor = (sum(gains) / sum(losses_abs)) if losses_abs else float("inf") if gains else 0.0

    # sharpe (daily-ish approximation)
    if len(stats["pnl_list"]) > 1:
        import statistics
        mean_pnl = statistics.mean(stats["pnl_list"])
        std_pnl = statistics.stdev(stats["pnl_list"])
        sharpe = (mean_pnl / std_pnl) if std_pnl else 0.0
    else:
        sharpe = 0.0

    # max drawdown
    peak = 0.0
    max_dd = 0.0
    for eq in stats["equity_curve"]:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    # best hours (top 3)
    sorted_hours = sorted(stats["hours"].items(), key=lambda x: x[1], reverse=True)
    best_hours = [h for h, _ in sorted_hours[:3]]

    return {
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 3) if profit_factor != float("inf") else "inf",
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown": round(max_dd, 2),
        "best_hours": best_hours,
        "total_trades": stats["total_trades"],
        "total_pnl": round(stats["total_pnl"], 2),
    }

# ---------- Claude API review ----------

def claude_review(params: dict) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import requests
    except ImportError:
        return None

    prompt = (
        "You are a quant trading advisor. Review these bot performance metrics "
        "and give short actionable suggestions (max 200 words):\n\n"
        + json.dumps(params, indent=2, default=str)
    )
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    except Exception as e:
        print(f"[WARN] Claude API call failed: {e}")
        return None

# ---------- Telegram ----------

def send_telegram(text: str):
    token = find_env_value("TELEGRAM_TOKEN")
    chat_id = find_env_value("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[WARN] Telegram credentials not found, skipping send.")
        return
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        # split long messages
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            requests.post(url, json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"}, timeout=15)
        print("[OK] Telegram summary sent.")
    except Exception as e:
        print(f"[WARN] Telegram send failed: {e}")

# ---------- main ----------

def main():
    parser = argparse.ArgumentParser(description="Self-Learning Bot Analyzer")
    parser.add_argument("--days", type=int, default=1, help="Analyze last N days (default 1)")
    parser.add_argument("--send", action="store_true", help="Send summary to Telegram")
    args = parser.parse_args()

    cutoff = datetime.now() - timedelta(days=args.days)
    log_files = glob.glob(LOG_PATTERN)

    if not log_files:
        print(f"No log files found in {BOTS_DIR}")
        sys.exit(0)

    print(f"Analyzing {len(log_files)} logs, last {args.days} day(s) ...")
    all_params = {}
    summary_lines = [f"*Self-Learning Report* ({args.days}d)\n"]

    for lf in sorted(log_files):
        bot_name = Path(lf).stem
        stats = parse_log(lf, cutoff)
        metrics = calc_metrics(stats)
        all_params[bot_name] = metrics
        summary_lines.append(
            f"*{bot_name}*: WR {metrics['win_rate']}% | "
            f"PF {metrics['profit_factor']} | PnL {metrics['total_pnl']} | "
            f"Trades {metrics['total_trades']}"
        )
        print(f"  {bot_name}: {metrics}")

    # save learning params
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_params, f, indent=2, default=str)
    print(f"\nSaved -> {OUTPUT_FILE}")

    # Claude review
    review = claude_review(all_params)
    if review:
        summary_lines.append(f"\n*AI Review:*\n{review}")
        print(f"\nClaude Review:\n{review}")

    if args.send:
        send_telegram("\n".join(summary_lines))

if __name__ == "__main__":
    main()
