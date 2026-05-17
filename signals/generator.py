import asyncio
from strategies.trend_pullback import find_setup as tp_setup
from strategies.vol_breakout import find_setup as vb_setup
from filters.regime import get_regime
import config


async def scan_all() -> tuple[list[dict], dict]:
    regime = await get_regime()

    tasks = []
    for symbol in config.SYMBOLS:
        tasks.append(tp_setup(symbol, regime))
        tasks.append(vb_setup(symbol, regime))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    signals = []
    for r in results:
        if isinstance(r, Exception) or r is None:
            continue
        signals.append(r)

    return signals, regime
