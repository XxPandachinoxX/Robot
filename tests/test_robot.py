from datetime import datetime, timedelta, timezone

import pytest

from robot.backtest import run_backtest
from robot.bot import Position, Robot, exit_reason
from robot.broker import PaperBroker
from robot.config import Config
from robot.data import SyntheticData
from robot.indicators import ema, rsi
from robot.strategy import should_buy

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def cfg(**kw):
    c = Config(data_source="synthetic", **kw)
    c.validate()
    return c


def pos(entry=100.0, fee=0.001):
    qty = 100 * (1 - fee) / entry
    return Position("X/USDT", qty, entry, 100.0, NOW.isoformat(), peak_price=entry)


def test_ema_and_rsi_basics():
    assert ema([1, 1, 1], 3) == [1, 1, 1]
    assert rsi(list(range(1, 40)))[-1] == 100.0


def test_take_profit_closes_on_net_gain():
    c = cfg(take_profit_pct=1.0)
    p = pos()
    assert exit_reason(p, 100.5, NOW, c) is None       # bruto +0.5 %, no basta
    assert exit_reason(p, 101.0, NOW, c) is None       # bruto +1 % pero neto < 1 % por comisiones
    assert exit_reason(p, 101.3, NOW, c) == "take_profit"


def test_stop_loss():
    c = cfg(stop_loss_pct=2.0)
    assert exit_reason(pos(), 97.9, NOW, c) == "stop_loss"


def test_trailing_stop_lets_winner_run():
    c = cfg(take_profit_pct=1.0, trailing_stop_pct=0.5)
    p = pos()
    assert exit_reason(p, 101.5, NOW, c) is None       # activa trailing, no vende
    assert exit_reason(p, 103.0, NOW, c) is None       # sigue subiendo
    assert exit_reason(p, 102.4, NOW, c) == "take_profit_trailing"


def test_max_hold_time():
    c = cfg(max_hold_minutes=10)
    assert exit_reason(pos(), 100.0, NOW + timedelta(minutes=11), c) == "max_hold_time"


def test_should_buy_on_cross():
    c = cfg(fast_ema=3, slow_ema=6, rsi_max_entry=101)
    closes = [100 - i * 0.5 for i in range(30)] + [90]
    assert should_buy(closes, c)
    assert not should_buy([100.0] * 40, c)


def test_robot_opens_and_closes_with_profit():
    c = cfg(fast_ema=3, slow_ema=6, rsi_max_entry=101, take_profit_pct=1.0, cooldown_minutes=0)
    broker = PaperBroker(1000, c.fee_rate)
    bot = Robot(c, broker, data=None, persist=False)
    closes = [100 - i * 0.5 for i in range(30)] + [90]
    assert bot.step(closes, 90.0, NOW) == "open"
    assert bot.step(closes, 90.5, NOW) is None
    assert bot.step(closes, 91.5, NOW) == "close:take_profit"
    assert bot.closed_trades[0]["profit"] > 0
    assert broker.balance > 1000


def test_state_survives_restart(tmp_path):
    c = cfg(state_file=str(tmp_path / "s.json"), log_file=str(tmp_path / "t.csv"))
    b1 = Robot(c, PaperBroker(1000, c.fee_rate), data=None)
    b1._open(100.0, NOW)
    b2 = Robot(c, PaperBroker(1000, c.fee_rate), data=None)
    assert b2.position is not None and b2.broker.balance == pytest.approx(900)


def test_backtest_runs():
    c = cfg()
    result = run_backtest(c, SyntheticData(seed=1, history=2000).closes)
    assert result["trades"] > 0


def test_config_requires_stop_loss():
    with pytest.raises(ValueError):
        Config(stop_loss_pct=0).validate()
