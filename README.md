# APEX FX Trading Bot

**Production-Ready Multi-Instrument Algorithmic Trading System**  
*Following PRD Specification Volume I & Volume II*

---

## Overview

APEX FX Trading Bot is a fully automated, institutional-grade algorithmic trading system designed to trade six major instruments:

- **EUR/USD** - Euro vs US Dollar
- **GBP/USD** - British Pound vs US Dollar
- **USD/JPY** - US Dollar vs Japanese Yen
- **USD/CHF** - US Dollar vs Swiss Franc
- **USD/CAD** - US Dollar vs Canadian Dollar
- **XAU/USD** - Gold vs US Dollar

### Core Objectives
1. **Consistent profitability** through regime-aware strategy selection
2. **Capital preservation** as the primary mandate
3. **Adaptive risk management** with per-instrument profiles
4. **Full automation** - zero manual intervention required
5. **Institutional-grade execution** with spread filtering and retry logic

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
TradingBot/
├── main.py                          # Entry point
├── config/                         # Configuration files
│   ├── config.yaml
│   ├── mt5_config.yaml
│   ├── risk_config.json
│   └── strategies_config.yaml
├── src/
│   ├── api/main.py                  # Flask API (all endpoints)
│   ├── config/__init__.py           # Config loader
│   ├── data/
│   │   ├── database.py              # SQLite (12 tables)
│   │   ├── mt5_connector.py         # MT5 integration
│   │   ├── commodity_feed.py        # WTI oil feed
│   │   ├── calendar_feed.py         # Economic calendar
│   │   ├── cot_parser.py            # CFTC COT parser (NEW)
│   │   └── swap_filter.py           # Rollover protection (NEW)
│   ├── strategies/engine.py         # 6 strategies + RDE
│   ├── risk/
│   │   ├── manager.py               # Risk management
│   │   ├── correlation.py           # Correlation controls
│   │   ├── portfolio_heat_monitor.py # Heat monitoring (NEW)
│   │   ├── volatility_scaler.py     # VRS scalar (NEW)
│   │   ├── signal_scorer.py          # Signal scoring (NEW)
│   │   ├── kelly_sizer.py           # Kelly sizing (NEW)
│   │   ├── fill_analyzer.py         # Execution quality (NEW)
│   │   └── regime_drift_detector.py  # RDD (NEW)
│   ├── execution/
│   │   ├── order_router.py          # MT5 execution
│   │   ├── time_exit_manager.py     # Time exits (NEW)
│   │   └── calendar_filter.py       # Day-of-week (NEW)
│   ├── analysis/
│   │   ├── technical.py             # 30+ indicators
│   │   └── performance_analyzer.py  # Self-learning (NEW)
│   └── monitoring/
│       ├── telegram_alerts.py       # 4-tier alerts
│       ├── logger.py                # Structured logs
│       └── health_monitor.py        # Heartbeat
├── templates/index.html             # Web dashboard
├── tests/                           # 133 pytest tests
└── SYSTEM_HIGHLIGHTS.md             # Detailed documentation
```

---

## Features

### Per-Instrument Strategies
| Instrument | Primary Strategy | Key Indicators |
|-------------|------------------|-----------------|
| EUR/USD | Multi-Timeframe Trend | EMA(20,50,200), RSI, MACD |
| GBP/USD | Momentum Breakout | EMA(50), RSI, ATR, Bollinger |
| USD/JPY | Carry Momentum + BoJ Filter | EMA(200), Stochastic |
| USD/CHF | Mean Reversion | Bollinger Bands, RSI, Williams %R |
| USD/CAD | Oil-Correlated Trend | EMA(50,200), MACD, WTI Oil |
| XAU/USD | Multi-Timeframe Trend | EMA(200,50), RSI, ATR, MACD |

### Risk Management (PRD Volume I + II)
- **Position Sizing**: ATR-based with per-instrument profiles
- **Kelly Criterion**: Fractional Kelly with activation thresholds
- **Portfolio Heat Monitor**: Real-time aggregate risk tracking
- **Volatility Scaler (VRS)**: Dynamic position sizing based on market vol
- **Signal Scorer**: 0-100 weighted scoring replacing binary gates
- **Circuit Breakers**: Daily (8%) and monthly (15%) drawdown limits
- **Correlation Controls**: EUR/CHF inverse, GBP/EUR combined risk

### Volume II Enhancements (11 New Modules)
1. **Portfolio Heat Monitor** - Real-time aggregate open risk
2. **Volatility Scaler (VRS)** - Portfolio-level volatility scalar (0.40-1.00)
3. **Signal Scorer** - 5-factor weighted scoring (0-100 scale)
4. **Kelly Sizer** - Fractional Kelly with cold streak ladder
5. **Fill Analyzer** - Broker Quality Score (BQS) tracking
6. **Regime Drift Detector** - Weekly strategy health check
7. **Performance Analyzer** - Self-learning feedback loop
8. **COT Parser** - CFTC COT report integration
9. **Time Exit Manager** - Max hold times, forward progress, weekend policy
10. **Calendar Filter** - Day-of-week, month-end, quarter-end rules
11. **Swap Filter** - Rollover cost protection

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

### Market Data
- `GET /api/market/ohlc` - OHLC data
- `GET /api/market/indicators` - Technical indicators
- `GET /api/market/symbols` - Available symbols

### Risk
- `GET /api/risk/status` - Risk status
- `POST /api/risk/validate` - Validate trade

### Stats
- `GET /api/stats` - Trading statistics

### API v2 Endpoints (NEW)
- `GET /api/v2/heat` - Portfolio heat %
- `GET /api/v2/vrs` - VRS scalar
- `GET /api/v2/bqs` - Broker Quality Score
- `GET /api/v2/kelly` - Kelly risk %
- `GET /api/v2/rdd` - RDD status
- `GET /api/v2/cot` - COT Index
- `GET /api/v2/signal-scores` - Signal scores
- `GET /api/v2/weekly-report` - Weekly report
- `POST /api/v2/rdd/reset/<symbol>` - Reset suspended symbol

---

## Configuration

Edit `config/config.yaml`:
```yaml
system:
  name: "APEX FX Trading Bot"
  version: "2.0.0"
  mode: "DEMO"

