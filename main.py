import asyncio
import logging
import sqlite3
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from db.database import get_db, init_db, seed_db
from signals.generator import scan_all
from paper.engine import open_paper_trade, monitor_open_trades
from bot.telegram import build_app, setup_commands, send_signal
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

db: sqlite3.Connection = None
app: Application = None


async def job_scan() -> None:
    global db, app
    logger.info("Scan started")

    try:
        signals, regime = await scan_all()
        app.bot_data["last_scan_time"] = int(time.time())
        app.bot_data["current_regime"] = regime

        db.execute(
            "INSERT INTO regime_log (timestamp, regime, ema50, ema200, price) VALUES (?,?,?,?,?)",
            (int(time.time()), regime.get("regime"), regime.get("ema50"),
             regime.get("ema200"), regime.get("price")),
        )
        db.commit()

        if not signals:
            logger.info(f"No setups found. Regime: {regime.get('regime')}")
            return

        # Count today's trades (UTC midnight boundary)
        today_start = int(time.time()) - (int(time.time()) % 86400)
        trades_today = db.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE open_time >= ?",
            (today_start,),
        ).fetchone()[0]

        for signal in signals:
            # Enforce MAX_TRADES_PER_DAY
            if trades_today >= config.MAX_TRADES_PER_DAY:
                logger.info(f"Daily trade limit reached ({trades_today}/{config.MAX_TRADES_PER_DAY}), skipping")
                break

            # Max 1 open paper trade per strategy
            existing = db.execute(
                "SELECT id FROM paper_trades WHERE strategy = ? AND status = 'open'",
                (signal["strategy"],),
            ).fetchone()
            if existing:
                logger.info(f"Skip {signal['strategy']} on {signal['symbol']} — already open")
                continue

            # Symbol cooldown: skip if same symbol traded in last 4h
            cooldown_since = int(time.time()) - 4 * 3600
            recent = db.execute(
                "SELECT id FROM paper_trades WHERE symbol = ? AND open_time >= ?",
                (signal["symbol"], cooldown_since),
            ).fetchone()
            if recent:
                logger.info(f"Skip {signal['symbol']} — cooldown active (traded in last 4h)")
                continue

            cursor = db.execute(
                """
                INSERT INTO signals
                    (timestamp, symbol, strategy, strategy_version, direction,
                     entry_low, entry_high, stop_loss, take_profit, rr, atr, volume_ratio, regime)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    int(time.time()),
                    signal["symbol"],
                    signal["strategy"],
                    signal.get("strategy_version"),
                    signal["direction"],
                    signal.get("entry_low"),
                    signal.get("entry_high"),
                    signal["stop_loss"],
                    signal["take_profit"],
                    signal.get("rr"),
                    signal.get("atr"),
                    signal.get("volume_ratio"),
                    regime.get("regime"),
                ),
            )
            db.commit()

            signal["signal_id"] = cursor.lastrowid
            signal["regime"] = regime.get("regime")

            await open_paper_trade(signal, db)
            await send_signal(app, signal)
            trades_today += 1
            logger.info(f"Signal: {signal['symbol']} {signal['direction']} {signal['strategy']}")

    except Exception:
        logger.exception("Scan error")


async def job_monitor() -> None:
    global db
    try:
        await monitor_open_trades(db)
    except Exception:
        logger.exception("Monitor error")


async def main() -> None:
    global db, app

    db = get_db()
    init_db(db)
    seed_db(db)

    app = build_app({"last_scan_time": None, "current_regime": {}})

    scheduler = AsyncIOScheduler()
    scheduler.add_job(job_scan, "interval", minutes=15, id="scan")
    scheduler.add_job(job_monitor, "interval", minutes=5, id="monitor")
    scheduler.start()

    await app.initialize()
    await setup_commands(app)
    await app.start()
    await app.updater.start_polling()

    logger.info("Prop Challenge Bot running.")
    await job_scan()

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
