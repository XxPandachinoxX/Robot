"""Lógica principal: abre operaciones solo y las cierra al ganar (o al tocar el stop)."""
from __future__ import annotations

import csv
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from .config import Config
from .strategy import should_buy

log = logging.getLogger("robot")


@dataclass
class Position:
    symbol: str
    qty: float
    entry_price: float
    cost: float                 # lo gastado, comisión incluida
    opened_at: str
    peak_price: float = 0.0
    trailing_active: bool = False

    def net_pnl_pct(self, price: float, fee_rate: float) -> float:
        """Ganancia neta en % si se vendiera ahora (descontando la comisión de venta)."""
        proceeds = self.qty * price * (1 - fee_rate)
        return (proceeds - self.cost) / self.cost * 100


def exit_reason(pos: Position, price: float, now: datetime, cfg: Config) -> str | None:
    """Decide si hay que cerrar la posición. Actualiza el pico para el trailing stop."""
    pnl = pos.net_pnl_pct(price, cfg.fee_rate)
    pos.peak_price = max(pos.peak_price, price)

    if pnl <= -cfg.stop_loss_pct:
        return "stop_loss"

    if cfg.trailing_stop_pct > 0:
        if pnl >= cfg.take_profit_pct:
            pos.trailing_active = True
        if pos.trailing_active:
            drop = (pos.peak_price - price) / pos.peak_price * 100
            # Cierra si cae desde el pico, pero solo mientras siga en ganancia
            if drop >= cfg.trailing_stop_pct and pnl > 0:
                return "take_profit_trailing"
            if pnl <= 0:
                return "trailing_breakeven"
    elif pnl >= cfg.take_profit_pct:
        return "take_profit"

    if cfg.max_hold_minutes > 0:
        opened = datetime.fromisoformat(pos.opened_at)
        if now - opened >= timedelta(minutes=cfg.max_hold_minutes):
            return "max_hold_time"
    return None


class Robot:
    def __init__(self, cfg: Config, broker, data, persist: bool = True):
        self.cfg = cfg
        self.broker = broker
        self.data = data
        self.persist = persist
        self.position: Position | None = None
        self.last_close_at: datetime | None = None
        self.trades_today: dict[str, int] = {}
        self.closed_trades: list[dict] = []
        if persist:
            self._load_state()

    # ---------- ciclo ----------
    def step(self, closes: list[float], price: float, now: datetime) -> str | None:
        """Una iteración. Devuelve 'open', 'close:<motivo>' o None."""
        if self.position:
            reason = exit_reason(self.position, price, now, self.cfg)
            if reason:
                self._close(price, now, reason)
                return f"close:{reason}"
            self._save_state()
            return None

        if self._can_open(now) and should_buy(closes, self.cfg):
            self._open(price, now)
            return "open"
        return None

    def run_forever(self) -> None:
        log.info("Robot iniciado: %s %s modo=%s TP=%.2f%% SL=%.2f%%",
                 self.cfg.symbol, self.cfg.timeframe, self.cfg.mode,
                 self.cfg.take_profit_pct, self.cfg.stop_loss_pct)
        limit = max(self.cfg.slow_ema, self.cfg.rsi_period) * 5
        while True:
            try:
                closes = self.data.fetch_closes(limit)
                price = self.data.last_price()
                now = datetime.now(timezone.utc)
                event = self.step(closes, price, now)
                if self.position and not event:
                    pnl = self.position.net_pnl_pct(price, self.cfg.fee_rate)
                    log.info("Precio %.4f | posición abierta PnL neto %.2f%%", price, pnl)
                elif not self.position and not event:
                    log.info("Precio %.4f | esperando señal de entrada", price)
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001 - el robot no debe caerse por un error de red
                log.exception("Error en el ciclo: %s", exc)
            time.sleep(self.cfg.poll_seconds)

    # ---------- acciones ----------
    def _can_open(self, now: datetime) -> bool:
        if self.trades_today.get(now.date().isoformat(), 0) >= self.cfg.max_trades_per_day:
            return False
        if self.last_close_at and now - self.last_close_at < timedelta(minutes=self.cfg.cooldown_minutes):
            return False
        return self.broker.free_quote(self.cfg.symbol) >= self.cfg.trade_amount

    def _open(self, price: float, now: datetime) -> None:
        qty, fill, cost = self.broker.buy(self.cfg.symbol, self.cfg.trade_amount, price)
        self.position = Position(self.cfg.symbol, qty, fill, cost, now.isoformat(), peak_price=fill)
        day = now.date().isoformat()
        self.trades_today = {day: self.trades_today.get(day, 0) + 1}
        log.info("COMPRA %.8f %s a %.4f (coste %.2f)", qty, self.cfg.symbol, fill, cost)
        self._save_state()

    def _close(self, price: float, now: datetime, reason: str) -> None:
        pos = self.position
        fill, proceeds = self.broker.sell(pos.symbol, pos.qty, price)
        profit = proceeds - pos.cost
        trade = {
            "symbol": pos.symbol, "opened_at": pos.opened_at, "closed_at": now.isoformat(),
            "entry": round(pos.entry_price, 8), "exit": round(fill, 8), "qty": pos.qty,
            "cost": round(pos.cost, 4), "proceeds": round(proceeds, 4),
            "profit": round(profit, 4), "profit_pct": round(profit / pos.cost * 100, 3),
            "reason": reason,
        }
        self.closed_trades.append(trade)
        log.info("VENTA a %.4f | %s | ganancia %.4f (%.2f%%)", fill, reason, profit, trade["profit_pct"])
        self.position = None
        self.last_close_at = now
        self._log_trade(trade)
        self._save_state()

    # ---------- persistencia ----------
    def _save_state(self) -> None:
        if not self.persist:
            return
        state = {
            "position": asdict(self.position) if self.position else None,
            "last_close_at": self.last_close_at.isoformat() if self.last_close_at else None,
            "trades_today": self.trades_today,
        }
        if hasattr(self.broker, "balance"):
            state["paper_balance"] = self.broker.balance
        tmp = self.cfg.state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        os.replace(tmp, self.cfg.state_file)

    def _load_state(self) -> None:
        if not os.path.exists(self.cfg.state_file):
            return
        with open(self.cfg.state_file, encoding="utf-8") as fh:
            state = json.load(fh)
        if state.get("position"):
            self.position = Position(**state["position"])
            log.info("Posición recuperada del estado guardado: %s", self.position)
        if state.get("last_close_at"):
            self.last_close_at = datetime.fromisoformat(state["last_close_at"])
        self.trades_today = state.get("trades_today", {})
        if "paper_balance" in state and hasattr(self.broker, "balance"):
            self.broker.balance = state["paper_balance"]

    def _log_trade(self, trade: dict) -> None:
        if not self.persist:
            return
        new = not os.path.exists(self.cfg.log_file)
        with open(self.cfg.log_file, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(trade))
            if new:
                writer.writeheader()
            writer.writerow(trade)