symbols:
  forex:
    - XAUUSD
    - EURUSD
    - GBPUSD
    - USDJPY
    - USDCHF
    - USDCAD
```

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/test_signal_scorer.py -v
pytest tests/test_kelly_sizer.py -v
```

**133 tests passing** ✓

---

## Scheduled Jobs

| Job | Schedule | Description |
|-----|-----------|-------------|
| RDD Check | Friday 21:00 UTC | Regime drift detection |
| Performance Analysis | Friday 21:30 UTC | Self-learning loop |
| COT Update | Friday 16:30 UTC | CFTC report refresh |
| Daily Report | Daily 22:00 UTC | Performance summary |

---

## Alert Tiering

| Tier | Examples | Delivery |
|------|----------|----------|
| INFO | Trade opened/closed | Telegram (silent) |
| WARNING | Spread high, VRS reduced | Telegram |
| CRITICAL | Daily breaker, RDD RED | Telegram + Email |
| EMERGENCY | 8% drawdown, VPS lost | Telegram + Email + SMS |

---

## Database Tables

### Volume I (5 tables)
- accounts, trades, signals, prices, settings

### Volume II (7 new tables)
- fill_quality, signal_scores, kelly_history, portfolio_heat_log, rdd_status, cot_data, weekly_reports

---

## Disclaimer

**Trading involves substantial risk.** This bot is for educational and research purposes. Only trade with capital you can afford to lose. Always:
- Test thoroughly on demo accounts
- Review all settings before live trading
- Monitor initial trades closely
- Understand the risk parameters

---

## Version History

- **v2.0.0** (2026-04-09) - PRD Volume II complete
- **v1.0.0** (2026-04-08) - PRD Volume I complete

---

*Version: 2.0.0 | Built: 2026-04-09*
