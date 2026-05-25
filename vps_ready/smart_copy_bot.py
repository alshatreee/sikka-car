"""
smart_copy_bot.py — بوت نسخ ذكي يتابع 5-10 محافظ ويشتري فقط عند توافق 2+
الاستخدام:
    python smart_copy_bot.py --paper   # وضع تجريبي (افتراضي)
    python smart_copy_bot.py --live    # تنفيذ حقيقي
    python smart_copy_bot.py --check   # عرض الحالة
"""

import sys, json, time, requests, argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import os

# ── مسارات ──
if os.name == "nt":
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE = BASE_DIR / ".env2"
STATE_FILE = BASE_DIR / "smart_copy_state.json"
WALLETS_FILE = BASE_DIR / "smart_wallets.json"

DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

POLL_SECS = 30
PNL_CHECK_SECS = 60
MAX_POSITIONS = 8
MAX_DAILY_TRADES = 15
MAX_DAILY_LOSS = 15.0
SL_PCT = 0.30
TP_PCT = 0.50
MAX_HOLD_HOURS = 48
CONSENSUS_WINDOW_MIN = 10
MIN_WIN_RATE = 60
MIN_PROFIT_FACTOR = 1.5
MIN_PRICE = 0.10
MAX_PRICE = 0.90
MIN_VOLUME = 3000

SIZING = {2: 3.0, 3: 5.0}


def load_env(path):
    env = {}
    if path.exists():
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


ENV = load_env(ENV_FILE)
PRIVATE_KEY = ENV.get("COPY_PRIVATE_KEY", "").strip()
if PRIVATE_KEY and not PRIVATE_KEY.startswith("0x"):
    PRIVATE_KEY = "0x" + PRIVATE_KEY
TG_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = ENV.get("TELEGRAM_CHAT_ID", "")
PROXY = ENV.get("HTTPS_PROXY", "")

SESSION = requests.Session()
if PROXY:
    SESSION.proxies = {"https": PROXY, "http": PROXY}


# ── Telegram ──
def tg_send(msg):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        SESSION.post(url, json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception:
        pass


# ── محافظ ──
def load_wallets():
    if not WALLETS_FILE.exists():
        default = [
            {"address": "0x751a2b86cab503496efd325c8344e10159349ea1", "name": "sharky6999", "win_rate": 99.3, "profit_factor": 8.0, "total_trades": 2400, "avg_trade_size": 500},
            {"address": "0xd91cfb1b1b30b1b8a4b6e0b0f0f0f0f0f0f0f0f0", "name": "whale_alpha", "win_rate": 72.0, "profit_factor": 2.4, "total_trades": 800, "avg_trade_size": 300},
            {"address": "0xa2b3c4d5e6f7081920a1b2c3d4e5f60718293040", "name": "degen_pro", "win_rate": 68.5, "profit_factor": 1.9, "total_trades": 1200, "avg_trade_size": 200},
            {"address": "0x1234567890abcdef1234567890abcdef12345678", "name": "poly_king", "win_rate": 65.0, "profit_factor": 1.7, "total_trades": 600, "avg_trade_size": 150},
            {"address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd", "name": "signal_master", "win_rate": 63.0, "profit_factor": 1.6, "total_trades": 900, "avg_trade_size": 250},
        ]
        WALLETS_FILE.write_text(json.dumps(default, indent=2))
        print(f"تم إنشاء {WALLETS_FILE} بمحافظ افتراضية — عدّلها حسب حاجتك")
    return json.loads(WALLETS_FILE.read_text())


def filter_wallets(wallets):
    return [w for w in wallets if w["win_rate"] >= MIN_WIN_RATE and w["profit_factor"] >= MIN_PROFIT_FACTOR]


# ── حالة ──
def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"positions": [], "daily_trades": 0, "daily_pnl": 0.0,
            "day": "", "seen_txs": [], "signals": []}


def save_state(state):
    state["seen_txs"] = state["seen_txs"][-1000:]
    state["signals"] = state["signals"][-200:]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def reset_daily(state):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("day") != today:
        state["day"] = today
        state["daily_trades"] = 0
        state["daily_pnl"] = 0.0
    return state


