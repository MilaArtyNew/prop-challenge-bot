import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
STRATEGY_VERSION = "v1"

TF_EXECUTION = "15m"
TF_TREND = "1h"

ACCOUNT_SIZE = 5000
RISK_PER_TRADE = 0.009   # 0.9% = $45 на $5000
RR_TARGET = 2.0          # TP = $90 на $5000

# Strategy 1: Trend Pullback
TP1_EMA_FAST = 50
TP1_EMA_SLOW = 200
TP1_RSI_PERIOD = 14
TP1_ATR_PERIOD = 14
TP1_RSI_LONG_ZONE = (35, 55)
TP1_RSI_SHORT_ZONE = (45, 65)
TP1_PULLBACK_ATR_THRESHOLD = 1.5  # price within N ATRs of EMA50

# Strategy 2: Volatility Breakout
VB_ATR_COMPRESSION = 0.7
VB_BB_COMPRESSION = 0.7
VB_RANGE_CANDLES = 12
VB_VOLUME_MULT = 1.3

SLIPPAGE_PCT = 0.0002
TAKER_FEE = 0.0004

SESSIONS = {
    "Asia": (0, 8),
    "Europe": (8, 16),
    "US": (13, 22),
}

MAX_DAILY_LOSS_PCT = 2.0
MAX_TRADES_PER_DAY = 3

DB_PATH = os.getenv("DB_PATH", "data/prop_challenge.db")
