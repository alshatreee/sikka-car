#!/usr/bin/env python3
"""
reconcile_monthly_state.py — يطابق مراكز بوت monthly مع محفظة Bybit الفعلية.

يحذف المراكز "الوهمية" (المسجلة في الملف لكن العملة لم تعد موجودة في محفظة
Bybit بقيمة > $1). هذا يصلح: توصيات بيع لعملات غير مملوكة، ومنع إعادة الشراء.

⚠️ شغّله وبوت monthly متوقف، وإلا سيعيد البوت كتابة المراكز من ذاكرته.

الاستخدام:
    # عرض ما سيُحذف فقط (آمن، لا يغيّر شيئاً):
    python3 reconcile_monthly_state.py

    # التنفيذ الفعلي (ينشئ نسخة احتياطية ثم يحذف الأوهام):
    python3 reconcile_monthly_state.py --apply
"""
import argparse, json, os, shutil, sys, time
from pathlib import Path

BASE_DIR = Path(r"C:\Users\xman9\Desktop") if os.name == "nt" else Path("/root/bots")
ENV_FILE = BASE_DIR / ".env_monthly"
STATE_FILE = BASE_DIR / "monthly_state.json"
MIN_VALUE_USD = 1.0


def load_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="نفّذ الحذف فعلاً")
    args = ap.parse_args()

    env = load_env()
    key, sec = env.get("BYBIT_API_KEY", ""), env.get("BYBIT_API_SECRET", "")
    if not key or not sec:
        print("❌ مفاتيح Bybit غير موجودة في .env_monthly")
        sys.exit(1)
    if not STATE_FILE.exists():
        print(f"❌ {STATE_FILE} غير موجود")
        sys.exit(1)

    import ccxt
    ex = ccxt.bybit({"apiKey": key, "secret": sec,
                     "options": {"defaultType": "spot"}})
    ex.load_markets()

    # actual Bybit wallet coins with value > $1
    bal = ex.fetch_balance()
    real = set()
    for coin, info in bal.items():
        if coin in ("info", "timestamp", "datetime", "free", "used", "total"):
            continue
        if coin in ("USDT", "USDC", "USD"):
            continue
        total = 0.0
        try:
            total = float(info.get("total") or 0)
        except (TypeError, ValueError):
            total = 0.0
        if total <= 0:
            continue
        try:
            px = float(ex.fetch_ticker(f"{coin}/USDT")["last"])
        except Exception:
            continue
        if total * px >= MIN_VALUE_USD:
            real.add(coin.upper())

    print(f"عملات موجودة فعلاً في Bybit (>${MIN_VALUE_USD:g}): {sorted(real)}\n")

    st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    op = st.get("open_positions", {})
    keep, removed = {}, []
    for pair, pos in op.items():
        base = pair.split("/")[0].upper()
        if base in real:
            keep[pair] = pos
        else:
            removed.append(pair)

    print(f"✅ مراكز حقيقية تبقى ({len(keep)}): {sorted(keep)}")
    print(f"🗑️  مراكز وهمية تُحذف ({len(removed)}): {sorted(removed)}\n")

    if not removed:
        print("لا شيء للحذف — الملف متطابق مع المحفظة.")
        return

    if not args.apply:
        print("هذا عرض فقط. للتنفيذ الفعلي أضِف --apply (وتأكد أن بوت monthly متوقف).")
        return

    backup = STATE_FILE.with_suffix(f".backup.{int(time.time())}.json")
    shutil.copy(STATE_FILE, backup)
    print(f"📦 نسخة احتياطية: {backup.name}")

    st["open_positions"] = keep
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)
    print(f"✅ تم — حُذفت {len(removed)} مراكز وهمية. أعد تشغيل بوت monthly الآن.")


if __name__ == "__main__":
    main()
