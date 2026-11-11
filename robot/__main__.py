"""Punto de entrada: python -m robot [run|backtest] --config config.yaml"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .backtest import run_backtest
from .bot import Robot
from .broker import LiveBroker, PaperBroker
from .config import load_config
from .data import ExchangeData, SyntheticData, make_exchange


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="robot", description="Robot de trading automático")
    p.add_argument("command", choices=["run", "backtest"], nargs="?", default="run")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--candles", type=int, default=1000, help="velas para el backtest")
    p.add_argument("--yes-live", action="store_true", help="confirma que quieres operar con dinero real")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)

    if args.command == "backtest":
        if cfg.data_source == "synthetic":
            closes = SyntheticData(seed=42, history=args.candles).closes
        else:
            ex = make_exchange(cfg)
            closes = [c[4] for c in ex.fetch_ohlcv(cfg.symbol, cfg.timeframe, limit=args.candles)]
        print(json.dumps(run_backtest(cfg, closes), indent=2, ensure_ascii=False))
        return 0

    if cfg.mode == "live" and not args.yes_live:
        print("Modo live = DINERO REAL. Vuelve a ejecutar con --yes-live si estás seguro.")
        return 1

    if cfg.data_source == "synthetic":
        data = SyntheticData()
        broker = PaperBroker(cfg.starting_balance, cfg.fee_rate)
    else:
        ex = make_exchange(cfg)
        data = ExchangeData(ex, cfg.symbol, cfg.timeframe)
        broker = LiveBroker(ex) if cfg.mode == "live" else PaperBroker(cfg.starting_balance, cfg.fee_rate)

    try:
        Robot(cfg, broker, data).run_forever()
    except KeyboardInterrupt:
        logging.info("Robot detenido por el usuario")
    return 0


if __name__ == "__main__":
    sys.exit(main())
