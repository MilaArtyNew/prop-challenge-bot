import httpx

BASE_URL = "https://fapi.binance.com"


async def get_klines(symbol: str, interval: str, limit: int = 200) -> list[dict]:
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        raw = resp.json()

    return [
        {
            "open_time": c[0],
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
        }
        for c in raw
    ]


async def get_price(symbol: str) -> float:
    url = f"{BASE_URL}/fapi/v1/ticker/price"
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(url, params={"symbol": symbol})
        resp.raise_for_status()
        return float(resp.json()["price"])
