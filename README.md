# Robot de trading automático

Robot en Python que **abre operaciones solo** y **las cierra cuando gana** (take profit),
con stop loss de protección. Funciona con cualquier exchange de criptomonedas soportado por
[ccxt](https://github.com/ccxt/ccxt) (Binance, Bybit, Kraken, OKX…).

> ⚠️ El trading conlleva riesgo de pérdida. Ningún robot gana siempre. Empieza en modo
> `paper` (simulado), haz backtests y usa solo dinero que puedas perder.

## Cómo funciona

1. Cada `poll_seconds` descarga las velas del par (`symbol`, `timeframe`).
2. **Entrada:** compra cuando la EMA rápida cruza por encima de la lenta y el RSI no está
   sobrecomprado (`rsi_max_entry`).
3. **Salida automática:**
   - `take_profit_pct`: vende al alcanzar esa ganancia **neta** (ya descontadas comisiones).
   - `stop_loss_pct`: vende si la pérdida llega a ese %.
   - `trailing_stop_pct` (opcional): al llegar al take profit no vende aún; deja correr la
     ganancia y vende cuando el precio cae ese % desde el máximo.
   - `max_hold_minutes` (opcional): cierra si la operación dura demasiado.
4. Guarda la posición en `state.json` (si reinicias, la recupera) y cada operación cerrada en
   `trades.csv`.
5. Límites de seguridad: `max_trades_per_day` y `cooldown_minutes` entre operaciones.

Solo opera en largo (compra → vende), una posición a la vez.

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # y edítalo
```

## Uso

```bash
# Backtest con precios reales del exchange (últimas 1000 velas)
python -m robot backtest --candles 1000

# Robot en modo simulado (paper) con precios reales — recomendado para empezar
python -m robot run

# Probar sin internet: pon data_source: synthetic en config.yaml
```

### Dinero real (modo live)

1. Crea una API key en tu exchange **solo con permiso de trading** (sin retiros).
2. Pon `mode: live` en `config.yaml`.
3. Exporta las claves (nunca las escribas en el YAML):
   ```bash
   export ROBOT_API_KEY="..."
   export ROBOT_API_SECRET="..."
   ```
4. Ejecuta confirmando: `python -m robot run --yes-live`

Detén el robot con `Ctrl+C`. Si queda una posición abierta, al reiniciar la seguirá gestionando.

## Tests

```bash
python -m pytest -q
```

## Estructura

| Archivo | Qué hace |
|---|---|
| `robot/bot.py` | Ciclo principal, apertura/cierre, take profit / stop loss / trailing |
| `robot/strategy.py` | Señal de entrada (cruce EMA + RSI) |
| `robot/indicators.py` | EMA y RSI |
| `robot/broker.py` | Órdenes simuladas (`PaperBroker`) y reales (`LiveBroker`) |
| `robot/data.py` | Precios del exchange o sintéticos |
| `robot/backtest.py` | Simulación sobre histórico |
| `config.example.yaml` | Configuración comentada |
