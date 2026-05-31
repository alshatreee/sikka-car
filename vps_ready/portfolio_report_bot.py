#!/usr/bin/env python3
"""
portfolio_report_bot.py — Multi-exchange portfolio P&L report
=============================================================
Fetches balances from Bybit, KuCoin, Gate.io — reports per-coin
and total value via Telegram and CLI.

    python3 portfolio_report_bot.py              # one-time CLI report
    python3 portfolio_report_bot.py --daemon     # daily Telegram report
    python3 portfolio_report_bot.py --json       # raw JSON output

Env file: .env_portfolio
"""
from __future__ import annotations
import argparse, base64, hashlib, hmac, json, os, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──
BASE_DIR = Path(r"C:\Users\xman9\Desktop") if os.name == "nt" else Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = BASE_DIR / ".env_portfolio"

# ── Load env ──
def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

ENV = load_env()
TG_TOKEN = ENV.get("TELEGRAM_TOKEN", "")
TG_CHAT = ENV.get("TELEGRAM_CHAT_ID", "")
TOTAL_INVESTED = float(ENV.get("TOTAL_INVESTED", "0"))
REPORT_HOUR = int(ENV.get("REPORT_HOUR", "9"))

# ── HTTP helper ──
def http_req(url: str, headers: dict = None, data: bytes = None,
             method: str = None, timeout: int = 15) -> dict | None:
    try:
        req = urllib.request.Request(url, data=data, headers=headers or {},
                                     method=method)
        if "User-Agent" not in (headers or {}):
            req.add_header("User-Agent", "portfolio-report/1.0")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)}

