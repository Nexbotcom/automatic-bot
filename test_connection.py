import os, time, hmac, hashlib, base64, requests
from urllib.parse import urlencode

K, S, P = (os.environ[x] for x in
           ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE"))

def get(path, params, demo):
    q = f"{path}?{urlencode(params)}"
    ts = str(int(time.time() * 1000))
    sign = base64.b64encode(hmac.new(S.encode(), (ts + "GET" + q).encode(),
                            hashlib.sha256).digest()).decode()
    h = {"ACCESS-KEY": K, "ACCESS-SIGN": sign, "ACCESS-TIMESTAMP": ts,
         "ACCESS-PASSPHRASE": P, "Content-Type": "application/json"}
    if demo:
        h["paptrading"] = "1"
    return requests.get("https://api.bitget.com" + q, headers=h, timeout=15).text[:200]

for demo in (False, True):
    for sym in ("XAUUSD", "XAUUSD.s", "XAUUSD.pro"):
        print("demo" if demo else "normal", sym,
              get("/api/v3/cfd/market/tickers", {"symbol": sym}, demo))
