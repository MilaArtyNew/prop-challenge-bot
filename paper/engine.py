import sqlite3
import time
import logging
from data.binance import get_price
import config

logger = logging.getLogger(__name__)


async def open_paper_trade(signal: dict, db: sqlite3.Connection) -> int:
    slip = config.SLIPPAGE_PCT
    entry_price = signal["entry"] * (1 + slip if signal["direction"] == "LONG" else 1 - slip)

    cursor = db.execute(
        """
        INSERT INTO paper_trades
            (signal_id, symbol, strategy, strategy_version, direction,
             entry_price, stop_loss, take_profit, open_time, status, mae, mfe)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', 0, 0)
        """,
        (
            signal.get("signal_id"),
            signal["symbol"],
            signal["strategy"],
            signal.get("strategy_version"),
            signal["direction"],
            entry_price,
            signal["stop_loss"],
            signal["take_profit"],
            int(time.time()),
        ),
    )
    db.commit()
    return cursor.lastrowid


async def monitor_open_trades(db: sqlite3.Connection) -> None:
    open_trades = db.execute(
        "SELECT * FROM paper_trades WHERE status = 'open'"
    ).fetchall()

    for trade in open_trades:
        symbol = trade["symbol"]
        try:
            price = await get_price(symbol)
        except Exception as e:
            logger.warning(f"Price fetch failed for {symbol}: {e}")
            continue

        entry = trade["entry_price"]
        sl = trade["stop_loss"]
        tp = trade["take_profit"]
        direction = trade["direction"]
        trade_id = trade["id"]

        if direction == "LONG":
            adverse = entry - price
            favorable = price - entry
        else:
            adverse = price - entry
            favorable = entry - price

        new_mae = max(trade["mae"], adverse)
        new_mfe = max(trade["mfe"], favorable)

        close_reason = None
        close_price = None

        if direction == "LONG":
            if price <= sl:
                close_reason, close_price = "sl", sl
            elif price >= tp:
                close_reason, close_price = "tp", tp
        else:
            if price >= sl:
                close_reason, close_price = "sl", sl
            elif price <= tp:
                close_reason, close_price = "tp", tp

        if close_reason:
            # raw price move % (informational)
            if direction == "LONG":
                raw_pnl = (close_price - entry) / entry * 100
            else:
                raw_pnl = (entry - close_price) / entry * 100

            # account-normalized PnL: fixed risk per trade with position sizing
            sl_dist_pct = abs(entry - trade["stop_loss"]) / entry
            leverage = config.RISK_PER_TRADE / sl_dist_pct if sl_dist_pct > 0 else 1
            fee_account = config.TAKER_FEE * 2 * leverage * 100

            if close_reason == "tp":
                pnl_pct = config.RISK_PER_TRADE * 100 * config.RR_TARGET - fee_account
            else:
                pnl_pct = -(config.RISK_PER_TRADE * 100) - fee_account

            db.execute(
                """
                UPDATE paper_trades
                SET status = 'closed', close_price = ?, close_time = ?,
                    close_reason = ?, pnl_pct = ?, mae = ?, mfe = ?
                WHERE id = ?
                """,
                (close_price, int(time.time()), close_reason, round(pnl_pct, 4),
                 new_mae, new_mfe, trade_id),
            )
        else:
            db.execute(
                "UPDATE paper_trades SET mae = ?, mfe = ? WHERE id = ?",
                (new_mae, new_mfe, trade_id),
            )

        db.commit()
