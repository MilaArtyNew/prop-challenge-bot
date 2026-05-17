import math
from typing import Optional


def ema(values: list[float], period: int) -> list[Optional[float]]:
    if len(values) < period:
        return [None] * len(values)
    result: list[Optional[float]] = [None] * (period - 1)
    sma = sum(values[:period]) / period
    result.append(sma)
    k = 2 / (period + 1)
    for v in values[period:]:
        result.append(result[-1] * (1 - k) + v * k)
    return result


def rsi(closes: list[float], period: int = 14) -> list[Optional[float]]:
    if len(closes) < period + 1:
        return [None] * len(closes)

    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    def _rsi(ag: float, al: float) -> float:
        if al == 0:
            return 100.0
        return 100 - (100 / (1 + ag / al))

    result: list[Optional[float]] = [None] * period
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result.append(_rsi(avg_gain, avg_loss))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result.append(_rsi(avg_gain, avg_loss))

    return result


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[Optional[float]]:
    tr_list = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)

    result: list[Optional[float]] = [None] * period
    avg = sum(tr_list[:period]) / period
    result.append(avg)
    for tr in tr_list[period:]:
        avg = (avg * (period - 1) + tr) / period
        result.append(avg)
    return result


def bollinger_bands(closes: list[float], period: int = 20, k: float = 2.0) -> list[tuple]:
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append((None, None, None, None))
            continue
        window = closes[i - period + 1 : i + 1]
        sma = sum(window) / period
        std = math.sqrt(sum((x - sma) ** 2 for x in window) / period)
        upper = sma + k * std
        lower = sma - k * std
        width = (upper - lower) / sma if sma > 0 else 0
        result.append((sma, upper, lower, width))
    return result


def volume_ratio(volumes: list[float], period: int = 20) -> Optional[float]:
    if len(volumes) < period + 1:
        return None
    avg = sum(volumes[-period - 1 : -1]) / period
    return volumes[-1] / avg if avg > 0 else None