# ── Telegram ──
def tg(msg: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

# ═══════════════════════════════════════════════
#  Exchange adapters
# ═══════════════════════════════════════════════

def fetch_bybit(key: str, secret: str, label: str = "Bybit") -> list[dict]:
    ts = str(int(time.time() * 1000))
    recv = "5000"
    params = "accountType=UNIFIED"
    sign_str = f"{ts}{key}{recv}{params}"
    sig = hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.bybit.com/v5/account/wallet-balance?{params}"
    resp = http_req(url, headers={
        "X-BAPI-API-KEY": key, "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": recv, "X-BAPI-SIGN": sig,
    })
    if not resp or "_error" in resp or resp.get("retCode") != 0:
        return [{"exchange": label, "coin": "ERROR", "qty": 0, "usd": 0,
                 "error": resp.get("_error") or resp.get("retMsg", "unknown")}]
    results = []
    for acc in resp.get("result", {}).get("list", []):
        for c in acc.get("coin", []):
            bal = float(c.get("walletBalance", 0))
            usd = float(c.get("usdValue", 0))
            if bal > 0.0001:
                results.append({"exchange": label, "coin": c["coin"],
                                "qty": bal, "usd": usd})
    return results


def fetch_kucoin(key: str, secret: str, passphrase: str) -> list[dict]:
    ts = str(int(time.time() * 1000))
    method = "GET"
    path = "/api/v1/accounts"
    sign_str = f"{ts}{method}{path}"
    sig = base64.b64encode(
        hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).digest()
    ).decode()
    pp_sig = base64.b64encode(
        hmac.new(secret.encode(), passphrase.encode(), hashlib.sha256).digest()
    ).decode()
    resp = http_req(f"https://api.kucoin.com{path}", headers={
        "KC-API-KEY": key,
        "KC-API-SIGN": sig,
        "KC-API-TIMESTAMP": ts,
        "KC-API-PASSPHRASE": pp_sig,
        "KC-API-KEY-VERSION": "2",
    })
    if not resp or "_error" in resp or resp.get("code") != "200000":
        return [{"exchange": "KuCoin", "coin": "ERROR", "qty": 0, "usd": 0,
                 "error": resp.get("_error") or resp.get("msg", "unknown")}]
    results = []
    seen = {}
    for acc in resp.get("data", []):
        coin = acc.get("currency", "")
        bal = float(acc.get("balance", 0))
        if bal <= 0.0001:
            continue
        if coin in seen:
            seen[coin]["qty"] += bal
        else:
            seen[coin] = {"exchange": "KuCoin", "coin": coin, "qty": bal, "usd": 0}
    # fetch prices
    for coin, entry in seen.items():
        if coin == "USDT":
            entry["usd"] = entry["qty"]
            continue
        ticker = http_req(f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={coin}-USDT")
        if ticker and ticker.get("code") == "200000" and ticker.get("data"):
            price = float(ticker["data"].get("price", 0))
            entry["usd"] = entry["qty"] * price
        results.append(entry)
    if "USDT" in seen:
        results.append(seen["USDT"])
    return results


def fetch_gate(key: str, secret: str) -> list[dict]:
    ts = str(int(time.time()))
    method = "GET"
    path = "/api/v4/spot/accounts"
    query = ""
    body = ""
    body_hash = hashlib.sha512(body.encode()).hexdigest()
    sign_str = f"{method}\n{path}\n{query}\n{body_hash}\n{ts}"
    sig = hmac.new(secret.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
    resp = http_req(f"https://api.gateio.ws{path}", headers={
        "KEY": key,
        "SIGN": sig,
        "Timestamp": ts,
        "Content-Type": "application/json",
    })
    if not resp or "_error" in resp:
        err = resp.get("_error", "unknown") if resp else "no response"
        return [{"exchange": "Gate.io", "coin": "ERROR", "qty": 0, "usd": 0,
                 "error": err}]
    if isinstance(resp, dict) and resp.get("message"):
        return [{"exchange": "Gate.io", "coin": "ERROR", "qty": 0, "usd": 0,
                 "error": resp.get("message")}]
    results = []
    for acc in (resp if isinstance(resp, list) else []):
        coin = acc.get("currency", "")
        bal = float(acc.get("available", 0)) + float(acc.get("locked", 0))
        if bal <= 0.0001:
            continue
        usd = bal
        if coin != "USDT":
            ticker = http_req(f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={coin}_USDT")
            if ticker and isinstance(ticker, list) and ticker:
                price = float(ticker[0].get("last", 0))
                usd = bal * price
        results.append({"exchange": "Gate.io", "coin": coin, "qty": bal, "usd": usd})
    return results


# ═══════════════════════════════════════════════
#  Report builder
# ═══════════════════════════════════════════════

def fetch_all() -> list[dict]:
    all_holdings = []

    # Bybit accounts
    for suffix in ["", "2", "3"]:
        bk = ENV.get(f"BYBIT{suffix}_API_KEY", "")
        bs = ENV.get(f"BYBIT{suffix}_API_SECRET", "")
        if bk and bs:
            label = "Bybit" if not suffix else f"Bybit-{suffix}"
            all_holdings.extend(fetch_bybit(bk, bs, label))

    # KuCoin
    kk = ENV.get("KUCOIN_API_KEY", "")
    ks = ENV.get("KUCOIN_API_SECRET", "")
    kp = ENV.get("KUCOIN_PASSPHRASE", "")
    if kk and ks and kp:
        all_holdings.extend(fetch_kucoin(kk, ks, kp))

    # Gate.io
    gk = ENV.get("GATE_API_KEY", "")
    gs = ENV.get("GATE_API_SECRET", "")
    if gk and gs:
        all_holdings.extend(fetch_gate(gk, gs))

    return all_holdings


def build_report(holdings: list[dict]) -> str:
    errors = [h for h in holdings if h.get("error")]
    coins = [h for h in holdings if not h.get("error")]

    # Aggregate per coin
    per_coin: dict[str, dict] = {}
    for h in coins:
        c = h["coin"]
        if c not in per_coin:
            per_coin[c] = {"qty": 0.0, "usd": 0.0, "exchanges": []}
        per_coin[c]["qty"] += h["qty"]
        per_coin[c]["usd"] += h["usd"]
        per_coin[c]["exchanges"].append(f"{h['exchange']}: {h['qty']:.6f}")

    total_usd = sum(v["usd"] for v in per_coin.values())
    sorted_coins = sorted(per_coin.items(), key=lambda x: -x[1]["usd"])

    # Per exchange totals
    per_exchange: dict[str, float] = {}
    for h in coins:
        ex = h["exchange"]
        per_exchange[ex] = per_exchange.get(ex, 0) + h["usd"]

    # Build text
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"<b>📊 Portfolio Report</b>", f"<i>{now}</i>", ""]

    # Per exchange summary
    lines.append("<b>📱 Per Exchange:</b>")
    for ex, val in sorted(per_exchange.items(), key=lambda x: -x[1]):
        lines.append(f"  {ex}: <b>${val:,.2f}</b>")
    lines.append("")

    # Per coin breakdown
    lines.append("<b>💰 Per Coin:</b>")
    for coin, data in sorted_coins:
        if data["usd"] < 0.01:
            continue
        pct = (data["usd"] / total_usd * 100) if total_usd > 0 else 0
        lines.append(f"  <b>{coin}</b>: ${data['usd']:,.2f} ({pct:.1f}%)")
        for ex_detail in data["exchanges"]:
            lines.append(f"    └ {ex_detail}")
    lines.append("")

    # Totals
    lines.append(f"<b>💎 Total: ${total_usd:,.2f}</b>")
    if TOTAL_INVESTED > 0:
        pnl = total_usd - TOTAL_INVESTED
        pnl_pct = (pnl / TOTAL_INVESTED) * 100
        icon = "📈" if pnl >= 0 else "📉"
        lines.append(f"{icon} <b>P&L: ${pnl:+,.2f} ({pnl_pct:+.1f}%)</b>")
        lines.append(f"  Invested: ${TOTAL_INVESTED:,.2f}")

    if errors:
        lines.append("")
        lines.append("<b>⚠️ Errors:</b>")
        for e in errors:
            lines.append(f"  {e['exchange']}: {e.get('error', '?')}")

    return "\n".join(lines)


def build_cli_report(holdings: list[dict]) -> str:
    errors = [h for h in holdings if h.get("error")]
    coins = [h for h in holdings if not h.get("error")]

    per_coin: dict[str, dict] = {}
    for h in coins:
        c = h["coin"]
        if c not in per_coin:
            per_coin[c] = {"qty": 0.0, "usd": 0.0, "exchanges": {}}
        per_coin[c]["qty"] += h["qty"]
        per_coin[c]["usd"] += h["usd"]
        per_coin[c]["exchanges"][h["exchange"]] = h["qty"]

    total_usd = sum(v["usd"] for v in per_coin.values())
    sorted_coins = sorted(per_coin.items(), key=lambda x: -x[1]["usd"])

    per_exchange: dict[str, float] = {}
    for h in coins:
        per_exchange[h["exchange"]] = per_exchange.get(h["exchange"], 0) + h["usd"]

    lines = ["", "═══════════════════════════════════════════"]
    lines.append("  PORTFOLIO REPORT")
    lines.append(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("═══════════════════════════════════════════")

    lines.append("\n  Per Exchange:")
    for ex, val in sorted(per_exchange.items(), key=lambda x: -x[1]):
        lines.append(f"    {ex:<15} ${val:>10,.2f}")

    lines.append(f"\n  Per Coin:")
    lines.append(f"    {'Coin':<8} {'Value':>10}  {'%':>6}  Exchanges")
    lines.append(f"    {'─'*8} {'─'*10}  {'─'*6}  {'─'*25}")
    for coin, data in sorted_coins:
        if data["usd"] < 0.01:
            continue
        pct = (data["usd"] / total_usd * 100) if total_usd > 0 else 0
        ex_list = ", ".join(f"{k}:{v:.4f}" for k, v in data["exchanges"].items())
        lines.append(f"    {coin:<8} ${data['usd']:>9,.2f}  {pct:>5.1f}%  {ex_list}")

    lines.append(f"\n  {'─'*41}")
    lines.append(f"  TOTAL:          ${total_usd:>10,.2f}")
    if TOTAL_INVESTED > 0:
        pnl = total_usd - TOTAL_INVESTED
        pnl_pct = (pnl / TOTAL_INVESTED) * 100
        lines.append(f"  INVESTED:       ${TOTAL_INVESTED:>10,.2f}")
        lines.append(f"  P&L:            ${pnl:>+10,.2f}  ({pnl_pct:+.1f}%)")
    lines.append("═══════════════════════════════════════════\n")

    if errors:
        lines.append("  ERRORS:")
        for e in errors:
            lines.append(f"    {e['exchange']}: {e.get('error', '?')}")
        lines.append("")

    return "\n".join(lines)


# ── Entry ──
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon", action="store_true", help="Run daily report daemon")
    ap.add_argument("--json", action="store_true", help="Output raw JSON")
    args = ap.parse_args()

    if args.daemon:
        print(f"Portfolio report daemon — sends daily at {REPORT_HOUR}:00 UTC")
        tg("🟢 Portfolio report bot started")
        last_sent = ""
        while True:
            try:
                now = datetime.now(timezone.utc)
                today = now.strftime("%Y-%m-%d")
                if now.hour == REPORT_HOUR and last_sent != today:
                    holdings = fetch_all()
                    report = build_report(holdings)
                    tg(report)
                    print(f"[{today}] Report sent")
                    last_sent = today
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(300)
    else:
        holdings = fetch_all()
        if args.json:
            print(json.dumps(holdings, indent=2))
        else:
            print(build_cli_report(holdings))
            tg(build_report(holdings))
            print("  (Telegram report sent)" if TG_TOKEN else "  (No Telegram configured)")


if __name__ == "__main__":
    main()
