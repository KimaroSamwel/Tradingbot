# APEX FX Trading Bot - System Documentation

## Overview

The APEX FX Trading Bot is a sophisticated algorithmic trading system supporting three operational modes: **PAPER** (virtual trading), **DEMO** (signal generation only), and **LIVE** (real money execution). The system scans multiple currency pairs and executes trades based on technical analysis and risk management rules.

---

## System Architecture

### Core Components

```
TradingBot/
├── src/
│   ├── api/main.py           # Flask API server
│   ├── config/               # Configuration management
│   ├── data/                 # MT5, database connectors
│   ├── analysis/             # Technical analysis, performance
│   ├── strategies/           # Trading strategy engine
│   ├── risk/                 # Risk management modules
│   ├── execution/            # Trade execution logic
│   ├── monitoring/            # Event logging, alerts
│   └── paper/                # Paper trading engine
├── config/                   # YAML configuration files
└── templates/index.html       # Dashboard UI
```

---

## Trading Modes

### 1. PAPER Mode (Current Default)
- **Description**: Virtual trading with simulated execution
- **Behavior**: 
  - Signals are auto-executed as paper trades
  - Slippage/spread/commission simulated
  - Full P&L tracking without real money
- **Use Case**: Testing strategy accuracy, learning

### 2. DEMO Mode
- **Description**: Signal generation only, no execution
- **Behavior**:
  - Scans pairs and generates signals
  - Shows signal quality scores
  - No trades executed
- **Use Case**: Watching live signals, strategy validation

### 3. LIVE Mode
- **Description**: Real money execution via MT5
- **Behavior**:
  - All risk checks active
  - Real trades sent to broker
  - Full position management
- **Use Case**: Production trading

### Switching Modes

**Option 1**: Edit `config/config.yaml`
```yaml
trading:
  mode: "PAPER"  # PAPER, DEMO, or LIVE
```

**Option 2**: Click the "Switch" button in the dashboard header to cycle through modes.

---

## Supported Trading Pairs

The system currently trades these pairs (configured in `config/watchlist.yaml`):
- **XAUUSD** (Gold)
- **EURUSD** (Euro/US Dollar)
- **GBPUSD** (British Pound/US Dollar)
- **USDJPY** (US Dollar/Japanese Yen)

You can add more pairs by editing `config/watchlist.yaml`.

---

## How the System Works

### 1. Signal Generation Pipeline (15-Step Process)

The system uses a comprehensive 15-step pre-trade validation:

```
Step 1:  Portfolio Heat Check     - Check total portfolio risk
Step 2:  Position Monitoring      - Check trailing stops, time exits
Step 3:  Calendar Filter          - Check trading hours/sessions
Step 4:  Signal Scoring           - Score the trade setup (0-100)
Step 5:  Spread-ATR Ratio         - Verify spread is acceptable
Step 6:  Swap Check               - Avoid negative swap periods
Step 7:  Kelly Sizing             - Calculate position size
Step 8:  Risk Assessment          - Final risk validation
Step 9:  VRS Scalar               - Apply volatility scalar
Step 10: COT Analysis             - Check Commitment of Traders
Step 11: Portfolio Heat           - Verify heat limit not exceeded
Step 12: RDD Check                - Check Regime Drift Detector
Step 13: Execution Quality        - Check broker fill quality
Step 14: Final Confirmation       - Last chance validation
Step 15: Trade Execution          - Execute the trade
```

### 2. Manual Scan Flow

When you click "Manual Scan":
1. System fetches OHLC data for all watchlist pairs
2. Runs through 15-step validation for each pair
3. Generates signals with scores and grades:
   - **HIGH** (85+): Strong trade
   - **STANDARD** (75-84): Normal trade
   - **MARGINAL** (60-74): Weak trade
   - **REJECT** (<60): No trade

### 3. Risk Management Features

