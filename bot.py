import os, time
import ccxt, requests

# ---------- Settings ----------
SYMBOL = "BTC/USDT"
TF = "15m"
START_BAL = 15.0
RISK = 0.02        # 2% of balance risked per trade
SL_PCT = 0.01      # stop loss 1% below entry
RR = 2             # take profit = 2x the risk
FEE = 0.001        # 0.1% per side
SLEEP = 30         # seconds between checks

TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")

ex = ccxt.bitget({"enableRateLimit": True})

# ---------- State (in memory) ----------
bal = START_BAL
pos = None
trades = 0
wins = 0
last_candle_ts = None


def notify(msg):
    print(msg)
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": msg},
            timeout=10,
        )
    except Exception as e:
        print("telegram error:", e)


def ema(vals, n):
    k = 2 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def get_signal():
    """Returns (signal, candle_ts). Uses closed candles only."""
    candles = ex.fetch_ohlcv(SYMBOL, TF, limit=120)[:-1]  # drop open candle
    closes = [c[4] for c in candles]
    ts = candles[-1][0]
    fast, slow = ema(closes, 20), ema(closes, 50)
    pfast, pslow = ema(closes[:-1], 20), ema(closes[:-1], 50)
    crossed_up = pfast <= pslow and fast > slow
    return crossed_up, ts


notify(f"Paper bot started. {SYMBOL} {TF}, balance ${bal:.2f}")

while True:
    try:
        price = ex.fetch_ticker(SYMBOL)["last"]

        # ----- Manage open position -----
        if pos:
            hit_sl = price <= pos["sl"]
            hit_tp = price >= pos["tp"]
            if hit_sl or hit_tp:
                exit_price = pos["sl"] if hit_sl else pos["tp"]
                pnl = (exit_price - pos["entry"]) * pos["size"]
                pnl -= (pos["entry"] + exit_price) * pos["size"] * FEE
                bal += pnl
                trades += 1
                wins += 1 if pnl > 0 else 0
                notify(
                    f"EXIT ({'TP' if hit_tp else 'SL'}) @ {exit_price:.2f}\n"
                    f"PnL: {pnl:+.4f} | Balance: ${bal:.2f}\n"
                    f"Trades: {trades} | Win rate: {wins / trades * 100:.0f}% "
                    f"| Total: {bal - START_BAL:+.2f}"
                )
                pos = None

        # ----- Look for entry -----
        else:
            signal, ts = get_signal()
            if signal and ts != last_candle_ts:
                last_candle_ts = ts
                sl = price * (1 - SL_PCT)
                tp = price + (price - sl) * RR
                size = (bal * RISK) / (price - sl)
                size = min(size, bal / price)  # cap at balance, no leverage
                pos = {"entry": price, "sl": sl, "tp": tp, "size": size}
                notify(
                    f"BUY @ {price:.2f}\n"
                    f"SL {sl:.2f} | TP {tp:.2f}\n"
                    f"Size {size:.6f} BTC (${size * price:.2f})"
                )

    except Exception as e:
        print("loop error:", e)

    time.sleep(SLEEP)
