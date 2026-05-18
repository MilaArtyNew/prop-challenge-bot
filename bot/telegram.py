import time
import logging
import sqlite3
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

from db.database import get_db
from paper.metrics import calculate_metrics
from signals.formatter import format_regime
import config

logger = logging.getLogger(__name__)


def build_app(bot_data: dict) -> Application:
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    app.bot_data.update(bot_data)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("regime", cmd_regime))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("trades", cmd_trades))
    app.add_handler(CommandHandler("signals", cmd_signals))
    return app


async def setup_commands(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show available commands"),
        BotCommand("status", "Bot status and last scan"),
        BotCommand("regime", "BTC market regime (1H)"),
        BotCommand("stats", "Paper trading statistics"),
        BotCommand("trades", "Last 10 closed paper trades"),
        BotCommand("signals", "Last 5 signals"),
    ])


async def send_signal(app: Application, signal: dict) -> None:
    from signals.formatter import format_signal
    text = format_signal(signal)
    await app.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Prop Challenge Bot\n\n"
        "Semi-auto signal generator for BTC/ETH/SOL.\n"
        "Strategies: Trend Pullback + Vol. Breakout\n"
        "Paper trading runs automatically.\n\n"
        "Use /help to see all commands."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n\n"
        "/status — Bot status, last scan time\n"
        "/regime — Current BTC regime (1H EMA50/200)\n"
        "/stats — Win rate, expectancy, profit factor\n"
        "/trades — Last 10 closed paper trades\n"
        "/signals — Last 5 signals sent\n\n"
        "Scans run every 15 min.\n"
        "Signals arrive here when setup conditions are met.\n"
        "Execute manually on your prop account."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    last_scan = context.bot_data.get("last_scan_time")
    last_scan_str = time.strftime("%H:%M UTC", time.gmtime(last_scan)) if last_scan else "—"
    regime = context.bot_data.get("current_regime", {})

    db = get_db()
    open_trades = db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='open'").fetchone()[0]
    total_signals = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    db.close()

    await update.message.reply_text(
        f"✅ Running\n"
        f"Last scan: {last_scan_str}\n"
        f"Regime: {regime.get('regime', '?')}\n"
        f"Open paper trades: {open_trades}\n"
        f"Total signals sent: {total_signals}\n"
        f"Symbols: BTC · ETH · SOL\n"
        f"Strategies: Trend Pullback | Vol. Breakout"
    )


async def cmd_regime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    regime = context.bot_data.get("current_regime")
    if not regime:
        await update.message.reply_text("Regime not yet loaded. Wait for the next scan.")
        return
    await update.message.reply_text(format_regime(regime))


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_db()
    rows = db.execute("SELECT * FROM paper_trades ORDER BY open_time DESC LIMIT 500").fetchall()
    db.close()

    trades = [dict(r) for r in rows]
    m = calculate_metrics(trades)

    if m["total"] == 0:
        await update.message.reply_text("No closed paper trades yet.")
        return

    pf = f"{m['profit_factor']}" if m["profit_factor"] else "N/A"
    by_s_lines = []
    for strat, v in m.get("by_strategy", {}).items():
        total_s = v["wins"] + v["losses"]
        wr_s = round(v["wins"] / total_s * 100, 1) if total_s else 0
        by_s_lines.append(f"  {strat}: {v['wins']}W/{v['losses']}L ({wr_s}%)")

    sign = "+" if m["total_pnl_usd"] >= 0 else ""
    text = (
        f"📊 Paper Trading — $5 000 account\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Closed: {m['total']} | Open: {m.get('open', 0)}\n"
        f"Win Rate:    {m['win_rate']}%\n"
        f"Avg Win:     +{m['avg_win_pct']}% (${m['avg_win_usd']})\n"
        f"Avg Loss:    {m['avg_loss_pct']}% (-${abs(m['avg_loss_usd'])})\n"
        f"Expectancy:  {m['expectancy']}% (${m['expectancy_usd']})\n"
        f"Prof.Factor: {pf}\n"
        f"Total PnL:   {sign}{m['total_pnl_pct']}% ({sign}${m['total_pnl_usd']})\n"
    )
    if by_s_lines:
        text += "\nBy strategy:\n" + "\n".join(by_s_lines)

    await update.message.reply_text(text)


async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM paper_trades WHERE status='closed' ORDER BY close_time DESC LIMIT 10"
    ).fetchall()
    db.close()

    if not rows:
        await update.message.reply_text("No closed paper trades yet.")
        return

    lines = ["📋 Last 10 paper trades:\n"]
    for r in rows:
        icon = "✅" if r["pnl_pct"] > 0 else "❌"
        sym = r["symbol"].replace("USDT", "")
        ts = time.strftime("%m-%d %H:%M", time.gmtime(r["close_time"]))
        sign = "+" if r["pnl_pct"] > 0 else ""
        lines.append(
            f"{icon} {sym} {r['direction']} | {r['close_reason'].upper()} | "
            f"{sign}{r['pnl_pct']:.3f}% | {ts}"
        )

    await update.message.reply_text("\n".join(lines))


async def cmd_signals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM signals ORDER BY timestamp DESC LIMIT 5"
    ).fetchall()
    db.close()

    if not rows:
        await update.message.reply_text("No signals yet.")
        return

    lines = ["📡 Last 5 signals:\n"]
    for r in rows:
        ts = time.strftime("%m-%d %H:%M UTC", time.gmtime(r["timestamp"]))
        sym = r["symbol"].replace("USDT", "")
        lines.append(f"• {sym} {r['direction']} | {r['strategy']} | {ts}")

    await update.message.reply_text("\n".join(lines))
