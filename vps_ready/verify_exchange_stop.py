#!/usr/bin/env python3
"""
verify_exchange_stop.py — يتحقق أن "الوقف على المنصّة" (Bybit spot) يعمل فعلاً.

يفعل بالترتيب:
  1) يتصل بـ Bybit (testnet إن كان BYBIT_TESTNET=true، وإلا الحقيقي بتأكيد صريح)
  2) يشتري كمية صغيرة بالسوق
  3) يضع أمر وقف خسارة شرطي على المنصّة (نفس صيغة البوت: triggerPrice/triggerDirection)
  4) يؤكد أن الوقف ظاهر ومستقر في الأوامر المفتوحة
  5) ينظّف: يلغي الوقف ويبيع الكمية (يرجع لـ USDT) — إلا مع --no-cleanup

الاستخدام:
    # تجربة آمنة على testnet (يحتاج مفاتيح testnet في .env_monthly):
    BYBIT_TESTNET=true python3 verify_exchange_stop.py --symbol BTC --usdt 10

    # على الشبكة الحقيقية بمبلغ صغير (مال فعلي) — يتطلب تأكيداً صريحاً:
    python3 verify_exchange_stop.py --symbol BTC --usdt 6 --i-understand-mainnet

ملاحظة: testnet له مفاتيح API منفصلة (من testnet.bybit.com) غير مفاتيح الحقيقي.
"""
import argparse, os, sys, time
from pathlib import Path

BASE_DIR = Path(r"C:\Users\xman9\Desktop") if os.name == "nt" else Path("/root/bots")
ENV_FILE = BASE_DIR / ".env_monthly"


def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


ENV = load_env()
KEY = ENV.get("BYBIT_API_KEY", "")
SEC = ENV.get("BYBIT_API_SECRET", "")
TESTNET = (ENV.get("BYBIT_TESTNET", "false").lower() == "true"
           or os.getenv("BYBIT_TESTNET", "").lower() == "true")


def _market_buy(ex, pair: str, usdt: float, price: float):
    """شراء سوق بنفس طريقة البوت: كمية أساسية + سعر.
    ccxt الافتراضي (createMarketBuyOrderRequiresPrice=True) يحسب التكلفة =
    الكمية × السعر ويرسلها — يتجنب تفسير الرقم كـ BTC بدل USDT."""
    qty = float(ex.amount_to_precision(pair, usdt / price))
    if qty <= 0:
        raise ValueError(f"الكمية المحسوبة صفر (usdt={usdt}, price={price})")
    return ex.create_order(pair, "market", "buy", qty, price)


def _place_stop(ex, pair: str, qty: float, trigger: float):
    """يضع وقف شرطي بصيغة البوت، مع صيغة بديلة عند الرفض."""
    trig = float(ex.price_to_precision(pair, trigger))
    # الصيغة الأساسية (نفس place_exchange_stop في البوت)
    try:
        order = ex.create_order(pair, "market", "sell", qty, None,
                                {"triggerPrice": trig, "triggerDirection": 2})
        return order, "triggerPrice+triggerDirection"
    except Exception as e1:
        print(f"  الصيغة 1 رُفضت: {e1}")
    # صيغة بديلة: بدون triggerDirection
    try:
        order = ex.create_order(pair, "market", "sell", qty, None,
                                {"triggerPrice": trig})
        return order, "triggerPrice فقط"
    except Exception as e2:
        print(f"  الصيغة 2 رُفضت: {e2}")
    # صيغة بديلة: stopPrice
    try:
        order = ex.create_order(pair, "market", "sell", qty, None,
                                {"stopPrice": trig})
        return order, "stopPrice"
    except Exception as e3:
        print(f"  الصيغة 3 رُفضت: {e3}")
    return None, None


