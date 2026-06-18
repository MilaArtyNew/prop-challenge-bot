import math
import sqlite3
import time
import logging
from typing import Callable, Awaitable
from data.binance import (
    get_step_size, round_qty, set_leverage, set_margin_type,
    place_order, get_order, cancel_order,
)
import config

logger = logging.getLogger(__name__)

SendFn = Callable[[str], Awaitable[None]]


def _calc_leverage(entry: float, sl: float) -> int:
    sl_dist_pct = abs(entry - sl) / entry
    if sl_dist_pct <= 0:
        return 1
    raw = config.RISK_PER_TRADE / sl_dist_pct
    return max(1, min(20, math.ceil(raw)))


async def open_live_trade(signal: dict, db: sqlite3.Connection,
                          send: SendFn | None = None) -> int | None:
    symbol = signal["symbol"]
    direction = signal["direction"]
    entry = signal["entry"]
    sl = signal["stop_loss"]
    tp = signal["take_profit"]
    strategy = signal["strategy"]

    leverage = _calc_leverage(entry, sl)
    sl_dist_pct = abs(entry - sl) / entry
    notional = (config.RISK_PER_TRADE / sl_dist_pct) * config.ACCOUNT_SIZE

    step = await get_step_size(symbol)
    quantity = round_qty(notional / entry, step)
    if quantity <= 0:
        logger.error(f"Calculated quantity is 0 for {symbol}, skipping")
        return None

    try:
        await set_margin_type(symbol, config.MARGIN_TYPE)
        await set_leverage(symbol, leverage)
    except Exception as e:
        logger.error(f"Failed to set margin/leverage for {symbol}: {e}")
        return None

    side = "BUY" if direction == "LONG" else "SELL"

    if strategy == "trend_pullback":
        try:
            entry_resp = await place_order(
                symbol, side, quantity, "LIMIT",
                price=round(entry, 2),
                time_in_force="GTC",
            )
        except Exception as e:
            logger.error(f"Entry LIMIT order failed for {symbol}: {e}")
            return None
        status = "pending"
        filled_price = None
        entry_order_id = entry_resp["orderId"]
        sl_order_id = None
        tp_order_id = None
    else:
        # vol_breakout → MARKET
        try:
            entry_resp = await place_order(symbol, side, quantity, "MARKET")
        except Exception as e:
            logger.error(f"Entry MARKET order failed for {symbol}: {e}")
            return None
        filled_price = float(entry_resp.get("avgPrice") or entry_resp.get("price") or entry)
        entry_order_id = entry_resp["orderId"]
        status = "open"

        sl_side = "SELL" if direction == "LONG" else "BUY"
        try:
            sl_resp = await place_order(
                symbol, sl_side, quantity, "STOP_MARKET",
                stop_price=round(sl, _price_precision(sl)),
                reduce_only=True,
            )
            tp_resp = await place_order(
                symbol, sl_side, quantity, "TAKE_PROFIT_MARKET",
                stop_price=round(tp, _price_precision(tp)),
                reduce_only=True,
            )
            sl_order_id = sl_resp["orderId"]
            tp_order_id = tp_resp["orderId"]
        except Exception as e:
            logger.error(f"SL/TP orders failed for {symbol}: {e}")
            sl_order_id = None
            tp_order_id = None

    cursor = db.execute(
        """
        INSERT INTO live_trades
            (signal_id, symbol, strategy, strategy_version, direction,
             entry_price, filled_price, stop_loss, take_profit,
             open_time, status, mae, mfe,
             entry_order_id, sl_order_id, tp_order_id, leverage, quantity)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,0,0,?,?,?,?,?)
        """,
        (
            signal.get("signal_id"),
            symbol,
            strategy,
            signal.get("strategy_version"),
            direction,
            entry,
            filled_price,
            sl,
            tp,
            int(time.time()),
            status,
            entry_order_id,
            sl_order_id,
            tp_order_id,
            leverage,
            quantity,
        ),
    )
    db.commit()

    trade_row = dict(db.execute(
        "SELECT * FROM live_trades WHERE id=?", (cursor.lastrowid,)
    ).fetchone())

    logger.info(
        f"Live trade opened: {symbol} {direction} {strategy} "
        f"qty={quantity} lev={leverage}x status={status}"
    )

    # Notify immediately for MARKET fills; LIMIT notifies when filled in monitor
    if status == "open" and send:
        try:
            await send(_format_opened(trade_row))
        except Exception as e:
            logger.warning(f"Trade opened notification failed: {e}")

    return cursor.lastrowid


