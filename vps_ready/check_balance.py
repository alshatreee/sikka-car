#!/usr/bin/env python3
"""Quick Bybit balance checker."""
import json, hashlib, hmac, time, urllib.request
from pathlib import Path

BASE = Path("/root/bots")

def load_env():
    env = {}
    for f in [BASE / ".env_monthly", BASE / ".env_dca"]:
        if f.exists():
            print(f"Using env file: {f}")
            for line in open(f):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
            break
    return env

env = load_env()
key = env.get("BYBIT_KEY", "")
sec = env.get("BYBIT_SECRET", "")

print(f"BYBIT_KEY: {'found (' + key[:6] + '...)' if key else 'MISSING'}")
print(f"BYBIT_SECRET: {'found (' + sec[:4] + '...)' if sec else 'MISSING'}")

if not key or not sec:
    print("\nERROR: API keys not found!")
    print("Available keys:", list(env.keys()))
    exit(1)

ts = str(int(time.time() * 1000))
recv = "5000"
params = "accountType=UNIFIED"
sign_str = f"{ts}{key}{recv}{params}"
sig = hmac.new(sec.encode(), sign_str.encode(), hashlib.sha256).hexdigest()

url = f"https://api.bybit.com/v5/account/wallet-balance?{params}"
try:
    req = urllib.request.Request(url, headers={
        "X-BAPI-API-KEY": key,
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": recv,
        "X-BAPI-SIGN": sig,
    })
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
except Exception as e:
    print(f"\nAPI Error: {e}")
    print("Trying SPOT account type...")
    ts = str(int(time.time() * 1000))
    params2 = "accountType=SPOT"
    sig2 = hmac.new(sec.encode(), f"{ts}{key}{recv}{params2}".encode(), hashlib.sha256).hexdigest()
    try:
        req2 = urllib.request.Request(
            f"https://api.bybit.com/v5/account/wallet-balance?{params2}",
            headers={
                "X-BAPI-API-KEY": key,
                "X-BAPI-TIMESTAMP": ts,
                "X-BAPI-RECV-WINDOW": recv,
                "X-BAPI-SIGN": sig2,
            })
        data = json.loads(urllib.request.urlopen(req2, timeout=15).read())
        print("SPOT account works!")
    except Exception as e2:
        print(f"SPOT also failed: {e2}")
        exit(1)

print(f"\nretCode: {data.get('retCode')} | retMsg: {data.get('retMsg')}")
coins = data.get("result", {}).get("list", [{}])[0].get("coin", [])
print(f"Coins found: {len(coins)}")
total = 0
for c in coins:
    name = c.get("coin", "")
    eq = c.get("equity", "0")
    bal = c.get("walletBalance", "0")
    avail = c.get("availableToWithdraw", "0")
    try:
        usd = float(c.get("usdValue", "0") or "0")
    except ValueError:
        usd = 0
    if usd > 0.5:
        print(f"  {name}: equity={eq} balance={bal} available={avail} (~${usd:.2f})")
        total += usd
print(f"\nTotal: ${total:.2f}")
