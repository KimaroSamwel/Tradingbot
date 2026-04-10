# APEX FX Trading Bot - Technical Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Core Components](#core-components)
5. [API Endpoints](#api-endpoints)
6. [Configuration](#configuration)
7. [Usage](#usage)

---

## System Overview

APEX FX Trading Bot is a fully automated, multi-instrument algorithmic trading system designed to trade six major instruments:
- EUR/USD - Euro vs US Dollar
- GBP/USD - British Pound vs US Dollar  
- USD/JPY - US Dollar vs Japanese Yen
- USD/CHF - US Dollar vs Swiss Franc
- USDCAD - US Dollar vs Canadian Dollar
- XAU/USD - Gold vs US Dollar

The bot runs 24/5, executes trades through MetaTrader 5, and implements instrument-specific strategies with bespoke risk management.

**Key Features:**
- Regime Detection Engine (RDE) - Classifies market as TRENDING/RANGING/BREAKOUT_PENDING/AVOID
- 6 instrument-specific strategies with unique indicators
- Per-instrument risk profiles (position sizing, stop-loss, take-profit)
- Correlation controls between pairs
- Daily/monthly circuit breakers (8%/15% drawdown limits)
- News blackout filtering
- WTI crude oil feed for USD/CAD correlation
- Telegram alerts for trade notifications

---

## Architecture

### Technology Stack
- **Language:** Python 3.11+
- **Trading Platform:** MetaTrader 5
- **Web Framework:** Flask
- **Database:** SQLite
- **Frontend:** HTML/CSS/JavaScript (Vanilla)

### System Layers
1. **Data Layer** - MT5 data feed, economic calendar, WTI oil prices
2. **Signal Engine** - Strategy modules + Regime Detection
3. **Risk Engine** - Position sizing, drawdown monitors, correlation
4. **Execution Engine** - Order routing with spread check & retry
5. **API Layer** - Flask REST API
6. **Frontend** - Dashboard web UI
7. **Monitoring** - Telegram alerts, structured logging

---

## Directory Structure

```
TradingBot/
├── main.py                     # Bot entry point
├── config/                     # Configuration files
│   ├── config.yaml            # Main config
│   ├── mt5_config.yaml        # MT5 connection
│   ├── risk_config.json       # Risk parameters
│   ├── strategies_config.yaml # Strategy params
│   └── watchlist.yaml         # Trading instruments
├── src/
│   ├── __init__.py
│   ├── api/
│   │   └── main.py           # Flask API (all endpoints)
│   ├── data/
│   │   ├── database.py       # SQLite manager
│   │   ├── mt5_connector.py  # MT5 connection
│   │   ├── commodity_feed.py # WTI oil feed
│   │   └── calendar_feed.py  # Economic calendar
│   ├── strategies/
│   │   └── engine.py         # All strategies + RDE
│   ├── risk/
│   │   ├── manager.py        # Risk management
│   │   └── correlation.py    # Correlation controls
│   ├── execution/
│   │   └── order_router.py   # MT5 order execution
│   ├── analysis/
│   │   └── technical.py      # 30+ technical indicators
│   ├── monitoring/
│   │   ├── telegram_alerts.py # Telegram notifications
│   │   ├── logger.py         # Structured JSON logging
│   │   └── health_monitor.py # Heartbeat & backup EA
│   └── config/
│       └── __init__.py       # Config loader
├── templates/
│   └── index.html           # Web dashboard
└── apex_trading.db           # SQLite database
```

---

## Core Components

### 1. Data Layer

#### MT5 Connector (`src/data/mt5_connector.py`)
```python
class MT5Connector:
    def connect() -> bool      # Initialize MT5 connection
    def get_account()         # Get account info (balance, equity)
    def get_ohlc(symbol, timeframe, count) # Get price data
    def open_order(symbol, direction, volume, entry, sl, tp, comment) # Execute trade
    def close_position(ticket) # Close by ticket
    def get_positions()       # Get all open positions
```

#### WTI Crude Oil Feed (`src/data/commodity_feed.py`)
- Provides oil prices for USD/CAD correlation strategy
- Uses Alpha Vantage API or returns mock data
- Methods: `get_current_price()`, `is_trending_up()`, `is_trending_down()`

#### Economic Calendar (`src/data/calendar_feed.py`)
```python
class EconomicCalendar:
    def fetch_calendar(days=7)      # Fetch upcoming news events
    def is_blackout_time(symbol)    # Check if in blackout period (30min before/after)
    def is_gold_blackout()          # Special 45min blackout for gold events
    def get_position_size_reduction(symbol) # Returns 0.5 for medium impact events
```

### 2. Strategy Engine (`src/strategies/engine.py`)

#### Regime Detection Engine (RDE)
```python
class RegimeDetector:
    def detect(df: pd.DataFrame) -> MarketRegime:
        # Uses ADX, ATR, Bollinger Band width
        # Returns: TRENDING, RANGING, BREAKOUT_PENDING, AVOID
```

#### Instrument Strategies

**EURUSDStrategy** - Multi-Timeframe Trend + Session Breakout
- Primary: EMA Crossover (20/50 EMA) with H4 trend confirmation
- Secondary: London Session Breakout (06:00-08:00 UTC)
- Indicators: EMA(20,50,200), RSI(14), MACD

**GBPUSDStrategy** - Momentum Breakout + Fibonacci
- Primary: London Open Momentum (07:00-11:00 UTC)
- Secondary: Fibonacci Retracement (50%, 61.8%)
- Indicators: EMA(50), RSI(14), ATR(14), Bollinger Bands

**USDJPYStrategy** - Carry Trade Momentum + BoJ Filter
- Primary: Multi-session trend (D1 for macro, H4 for trend)
- BoJ Intervention Filter: Pause 24h if >200 pips move in single H4 candle
- Indicators: EMA(200), Stochastic(5,3,3)

**USDCHFStrategy** - Mean Reversion + EUR/USD Divergence
- Primary: Bollinger Band Mean Reversion
- EUR/USD Divergence Filter: Only trade when EUR/USD ranging
- Indicators: Bollinger Bands(20,2), RSI(14), Williams %R

**USDCADStrategy** - Oil-Correlated Trend
- Primary: WTI crude correlation
- Oil up = USD/CAD down (sell signal)
- Oil EIA Filter: No trades 30min before/after Wednesday 15:30 UTC
- Indicators: EMA(50,200), MACD, WTI oil price

**XAUUSDStrategy** - Multi-Timeframe Trend + Breakout
- Primary: 200 EMA Trend (D1 for macro, H4 for entry)
- Gold News Filter: 45min blackout for CPI, FOMC, NFP, GDP
- Secondary: Session Open Breakout (London/NY)
- Indicators: EMA(200,50), RSI(14), ATR(14), MACD

#### Strategy Engine
```python
class StrategyEngine:
    STRATEGIES = {
        'EURUSD': EURUSDStrategy,
        'GBPUSD': GBPUSDStrategy,
        'USDJPY': USDJPYStrategy,
        'USDCHF': USDCHFStrategy,
        'USDCAD': USDCADStrategy,
        'XAUUSD': XAUUSDStrategy
    }
    
    def scan_symbol(symbol, df_h1, df_h4, df_d1, category):
        # Detects regime, calls appropriate strategy
        # Returns list of signals with: direction, entry, sl, tp, confidence, strategy
```

### 3. Risk Management (`src/risk/manager.py`)

#### Per-Instrument Risk Profiles (PRD Section 5.3)
```python
INSTRUMENT_PROFILES = {
    'EURUSD': {'risk_per_trade': 1.5, 'atr_multiplier': 1.5, 'max_lot': 2.0, 'tp_multiplier': 2.5},
    'GBPUSD': {'risk_per_trade': 1.2, 'atr_multiplier': 1.8, 'max_lot': 2.0, 'tp_multiplier': 3.0},
    'USDJPY': {'risk_per_trade': 1.5, 'atr_multiplier': 1.5, 'max_lot': 1.5, 'tp_multiplier': 2.5},
    'USDCHF': {'risk_per_trade': 1.0, 'atr_multiplier': 1.5, 'max_lot': 1.5, 'tp_multiplier': 2.0},
    'USDCAD': {'risk_per_trade': 1.2, 'atr_multiplier': 1.5, 'max_lot': 1.5, 'tp_multiplier': 2.5},
    'XAUUSD': {'risk_per_trade': 0.75, 'atr_multiplier': 2.0, 'max_lot': 0.5, 'tp_multiplier': 3.5}
}
```

#### Risk Manager Methods
```python
class RiskManager:
    def calculate_position_size(symbol, account_balance, current_price, sl_price)
        # PRD Formula: Lot Size = (Balance × Risk%) / (ATR × ATR_Multiplier × Pip_Value)
    
    def calculate_stop_loss(symbol, entry_price, direction)
        # ATR-based stop: entry ± (ATR × multiplier)
        # USD/JPY gets +10 pip buffer for intervention risk
    
    def calculate_take_profit(symbol, entry_price, direction)
        # ATR-based: entry ± (ATR × tp_multiplier)
    
    def should_activate_trailing_stop(symbol, current_price, entry, direction, profit_pips)
        # Activates when profit >= ATR × trailing_activation_rr
    
    def calculate_trailing_stop(symbol, current_price, entry, direction)
        # Returns trailing SL price
    
    def check_trade_allowed(symbol, direction, open_positions, account_balance)
        # Checks: circuit breaker, daily loss, pair limit, position limit
    
    def check_daily_drawdown(current_balance)  # Triggers at 8% loss
    def check_monthly_drawdown(current_balance)  # Triggers at 15% loss
    
    def _trigger_circuit_breaker(hours)  # Pauses all trading
```

#### Correlation Manager (`src/risk/correlation.py`)
```python
class CorrelationManager:
    # PRD Section 5.5 Correlation Rules:
    # EUR/USD + USD/CHF: Cannot hold same direction (inverse -0.85 correlation)
    # EUR/USD + GBP/USD: Max combined risk = 2.5% of account
    # USD/CAD + XAUUSD: Max combined risk = 1.5% when both commodity-correlated
    
    def can_open_position(symbol, direction, risk_pct) -> (bool, reason)
    def add_position(position)
    def remove_position(symbol)
```

### 4. Execution Engine (`src/execution/order_router.py`)

```python
class OrderRouter:
    def check_spread(symbol) -> (bool, reason)
        # Max spreads: EURUSD 1.5pips, GBPUSD 2.0, XAUUSD 3.0
    
    def place_order(symbol, direction, lots, sl=None, tp=None, comment="")
        # Retry logic with exponential backoff (max 3 attempts)
        # Returns: (success, message, ticket)
    
    def close_position(ticket, lots=None)
    def modify_position(ticket, sl=None, tp=None)
    def get_positions() -> list
```

### 5. Monitoring

#### Telegram Alerts (`src/monitoring/telegram_alerts.py`)
```python
class TelegramAlert:
    # Sends: Trade open/close, SL/TP hit, Circuit breaker, Daily report, Heartbeat
    
    def send_trade_alert(alert)
    def send_circuit_breaker_alert(reason, duration_hours)
    def send_daily_report(stats)
    def send_heartbeat()  # Every 5 minutes
```

#### Structured Logging (`src/monitoring/logger.py`)
- JSON formatted logs in `logs/` directory
- Separate logs: trades.log, signals.log, risk.log, errors.log

#### Health Monitor (`src/monitoring/health_monitor.py`)
```python
class HealthMonitor:
    def ping()  # Update heartbeat
    def check_health()  # Returns status with seconds since last heartbeat

class BackupEAHandler:
    def check_backup_ea_status()  # Checks if backup EA is running
    def trigger_emergency_close()  # Signal EA to close all positions
```

### 6. Technical Analysis (`src/analysis/technical.py`)

```python
class TechnicalAnalysis:
    def calculate_all(df) -> Dict
        # Returns: trend, momentum, volatility, volume, pattern indicators
        
    # Includes: SMA, EMA, RSI, MACD, Bollinger Bands, Stochastic, ADX, ATR, etc.
```

### 7. Database (`src/data/database.py`)

Tables:
- `accounts` - Account info
- `trades` - All trade records
- `signals` - Generated signals
- `prices` - Historical price data
- `settings` - Bot settings

---

## API Endpoints

### Account
- `GET /api/account` - Account balance, equity, margin

### Positions
- `GET /api/positions` - All open positions
- `POST /api/positions/open` - Open new position
- `POST /api/positions/close/<ticket>` - Close position

### Signals
- `GET /api/signals` - Recent signals
- `POST /api/signals/scan` - Scan for new signals
- `GET /api/signals/<id>` - Specific signal

### Market Data
- `GET /api/market/ohlc?symbol=XAUUSD&timeframe=H1&count=100` - OHLC data
- `GET /api/market/indicators?symbol=EURUSD&timeframe=H1` - Technical indicators

### Risk
- `GET /api/risk/status` - Risk metrics, drawdown, circuit breaker status
- `GET /api/risk/limits` - Per-pair limits

### Watchlist
- `GET /api/watchlist` - Current watchlist
- `POST /api/watchlist` - Update watchlist

### Stats
- `GET /api/stats` - Trade statistics, win rate, profit factor

### Config
- `GET /api/config` - All configuration
- `GET /api/config/<key>` - Specific config value

### System
- `GET /api/system/status` - MT5 connection, scanning status

---

## Configuration

### config.yaml
```yaml
app:
  name: "APEX FX Trading Bot"
  version: "1.0"
  
server:
  host: "0.0.0.0"
  port: 5000
```

### mt5_config.yaml
```yaml
login: 6023219
password: ""
server: "MetaQuotes-Demo"
```

### risk_config.json
```json
{
  "daily_loss_limit": 8.0,
  "monthly_drawdown_limit": 15.0,
  "max_consecutive_losses": 5,
  "circuit_breaker_hours": 24
}
```

### watchlist.yaml
```yaml
symbols:
  - XAUUSD
  - EURUSD
  - GBPUSD
  - USDJPY
```

---

## Usage

### Starting the Bot
```bash
python main.py
```

The bot will:
1. Connect to MT5
2. Initialize all components
3. Start Flask web server on http://localhost:5000
4. Display watchlist instruments

### Using the Web Interface

1. **Dashboard** - Open http://localhost:5000
   - View balance, equity, P&L
   - See open positions
   - Monitor risk status

2. **Scan Signals** - Click "Scan Now" button
   - Bot fetches H1, H4, D1 data for each symbol
   - Runs regime detection
   - Generates trading signals
   - Displays signals with entry, SL, TP, confidence

3. **Execute Trade** - Click "Execute Trade" on a signal
   - Opens position in MT5
   - Sends Telegram notification

4. **Manual Trading**
   - Enter symbol, direction, volume
   - Click from watchlist

### API Usage
```bash
# Get account
curl http://localhost:5000/api/account

# Scan signals
curl -X POST http://localhost:5000/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["XAUUSD", "EURUSD"]}'

# Open position
curl -X POST http://localhost:5000/api/positions/open \
  -H "Content-Type: application/json" \
  -d '{"symbol": "XAUUSD", "direction": "BUY", "volume": 0.1}'
```

---

## Risk Management Flow

1. **Pre-Trade Checks:**
   - Circuit breaker active? → Block
   - Daily drawdown > 8%? → Block
   - Monthly drawdown > 15%? → Block
   - Pair daily loss > limit? → Block
   - Too many positions? → Block
   - News blackout? → Block
   - Spread too wide? → Block
   - Correlation rule violation? → Block

2. **Position Sizing:**
   - Calculate ATR
   - Apply formula: `Lot = (Balance × Risk%) / (SL_Pips × ATR_Mult × Pip_Value)`

3. **Trade Execution:**
   - Place order with SL and TP
   - Hard stop at broker level

4. **Monitoring:**
   - Check trailing stop activation
   - Update daily/monthly P&L
   - Send Telegram alerts

---

## Error Handling

- Spread check fails → Retry with exponential backoff
- MT5 order fails → Log error, send alert
- Database error → Log but continue operation
- Regime detection fails → Return AVOID regime

---

## File Dependencies

```
main.py
├── src/api/main.py
│   ├── src/config/__init__.py
│   ├── src/data/database.py
│   ├── src/data/mt5_connector.py
│   ├── src/data/commodity_feed.py
│   ├── src/data/calendar_feed.py
│   ├── src/analysis/technical.py
│   ├── src/strategies/engine.py
│   └── src/risk/manager.py
├── src/strategies/engine.py
│   └── src/analysis/technical.py
├── src/risk/manager.py
│   └── src/risk/correlation.py
└── templates/index.html
```

---

## Summary

This bot implements a complete algorithmic trading system following the PRD specifications:

- **6 instruments** with bespoke strategies
- **Regime detection** for strategy selection
- **ATR-based** position sizing and stops
- **Correlation controls** between pairs
- **Circuit breakers** for risk protection
- **News filtering** for event avoidance
- **Oil correlation** for USD/CAD
- **Telegram alerts** for notifications
- **Web dashboard** for monitoring and control

All components work together to provide automated, risk-aware multi-instrument trading through MetaTrader 5.