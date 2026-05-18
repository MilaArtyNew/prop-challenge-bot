import httpx

BASE_URL = "https://api.bybit.com"

_INTERVAL_MAP = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "120", "4h": "240", "1d": "D",
}


async def get_klines(symbol: str, interval: str, limit: int = 200) -> list[dict]:
    bybit_interval = _INTERVAL_MAP.get(interval, interval)
    url = f"{BASE_URL}/v5/market/kline"
    params = {"category": "linear", "symbol": symbol, "interval": bybit_interval, "limit": limit}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        raw = resp.json()["result"]["list"]  # newest first

    return [
        {
            "open_time": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
        }
        for c in reversed(raw)  # oldest first, same as before
    ]


async def get_price(symbol: str) -> float:
    url = f"{BASE_URL}/v5/market/tickers"
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(url, params={"category": "linear", "symbol": symbol})
        resp.raise_for_status()
        return float(resp.json()["result"]["list"][0]["lastPrice"])
