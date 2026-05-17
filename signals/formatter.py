def format_signal(s: dict) -> str:
    icon = "🟢" if s["direction"] == "LONG" else "🔴"
    strategy_labels = {
        "trend_pullback": "Trend Pullback",
        "vol_breakout": "Vol. Breakout",
    }
    label = strategy_labels.get(s["strategy"], s["strategy"])
    sym = s["symbol"].replace("USDT", "/USDT")
    version = s.get("strategy_version", "")

    lines = [
        f"{icon} SIGNAL: {s['direction']} {sym}",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"Strategy: {label} {version}",
        f"Entry zone: {_fmt(s.get('entry_low'))} – {_fmt(s.get('entry_high'))}",
        f"Stop Loss: {_fmt(s['stop_loss'])}",
        f"Take Profit: {_fmt(s['take_profit'])}",
        f"Risk/Reward: 1:{s['rr']}",
        f"ATR (15m): {_fmt(s['atr'])}",
    ]

    if s.get("rsi"):
        lines.append(f"RSI (14): {s['rsi']}")
    if s.get("volume_ratio"):
        lines.append(f"Volume: {s['volume_ratio']}x avg")
    if s.get("confirmation"):
        lines.append(f"Trigger: {s['confirmation'].replace('_', ' ').title()}")
    if s.get("atr_ratio"):
        lines.append(f"ATR compression: {s['atr_ratio']}x")
    if s.get("regime"):
        lines.append(f"Regime: {s['regime']}")

    lines.extend(["", "⚠️ Manual execution. Check context before opening."])
    return "\n".join(lines)


def format_regime(regime: dict) -> str:
    icons = {"BULL": "🐂", "BEAR": "🐻", "SIDEWAYS": "↔️", "UNKNOWN": "❓"}
    r = regime.get("regime", "UNKNOWN")
    icon = icons.get(r, "")
    lines = [
        f"{icon} BTC Regime: {r}",
        f"EMA50:  {_fmt(regime.get('ema50'))}",
        f"EMA200: {_fmt(regime.get('ema200'))}",
        f"Price:  {_fmt(regime.get('price'))}",
        f"Longs:  {'✅' if regime.get('long_allowed') else '❌'}",
        f"Shorts: {'✅' if regime.get('short_allowed') else '❌'}",
    ]
    return "\n".join(lines)


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if v > 10_000:
            return f"{v:,.0f}"
        if v > 1_000:
            return f"{v:,.2f}"
        if v > 10:
            return f"{v:.2f}"
        return f"{v:.4f}"
    return str(v)
