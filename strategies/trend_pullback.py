from data.binance import get_klines
from data.indicators import ema, rsi, atr, volume_ratio
import config

STRATEGY_NAME = "trend_pullback"


async def find_setup(symbol: str, regime: dict) -> dict | None:
    if not regime.get("long_allowed") and not regime.get("short_allowed"):
        return None

    candles = await get_klines(symbol, "15m", limit=220)
    if len(candles) < 210:
        return None

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    volumes = [c["volume"] for c in candles]

    ema50_vals = ema(closes, 50)
    rsi_vals = rsi(closes, config.TP1_RSI_PERIOD)
    atr_vals = atr(highs, lows, closes, config.TP1_ATR_PERIOD)

    last = candles[-1]
    prev = candles[-2]

    e50 = ema50_vals[-1]
    rsi_val = rsi_vals[-1]
    atr_val = atr_vals[-1]
    vol_rat = volume_ratio(volumes, 20)

    if e50 is None or rsi_val is None or atr_val is None:
        return None

    if vol_rat is None or vol_rat < config.TP1_MIN_VOLUME_RATIO:
        return None

    price = last["close"]
    direction = None

    near_ema50 = abs(price - e50) <= atr_val * config.TP1_PULLBACK_ATR_THRESHOLD

    if regime.get("long_allowed") and near_ema50:
        rsi_ok = config.TP1_RSI_LONG_ZONE[0] <= rsi_val <= config.TP1_RSI_LONG_ZONE[1]
        if rsi_ok:
            direction = "LONG"

    if regime.get("short_allowed") and direction is None and near_ema50:
        rsi_ok = config.TP1_RSI_SHORT_ZONE[0] <= rsi_val <= config.TP1_RSI_SHORT_ZONE[1]
        if rsi_ok:
            direction = "SHORT"

    if not direction:
        return None

    confirmation = _check_confirmation(last, prev, direction)
    if not confirmation:
        return None

    if direction == "LONG":
        entry = price
        sl = price - atr_val * config.TP1_SL_ATR_MULT
        tp = price + (price - sl) * config.RR_TARGET
    else:
        entry = price
        sl = price + atr_val * config.TP1_SL_ATR_MULT
        tp = price - (sl - price) * config.RR_TARGET

    rr = round(abs(tp - entry) / abs(sl - entry), 2)

    return {
        "symbol": symbol,
        "strategy": STRATEGY_NAME,
        "strategy_version": f"{STRATEGY_NAME}_{config.STRATEGY_VERSION}",
        "direction": direction,
        "entry": entry,
        "entry_low": min(entry, e50),
        "entry_high": max(entry, e50),
        "stop_loss": sl,
        "take_profit": tp,
        "rr": rr,
        "atr": round(atr_val, 4),
        "rsi": round(rsi_val, 1),
        "ema50": round(e50, 4),
        "volume_ratio": round(vol_rat, 2) if vol_rat else None,
        "confirmation": confirmation,
    }


def _check_confirmation(last: dict, prev: dict, direction: str) -> str | None:
    body = abs(last["close"] - last["open"])
    candle_range = last["high"] - last["low"]
    wick_up = last["high"] - max(last["close"], last["open"])
    wick_down = min(last["close"], last["open"]) - last["low"]

    if direction == "LONG":
        if (
            last["close"] > last["open"]
            and prev["close"] < prev["open"]
            and last["close"] > prev["open"]
            and last["open"] < prev["close"]
        ):
            return "bullish_engulfing"
        if candle_range > 0 and last["close"] > last["open"]:
            if (last["close"] - last["low"]) / candle_range >= 0.6:
                return "strong_close"
        if body > 0 and wick_down >= body * 2:
            return "rejection_wick"

    elif direction == "SHORT":
        if (
            last["close"] < last["open"]
            and prev["close"] > prev["open"]
            and last["close"] < prev["open"]
            and last["open"] > prev["close"]
        ):
            return "bearish_engulfing"
        if candle_range > 0 and last["close"] < last["open"]:
            if (last["high"] - last["close"]) / candle_range >= 0.6:
                return "strong_close"
        if body > 0 and wick_up >= body * 2:
            return "rejection_wick"

    return None
