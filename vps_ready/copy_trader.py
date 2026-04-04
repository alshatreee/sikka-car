"""
copy_trader.py — يراقب صفقات sharky6999 ويكررها تلقائياً
نسبة الفوز: 99.3% | الربح: $800K+

الاستخدام:
    python copy_trader.py          # تشغيل المراقبة والنسخ
    python copy_trader.py --setup  # إعداد الموافقات (approve USDC)
    python copy_trader.py --check  # فحص رصيد المحفظة
    python copy_trader.py --swap   # تحويل USDC → USDC.e
"""

import sys, json, time, requests
from pathlib import Path
from datetime import datetime
import os

# ── تحديد المسارات تلقائياً (Windows أو Linux) ──
if os.name == "nt":  # Windows
    BASE_DIR = Path(r"C:\Users\xman9\Desktop")
else:  # Linux (VPS)
    BASE_DIR = Path("/root/bots")
    BASE_DIR.mkdir(parents=True, exist_ok=True)

ENV_FILE2   = BASE_DIR / ".env2"
SEEN_FILE   = BASE_DIR / "copy_log.json"

SHARKY_WALLET = "0x751a2b86cab503496efd325c8344e10159349ea1"
DATA_API      = "https://data-api.polymarket.com"
CLOB_API      = "https://clob.polymarket.com"
GAMMA_API     = "https://gamma-api.polymarket.com"

TRADE_SIZE_USD = 5.0
POLL_SECS      = 120
MAX_PRICE      = 0.97
MIN_PRICE      = 0.50

# عناوين العقود على Polygon
USDC_E        = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
USDC_NATIVE   = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
CTF_EXCHANGE  = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EX   = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
SWAP_ROUTER   = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"
RPCS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://polygon.llamarpc.com",
]

ERC20_ABI = [
    {"name":"balanceOf","type":"function","inputs":[{"name":"owner","type":"address"}],
     "outputs":[{"name":"","type":"uint256"}],"stateMutability":"view"},
    {"name":"approve","type":"function","inputs":[{"name":"spender","type":"address"},
     {"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}],
     "stateMutability":"nonpayable"},
    {"name":"allowance","type":"function","inputs":[{"name":"owner","type":"address"},
     {"name":"spender","type":"address"}],"outputs":[{"name":"","type":"uint256"}],
     "stateMutability":"view"},
]


# ── تحميل .env2 ──
def load_env(path):
    env = {}
    if path.exists():
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

ENV2 = load_env(ENV_FILE2)
PRIVATE_KEY2 = ENV2.get("COPY_PRIVATE_KEY", "").strip()
if not PRIVATE_KEY2.startswith("0x"):
    PRIVATE_KEY2 = "0x" + PRIVATE_KEY2


def get_wallet():
    from eth_account import Account
    return Account.from_key(PRIVATE_KEY2).address


# ── Web3 ──
def get_w3():
    from web3 import Web3
    for rpc in RPCS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
            if w3.is_connected():
                return w3
        except Exception:
            continue
    return None


# ── بيانات sharky6999 ──
def fetch_sharky_trades(limit=30):
    url = f"{DATA_API}/activity?user={SHARKY_WALLET}&limit={limit}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


# ── تتبع الصفقات المرئية ──
def load_state():
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text())
        except Exception:
            pass
    return {"seen_hashes": [], "trades": [], "last_check": 0}


def save_state(state):
    state["seen_hashes"] = state["seen_hashes"][-500:]
    SEEN_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# ── CLOB Client ──
def get_clob_client():
    from py_clob_client.client import ClobClient
    from py_clob_client.constants import POLYGON

    pk_clean = PRIVATE_KEY2[2:] if PRIVATE_KEY2.startswith("0x") else PRIVATE_KEY2
    client = ClobClient(
        host=CLOB_API,
        key=pk_clean,
        chain_id=POLYGON,
        signature_type=0,
    )
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    return client


# ── إعداد الموافقات ──
def setup_approvals(wallet):
    from web3 import Web3
    print("━" * 50)
    print("  🔐 إعداد موافقات USDC لـ Polymarket")
    print("━" * 50)

    w3 = get_w3()
    if not w3:
        print("❌ فشل الاتصال بـ Polygon")
        return False

    usdc_e      = w3.eth.contract(address=Web3.to_checksum_address(USDC_E),      abi=ERC20_ABI)
    usdc_native = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)

    bal_e      = usdc_e.functions.balanceOf(wallet).call()
    bal_native = usdc_native.functions.balanceOf(wallet).call()
    pol        = w3.eth.get_balance(wallet)

    print(f"USDC.e  (Polymarket): ${bal_e/1e6:.2f}")
    print(f"USDC    (Binance):    ${bal_native/1e6:.2f}")
    print(f"POL:                  {w3.from_wei(pol, 'ether'):.4f}")

    if bal_e == 0 and bal_native > 0:
        print()
        print("⚠️  عندك USDC عادية فقط وتحتاج USDC.e")
        print("   الحل: شغّل هذا الأمر لتحويلها تلقائياً:")
        print(f"   python copy_trader.py --swap")
        return False

    if bal_e == 0 and bal_native == 0:
        print("⚠️  لا يوجد USDC. أرسل USDC من Binance (شبكة Polygon) إلى:")
        print(f"   {wallet}")
        return False

    usdc = usdc_e
    bal  = bal_e

    MAX_UINT = 2**256 - 1
    gas_price = int(w3.eth.gas_price * 1.2)
    nonce = w3.eth.get_transaction_count(wallet)

    for name, addr in [("CTF Exchange", CTF_EXCHANGE), ("NegRisk Exchange", NEG_RISK_EX)]:
        cs_addr = Web3.to_checksum_address(addr)
        allowance = usdc.functions.allowance(wallet, cs_addr).call()
        if allowance < bal:
            print(f"⏳ موافقة على {name}...")
            tx = usdc.functions.approve(cs_addr, MAX_UINT).build_transaction({
                "from": wallet, "nonce": nonce,
                "gas": 100_000, "gasPrice": gas_price,
            })
            signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY2)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"✅ TX: {tx_hash.hex()}")
            w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            print(f"✅ تم {name}")
            nonce += 1
        else:
            print(f"✅ {name}: مُفعّل مسبقاً")

    return True