# ── بيانات السوق ──
def fetch_wallet_activity(address):
    try:
        url = f"{DATA_API}/activity?address={address}&limit=20"
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def get_market_info(condition_id):
    try:
        url = f"{GAMMA_API}/markets?condition_id={condition_id}&closed=false"
        r = SESSION.get(url, timeout=10)
        data = r.json()
        if data:
            m = data[0]
            return {
                "volume": float(m.get("volume", 0) or 0),
                "end_date": m.get("end_date_iso", ""),
                "slug": m.get("slug", ""),
                "question": m.get("question", m.get("title", "")),
            }
    except Exception:
        pass
    return None


def get_market_by_token(token_id):
    try:
        url = f"{CLOB_API}/markets/{token_id}"
        r = SESSION.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ── CLOB Client ──
def get_clob_client():
    from py_clob_client.client import ClobClient
    from py_clob_client.constants import POLYGON
    pk = PRIVATE_KEY[2:] if PRIVATE_KEY.startswith("0x") else PRIVATE_KEY
    client = ClobClient(host=CLOB_API, key=pk, chain_id=POLYGON, signature_type=0)
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    return client


# ── تنفيذ ──
def execute_trade(token_id, price, size_usd, mode):
    size = round(size_usd / price, 2)
    if mode == "paper":
        return True, f"PAPER: {size} shares @ {price:.3f}"
    try:
        from py_clob_client.clob_types import OrderArgs
        try:
            from py_clob_client.clob_types import BUY
            side = BUY
        except ImportError:
            side = "BUY"
        client = get_clob_client()
        order = client.create_and_post_order(OrderArgs(
            token_id=token_id, price=round(price, 4), size=size, side=side))
        return True, str(order)
    except Exception as e:
        return False, str(e)[:150]


def get_token_price(token_id):
    try:
        url = f"{CLOB_API}/price?token_id={token_id}&side=sell"
        r = SESSION.get(url, timeout=10)
        if r.status_code == 200:
            return float(r.json().get("price", 0))
    except Exception:
        pass
    return 0.0


# ── كشف التوافق ──
def detect_consensus(wallets, seen_txs):
    now = datetime.now(timezone.utc)
    window = timedelta(minutes=CONSENSUS_WINDOW_MIN)
    market_signals = defaultdict(list)

    for w in wallets:
        activities = fetch_wallet_activity(w["address"])
        for act in activities:
            tx = act.get("transactionHash", "") or act.get("id", "")
            if not tx or tx in seen_txs:
                continue
            if act.get("type") != "TRADE" or act.get("side") != "BUY":
                continue
            price = float(act.get("price", 0))
            if not (MIN_PRICE <= price <= MAX_PRICE):
                continue
            ts_raw = act.get("timestamp", 0)
            if isinstance(ts_raw, str):
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except Exception:
                    continue
            else:
                ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc) if ts_raw > 1e9 else \
                     datetime.fromtimestamp(ts_raw / 1000, tz=timezone.utc) if ts_raw > 1e12 else None
                if not ts:
                    continue
            if now - ts > window:
                continue

            token_id = act.get("asset", "") or act.get("token_id", "")
            outcome = act.get("outcome", "")
            title = act.get("title", act.get("market", ""))
            condition_id = act.get("conditionId", act.get("condition_id", ""))

            if not token_id:
                continue

            key = f"{token_id}_{outcome}"
            market_signals[key].append({
                "wallet": w["name"], "address": w["address"],
                "price": price, "token_id": token_id,
                "outcome": outcome, "title": title,
                "condition_id": condition_id, "tx": tx, "ts": ts,
            })
        time.sleep(0.5)

    consensus = []
    for key, signals in market_signals.items():
        unique_wallets = set(s["wallet"] for s in signals)
        if len(unique_wallets) >= 2:
            consensus.append({
                "key": key,
                "token_id": signals[0]["token_id"],
                "outcome": signals[0]["outcome"],
                "title": signals[0]["title"],
                "condition_id": signals[0]["condition_id"],
                "avg_price": sum(s["price"] for s in signals) / len(signals),
                "wallet_count": len(unique_wallets),
                "wallets": list(unique_wallets),
                "txs": [s["tx"] for s in signals],
            })
    return consensus


