import os, ccxt
ex = ccxt.bitget({
    "apiKey": os.environ["BITGET_DEMO_KEY"],
    "secret": os.environ["BITGET_DEMO_SECRET"],
    "password": os.environ["BITGET_DEMO_PASSPHRASE"],
    "options": {"defaultType": "swap"},
})
ex.set_sandbox_mode(True)
ex.load_markets()
for s, m in ex.markets.items():
    if "XAU" in s:
        print(s, "contractSize:", m.get("contractSize"),
              "min:", m["limits"]["amount"]["min"])
print(ex.fetch_balance().get("USDT"))