async def monitor_live_trades(db: sqlite3.Connection,
                               send: SendFn | None = None) -> None:
    trades = db.execute(
        "SELECT * FROM live_trades WHERE status IN ('pending', 'open')"
    ).fetchall()

    for trade in trades:
        trade = dict(trade)
        symbol = trade["symbol"]
        trade_id = trade["id"]
        direction = trade["direction"]

        if trade["status"] == "pending":
            await _monitor_pending(trade, db, send)
            continue

        # status == 'open' — check SL and TP orders
        closed = False

        for order_type, reason in [("sl", "sl"), ("tp", "tp")]:
            order_id = trade.get(f"{order_type}_order_id")
            if not order_id:
                continue
            try:
                order = await get_order(symbol, order_id)
            except Exception as e:
                logger.warning(f"get_order failed {symbol} #{order_id}: {e}")
                continue

            if order["status"] == "FILLED":
                close_price = float(order.get("avgPrice") or order.get("stopPrice"))
                entry = trade["filled_price"] or trade["entry_price"]
                pnl_pct = _calc_pnl(entry, close_price, direction, trade["stop_loss"], trade["leverage"])
                db.execute(
                    """UPDATE live_trades
                       SET status='closed', close_price=?, close_time=?,
                           close_reason=?, pnl_pct=?
                       WHERE id=?""",
                    (close_price, int(time.time()), reason, round(pnl_pct, 4), trade_id),
                )
                db.commit()
                closed = True

                other_id = trade["tp_order_id"] if reason == "sl" else trade["sl_order_id"]
                if other_id:
                    try:
                        await cancel_order(symbol, other_id)
                    except Exception:
                        pass

                logger.info(f"Live trade closed: {symbol} #{trade_id} via {reason} pnl={pnl_pct:.3f}%")

                if send:
                    try:
                        await send(_format_closed(trade, close_price, reason, pnl_pct))
                    except Exception as e:
                        logger.warning(f"Trade closed notification failed: {e}")
                break

        if not closed:
            try:
                from data.binance import get_price
                price = await get_price(symbol)
                entry = trade["filled_price"] or trade["entry_price"]
                adverse = (entry - price) if direction == "LONG" else (price - entry)
                favorable = (price - entry) if direction == "LONG" else (entry - price)
                new_mae = max(trade["mae"], adverse)
                new_mfe = max(trade["mfe"], favorable)
                db.execute(
                    "UPDATE live_trades SET mae=?, mfe=? WHERE id=?",
                    (new_mae, new_mfe, trade_id),
                )
                db.commit()
            except Exception as e:
                logger.warning(f"MAE/MFE update failed for {symbol}: {e}")


async def _monitor_pending(trade: dict, db: sqlite3.Connection,
                            send: SendFn | None = None) -> None:
    symbol = trade["symbol"]
    trade_id = trade["id"]
    order_id = trade["entry_order_id"]
    direction = trade["direction"]
    quantity = trade["quantity"]
    sl = trade["stop_loss"]
    tp = trade["take_profit"]

    age_minutes = (int(time.time()) - trade["open_time"]) / 60
    if age_minutes > config.LIMIT_ORDER_EXPIRY_MINUTES:
        try:
            await cancel_order(symbol, order_id)
        except Exception:
            pass
        db.execute("UPDATE live_trades SET status='cancelled' WHERE id=?", (trade_id,))
        db.commit()
        logger.info(f"Limit order expired and cancelled: {symbol} #{trade_id}")
        return

    try:
        order = await get_order(symbol, order_id)
    except Exception as e:
        logger.warning(f"get_order failed for pending {symbol} #{trade_id}: {e}")
        return

    if order["status"] == "FILLED":
        filled_price = float(order.get("avgPrice") or order.get("price"))
        sl_side = "SELL" if direction == "LONG" else "BUY"
        sl_order_id = None
        tp_order_id = None
        try:
            sl_resp = await place_order(
                symbol, sl_side, quantity, "STOP_MARKET",
                stop_price=round(sl, _price_precision(sl)),
                reduce_only=True,
            )
            tp_resp = await place_order(
                symbol, sl_side, quantity, "TAKE_PROFIT_MARKET",
                stop_price=round(tp, _price_precision(tp)),
                reduce_only=True,
            )
            sl_order_id = sl_resp["orderId"]
            tp_order_id = tp_resp["orderId"]
        except Exception as e:
            logger.error(f"SL/TP placement after fill failed {symbol}: {e}")

        db.execute(
            """UPDATE live_trades
               SET status='open', filled_price=?, sl_order_id=?, tp_order_id=?
               WHERE id=?""",
            (filled_price, sl_order_id, tp_order_id, trade_id),
        )
        db.commit()
        logger.info(f"Limit order filled: {symbol} #{trade_id} @ {filled_price}")

        updated = dict(db.execute(
            "SELECT * FROM live_trades WHERE id=?", (trade_id,)
        ).fetchone())
        if send:
            try:
                await send(_format_opened(updated))
            except Exception as e:
                logger.warning(f"Trade opened notification failed: {e}")

    elif order["status"] in ("CANCELED", "EXPIRED", "REJECTED"):
        db.execute("UPDATE live_trades SET status='cancelled' WHERE id=?", (trade_id,))
        db.commit()


