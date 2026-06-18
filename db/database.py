import sqlite3
import os
import config


def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def seed_db(db: sqlite3.Connection) -> None:
    """Seed initial data on first run (empty DB). Safe to call always — skips if data exists."""
    if db.execute("SELECT COUNT(*) FROM signals").fetchone()[0] > 0:
        return
    try:
        from db.seed_data import SEED_SIGNALS, SEED_PAPER_TRADES, SEED_REGIME_LOG
    except ImportError:
        return

    for r in SEED_SIGNALS:
        r.pop("id", None)
        cols = ", ".join(r.keys())
        placeholders = ", ".join("?" for _ in r)
        db.execute(f"INSERT INTO signals ({cols}) VALUES ({placeholders})", list(r.values()))

    for r in SEED_PAPER_TRADES:
        r.pop("id", None)
        cols = ", ".join(r.keys())
        placeholders = ", ".join("?" for _ in r)
        db.execute(f"INSERT INTO paper_trades ({cols}) VALUES ({placeholders})", list(r.values()))

    for r in SEED_REGIME_LOG:
        r.pop("id", None)
        cols = ", ".join(r.keys())
        placeholders = ", ".join("?" for _ in r)
        db.execute(f"INSERT INTO regime_log ({cols}) VALUES ({placeholders})", list(r.values()))

    db.commit()


def init_db(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       INTEGER NOT NULL,
            symbol          TEXT NOT NULL,
            strategy        TEXT NOT NULL,
            strategy_version TEXT,
            direction       TEXT NOT NULL,
            entry_low       REAL,
            entry_high      REAL,
            stop_loss       REAL NOT NULL,
            take_profit     REAL NOT NULL,
            rr              REAL,
            atr             REAL,
            volume_ratio    REAL,
            regime          TEXT,
            status          TEXT DEFAULT 'sent'
        );

        CREATE TABLE IF NOT EXISTS paper_trades (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id        INTEGER,
            symbol           TEXT NOT NULL,
            strategy         TEXT,
            strategy_version TEXT,
            direction        TEXT NOT NULL,
            entry_price      REAL NOT NULL,
            stop_loss        REAL NOT NULL,
            take_profit      REAL NOT NULL,
            open_time        INTEGER NOT NULL,
            close_time       INTEGER,
            close_price      REAL,
            close_reason     TEXT,
            pnl_pct          REAL,
            mae              REAL DEFAULT 0,
            mfe              REAL DEFAULT 0,
            status           TEXT DEFAULT 'open'
        );

        CREATE TABLE IF NOT EXISTS regime_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            regime    TEXT NOT NULL,
            ema50     REAL,
            ema200    REAL,
            price     REAL
        );

        CREATE TABLE IF NOT EXISTS live_trades (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id        INTEGER,
            symbol           TEXT NOT NULL,
            strategy         TEXT,
            strategy_version TEXT,
            direction        TEXT NOT NULL,
            entry_price      REAL NOT NULL,
            filled_price     REAL,
            stop_loss        REAL NOT NULL,
            take_profit      REAL NOT NULL,
            open_time        INTEGER NOT NULL,
            close_time       INTEGER,
            close_price      REAL,
            close_reason     TEXT,
            pnl_pct          REAL,
            mae              REAL DEFAULT 0,
            mfe              REAL DEFAULT 0,
            status           TEXT DEFAULT 'pending',
            entry_order_id   INTEGER,
            sl_order_id      INTEGER,
            tp_order_id      INTEGER,
            leverage         INTEGER,
            quantity         REAL
        );
    """)
    db.commit()
