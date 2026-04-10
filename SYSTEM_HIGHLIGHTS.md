# APEX FX Trading Bot - System Highlights

**Production-Ready Multi-Instrument Algorithmic Trading System**  
*Following PRD Specification Volume I & Volume II*

---

## 1. System Overview

APEX FX Trading Bot is a fully automated, institutional-grade algorithmic trading system designed to trade six major instruments:

| Instrument | Type | Average Daily Range | Primary Strategy |
|------------|------|-------------------|------------------|
| EUR/USD | Forex | 60-90 pips | Multi-Timeframe Trend + Session Breakout |
| GBP/USD | Forex | 80-130 pips | Momentum Breakout + Fibonacci |
| USD/JPY | Forex | 50-80 pips | Carry Trade Momentum + BoJ Filter |
| USD/CHF | Forex | 50-75 pips | Mean Reversion + EUR/USD Divergence |
| USD/CAD | Forex | 60-90 pips | Oil-Correlated Trend (WTI) |
| XAU/USD | Gold | $15-$40 (150-400 pips) | Multi-Timeframe Trend + Breakout |

### Core Objectives
1. **Consistent profitability** across all six instruments through regime-aware strategy selection
2. **Capital preservation** as the primary mandate
3. **Adaptive risk management** with per-instrument profiles
4. **Full automation** - zero manual intervention required
5. **Institutional-grade execution** with low latency and spread filtering

---

## 2. Architecture

### Technology Stack
- **Language**: Python 3.11+
- **Trading Platform**: MetaTrader 5
- **Web Framework**: Flask
- **Database**: SQLite
- **Scheduling**: APScheduler
- **Frontend**: HTML/CSS/JavaScript (Vanilla)

### Directory Structure
```
TradingBot/
├── main.py                          # Entry point
├── config/                          # YAML configuration
│   ├── config.yaml                  # Main config
│   ├── mt5_config.yaml              # MT5 credentials
│   ├── risk_config.json             # Risk parameters
│   └── strategies_config.yaml       # Strategy params
├── src/
│   ├── api/main.py                  # Flask API (all endpoints)
│   ├── config/__init__.py            # Config loader
│   ├── data/
│   │   ├── database.py              # SQLite manager
│   │   ├── mt5_connector.py         # MT5 connection
│   │   ├── commodity_feed.py        # WTI oil feed
│   │   ├── calendar_feed.py         # Economic calendar
│   │   ├── cot_parser.py             # CFTC COT report parser
│   │   └── swap_filter.py            # Rollover protection
│   ├── strategies/
│   │   └── engine.py                # All strategies + RDE
│   ├── risk/
│   │   ├── manager.py               # Risk management
│   │   ├── correlation.py            # Correlation controls
│   │   ├── portfolio_heat_monitor.py # Heat monitoring
│   │   ├── volatility_scaler.py      # VRS scalar
│   │   ├── signal_scorer.py           # Signal quality scoring
│   │   ├── kelly_sizer.py             # Kelly criterion sizing
│   │   ├── fill_analyzer.py          # Execution quality
│   │   └── regime_drift_detector.py  # RDD weekly check
│   ├── execution/
│   │   ├── order_router.py          # MT5 order execution
│   │   ├── time_exit_manager.py      # Time-based exits
│   │   └── calendar_filter.py         # Day-of-week rules
│   ├── analysis/
│   │   ├── technical.py              # 30+ indicators
│   │   └── performance_analyzer.py   # Self-learning loop
│   └── monitoring/
│       ├── telegram_alerts.py       # Telegram notifications
│       ├── logger.py                 # Structured JSON logs
│       └── health_monitor.py         # Heartbeat monitoring
├── templates/
│   └── index.html                    # Web dashboard
└── tests/                            # pytest test suite
```

---

## 3. Risk Management Framework

### Per-Instrument Risk Profiles
| Pair | Risk/Trade | ATR Mult. | Max Daily Loss | Max Lot |
|------|------------|-----------|-----------------|---------|
| EUR/USD | 1.5% | 1.5× | 3% | 2.0 |
| GBP/USD | 1.2% | 1.8× | 3% | 1.5 |
| USD/JPY | 1.5% | 1.5× | 3% | 2.0 |
| USD/CHF | 1.0% | 1.5× | 2.5% | 1.5 |
| USD/CAD | 1.2% | 1.5× | 3% | 1.5 |
| XAU/USD | 0.75% | 2.0× | 2% | 0.5 |

### Portfolio-Level Controls
- **Daily Circuit Breaker**: 8% loss halts all trading
- **Monthly Drawdown**: 15% triggers defensive mode
- **Correlation Limits**: EUR/USD + USD/CHF cannot be same direction
- **Portfolio Heat Monitor**: Real-time aggregate risk tracking

---

## 4. Volume II Modules (11 New Modules)

### Risk Enhancement Modules
1. **Portfolio Heat Monitor** - Real-time aggregate open risk tracking
2. **Volatility Scaler (VRS)** - Portfolio-level size scalar based on market volatility
3. **Signal Scorer** - Weighted 0-100 signal scoring with 5 factor groups
4. **Kelly Sizer** - Fractional Kelly adaptive position sizing
5. **Fill Analyzer** - Execution quality tracking and Broker Quality Score (BQS)
6. **Regime Drift Detector** - Weekly strategy health vs backtest baseline