# ─── Message formatters ───────────────────────────────────────────────────────

def _format_opened(trade: dict) -> str:
    direction = trade["direction"]
    symbol = trade["symbol"].replace("USDT", "/USDT")
    icon = "🟢" if direction == "LONG" else "🔴"
    entry = trade["filled_price"] or trade["entry_price"]
    sl = trade["stop_loss"]
    tp = trade["take_profit"]
    sl_dist = abs(entry - sl)
    tp_dist = abs(tp - entry)
    strategy_labels = {"trend_pullback": "Trend Pullback", "vol_breakout": "Vol. Breakout"}
    strategy = strategy_labels.get(trade.get("strategy", ""), trade.get("strategy", ""))
    order_type = "LIMIT" if trade.get("strategy") == "trend_pullback" else "MARKET"
    risk_usd = round(config.ACCOUNT_SIZE * config.RISK_PER_TRADE, 2)
    target_usd = round(risk_usd * config.RR_TARGET, 2)
    risk_pct = round(config.RISK_PER_TRADE * 100, 1)
    target_pct = round(config.RISK_PER_TRADE * config.RR_TARGET * 100, 1)

    return (
        f"{icon} TRADE OPENED: {direction} {symbol}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Strategy:    {strategy} ({order_type})\n"
        f"Entry:       {_fmt(entry)}\n"
        f"Stop Loss:   {_fmt(sl)}  (-${risk_usd}, -{risk_pct}%)\n"
        f"Take Profit: {_fmt(tp)}  (+${target_usd}, +{target_pct}%)\n"
        f"Leverage: {trade.get('leverage', '?')}x | Qty: {trade.get('quantity', '?')}"
    )


def _format_closed(trade: dict, close_price: float,
                   close_reason: str, pnl_pct: float) -> str:
    direction = trade["direction"]
    symbol = trade["symbol"].replace("USDT", "/USDT")
    entry = trade["filled_price"] or trade["entry_price"]
    pnl_usd = round(pnl_pct / 100 * config.ACCOUNT_SIZE, 2)

    if close_reason == "tp":
        icon, result = "✅", "TP HIT"
    else:
        icon, result = "❌", "SL HIT"

    sign = "+" if pnl_pct >= 0 else ""
    return (
        f"{icon} TRADE CLOSED: {direction} {symbol}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Result:  {result}\n"
        f"Entry:   {_fmt(entry)}  →  Exit: {_fmt(close_price)}\n"
        f"PnL:     {sign}{round(pnl_pct, 3)}%  ({sign}${pnl_usd})"
    )


def _calc_pnl(entry: float, close: float, direction: str, sl: float, leverage: int) -> float:
    sl_dist_pct = abs(entry - sl) / entry
    fee_account = config.TAKER_FEE * 2 * leverage * 100
    if direction == "LONG":
        raw = (close - entry) / entry
    else:
        raw = (entry - close) / entry
    return raw / sl_dist_pct * config.RISK_PER_TRADE * 100 - fee_account


def _price_precision(price: float) -> int:
    if price >= 1000:
        return 1
    if price >= 10:
        return 2
    return 4


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if v > 10_000:
            return f"{v:,.1f}"
        if v > 1_000:
            return f"{v:,.2f}"
        if v > 10:
            return f"{v:.2f}"
        return f"{v:.4f}"
    return str(v)