def validate_market(condition_id, token_id):
    info = get_market_info(condition_id) if condition_id else None
    if not info:
        info = get_market_by_token(token_id)
        if info:
            info = {"volume": float(info.get("volume", 0) or 0),
                    "end_date": info.get("end_date_iso", ""),
                    "slug": info.get("slug", ""), "question": info.get("question", "")}
    if not info:
        return False, "لا يمكن جلب بيانات السوق"
    if info["volume"] < MIN_VOLUME:
        return False, f"حجم منخفض: ${info['volume']:.0f}"
    if info.get("end_date"):
        try:
            end = datetime.fromisoformat(info["end_date"].replace("Z", "+00:00"))
            if end - datetime.now(timezone.utc) < timedelta(hours=12):
                return False, "السوق ينتهي خلال 12 ساعة"
        except Exception:
            pass
    return True, info.get("question", "")


# ── إدارة المراكز ──
def check_positions(state, mode):
    closed = []
    now = datetime.now(timezone.utc)
    for pos in state["positions"]:
        entry_price = pos["entry_price"]
        token_id = pos["token_id"]
        entry_time = datetime.fromisoformat(pos["entry_time"])
        current_price = get_token_price(token_id)
        if current_price <= 0:
            continue

        pnl_pct = (current_price - entry_price) / entry_price
        hold_hours = (now - entry_time).total_seconds() / 3600
        reason = None

        if pnl_pct <= -SL_PCT:
            reason = f"SL ({pnl_pct*100:.1f}%)"
        elif pnl_pct >= TP_PCT:
            reason = f"TP ({pnl_pct*100:.1f}%)"
        elif hold_hours >= MAX_HOLD_HOURS:
            reason = f"MAX_HOLD ({hold_hours:.0f}h)"

        if reason:
            pnl_usd = pos["size_usd"] * pnl_pct
            state["daily_pnl"] += pnl_usd
            msg = (f"{'EXIT'} | {pos['title'][:40]}\n"
                   f"سبب: {reason} | PnL: ${pnl_usd:.2f}\n"
                   f"دخول: {entry_price:.3f} → حالي: {current_price:.3f}")
            print(f"   EXIT: {reason} | {pos['title'][:30]} | ${pnl_usd:.2f}")
            tg_send(msg)
            closed.append(pos)

    for c in closed:
        state["positions"].remove(c)
    return state


# ── عرض الحالة ──
def show_status(state):
    state = reset_daily(state)
    print("━" * 55)
    print("  حالة بوت النسخ الذكي")
    print("━" * 55)
    print(f"  اليوم: {state['day']}")
    print(f"  صفقات اليوم: {state['daily_trades']}/{MAX_DAILY_TRADES}")
    print(f"  PnL اليوم: ${state['daily_pnl']:.2f}")
    print(f"  مراكز مفتوحة: {len(state['positions'])}/{MAX_POSITIONS}")
    print()
    if state["positions"]:
        for p in state["positions"]:
            cur = get_token_price(p["token_id"])
            pnl = ((cur - p["entry_price"]) / p["entry_price"] * 100) if cur > 0 else 0
            print(f"  {p['title'][:35]} | ${p['size_usd']:.0f} | {p['entry_price']:.3f}→{cur:.3f} ({pnl:+.1f}%)")
    else:
        print("  لا توجد مراكز مفتوحة")
    wallets = filter_wallets(load_wallets())
    print(f"\n  محافظ مؤهلة: {len(wallets)}")
    for w in wallets:
        print(f"    {w['name']}: WR={w['win_rate']}% PF={w['profit_factor']}")


