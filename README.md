# APEX FX Trading Bot - Complete System

**Version:** 3.0.0 (PRD Volume III Compliant)  
**Status:** PRODUCTION READY

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Features](#features)
3. [Installation](#installation)
4. [Running the System](#running-the-system)
5. [Using the Dashboard](#using-the-dashboard)
6. [Trading Modes](#trading-modes)
7. [Historical Backtesting](#historical-backtesting)
8. [API Endpoints](#api-endpoints)
9. [Configuration](#configuration)
10. [Testing](#testing)
11. [Troubleshooting](#troubleshooting)

---

## System Overview

APEX FX Trading Bot is a fully automated algorithmic trading system that trades Forex and Gold (XAUUSD) using advanced technical analysis and risk management. The system supports three operational modes:

- **PAPER** - Virtual trading with historical backtesting
- **DEMO** - Real trades on MT5 demo account
- **LIVE** - Real money trading

### Supported Instruments

| Instrument | Type | Strategy |
|------------|------|----------|
| EURUSD | Forex | EMA Crossover + Trend |
| GBPUSD | Forex | Momentum + Fibonacci |
| USDJPY | Forex | Carry Trade + BoJ Filter |
| XAUUSD | Gold | Multi-Timeframe Breakout |

---

## Features

### Core Trading Features
- 15-step pre-trade validation pipeline
- 6 instrument-specific trading strategies
- Regime detection (Trending/Ranging/Breakout)
- Kelly position sizing
- Volatility Risk Scalar (VRS)
- Portfolio Heat Monitor
- Trailing stops
- Time-based exits

### Risk Management
- Signal Scorer (grades: HIGH/STD/MARGINAL/REJECT)
- Regime Drift Detector
- Fill Analyzer
- Calendar/Swap filters
- Correlation controls
- Max drawdown limits

### UI Features
- Real-time dashboard with 7 zones
- Live candlestick charts (multiple timeframes)
- Watchlist with live prices
- Signal queue
- Position management
- Event logging
- Mode switching

---

## Installation

### Prerequisites

1. **Python 3.11+** - [Download Python](https://www.python.org/downloads/)
2. **MetaTrader 5** - For DEMO/LIVE trading (optional for PAPER mode)
3. **Windows 10/11** (developed for Windows)

### Step 1: Install Dependencies

```bash
# Navigate to the project folder
cd TradingBot

# Install required packages
pip install flask flask-cors flask-sse metatrader5 pandas numpy pyyaml
```

Or install all at once:
```bash
pip install flask flask-cors flask-sse metatrader5 pandas numpy pyyaml pillow requests
```

### Step 2: Configure MT5 (Optional - for DEMO/LIVE mode)

Edit `config/mt5_config.yaml`:
```yaml
mt5:
  account:
    demo: true  # Set to false for LIVE trading
    server: "Your-Broker-Server"
    login: 12345678
    password: "your_password"
```

### Step 3: Run the System

```bash
python -m src.api.main
```

### Step 4: Open Dashboard

Open your browser and go to:
```
http://localhost:5000
```

---

## Using the Dashboard

### Header Zone
- **Mode Indicator**: Shows current mode (PAPER/DEMO/LIVE)
- **MT5 Status**: Connection status
- **Equity/Balance**: Account values
- **VRS**: Volatility Risk Scalar
- **Heat**: Portfolio heat gauge

### KPI Strip
- Today's P&L
- Open Positions count
- Win Rate
- Profit Factor
- Portfolio Heat %
- BQS (Broker Quality Score)
- RDD Status

### Control Panel
- **Switch Mode Button**: Toggle between PAPER/DEMO/LIVE
- **Start/Stop Scanning**: Auto-scan toggle
- **Run Manual Scan**: Execute scan immediately
- **Emergency Stop**: Close all positions

### Historical Backtest Panel
1. Select start date
2. Select end date  
3. Choose currency pairs to test
4. Click "Run Historical Backtest"
5. View results on chart and in positions panel

---

## Trading Modes

### PAPER Mode (Default)
- **Purpose**: Training, testing, backtesting
- **Behavior**: 
  - Virtual trades with simulated execution
  - Full P&L tracking
  - Uses historical data for backtesting
  - Commission/spread simulated
- **How to use**:
  1. Click "Switch" to select PAPER mode
  2. Use the Backtest panel to select date range
  3. Click "Run Historical Backtest"
  4. Watch trades execute on the chart

### DEMO Mode
- **Purpose**: Testing with real broker conditions
- **Behavior**:
  - Real trades on MT5 demo account
  - No real money risk
  - Tests execution quality
- **How to use**:
  1. Ensure MT5 demo account is configured
  2. Click "Switch" to select DEMO mode
  3. Click "Run Manual Scan"
  4. Real trades will execute on demo account

### LIVE Mode
- **Purpose**: Real money trading
- **Behavior**:
  - Real trades on MT5 live account
  - Full risk management active
  - WARNING: Real money at risk!
- **How to use**:
  1. Configure MT5 live credentials
  2. Click "Switch" - confirmation dialog appears
  3. Confirm to enable LIVE mode
  4. Trades execute with real money

---

## Historical Backtesting

The backtesting feature allows you to test the system using historical data:

### How to Run a Backtest

1. **Select Mode**: Ensure you're in PAPER mode
2. **Set Date Range**: 
   - Start Date: e.g., 2026-01-01
   - End Date: e.g., 2026-04-10
3. **Select Pairs**: Check the pairs you want to test
4. **Run**: Click "Run Historical Backtest"

### Backtest Results

The system will show:
- Total trades executed
- Total P&L
- Win Rate
- Trade markers on the chart

### Understanding Backtest

The backtest uses:
- **Entry Signal**: EMA 9/21 crossover
- **Stop Loss**: 50 pips
- **Take Profit**: 100 pips (1:2 risk-reward)
- **Execution**: Simulates entry at close price with spread

---

## API Endpoints

### Core Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/api/account` | GET | Account info |
| `/api/positions` | GET | Open positions |
| `/api/signals` | GET | Active signals |
| `/api/market/ohlc` | GET | OHLC data |

### Mode Control
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v3/mode` | GET | Get current mode |
| `/api/v3/mode` | POST | Switch mode |

### Trading
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/system/scan-v2` | POST | Run manual scan |
| `/api/backtest` | POST | Run backtest |

### Statistics
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Trading stats |
| `/api/v2/heat` | GET | Heat monitor |
| `/api/v2/vrs` | GET | VRS scalar |
| `/api/v2/bqs` | GET | Broker quality |
| `/api/v2/rdd` | GET | Regime drift |

---

## Configuration

### Main Config (`config/config.yaml`)
```yaml
trading:
  mode: "PAPER"  # PAPER, DEMO, or LIVE

risk:
  max_heat_pct: 6
  max_daily_loss: 5
  max_position_size: 1.0
```

### MT5 Config (`config/mt5_config.yaml`)
```yaml
mt5:
  account:
    demo: true
    server: "Deriv-Demo"
    login: 6023219
    password: ""
```

### Paper Config (`config/paper_config.yaml`)
```yaml
paper:
  starting_balance: 10000
  commission_per_lot: 7
  slippage_pips: 0.3
```

---

## Testing

### Test 1: API Server
```bash
python -m src.api.main
# Should show: Running on http://localhost:5000
```

### Test 2: Dashboard
- Open http://localhost:5000
- Should see dashboard with live data

### Test 3: Mode Switching
- Click "Switch" button
- Mode should change (PAPER → DEMO → LIVE)

### Test 4: Backtest
1. Select dates (e.g., 2026-01-01 to 2026-03-31)
2. Select pairs (EURUSD, XAUUSD)
3. Click "Run Historical Backtest"
4. Check positions panel for trades

### Test 5: DEMO Mode
1. Switch to DEMO mode
2. Click "Run Manual Scan"
3. If signals found, real demo trades execute
4. Check MT5 terminal for executed trades

---

## Troubleshooting

### Dashboard Shows "Connecting..."
- Check if API server is running
- Check browser console (F12) for errors
- Verify MT5 connection

### No Signals Generated
- Check if market is open
- EMA crossover requires specific conditions
- Try different date ranges for backtest

### Backtest Not Working
- Ensure you're in PAPER mode
- Check date format (YYYY-MM-DD)
- Verify MT5 has historical data

### MT5 Connection Issues
- Ensure MT5 terminal is installed
- Check login credentials
- Verify server name matches broker

### Trades Not Executing
- Check mode (PAPER doesn't execute real trades)
- Verify heat level not at CRITICAL
- Check calendar filter (no trading during major holidays)

---

## File Structure

```
TradingBot/
├── main.py                      # Legacy entry point
├── src/
│   ├── api/main.py             # Flask API server
│   ├── config/__init__.py      # Configuration loader
│   ├── data/
│   │   ├── mt5_connector.py    # MT5 connection
│   │   └── database.py        # SQLite database
│   ├── strategies/engine.py   # Trading strategies
│   ├── risk/                  # Risk management modules
│   ├── execution/             # Order execution
│   ├── paper/paper_engine.py  # Paper trading
│   └── monitoring/            # Event logging
├── config/
│   ├── config.yaml             # Main config
│   ├── mt5_config.yaml         # MT5 credentials
│   └── paper_config.yaml      # Paper settings
├── templates/
│   └── index.html              # Dashboard UI
├── tests/                      # Unit tests
└── README.md                   # This file
```

---

## Important Notes

1. **Always test in PAPER mode first** before using DEMO or LIVE
2. **Backtesting is not guarantee of future results**
3. **Start with small position sizes** in LIVE mode
4. **Monitor the system** during live trading
5. **Keep MT5 terminal running** for DEMO/LIVE modes

---

## Support

For issues or questions:
- Check the browser console (F12) for error messages
- Review the API logs in the terminal
- Check MT5 terminal for trade confirmations

---

**Version 3.0.0 - PRD Volume III Compliant**  
**Last Updated:** April 10, 2026