# ── تحويل USDC → USDC.e عبر Uniswap ──
def swap_usdc_to_usdce(wallet):
    from web3 import Web3
    print("━" * 50)
    print("  🔄 تحويل USDC → USDC.e")
    print("━" * 50)

    w3 = get_w3()
    if not w3:
        print("❌ فشل الاتصال")
        return False

    usdc_native = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=ERC20_ABI)
    bal = usdc_native.functions.balanceOf(wallet).call()
    print(f"USDC المتاح: ${bal/1e6:.2f}")

    if bal == 0:
        print("❌ لا يوجد USDC لتحويلها")
        return False

    amount_in = bal
    nonce = w3.eth.get_transaction_count(wallet)
    gas_price = int(w3.eth.gas_price * 1.3)

    router_cs = Web3.to_checksum_address(SWAP_ROUTER)
    allowance = usdc_native.functions.allowance(wallet, router_cs).call()
    if allowance < amount_in:
        print("⏳ موافقة Uniswap...")
        tx = usdc_native.functions.approve(router_cs, 2**256-1).build_transaction({
            "from": wallet, "nonce": nonce,
            "gas": 100_000, "gasPrice": gas_price,
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY2)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        print(f"✅ Approve: {tx_hash.hex()}")
        nonce += 1

    SWAP_ABI = [{
        "name": "exactInputSingle", "type": "function",
        "inputs": [{"name": "params", "type": "tuple", "components": [
            {"name": "tokenIn",           "type": "address"},
            {"name": "tokenOut",          "type": "address"},
            {"name": "fee",               "type": "uint24"},
            {"name": "recipient",         "type": "address"},
            {"name": "amountIn",          "type": "uint256"},
            {"name": "amountOutMinimum",  "type": "uint256"},
            {"name": "sqrtPriceLimitX96", "type": "uint160"},
        ]}],
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
    }]
    router = w3.eth.contract(address=router_cs, abi=SWAP_ABI)
    min_out = int(amount_in * 0.995)

    print(f"⏳ تحويل ${amount_in/1e6:.2f} USDC → USDC.e ...")
    swap_params = (
        Web3.to_checksum_address(USDC_NATIVE),
        Web3.to_checksum_address(USDC_E),
        100,
        wallet,
        amount_in,
        min_out,
        0,
    )
    try:
        tx = router.functions.exactInputSingle(swap_params).build_transaction({
            "from": wallet, "nonce": nonce,
            "gas": 300_000, "gasPrice": gas_price, "value": 0,
        })
        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY2)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status == 1:
            print(f"✅ تم التحويل! TX: {tx_hash.hex()}")
            print("   الآن شغّل: python copy_trader.py --setup")
            return True
        else:
            print(f"❌ فشل TX: {tx_hash.hex()}")
            return False
    except Exception as e:
        print(f"❌ خطأ في Swap: {e}")
        return False


# ── فحص الرصيد ──
def check_balance(wallet):
    from web3 import Web3
    w3 = get_w3()
    if not w3:
        print("❌ فشل الاتصال")
        return

    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E),
        abi=ERC20_ABI
    )
    bal = usdc.functions.balanceOf(wallet).call()
    pol = w3.eth.get_balance(wallet)
    print(f"\n📊 رصيد محفظة النسخ ({wallet[:10]}...)")
    print(f"   USDC.e: ${bal/1e6:.2f}")
    print(f"   POL:    {w3.from_wei(pol, 'ether'):.4f}")

    try:
        client = get_clob_client()
        poly_bal = client.get_balance()
        print(f"   Polymarket: {poly_bal}")
    except Exception as e:
        print(f"   Polymarket: {e}")


