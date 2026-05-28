"""
wallet_scorer.py -- تقييم جودة المحافظ لبوت النسخ الذكي
يحلل تاريخ التداول لمحافظ Polymarket ويعطي كل محفظة درجة مركبة (0-100).

استخدام:
    python wallet_scorer.py 0xaddr1 0xaddr2         # تقييم محافظ محددة
    python wallet_scorer.py --generate              # تقييم + توليد smart_wallets.json
    python wallet_scorer.py --top 20                # أفضل 20 محفظة
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev
import requests

# ── مسارات ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = BASE_DIR / "smart_wallets.json"
DATA_API = "https://data-api.polymarket.com"
RATE_LIMIT_SECS = 0.5

SESSION = requests.Session()
PROXY = os.environ.get("HTTPS_PROXY", "")
if PROXY:
    SESSION.proxies = {"https": PROXY, "http": PROXY}

DEFAULT_WALLETS = [
    "0x751a2b86cab503496efd325c8344e10159349ea1",
    "0xd91cfb1b1b30b1b8a4b6e0b0f0f0f0f0f0f0f0f0",
    "0xa2b3c4d5e6f7081920a1b2c3d4e5f60718293040",
    "0x1234567890abcdef1234567890abcdef12345678",
    "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
]

def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def _parse_ts(ts_raw) -> datetime | None:
    if isinstance(ts_raw, str):
        try: return datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except Exception: return None
    if ts_raw > 1e12: return datetime.fromtimestamp(ts_raw / 1000, tz=timezone.utc)
    if ts_raw > 0: return datetime.fromtimestamp(ts_raw, tz=timezone.utc)
    return None


# ── 1. جلب تاريخ المحفظة ──
def fetch_wallet_history(address: str, limit: int = 100) -> list[dict]:
    """GET /activity — جلب آخر الصفقات."""
    url = f"{DATA_API}/activity?address={address}&limit={limit}"
    try:
        r = SESSION.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        _log(f"خطأ في جلب بيانات {address[:10]}...: {e}")
        return []
    trades = []
    for item in data:
        if item.get("type") != "TRADE":
            continue
        ts = _parse_ts(item.get("timestamp", 0))
        if not ts:
            continue
        trades.append({
            "market": item.get("title", item.get("market", "")),
            "side": item.get("side", ""), "price": float(item.get("price", 0)),
            "size": float(item.get("size", 0)), "timestamp": ts.isoformat(),
            "outcome": item.get("outcome", ""),
        })
    return trades


# ── 2. تقييم المحفظة ──
def score_wallet(address: str, trades: list[dict] | None = None) -> dict:
    """حساب درجة المحفظة المركبة (0-100)."""
    if trades is None:
        trades = fetch_wallet_history(address)
        time.sleep(RATE_LIMIT_SECS)

    result = {"address": address, "win_rate": 0.0, "profit_factor": 0.0,
              "avg_trade_size": 0.0, "total_trades": len(trades), "active_days": 0,
              "consistency": 1.0, "recency": 999, "composite_score": 0.0, "grade": "D"}
    if not trades:
        return result

    now = datetime.now(timezone.utc)
    sizes = [t["price"] * t["size"] for t in trades if t["size"] > 0]
    result["avg_trade_size"] = round(mean(sizes), 2) if sizes else 0.0

    # أيام النشاط وآخر نشاط
    days, timestamps = set(), []
    for t in trades:
        try:
            dt = datetime.fromisoformat(t["timestamp"])
            days.add(dt.strftime("%Y-%m-%d"))
            timestamps.append(dt)
        except Exception:
            pass
    result["active_days"] = len(days)
    if timestamps:
        latest = max(timestamps)
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        result["recency"] = (now - latest).days

    # نسبة الفوز والأرباح
    wins, losses, gross_profit, gross_loss = 0, 0, 0.0, 0.0
    daily_returns: dict[str, float] = {}
    for t in trades:
        side = t.get("side", "").upper()
        outcome = t.get("outcome", "").upper()
        if outcome not in ("YES", "NO"):
            continue
        price, usd = t["price"], t["price"] * t["size"] if t["size"] > 0 else t["price"]
        won = (side == "BUY" and outcome == "YES") or (side == "SELL" and outcome == "NO")
        if won:
            wins += 1
            pnl = usd * (1.0 - price)
            gross_profit += pnl
        else:
            losses += 1
            pnl = -usd * price
            gross_loss += abs(pnl)
        try:
            day = datetime.fromisoformat(t["timestamp"]).strftime("%Y-%m-%d")
            daily_returns[day] = daily_returns.get(day, 0.0) + pnl
        except Exception:
            pass

    total_resolved = wins + losses
    result["win_rate"] = round((wins / total_resolved * 100) if total_resolved else 0.0, 1)
    result["profit_factor"] = round((gross_profit / gross_loss) if gross_loss > 0 else 0.0, 2)

    # الاتساق
    if len(daily_returns) >= 2:
        vals = list(daily_returns.values())
        avg = mean([abs(v) for v in vals]) or 1.0
        result["consistency"] = round(min(stdev(vals) / avg, 3.0) / 3.0, 3)
    else:
        result["consistency"] = 0.5

    # ── الدرجة المركبة ──
    wr_score = min(result["win_rate"] / 100.0, 1.0) * 30
    pf_score = (min(result["profit_factor"], 3.0) / 3.0) * 15
    trades_score = (math.log(max(min(result["total_trades"], 200), 1)) / math.log(200)) * 10
    days_score = min(result["active_days"] / 30.0, 1.0) * 10
    consistency_score = (1.0 - result["consistency"]) * 10
    recency_score = (1.0 - result["recency"] / 30.0) * 10 if result["recency"] <= 30 else 0.0
    sz = result["avg_trade_size"]
    size_score = 15.0 if sz >= 500 else 10.0 if sz >= 100 else (sz / 100.0) * 10 if sz >= 25 else 2.0

    composite = wr_score + pf_score + trades_score + days_score + \
                consistency_score + recency_score + size_score
    result["composite_score"] = round(min(composite, 100.0), 1)
    s = result["composite_score"]
    result["grade"] = "A" if s >= 80 else "B" if s >= 60 else "C" if s >= 40 else "D"
    return result


# ── 3. ترتيب المحافظ ──
def rank_wallets(addresses: list[str]) -> list[dict]:
    """تقييم وترتيب قائمة محافظ حسب الدرجة."""
    results = []
    for i, addr in enumerate(addresses, 1):
        _log(f"تقييم المحفظة {i}/{len(addresses)}: {addr[:12]}...")
        sc = score_wallet(addr)
        results.append(sc)
        _log(f"  → درجة: {sc['composite_score']} ({sc['grade']}) | WR={sc['win_rate']}%")
    results.sort(key=lambda x: x["composite_score"], reverse=True)
    return results


# ── 4. فلتر المحافظ الممتازة ──
def filter_s_tier(addresses: list[str], min_score: int = 70) -> list[dict]:
    """ارجاع محافظ A و B فقط."""
    ranked = rank_wallets(addresses)
    filtered = [w for w in ranked if w["composite_score"] >= min_score]
    _log(f"تم اختيار {len(filtered)}/{len(ranked)} محفظة بدرجة >= {min_score}")
    return filtered


# ── 5. توليد smart_wallets.json ──
def generate_smart_wallets_json(addresses: list[str], output_path: str | None = None) -> str:
    """تصدير الملف بالصيغة المطلوبة لبوت النسخ الذكي."""
    path = Path(output_path) if output_path else OUTPUT_FILE
    ranked = filter_s_tier(addresses)
    if not ranked:
        _log("تحذير: لا توجد محافظ مؤهلة — يتم حفظ الكل كاحتياط")
        ranked = rank_wallets(addresses)
    export = [{"address": w["address"], "name": f"wallet_{i}",
               "win_rate": w["win_rate"], "profit_factor": w["profit_factor"],
               "total_trades": w["total_trades"], "avg_trade_size": w["avg_trade_size"]}
              for i, w in enumerate(ranked, 1)]
    path.write_text(json.dumps(export, indent=2))
    _log(f"تم حفظ {len(export)} محفظة في {path}")
    return str(path)


# ── CLI ──
def _print_table(results: list[dict]) -> None:
    print(f"\n{'العنوان':<14} {'الدرجة':>6} {'#':>2} {'WR%':>6} {'PF':>5} "
          f"{'الصفقات':>7} {'الحجم$':>7} {'الأيام':>5} {'آخر':>4}")
    print("─" * 75)
    for w in results:
        print(f"{w['address'][:12]}.. {w['composite_score']:>5.1f} {w['grade']:>2} "
              f"{w['win_rate']:>5.1f}% {w['profit_factor']:>5.2f} "
              f"{w['total_trades']:>7} {w['avg_trade_size']:>7.1f} "
              f"{w['active_days']:>5} {w['recency']:>4}d")

def main():
    parser = argparse.ArgumentParser(description="Polymarket Wallet Scorer — تقييم المحافظ")
    parser.add_argument("addresses", nargs="*", help="عناوين المحافظ للتقييم")
    parser.add_argument("--generate", action="store_true", help="توليد smart_wallets.json")
    parser.add_argument("--top", type=int, default=0, help="عرض أفضل N محفظة")
    parser.add_argument("--output", type=str, default=None, help="مسار ملف الإخراج")
    args = parser.parse_args()
    addrs = args.addresses or DEFAULT_WALLETS
    if args.generate:
        path = generate_smart_wallets_json(addrs, args.output)
        print(f"\nتم التوليد: {path}")
    elif args.top:
        _print_table(rank_wallets(addrs)[:args.top])
    elif args.addresses:
        _print_table(rank_wallets(addrs))
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
