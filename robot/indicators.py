"""Indicadores técnicos sin dependencias externas."""
from __future__ import annotations


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(values: list[float], period: int = 14) -> list[float]:
    """RSI de Wilder. Devuelve una lista del mismo largo (50 donde no hay datos)."""
    n = len(values)
    out = [50.0] * n
    if n <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_g, avg_l = gains / period, losses / period
    out[period] = _rsi_value(avg_g, avg_l)
    for i in range(period + 1, n):
        d = values[i] - values[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0)) / period
        out[i] = _rsi_value(avg_g, avg_l)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)
