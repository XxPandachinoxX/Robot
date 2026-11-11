"""Estrategia de entrada: cruce alcista de EMAs filtrado por RSI."""
from __future__ import annotations

from .config import Config
from .indicators import ema, rsi


def should_buy(closes: list[float], cfg: Config) -> bool:
    """True si la EMA rápida acaba de cruzar por encima de la lenta y el RSI no está sobrecomprado."""
    if len(closes) < cfg.slow_ema + 2:
        return False
    fast = ema(closes, cfg.fast_ema)
    slow = ema(closes, cfg.slow_ema)
    crossed_up = fast[-2] <= slow[-2] and fast[-1] > slow[-1]
    if not crossed_up:
        return False
    return rsi(closes, cfg.rsi_period)[-1] < cfg.rsi_max_entry
