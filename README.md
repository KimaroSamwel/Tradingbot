# APEX FX Trading Bot

**Production-Ready Multi-Market Trading System**
*Following PRD Specification v1.0*

---

## Overview

APEX FX Trading Bot is a professional-grade algorithmic trading system supporting:
- **Multi-source data**: MT5 (Forex/Metals), Binance (Crypto), Polygon (Stocks)
- **30+ Technical Indicators** with pattern recognition
- **6 Strategy Categories**: Trend, Mean Reversion, Breakout, Grid, Scalping, Custom
- **Strict Risk Management**: Position sizing, drawdown limits, max positions, correlation limits
- **Full Backend**: Flask API, SQLite database, real-time updates, Telegram alerts
- **Backtesting**: Historical backtesting, walk-forward validation, parameter optimization

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py

# Open dashboard
http://localhost:5000
```

---

## Architecture

```
APEX FX Trading Bot/
├── main.py                    # Entry point
├── src/
│   ├── config/               # Configuration management
│   ├── data/                 # Database & connectors
│   │   ├── database.py       # SQLite database
│   │   ├── mt5_connector.py  # MT5 integration
│   │   └── binance_connector.py  # Binance crypto
│   ├── analysis/
│   │   └── technical.py      # 30+ technical indicators
│   ├── strategies/
│   │   └── engine.py         # Strategy engine (6 categories)
│   ├── risk/
│   │   └── manager.py        # Risk management
│   ├── api/
│   │   └── main.py           # Flask API
│   ├── monitoring/           # Performance tracking
│   └── backtesting/          # Backtesting engine
├── config/                   # Configuration files
├── templates/
│   └── index.html            # Dashboard UI
└── apex_trading.db           # SQLite database
```

---

## Features

### Technical Analysis (30+ Indicators)
- **Trend**: EMA, SMA, Parabolic SAR, Ichimoku, Supertrend
- **Momentum**: RSI, Stochastic, MACD, CCI, Williams %R, ROC
- **Volatility**: ATR, Bollinger Bands, Keltner Channel, Donchian
- **Volume**: MFI, OBV, VWAP
- **Patterns**: Doji, Hammer, Engulfing, Morning/Evening Star

### Strategy Categories
1. **Trend Following**: EMA Crossover, Supertrend, Ichimoku
2. **Mean Reversion**: RSI, Bollinger Bounce, Stochastic
3. **Breakout**: Donchian, Higher Highs
4. **Grid Trading**: Range-bound strategies
5. **Scalping**: AO Cross, Volume Spike
6. **Custom/AI**: Multi-factor confluence

### Risk Management
- Position sizing (Kelly Criterion available)
- Max risk per trade (1% default)
- Daily loss limit (2%)
- Max concurrent positions (3)
- Circuit breaker after 3 consecutive losses
- Correlation limits

### Data Sources
- **MT5**: Forex, Metals (XAUUSD, etc.)
- **Binance**: Crypto (BTCUSDT, etc.)
- **Polygon**: Stocks (future)

---

## API Endpoints

### Account
- `GET /api/account` - Account info
- `POST /api/account/connect` - Connect MT5
- `POST /api/account/disconnect` - Disconnect MT5

### Positions
- `GET /api/positions` - Open positions
- `POST /api/positions/open` - Open position
- `POST /api/positions/close/<ticket>` - Close position
- `POST /api/positions/close-all` - Close all

### Signals
- `GET /api/signals` - Recent signals
- `POST /api/signals/scan` - Scan for signals

### Watchlist
- `GET /api/watchlist` - Get watchlist
- `POST /api/watchlist` - Update watchlist
- `POST /api/watchlist/add` - Add symbol
- `POST /api/watchlist/remove/<symbol>` - Remove symbol

### Market Data
- `GET /api/market/ohlc` - OHLC data
- `GET /api/market/indicators` - Technical indicators
- `GET /api/market/symbols` - Available symbols

### Risk
- `GET /api/risk/status` - Risk status
- `POST /api/risk/validate` - Validate trade

### Stats
- `GET /api/stats` - Trading statistics
- `GET /api/stats/performance` - Performance history
- `GET /api/stats/trades` - Trade history

---

## Configuration

Edit `config/config.yaml` to customize:
- Broker settings (MT5, Binance)
- Trading parameters (risk, positions)
- Symbol lists
- Timeframes
- Sessions

---

## Disclaimer

**Trading involves substantial risk.** Only trade with capital you can afford to lose. Always use proper risk management and test strategies thoroughly before live trading.

---

*Version: 1.0.0 | Built: 2026-04-08*