### Intelligence Modules
7. **Performance Analyzer** - Self-learning feedback loop with dimension clustering
8. **COT Parser** - CFTC Commitment of Traders report integration

### Execution Modules
9. **Time Exit Manager** - Max hold times, forward progress rule, weekend policy
10. **Calendar Filter** - Day-of-week rules, month-end/quarter-end adjustments
11. **Swap Filter** - Rollover cost protection

---

## 5. Pre-Trade Check Sequence (15 Steps)

The full execution pipeline before any order:

1. Regime detection (RDE) - must not be AVOID
2. Session gate check
3. News blackout check
4. Spread percentile filter (< 80th percentile)
5. Spread-to-ATR ratio filter (< 0.15)
6. Swap cost check (near rollover)
7. COT alignment check
8. SignalScorer evaluation (≥60 to proceed)
9. VRS scalar application
10. Kelly sizing calculation
11. Portfolio heat check
12. Correlation exposure check
13. Maximum simultaneous trades check
14. Market impact order splitting
15. Order submission with server-side SL/TP

---

## 6. API Endpoints

### Standard Endpoints (Volume I)
- `GET /api/account` - Account balance, equity, margin
- `GET /api/positions` - All open positions
- `POST /api/positions/open` - Open new position
- `POST /api/positions/close/<ticket>` - Close position
- `GET /api/signals` - Recent signals
- `POST /api/signals/scan` - Scan for new signals
- `GET /api/risk/status` - Risk metrics
- `GET /api/stats` - Trading statistics
- `GET /api/watchlist` - Current watchlist

### Volume II Endpoints (New)
- `GET /api/v2/heat` - Portfolio heat percentage and level
- `GET /api/v2/vrs` - Volatility scalar and per-symbol ratios
- `GET /api/v2/bqs` - Broker Quality Score
- `GET /api/v2/kelly` - Kelly risk percentage per symbol
- `GET /api/v2/rdd` - RDD status (GREEN/AMBER/RED/CRITICAL)
- `GET /api/v2/cot` - COT Index per symbol
- `GET /api/v2/signal-scores` - Last 50 signal scores
- `GET /api/v2/weekly-report` - Weekly performance report
- `POST /api/v2/rdd/reset/<symbol>` - Manual reset suspended symbol

---

## 7. Scheduled Jobs (APScheduler)

| Job | Schedule | Description |
|-----|-----------|-------------|
| RDD Check | Friday 21:00 UTC | Regime drift detection |
| Performance Analysis | Friday 21:30 UTC | Self-learning feedback |
| COT Update | Friday 16:30 UTC | CFTC report refresh |
| Daily Report | Daily 22:00 UTC | Performance summary |

---

## 8. Alert Tiering System

| Tier | Trigger Examples | Delivery |
|------|------------------|----------|
| INFO | Trade opened/closed, trailing stop moved | Telegram (silent) |
| WARNING | Spread > 70th pct, VRS drops to 0.70, RDD→AMBER | Telegram |
| CRITICAL | Daily breaker, RDD→RED, BQS < 65, pair suspended | Telegram + Email |
| EMERGENCY | 8% drawdown, VPS lost, MT5 crash, backup EA activated | Telegram + Email + SMS |

---

## 9. Success Metrics

| Metric | Minimum | Target |
|--------|---------|--------|
| Monthly Net Return | 4% | 8-12% |
| Max Drawdown | < 10% | < 7% |
| Win Rate | > 52% | > 62% |
| Profit Factor | > 1.5 | > 2.0 |
| Sharpe Ratio | > 1.2 | > 1.8 |
| Broker Quality Score | > 72 | > 85 |
| System Uptime | > 99.5% | > 99.9% |

---

## 10. Database Schema

### Volume I Tables
- `accounts` - Account information
- `trades` - All trade records
- `signals` - Generated signals
- `prices` - Historical price data
- `settings` - Bot settings

### Volume II Tables
- `fill_quality` - Execution quality metrics
- `signal_scores` - Signal scoring records
- `kelly_history` - Kelly calculation history
- `portfolio_heat_log` - Heat level logging
- `rdd_status` - Regime drift detection status
- `cot_data` - COT report data
- `weekly_reports` - Weekly performance reports

---

## 11. Testing

**133 tests passing** across all modules:
- `test_portfolio_heat_monitor.py`
- `test_volatility_scaler.py`
- `test_signal_scorer.py`
- `test_kelly_sizer.py`
- `test_fill_analyzer.py`
- `test_regime_drift_detector.py`
- `test_time_exit_manager.py`
- `test_calendar_filter.py`
- `test_cot_parser.py`

---

## 12. Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python main.py

# Open dashboard
http://localhost:5000
```

---

## 13. Configuration

All settings are managed through YAML/JSON config files:
- `config/config.yaml` - Main system config
- `config/mt5_config.yaml` - MT5 connection
- `config/risk_config.json` - Risk parameters

---

## Disclaimer

**Trading involves substantial risk.** This bot is for educational purposes. Only trade with capital you can afford to lose. Always test thoroughly on demo accounts before live trading.

---

*Version: 2.0.0 | Built: 2026-04-09 | PRD Volume I + Volume II Compliant*
