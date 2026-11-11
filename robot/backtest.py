"""Prueba la estrategia sobre precios históricos o sintéticos."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .bot import Robot
from .broker import PaperBroker
from .config import Config

TF_MINUTES = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


def run_backtest(cfg: Config, closes: list[float]) -> dict:
    broker = PaperBroker(cfg.starting_balance, cfg.fee_rate)
    bot = Robot(cfg, broker, data=None, persist=False)
    step = timedelta(minutes=TF_MINUTES.get(cfg.timeframe, 1))
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    warmup = cfg.slow_ema + 2
    for i in range(warmup, len(closes)):
        now += step
        bot.step(closes[: i + 1], closes[i], now)
    if bot.position:  # cierra lo que quede abierto al final
        bot._close(closes[-1], now, "end_of_test")

    trades = bot.closed_trades
    wins = [t for t in trades if t["profit"] > 0]
    return {
        "trades": len(trades),
        "wins": len(wins),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
        "total_profit": round(sum(t["profit"] for t in trades), 4),
        "final_balance": round(broker.balance, 4),
        "by_reason": {r: sum(1 for t in trades if t["reason"] == r) for r in {t["reason"] for t in trades}},
    }