def _fetch_stop_orders(ex, pair: str):
    for params in ({"orderFilter": "StopOrder"}, {}):
        try:
            return ex.fetch_open_orders(pair, params=params)
        except Exception:
            continue
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC")
    ap.add_argument("--usdt", type=float, default=10.0)
    ap.add_argument("--sl-pct", type=float, default=5.0)
    ap.add_argument("--i-understand-mainnet", action="store_true")
    ap.add_argument("--no-cleanup", action="store_true")
    args = ap.parse_args()

    if not KEY or not SEC:
        print("❌ مفاتيح Bybit غير موجودة في .env_monthly")
        sys.exit(1)

    if not TESTNET and not args.i_understand_mainnet:
        print("⛔ هذا سيعمل على الشبكة الحقيقية بمال فعلي.")
        print("   للتجربة الآمنة: BYBIT_TESTNET=true (بمفاتيح testnet).")
        print("   أو أضِف --i-understand-mainnet للتأكيد على الحقيقي.")
        sys.exit(1)

    import ccxt
    ex = ccxt.bybit({"apiKey": KEY, "secret": SEC, "options": {"defaultType": "spot"}})
    if TESTNET:
        ex.set_sandbox_mode(True)
    ex.load_markets()
    print(f"الشبكة: {'TESTNET' if TESTNET else 'MAINNET (حقيقي)'}")

    pair = f"{args.symbol.upper()}/USDT"
    if pair not in ex.markets:
        print(f"❌ الزوج غير موجود: {pair}")
        sys.exit(1)

    # 1) الرصيد
    usdt = float(ex.fetch_balance().get("USDT", {}).get("free", 0))
    print(f"رصيد USDT: {usdt:.2f}")
    if usdt < args.usdt:
        print(f"❌ رصيد غير كافٍ ({usdt:.2f} < {args.usdt})")
        sys.exit(1)

    price = float(ex.fetch_ticker(pair)["last"])
    print(f"السعر الحالي: {price}")

    base = args.symbol.upper()
    stop_id = None
    stop_fmt = None
    found = False
    try:
        # 2) شراء سوق
        print(f"→ شراء سوق بـ ${args.usdt}...")
        try:
            _market_buy(ex, pair, args.usdt, price)
        except Exception as e:
            print(f"❌ فشل الشراء: {e}")
            print("   جرّب مبلغاً أكبر (--usdt 12) لو السبب الحد الأدنى للأمر.")
            return
        time.sleep(2)
        base_free = float(ex.fetch_balance().get(base, {}).get("free", 0))
        print(f"✓ تم الشراء | كمية مملوكة: {base_free}")
        if base_free <= 0:
            print("❌ لم تُنفَّذ عملية الشراء — توقف")
            sys.exit(1)
        sell_qty = float(ex.amount_to_precision(pair, base_free * 0.999))

        # 3) وضع الوقف على المنصّة
        trigger = price * (1 - args.sl_pct / 100)
        print(f"→ وضع وقف على المنصّة عند ~{trigger:.6g} (-{args.sl_pct}%)...")
        stop, stop_fmt = _place_stop(ex, pair, sell_qty, trigger)
        if stop:
            stop_id = stop.get("id")
            print(f"✓ قَبِلت المنصّة الوقف | الصيغة: {stop_fmt} | أمر={stop_id}")
        else:
            print("❌ رفضت المنصّة كل صيغ الوقف — راجع الأخطاء أعلاه")

        # 4) تأكيد الاستقرار
        if stop_id:
            time.sleep(2)
            for o in _fetch_stop_orders(ex, pair):
                if o.get("id") == stop_id:
                    found = True
                    trg = o.get("triggerPrice") or o.get("stopPrice") or \
                          o.get("info", {}).get("triggerPrice")
                    print(f"✓ الوقف ظاهر ومستقر في الأوامر | trigger={trg}")
                    break
            if not found:
                print("⚠️ لم أجد الوقف في الأوامر المفتوحة — تحقق يدوياً من المنصّة")

    finally:
        # 5) تنظيف دائماً (حتى عند خطأ) — لا نترك صفقة معلّقة
        if not args.no_cleanup:
            print("→ تنظيف: إلغاء الوقف + بيع الكمية...")
            if stop_id:
                for params in ({"orderFilter": "StopOrder"}, {}):
                    try:
                        ex.cancel_order(stop_id, pair, params=params)
                        print("✓ أُلغي الوقف")
                        break
                    except Exception:
                        continue
            time.sleep(1)
            try:
                base_free = float(ex.fetch_balance().get(base, {}).get("free", 0))
                if base_free * price > 1:
                    ex.create_market_sell_order(
                        pair, float(ex.amount_to_precision(pair, base_free)))
                    print("✓ بِعت الكمية (رجعنا لـ USDT)")
            except Exception as e:
                print(f"تحذير: تعذّر البيع، بِع يدوياً: {e}")

    # الخلاصة
    print("\n===== الخلاصة =====")
    print(f"  قبول صيغة الوقف على المنصّة: {'نعم ✅ ('+str(stop_fmt)+')' if stop_id else 'لا ❌'}")
    print(f"  ظهوره مستقراً في الأوامر:    {'نعم ✅' if found else 'غير مؤكد ⚠️'}")
    if stop_id and found:
        print("النتيجة: الوقف على المنصّة يعمل ✅ — آمن للاعتماد عليه.")
        if stop_fmt and stop_fmt != "triggerPrice+triggerDirection":
            print(f"⚠️ ملاحظة: نجحت الصيغة '{stop_fmt}' وليست الأساسية —")
            print("   أخبرني لأحدّث place_exchange_stop في البوت لتطابقها.")
    else:
        print("النتيجة: راجع الأخطاء أعلاه قبل الاعتماد على الوقف على المنصّة.")


if __name__ == "__main__":
    main()
