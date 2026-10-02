import os, time, hmac, hashlib, base64, requests
from urllib.parse import urlencode

K, S, P = (os.environ[x] for x in
           ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_API_PASSPHRASE"))

def get(path, params):
    q = f"{path}?{urlencode(params)}"
    ts = str(int(time.time() * 1000))
    sign = base64.b64encode(hmac.new(S.encode(), (ts + "GET" + q).encode(),
                            hashlib.sha256).digest()).decode()
    h = {"ACCESS-KEY": K, "ACCESS-SIGN": sign, "ACCESS-TIMESTAMP": ts,
         "ACCESS-PASSPHRASE": P, "Content-Type": "application/json"}
    return requests.get("https://api.bitget.com" + q, headers=h, timeout=15).text[:300]

print(get("/api/v3/cfd/market/tickers", {"symbol": "XAUUSD"}))
now = int(time.time() * 1000)
for side in ("sell", "buy"):
    print(side, get("/api/v3/cfd/market/history-candlestick",
          {"symbol": "XAUUSD", "interval": "1m", "side": side,
           "startTime": str(now - 600000), "limit": "10"}))