# ── الحلقة الرئيسية ──
def run_loop(mode):
    wallets = filter_wallets(load_wallets())
    if not wallets:
        print("لا توجد محافظ مؤهلة في smart_wallets.json")
        return

    print("━" * 55)
    print(f"  بوت النسخ الذكي — وضع {'تجريبي' if mode == 'paper' else 'حقيقي'}")
    print(f"  محافظ: {len(wallets)} | فحص كل {POLL_SECS}ث | توافق 2+")
    print("━" * 55)
    tg_send(f"بوت النسخ الذكي شغّال | وضع: {mode} | محافظ: {len(wallets)}")

    state = load_state()
    state = reset_daily(state)
    seen_txs = set(state.get("seen_txs", []))
    last_pnl_check = 0
    cycle = 0

    while True:
        cycle += 1
        now = time.time()
        now_str = datetime.now().strftime("%H:%M:%S")
        state = reset_daily(state)

        # فحص PnL
        if now - last_pnl_check >= PNL_CHECK_SECS and state["positions"]:
            state = check_positions(state, mode)
            last_pnl_check = now
            if state["daily_pnl"] <= -MAX_DAILY_LOSS:
                msg = f"وقف الخسارة اليومي! ${state['daily_pnl']:.2f} — البوت متوقف"
                print(f"\n   {msg}")
                tg_send(msg)
                save_state(state)
                return

        print(f"\n[{now_str}] فحص #{cycle}")

        # فحص الحدود
        if state["daily_trades"] >= MAX_DAILY_TRADES:
            print("   وصلنا الحد اليومي للصفقات")
            time.sleep(POLL_SECS)
            continue
        if len(state["positions"]) >= MAX_POSITIONS:
            print("   الحد الأقصى للمراكز")
            time.sleep(POLL_SECS)
            continue

        try:
            consensus_list = detect_consensus(wallets, seen_txs)
            if not consensus_list:
                print("   لا توجد إشارات توافق")
            else:
                for signal in consensus_list:
                    for tx in signal["txs"]:
                        seen_txs.add(tx)

                    wc = signal["wallet_count"]
                    size_usd = SIZING.get(wc, SIZING[3]) if wc >= 3 else SIZING.get(wc, 0)
                    if size_usd == 0:
                        continue

                    # فحص السوق
                    valid, market_info = validate_market(signal["condition_id"], signal["token_id"])
                    if not valid:
                        print(f"   تخطي: {market_info}")
                        continue

                    # تكرار؟
                    existing = [p for p in state["positions"] if p["token_id"] == signal["token_id"]]
                    if existing:
                        print(f"   موجود مسبقاً: {signal['title'][:30]}")
                        continue

                    # حدود
                    if state["daily_trades"] >= MAX_DAILY_TRADES or len(state["positions"]) >= MAX_POSITIONS:
                        break

                    title_display = signal["title"][:40] or market_info[:40]
                    msg = (f"{'SIGNAL'} | {wc} محافظ\n"
                           f"{title_display}\n"
                           f"{signal['outcome']} @ {signal['avg_price']:.3f} | ${size_usd}\n"
                           f"محافظ: {', '.join(signal['wallets'])}")
                    print(f"   SIGNAL: {wc} محافظ → {signal['outcome']} @ {signal['avg_price']:.3f}")
                    tg_send(msg)

                    ok, result = execute_trade(signal["token_id"], signal["avg_price"], size_usd, mode)
                    if ok:
                        state["positions"].append({
                            "token_id": signal["token_id"],
                            "outcome": signal["outcome"],
                            "title": title_display,
                            "entry_price": signal["avg_price"],
                            "size_usd": size_usd,
                            "wallet_count": wc,
                            "entry_time": datetime.now(timezone.utc).isoformat(),
                        })
                        state["daily_trades"] += 1
                        trade_msg = f"TRADE | {title_display}\n${size_usd} | {result[:60]}"
                        print(f"   TRADE: ${size_usd} | {result[:50]}")
                        tg_send(trade_msg)
                    else:
                        print(f"   FAIL: {result[:60]}")
                        tg_send(f"FAIL | {result[:80]}")

                    state["signals"].append({
                        "time": now_str, "title": title_display,
                        "wallets": signal["wallets"], "price": signal["avg_price"],
                        "executed": ok,
                    })
                    time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"   خطأ شبكة: {str(e)[:80]}")
        except Exception as e:
            print(f"   خطأ: {str(e)[:100]}")

        state["seen_txs"] = list(seen_txs)
        save_state(state)
        time.sleep(POLL_SECS)


def main():
    parser = argparse.ArgumentParser(description="Smart Copy Trading Bot")
    parser.add_argument("--paper", action="store_true", help="وضع تجريبي (افتراضي)")
    parser.add_argument("--live", action="store_true", help="تنفيذ حقيقي")
    parser.add_argument("--check", action="store_true", help="عرض الحالة")
    args = parser.parse_args()

    if args.check:
        show_status(load_state())
        return

    if args.live:
        if not PRIVATE_KEY or PRIVATE_KEY == "0x":
            print("COPY_PRIVATE_KEY غير موجود في .env2")
            return
        mode = "live"
    else:
        mode = "paper"

    run_loop(mode)


if __name__ == "__main__":
    main()
