import asyncio
from strategies.trend_pullback import find_setup as tp_setup
from strategies.vol_breakout import find_setup as vb_setup
from filters.regime import get_regime
import config


async def scan_all() -> tuple[list[dict], dict]:
    # BTC macro regime — used for vol_breakout and returned for display
    btc_regime = await get_regime("BTCUSDT")

    # Per-symbol regimes: trend_pullback direction based on each symbol's own 1H EMA50
    sym_regimes = await asyncio.gather(*[get_regime(s) for s in config.SYMBOLS])
    sym_regime_map = dict(zip(config.SYMBOLS, sym_regimes))

    tasks = []
    for symbol in config.SYMBOLS:
        sym_r = sym_regime_map[symbol]
        tp_regime = {
            **btc_regime,
            "long_allowed": sym_r["long_allowed"],
            "short_allowed": sym_r["short_allowed"],
        }
        tasks.append(tp_setup(symbol, tp_regime))
        tasks.append(vb_setup(symbol, btc_regime))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    signals = []
    for r in results:
        if isinstance(r, Exception) or r is None:
            continue
        signals.append(r)

    return signals, btc_regime
