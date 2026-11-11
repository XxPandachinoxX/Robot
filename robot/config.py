"""Carga de configuración desde YAML + variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields

import yaml


@dataclass
class Config:
    # Modo: "paper" (simulado, sin dinero real) o "live" (dinero real)
    mode: str = "paper"
    # Fuente de precios: "exchange" (precios reales vía ccxt) o "synthetic" (aleatorios, para probar sin internet)
    data_source: str = "exchange"
    exchange: str = "binance"
    symbol: str = "BTC/USDT"
    timeframe: str = "1m"
    poll_seconds: int = 30

    # Dinero
    starting_balance: float = 1000.0   # solo modo paper
    trade_amount: float = 100.0        # cuánto (en moneda cotizada, ej. USDT) usar por operación
    fee_rate: float = 0.001            # comisión por lado (0.1 %)

    # Salidas
    take_profit_pct: float = 1.0       # cierra cuando gana este %
    stop_loss_pct: float = 2.0         # cierra si pierde este % (protección)
    trailing_stop_pct: float = 0.0     # 0 = desactivado; si >0, sigue el precio tras activarse el take profit
    max_hold_minutes: int = 0          # 0 = sin límite

    # Estrategia (cruce de medias + RSI)
    fast_ema: int = 9
    slow_ema: int = 21
    rsi_period: int = 14
    rsi_max_entry: float = 70.0        # no comprar si RSI está sobrecomprado

    # Seguridad
    max_trades_per_day: int = 20
    cooldown_minutes: int = 5          # espera tras cerrar antes de abrir otra
    state_file: str = "state.json"
    log_file: str = "trades.csv"

    # Credenciales (se leen de variables de entorno, nunca del YAML)
    api_key: str = field(default="", repr=False)
    api_secret: str = field(default="", repr=False)

    def validate(self) -> None:
        if self.mode not in ("paper", "live"):
            raise ValueError("mode debe ser 'paper' o 'live'")
        if self.data_source not in ("exchange", "synthetic"):
            raise ValueError("data_source debe ser 'exchange' o 'synthetic'")
        if self.mode == "live" and self.data_source != "exchange":
            raise ValueError("El modo live necesita data_source: exchange")
        if self.take_profit_pct <= 0:
            raise ValueError("take_profit_pct debe ser > 0")
        if self.stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct debe ser > 0 (siempre usa stop loss)")
        if self.fast_ema >= self.slow_ema:
            raise ValueError("fast_ema debe ser menor que slow_ema")
        if self.trade_amount <= 0:
            raise ValueError("trade_amount debe ser > 0")
        if self.mode == "live" and not (self.api_key and self.api_secret):
            raise ValueError("Modo live: define ROBOT_API_KEY y ROBOT_API_SECRET")


def load_config(path: str | None) -> Config:
    data: dict = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    known = {f.name for f in fields(Config)} - {"api_key", "api_secret"}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"Claves desconocidas en la config: {sorted(unknown)}")
    cfg = Config(**data)
    cfg.api_key = os.environ.get("ROBOT_API_KEY", "")
    cfg.api_secret = os.environ.get("ROBOT_API_SECRET", "")
    cfg.validate()
    return cfg
