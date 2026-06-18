import hashlib
import hmac
import math
import time
import httpx
import config

BASE_URL = "https://fapi.binance.com"

_step_size_cache: dict[str, float] = {}


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


# ─── Signed request helpers ───────────────────────────────────────────────────

def _sign(params: dict) -> dict:
    params["timestamp"] = int(time.time() * 1000)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(
        config.BINANCE_API_SECRET.encode(),
        query.encode(),
        hashlib.sha256,
    ).hexdigest()
    params["signature"] = sig
    return params


async def _signed_get(endpoint: str, params: dict) -> dict:
    headers = {"X-MBX-APIKEY": config.BINANCE_API_KEY}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}{endpoint}", params=_sign(params), headers=headers
        )
        resp.raise_for_status()
        return resp.json()


async def _signed_post(endpoint: str, params: dict) -> dict:
    headers = {"X-MBX-APIKEY": config.BINANCE_API_KEY}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{BASE_URL}{endpoint}", data=_sign(params), headers=headers
        )
        resp.raise_for_status()
        return resp.json()


async def _signed_delete(endpoint: str, params: dict) -> dict:
    headers = {"X-MBX-APIKEY": config.BINANCE_API_KEY}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.delete(
            f"{BASE_URL}{endpoint}", params=_sign(params), headers=headers
        )
        resp.raise_for_status()
        return resp.json()


# ─── Account ──────────────────────────────────────────────────────────────────

async def get_account_balance() -> float:
    data = await _signed_get("/fapi/v2/balance", {})
    for asset in data:
        if asset["asset"] == "USDT":
            return float(asset["availableBalance"])
    return 0.0


# ─── Symbol info ──────────────────────────────────────────────────────────────

async def get_step_size(symbol: str) -> float:
    if symbol in _step_size_cache:
        return _step_size_cache[symbol]
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{BASE_URL}/fapi/v1/exchangeInfo")
        resp.raise_for_status()
        info = resp.json()
    for s in info["symbols"]:
        if s["symbol"] == symbol:
            for f in s["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    step = float(f["stepSize"])
                    _step_size_cache[symbol] = step
                    return step
    return 0.001


def round_qty(qty: float, step: float) -> float:
    precision = max(0, round(-math.log10(step)))
    return round(math.floor(qty / step) * step, int(precision))


# ─── Leverage & margin ────────────────────────────────────────────────────────

async def set_leverage(symbol: str, leverage: int) -> None:
    await _signed_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})


async def set_margin_type(symbol: str, margin_type: str) -> None:
    try:
        await _signed_post("/fapi/v1/marginType", {"symbol": symbol, "marginType": margin_type})
    except httpx.HTTPStatusError as e:
        # -4046 = already set — not an error
        if '"code":-4046' not in e.response.text:
            raise


# ─── Orders ───────────────────────────────────────────────────────────────────

async def place_order(
    symbol: str,
    side: str,
    quantity: float,
    order_type: str,
    price: float | None = None,
    stop_price: float | None = None,
    reduce_only: bool = False,
    time_in_force: str | None = None,
) -> dict:
    params: dict = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": quantity,
    }
    if price is not None:
        params["price"] = price
    if stop_price is not None:
        params["stopPrice"] = stop_price
    if reduce_only:
        params["reduceOnly"] = "true"
    if time_in_force:
        params["timeInForce"] = time_in_force
    return await _signed_post("/fapi/v1/order", params)


async def place_algo_order(
    symbol: str,
    side: str,
    quantity: float,
    order_type: str,
    trigger_price: float,
    reduce_only: bool = False,
) -> dict:
    params: dict = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "algoType": "CONDITIONAL",
        "quantity": quantity,
        "triggerPrice": trigger_price,
    }
    if reduce_only:
        params["reduceOnly"] = "true"
    return await _signed_post("/fapi/v1/algoOrder", params)


async def get_order(symbol: str, order_id: int) -> dict:
    return await _signed_get("/fapi/v1/order", {"symbol": symbol, "orderId": order_id})


async def get_algo_order(algo_id: int) -> dict:
    return await _signed_get("/fapi/v1/algoOrder", {"algoId": algo_id})


async def cancel_order(symbol: str, order_id: int) -> dict:
    return await _signed_delete("/fapi/v1/order", {"symbol": symbol, "orderId": order_id})


async def cancel_algo_order(algo_id: int) -> dict:
    return await _signed_delete("/fapi/v1/algoOrder", {"algoId": algo_id})
