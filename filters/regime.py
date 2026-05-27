from data.binance import get_klines
from data.indicators import ema


async def get_regime(symbol: str = "BTCUSDT") -> dict:
    candles = await get_klines(symbol, "1h", limit=250)
    closes = [c["close"] for c in candles]

    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)

    last_close = closes[-1]
    last_ema50 = ema50[-1]
    last_ema200 = ema200[-1]

    if last_ema50 is None or last_ema200 is None:
        return {
            "regime": "UNKNOWN",
            "long_allowed": False,
            "short_allowed": False,
            "ema50": None,
            "ema200": None,
            "price": last_close,
        }

    if last_ema50 > last_ema200 and last_close > last_ema200:
        regime = "BULL"
        long_allowed = last_close > last_ema50  # price above EMA50 — trend confirmed
        short_allowed = False
    elif last_ema50 < last_ema200 and last_close < last_ema200:
        regime = "BEAR"
        long_allowed = False
        short_allowed = last_close < last_ema50  # price below EMA50 — not a pullback
    else:
        regime = "SIDEWAYS"
        long_allowed = False
        short_allowed = False

    return {
        "regime": regime,
        "long_allowed": long_allowed,
        "short_allowed": short_allowed,
        "ema50": last_ema50,
        "ema200": last_ema200,
        "price": last_close,
        "price_vs_ema50": "below" if last_close < last_ema50 else "above",
    }
