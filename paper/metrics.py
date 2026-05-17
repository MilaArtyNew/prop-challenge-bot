from typing import Optional


def calculate_metrics(trades: list[dict]) -> dict:
    closed = [t for t in trades if t["status"] == "closed"]
    if not closed:
        return {"total": 0, "open": len([t for t in trades if t["status"] == "open"])}

    wins = [t for t in closed if t["pnl_pct"] > 0]
    losses = [t for t in closed if t["pnl_pct"] <= 0]

    total = len(closed)
    win_rate = len(wins) / total * 100
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0.0

    wr = win_rate / 100
    expectancy = wr * avg_win + (1 - wr) * avg_loss

    gross_profit = sum(t["pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["pnl_pct"] for t in losses))
    profit_factor: Optional[float] = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    mae_vals = [t["mae"] for t in closed if t["mae"] is not None]
    mfe_vals = [t["mfe"] for t in closed if t["mfe"] is not None]
    avg_mae = sum(mae_vals) / len(mae_vals) if mae_vals else 0
    avg_mfe = sum(mfe_vals) / len(mfe_vals) if mfe_vals else 0

    by_strategy: dict[str, dict] = {}
    for t in closed:
        s = t.get("strategy") or "unknown"
        by_strategy.setdefault(s, {"wins": 0, "losses": 0, "pnl": 0.0})
        by_strategy[s]["pnl"] += t["pnl_pct"]
        if t["pnl_pct"] > 0:
            by_strategy[s]["wins"] += 1
        else:
            by_strategy[s]["losses"] += 1

    return {
        "total": total,
        "open": len([t for t in trades if t["status"] == "open"]),
        "win_rate": round(win_rate, 1),
        "avg_win_pct": round(avg_win, 3),
        "avg_loss_pct": round(avg_loss, 3),
        "expectancy": round(expectancy, 4),
        "profit_factor": profit_factor,
        "avg_mae": round(avg_mae, 4),
        "avg_mfe": round(avg_mfe, 4),
        "by_strategy": by_strategy,
    }
