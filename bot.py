import os, time
import ccxt, requests

# ---------- Settings ----------
SYMBOL = "BTC/USDT"
TF = "5m"
FAST, SLOW = 5, 13
START_BAL = 15.0
RISK = 0.02          # 2% of balance risked per trade
MIN_SL_PCT = 0.003   # stop never tighter than 0.3%
ATR_MULT = 1.2       # stop = 1.2 x ATR (or MIN_SL_PCT if larger)
RR = 1.5             # take profit = 1.5x the stop distance
FEE = 0.001          # 0.1% per side
SLEEP = 15           # seconds between checks
HB_EVERY = 3600      # Telegram heartbeat every hour

TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")

ex = ccxt.bitget({"enableRateLimit": True})

# ---------- State (in memory) ----------
bal = START_BAL
pos = None
trades = 0
wins = 0
last_signal_ts = None
last_hb = time.time()
day_start = time.time()
day_trades = 0
price = 0


def notify(msg):
    print(msg, flush=True)
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": msg},
            timeout=10,
        )
    except Exception as e:
        print("telegram error:", e, flush=True)


def ema(vals, n):
    k = 2 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def get_signal():
    """Returns (side, candle_ts, atr). Closed candles only."""
    candles = ex.fetch_ohlcv(SYMBOL, TF, limit=120)[:-1]
    closes = [c[4] for c in candles]
    ts = candles[-1][0]

    fast, slow = ema(closes, FAST), ema(closes, SLOW)
    pfast, pslow = ema(closes[:-1], FAST), ema(closes[:-1], SLOW)

    trs = []
    for i in range(len(candles) - 14, len(candles)):
        h, l, pc = candles[i][2], candles[i][3], candles[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs) / len(trs)

    side = None
    if pfast <= pslow and fast > slow:
        side = "long"
    elif pfast >= pslow and fast < slow:
        side = "short"
    return side, ts, atr


def close_pos(exit_price, reason):
    global bal, pos, trades, wins, day_trades
    if pos["side"] == "long":
        pnl = (exit_price - pos["entry"]) * pos["size"]
    else:
        pnl = (pos["entry"] - exit_price) * pos["size"]
    pnl -= (pos["entry"] + exit_price) * pos["size"] * FEE
    bal += pnl
    trades += 1
    day_trades += 1
    wins += 1 if pnl > 0 else 0
    notify(
        f"EXIT {pos['side'].upper()} ({reason}) @ {exit_price:.2f}\n"
        f"PnL: {pnl:+.4f} | Balance: ${bal:.2f}\n"
        f"Trades: {trades} (24h: {day_trades}) | Win rate: {wins / trades * 100:.0f}% "
        f"| Total: {bal - START_BAL:+.2f}"
    )
    pos = None


def open_pos(side, entry, atr):
    global pos
    dist = max(atr * ATR_MULT, entry * MIN_SL_PCT)
    if side == "long":
        sl, tp = entry - dist, entry + dist * RR
    else:
        sl, tp = entry + dist, entry - dist * RR
    size = (bal * RISK) / dist
    size = min(size, bal / entry)  # cap at balance, no leverage
    pos = {"side": side, "entry": entry, "sl": sl, "tp": tp, "size": size}
    notify(
        f"{side.upper()} @ {entry:.2f}\n"
        f"SL {sl:.2f} | TP {tp:.2f}\n"
        f"Size {size:.6f} BTC (${size * entry:.2f})"
    )


notify(f"Paper bot v3 (fast) started. {SYMBOL} {TF} EMA {FAST}/{SLOW}, long+short, balance ${bal:.2f}")

while True:
    try:
        price = ex.fetch_ticker(SYMBOL)["last"]

        # ----- SL / TP -----
        if pos:
            if pos["side"] == "long":
                hit_sl, hit_tp = price <= pos["sl"], price >= pos["tp"]
            else:
                hit_sl, hit_tp = price >= pos["sl"], price <= pos["tp"]
            if hit_sl or hit_tp:
                close_pos(pos["sl"] if hit_sl else pos["tp"], "TP" if hit_tp else "SL")

        # ----- Signals: enter, or flip on opposite cross -----
        side, ts, atr = get_signal()
        print(
            f"scan | price {price:.2f} | signal {side} | "
            f"{'holding ' + pos['side'] if pos else 'flat'}",
            flush=True,
        )
        if side and ts != last_signal_ts:
            last_signal_ts = ts
            if pos and pos["side"] != side:
                close_pos(price, "flip")
            if pos is None:
                open_pos(side, price, atr)

    except Exception as e:
        print("loop error:", e, flush=True)

    # ----- Reset 24h counter -----
    if time.time() - day_start > 86400:
        day_start = time.time()
        day_trades = 0

    # ----- Hourly heartbeat -----
    if time.time() - last_hb > HB_EVERY:
        last_hb = time.time()
        notify(
            f"Alive. Price {price:.2f} | Balance ${bal:.2f} | "
            f"Trades {trades} (24h: {day_trades}) | {pos['side'] if pos else 'flat'}"
        )

    time.sleep(SLEEP)