- **Portfolio Heat Monitor**: Limits total exposure (COLD/WARM/HOT/CRITICAL)
- **Kelly Sizing**: Dynamic position sizing based on win rate
- **Trailing Stops**: Protects profits as trade moves in your favor
- **Time Exits**: Auto-close at session end
- **VRS (Volatility Risk Scalar)**: Adjusts exposure based on market volatility

---

## Paper Trading Features

### Viewing Paper Trade History

1. **Dashboard Positions Panel**: Shows open paper positions
2. **API Endpoint**: `/api/paper/positions` - Returns all open paper positions
3. **API Endpoint**: `/api/paper/stats` - Returns P&L statistics

### Trade Entry/Exit Visualization

The chart shows:
- **Green markers**: Buy entry points
- **Red markers**: Sell entry points  
- **Blue markers**: Take Profit levels
- **Orange markers**: Stop Loss levels

### Performance Testing

To test accuracy in PAPER mode:

1. Set mode to PAPER in config or via UI button
2. Click "Manual Scan" or enable auto-scanning
3. Monitor the **Positions** panel for executed trades
4. Check **P&L** stats in the KPI tiles
5. Review individual trade outcomes in the Performance tab

---

## API Endpoints

### Core Endpoints
- `GET /api/account` - Account info (balance, equity)
- `GET /api/positions` - Open positions
- `GET /api/signals` - Active signals

### Mode Control
- `GET /api/v3/mode` - Get current mode
- `POST /api/v3/mode` - Switch mode ({"mode": "PAPER"})

### Paper Trading
- `GET /api/paper/account` - Paper account status
- `GET /api/paper/positions` - Paper positions
- `GET /api/paper/stats` - P&L statistics
- `POST /api/paper/reset` - Reset paper account

### System Control
- `POST /api/system/scan-v2` - Run manual scan
- `POST /api/system/scan-start` - Start auto-scan
- `POST /api/system/scan-stop` - Stop auto-scan

### Market Data
- `GET /api/market/ohlc` - OHLC candlestick data
- `GET /api/market/indicators` - Technical indicators

---

## Dashboard Zones

### Zone 1: Header
- Mode indicator (PAPER/DEMO/LIVE)
- MT5 connection status
- Equity/Balance display
- VRS scalar badge
- Heat gauge

### Zone 2: KPI Tiles
- P&L (daily profit/loss)
- Positions count
- Win Rate
- Profit Factor
- Portfolio Heat %
- BQS (Broker Quality Score)
- RDD Status
- VRS Scalar

### Zone 3: Left Sidebar
- Watchlist with prices
- Regime indicators (T/B/S)
- RDD status dots

### Zone 4: Main Chart Area
- 6 tabs: Chart, Signals, Performance, Risk, Execution, Weekly Report

### Zone 5: Right Sidebar
- Signal queue with progress
- Mini positions view
- News feed

### Zone 6: Positions Panel
- Slide-up panel showing all positions

### Zone 7: Event Log
- Collapsible log of system events

---

## Troubleshooting

### Manual Scan Fails
- Check MT5 connection
- Verify watchlist has valid symbols
- Check calendar filter allows trading

### Mode Switch Fails
- Ensure config.yaml is writable
- Restart Flask app after mode change

### No Signals Generated
- Market may be outside trading hours
- No pairs meeting all criteria
- Increase scan frequency

---

## Technical Details

### Database Tables
- `trades` - Trade history
- `signals` - Signal log
- `performance` - Daily metrics
- `paper_account` - Paper trading balance
- `paper_positions` - Open paper trades
- `paper_trades_log` - Paper trade history

### Configuration Files
- `config.yaml` - Main config (mode, pairs)
- `mt5_config.yaml` - MT5 broker settings
- `risk_config.json` - Risk parameters
- `paper_config.yaml` - Paper trading settings

---

## Next Steps

1. **Start in PAPER mode** - Test the system
2. **Review paper trades** - Check accuracy
3. **Switch to DEMO** - Observe signals without execution
4. **Switch to LIVE** - Trade with real capital (when ready)
