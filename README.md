# Prop Challenge Bot

Telegram bot for prop-trading challenge signal monitoring and paper-trade tracking.

The bot scans configured symbols, evaluates strategy setups, sends Telegram alerts, and tracks simulated trades with risk rules similar to prop challenge constraints.

## Features

- Binance market data collection.
- Regime filter.
- Trend pullback strategy.
- Volatility breakout strategy.
- Paper-trade engine and metrics.
- Telegram signal delivery.
- SQLite persistence.
- Railway and systemd deployment files.

## Default Market Setup

Configured symbols:

- `BTCUSDT`
- `ETHUSDT`
- `SOLUSDT`

Default timeframes:

- Execution: `15m`
- Trend: `1h`

## Environment

```bash
cp .env.example .env
```

Required variables:

- `TELEGRAM_TOKEN` — Telegram bot token.
- `TELEGRAM_CHAT_ID` — target chat ID.

Optional:

- `DB_PATH` — SQLite database path, default `data/prop_challenge.db`.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python main.py
```

## Deployment

The repository includes:

- `railway.toml`
- `prop-challenge.service`

Set environment variables in the target runtime. Do not commit `.env`.

## Risk Notes

- This bot is for signal monitoring and paper-trade tracking.
- It does not guarantee prop challenge success.
- Validate all signals manually before using any live execution workflow.
