"""Ejecución de órdenes: simulada (paper) o real (live vía ccxt)."""
from __future__ import annotations


class PaperBroker:
    """Simula compras y ventas a mercado con comisión. No toca dinero real."""

    def __init__(self, balance: float, fee_rate: float):
        self.balance = balance
        self.fee_rate = fee_rate

    def buy(self, symbol: str, quote_amount: float, price: float) -> tuple[float, float, float]:
        """Devuelve (cantidad, precio, coste total en moneda cotizada)."""
        quote_amount = min(quote_amount, self.balance)
        if quote_amount <= 0:
            raise RuntimeError("Saldo insuficiente")
        qty = quote_amount * (1 - self.fee_rate) / price
        self.balance -= quote_amount
        return qty, price, quote_amount

    def sell(self, symbol: str, qty: float, price: float) -> tuple[float, float]:
        """Devuelve (precio, ingreso neto en moneda cotizada)."""
        proceeds = qty * price * (1 - self.fee_rate)
        self.balance += proceeds
        return price, proceeds

    def free_quote(self, symbol: str) -> float:
        return self.balance


class LiveBroker:
    """Órdenes reales a mercado en el exchange. ¡Usa dinero de verdad!"""

    def __init__(self, exchange):
        self.ex = exchange

    def free_quote(self, symbol: str) -> float:
        quote = self.ex.market(symbol)["quote"]
        return float(self.ex.fetch_balance()["free"].get(quote, 0.0))

    def buy(self, symbol: str, quote_amount: float, price: float) -> tuple[float, float, float]:
        if self.ex.has.get("createMarketBuyOrderWithCost"):
            order = self.ex.create_market_buy_order_with_cost(symbol, quote_amount)
        else:
            amount = float(self.ex.amount_to_precision(symbol, quote_amount / price))
            order = self.ex.create_market_buy_order(symbol, amount)
        order = self._wait_filled(order, symbol)
        qty = float(order.get("filled") or order["amount"])
        avg = float(order.get("average") or price)
        cost = float(order.get("cost") or qty * avg)
        # Si la comisión se cobra en la moneda base, la cantidad disponible es menor
        fee = order.get("fee") or {}
        base = self.ex.market(symbol)["base"]
        if fee.get("currency") == base and fee.get("cost"):
            qty -= float(fee["cost"])
        return qty, avg, cost

    def sell(self, symbol: str, qty: float, price: float) -> tuple[float, float]:
        amount = float(self.ex.amount_to_precision(symbol, qty))
        order = self._wait_filled(self.ex.create_market_sell_order(symbol, amount), symbol)
        avg = float(order.get("average") or price)
        proceeds = float(order.get("cost") or amount * avg)
        fee = order.get("fee") or {}
        quote = self.ex.market(symbol)["quote"]
        if fee.get("currency") == quote and fee.get("cost"):
            proceeds -= float(fee["cost"])
        return avg, proceeds

    def _wait_filled(self, order: dict, symbol: str) -> dict:
        if order.get("status") == "closed" or not order.get("id"):
            return order
        try:
            return self.ex.fetch_order(order["id"], symbol)
        except Exception:  # noqa: BLE001 - algunos exchanges no soportan fetch_order
            return order
