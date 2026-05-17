from data.binance import get_klines
from data.indicators import atr, bollinger_bands, volume_ratio
import config

STRATEGY_NAME = "vol_breakout"


async def find_setup(symbol: str, regime: dict) -> dict | None:
    if not regime.get("long_allowed") and not regime.get("short_allowed"):
        return None

    candles = await get_klines(symbol, "15m", limit=100)
    if len(candles) < 60:
        return None

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    volumes = [c["volume"] for c in candles]

    atr_vals = atr(highs, lows, closes, 14)
    bb_vals = bollinger_bands(closes, 20)
    vol_rat = volume_ratio(volumes, 20)

    last_atr = atr_vals[-1]
    if last_atr is None or vol_rat is None:
        return None

    atr_window = [v for v in atr_vals[-15:-1] if v is not None]
    if len(atr_window) < 10:
        return None
    avg_atr = sum(atr_window) / len(atr_window)

    bb_width_window = [bb_vals[i][3] for i in range(-21, -1) if bb_vals[i][3] is not None]
    if len(bb_width_window) < 10:
        return None
    avg_bb_width = sum(bb_width_window) / len(bb_width_window)

    last_bb_width = bb_vals[-1][3]
    if last_bb_width is None:
        return None

    atr_compressed = last_atr < avg_atr * config.VB_ATR_COMPRESSION
    bb_compressed = last_bb_width < avg_bb_width * config.VB_BB_COMPRESSION
    if not (atr_compressed and bb_compressed):
        return None

    n = config.VB_RANGE_CANDLES
    range_candles = candles[-n - 1 : -1]
    range_high = max(c["high"] for c in range_candles)
    range_low = min(c["low"] for c in range_candles)

    last = candles[-1]
    price = last["close"]

    direction = None
    if regime.get("long_allowed") and price > range_high:
        direction = "LONG"
    elif regime.get("short_allowed") and price < range_low:
        direction = "SHORT"

    if not direction:
        return None

    if vol_rat < config.VB_VOLUME_MULT:
        return None

    if direction == "LONG":
        sl = range_low
        entry = price
        risk = entry - sl
        tp = entry + risk * config.RR_TARGET
    else:
        sl = range_high
        entry = price
        risk = sl - entry
        tp = entry - risk * config.RR_TARGET

    if risk <= 0:
        return None

    rr = round(abs(tp - entry) / abs(sl - entry), 2)

    return {
        "symbol": symbol,
        "strategy": STRATEGY_NAME,
        "strategy_version": f"{STRATEGY_NAME}_{config.STRATEGY_VERSION}",
        "direction": direction,
        "entry": entry,
        "entry_low": entry * 0.999,
        "entry_high": entry * 1.001,
        "stop_loss": sl,
        "take_profit": tp,
        "rr": rr,
        "atr": round(last_atr, 4),
        "atr_ratio": round(last_atr / avg_atr, 2),
        "range_high": round(range_high, 4),
        "range_low": round(range_low, 4),
        "volume_ratio": round(vol_rat, 2),
    }
