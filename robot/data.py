"""Fuentes de precios: exchange real (ccxt) o sintético (para probar sin internet)."""
from __future__ import annotations

import math
import random


class SyntheticData:
    """Paseo aleatorio con tendencias, útil para probar el robot sin conexión."""

    def __init__(self, start: float = 30000.0, seed: int | None = None, history: int = 200):
        self.rng = random.Random(seed)
        self.price = start
        self.t = 0
        self.closes: list[float] = []
        for _ in range(history):
            self._advance()

    def _advance(self) -> None:
        self.t += 1
        drift = 0.0006 * math.sin(self.t / 40)
        self.price *= 1 + drift + self.rng.gauss(0, 0.002)
        self.closes.append(self.price)
        self.closes = self.closes[-500:]

    def fetch_closes(self, limit: int) -> list[float]:
        self._advance()
        return self.closes[-limit:]

    def last_price(self) -> float:
        return self.price


class ExchangeData:
    def __init__(self, exchange, symbol: str, timeframe: str):
        self.ex = exchange
        self.symbol = symbol
        self.timeframe = timeframe

    def fetch_closes(self, limit: int) -> list[float]:
        candles = self.ex.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=limit)
        # Descarta la última vela (todavía abierta) para no dar señales que luego desaparecen
        return [c[4] for c in candles[:-1]]

    def last_price(self) -> float:
        return float(self.ex.fetch_ticker(self.symbol)["last"])


def make_exchange(cfg):
    import ccxt  # import diferido: no hace falta para modo sintético

    klass = getattr(ccxt, cfg.exchange)
    params = {"enableRateLimit": True}
    if cfg.api_key:
        params.update(apiKey=cfg.api_key, secret=cfg.api_secret)
    ex = klass(params)
    ex.load_markets()
    return ex