# ── تنفيذ الصفقة ──
def place_copy_order(client, trade_info):
    try:
        from py_clob_client.clob_types import OrderArgs
        try:
            from py_clob_client.clob_types import BUY
            side = BUY
        except ImportError:
            side = "BUY"

        token_id = trade_info["token_id"]
        price    = trade_info["price"]
        size     = trade_info["size"]
        title    = trade_info["title"]
        outcome  = trade_info["outcome"]

        print(f"\n🎯 نسخ صفقة:")
        print(f"   📋 {title}")
        print(f"   نتيجة: {outcome} @ ${price:.3f}")
        print(f"   الحجم: {size:.2f} (💵 ${TRADE_SIZE_USD})")

        order = client.create_and_post_order(OrderArgs(
            token_id=token_id,
            price=round(price, 4),
            size=round(size, 2),
            side=side,
        ))
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"   ✅ [{ts}] تم! الأمر: {order}")
        return True, str(order)
    except Exception as e:
        print(f"   ❌ فشل: {str(e)[:120]}")
        return False, str(e)


# ── الحلقة الرئيسية ──
def run_copy_loop(wallet):
    print("━" * 60)
    print("  👁️ نظام نسخ صفقات sharky6999 — نشط")
    print(f"  محفظتنا: {wallet}")
    print(f"  حجم الصفقة: ${TRADE_SIZE_USD} | فحص كل {POLL_SECS//60} دقيقة")
    print("━" * 60)

    client = get_clob_client()
    state = load_state()
    seen = set(state.get("seen_hashes", []))

    # في أول تشغيل، نعلّم الصفقات الموجودة كـ "رأيناها" حتى لا ننسخ القديمة
    if not state.get("seen_hashes"):
        print("⏳ التشغيل الأول: تحميل الصفقات الحالية...")
        try:
            initial = fetch_sharky_trades(50)
            for t in initial:
                h = t.get("transactionHash", "")
                if h:
                    seen.add(h)
            state["seen_hashes"] = list(seen)
            save_state(state)
            print(f"✅ تم تسجيل {len(seen)} صفقة موجودة. سننسخ الجديدة فقط.")
        except Exception as e:
            print(f"⚠️ {e}")
        print()

    cycle = 0
    while True:
        cycle += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now_str}] 🔄 فحص #{cycle} — مراقبة sharky6999...")

        try:
            trades = fetch_sharky_trades(30)
            new_trades = []

            for t in trades:
                tx_hash = t.get("transactionHash", "")
                if not tx_hash or tx_hash in seen:
                    continue
                if t.get("type") != "TRADE":
                    seen.add(tx_hash)
                    continue
                if t.get("side") != "BUY":
                    seen.add(tx_hash)
                    continue

                price = float(t.get("price", 0))
                token_id = t.get("asset", "")
                outcome = t.get("outcome", "")
                title = t.get("title", "")

                if not (MIN_PRICE <= price <= MAX_PRICE):
                    print(f"   ⏭ تجاوز (سعر {price:.2f} خارج النطاق): {title} → {outcome}")
                    seen.add(tx_hash)
                    continue

                if not token_id:
                    seen.add(tx_hash)
                    continue

                size = round(TRADE_SIZE_USD / price, 2)
                new_trades.append({
                    "tx_hash": tx_hash,
                    "token_id": token_id,
                    "price": price,
                    "size": size,
                    "outcome": outcome,
                    "title": title,
                    "timestamp": t.get("timestamp", 0),
                })

            if not new_trades:
                print(f"   ✔️ لا توجد صفقات جديدة")
            else:
                print(f"   🆕 وجدنا {len(new_trades)} صفقة جديدة!")
                for tr in sorted(new_trades, key=lambda x: x["timestamp"]):
                    ok, result = place_copy_order(client, tr)
                    seen.add(tr["tx_hash"])
                    state.setdefault("trades", []).append({
                        "time": now_str,
                        "title": tr["title"],
                        "outcome": tr["outcome"],
                        "price": tr["price"],
                        "size": tr["size"],
                        "success": ok,
                        "result": result[:100],
                    })
                    time.sleep(2)

            state["seen_hashes"] = list(seen)
            state["last_check"] = int(time.time())
            save_state(state)

        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ خطأ شبكة: {e}")
        except Exception as e:
            print(f"   ❌ خطأ: {e}")
            import traceback
            traceback.print_exc()

        print(f"   ⏳ الانتظار {POLL_SECS//60} دقيقة...")
        time.sleep(POLL_SECS)


# ── نقطة الدخول ──
def main():
    if not PRIVATE_KEY2 or PRIVATE_KEY2 == "0x":
        print("❌ COPY_PRIVATE_KEY غير موجود في .env2")
        print(f"   الملف: {ENV_FILE2}")
        return

    wallet = get_wallet()

    if "--check" in sys.argv:
        check_balance(wallet)
        return

    if "--swap" in sys.argv:
        swap_usdc_to_usdce(wallet)
        return

    if "--setup" in sys.argv:
        setup_approvals(wallet)
        return

    run_copy_loop(wallet)


if __name__ == "__main__":
    main()
