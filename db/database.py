import sqlite3
import os
import config


def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


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
    """)
    db.commit()
