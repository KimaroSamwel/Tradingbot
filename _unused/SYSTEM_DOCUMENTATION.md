# TradingBot - Complete System Documentation

## Table of Contents
- [System Overview](#system-overview)
- [Active Files (Root)](#active-files-root)
- [Configuration Files](#configuration-files)
- [Scripts](#scripts)
- [MQL5 Expert Advisors](#mql5-expert-advisors)
- [Source Modules (src/)](#source-modules-src)
- [Unused/Legacy Files (_unused/)](#unusedlegacy-files-_unused)
- [Architecture Diagram](#architecture-diagram)
- [How to Run](#how-to-run)
- [Trading Rules](#trading-rules)

---

## System Overview

This is a **human-in-the-loop forex and gold trading system**:

1. **Web Dashboard** (`web_controller.py` + `template.html`) - Signal scanner only. Human makes execution decisions. NO auto-trading.
2. **Source Modules** (`src/`) - Reference library of 110+ strategies (disabled for live trading)

**Account:** Demo | **Broker:** Deriv-Demo | **Account #:** 6023219
**Timezone:** GMT+3 (Africa/Nairobi) | **Session Detection:** UTC-based

---

## Active Files (Root)

### `web_controller.py` (v22 - Human-in-the-Loop)
**Purpose:** Signal scanner dashboard - human executes trades.

**Mode:** Human makes execution decisions - bot ONLY scans and displays signals.

**Key Features:**
- 2 Strategies (Simplified from 5):
  - `Swing_H4H1` (Primary): H4 EMA20/50 + H1 EMA9/21 + RSI + ADX
  - `Trend_Rider` (Secondary): ADX > 20 + EMA trend following
- ATR-based stop loss (1.5x ATR)
- 2:1 minimum risk:reward ratio
- 1% risk per trade, max 2 positions
- **STRICT RISK MANAGEMENT:**
  - Daily loss limit: 2%
  - Circuit breaker: 3 consecutive losses = 4hr pause
  - 24hr pause if daily limit exceeded
- **Trade Journal:** All trades recorded with full details
- ORDER_FILLING_FOK for broker compatibility
- UTC-based session detection

**API Endpoints:**
- `GET /` - Dashboard UI
- `GET /api/status` - Full system status
- `POST /api/scan` - Scan all pairs for signals
- `POST /api/start` - Start auto-scanning
- `POST /api/stop` - Stop auto-scanning
- `POST /api/execute/<idx>` - Execute signal by index
- `POST /api/execute-override/<idx>` - Force execute (bypass can_trade check)
- `POST /api/close/<ticket>` - Close specific position
- `POST /api/close-profitable` - Close all profitable positions
- `POST /api/close-all` - Close all positions
- `POST /api/pairs?pairs=X,Y` - Set trading pairs
- `POST /api/strategies?strategies=A,B` - Set active strategies

**Risk Functions:**
- `_get_pip_value_per_lot(symbol)` - Dollar value per pip per 1.0 lot
- `_calculate_lot_size(symbol, sl_pips, max_risk)` - Calculates lot size for exact risk amount
- `_calculate_risk(symbol, lot, sl_pips)` - Calculates dollar risk for a trade
- `_calculate_sl_price(symbol, entry, sl_pips, direction)` - Stop loss price from pip distance
- `_calculate_tp_price(symbol, entry, sl_pips, direction, rr)` - Take profit price with R:R ratio

**Run:** `python web_controller.py` → `http://127.0.0.1:5000`

---

### `signals.py`
**Purpose:** Standalone signal generator for quick analysis without the web UI.

**Features:**
- Scans 6 pairs (XAUUSD, EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD)
- Requires H4+H1 trend alignment
- ADX > 18 for momentum
- ATR-based SL (1.5x ATR)
- TP at 2:1 R:R
- Shows exact Entry, SL, TP levels

**Run:** `python signals.py`

---

### `template.html`
**Purpose:** HTML/CSS/JS dashboard UI rendered by Flask.

**Components:**
- Status cards (Balance, Equity, Floating P/L, Positions, Margin, Session)
- Session indicators (SYDNEY, TOKYO, LONDON, NEW_YORK, OVERLAP)
- Market direction grid (H4/H1/M30 trends per pair)
- Pair selection tags
- Strategy selection tags
- Signal cards with Entry/SL/TP/R:R/Lot/Risk
- Trade confirmation modal
- Position table with close buttons
- Trade history with pagination
- Auto-scan timer (H4 candle countdown)

**JavaScript Functions:**
- `refresh()` - Fetches status from API every 30s
- `renderSignals()` - Renders signal cards
- `showTrade(idx)` - Opens trade confirmation modal
- `confirmTrade()` - Executes trade via API
- `closePos(ticket)` - Closes position
- `executeAction()` - Handles close all/profitable actions

---

### `requirements.txt`
**Purpose:** Python dependencies list.

**Core packages:** MetaTrader5, Flask, pandas, numpy, TA-Lib, scikit-learn, lightgbm, statsmodels, websocket-client, PyYAML, cryptography, pytelegrambotapi, matplotlib, seaborn

---

## Configuration Files

### `config/config.yaml` (262 lines)
**Purpose:** Main bot configuration. Defines broker settings (MT5, demo), 7 trading pairs, multi-timeframe analysis (M5, M15, H1, H4), and auto-reconnect logic.

### `config/pairs_config.yaml` (221 lines)
**Purpose:** Pair-specific specifications. Includes pip values, average/max spreads, volatility ratings, session priorities, lot size limits, contract sizes, margin requirements, news sensitivity, and correlation data between pairs.

### `config/risk_config.json` (180 lines)
**Purpose:** Risk management configuration. Three position sizing methods: fixed lot, risk-based (% of account), Kelly Criterion (1/8 Kelly = 12.5%). Drawdown limits, daily loss caps, position sizing rules.

### `config/sniper_config.json` (144 lines)
**Purpose:** "Professional Sniper Trading Bot v2.0.0" config. Max 10 daily trades, 3 open positions, max spread 30, magic number 202601, minimum confluence score 65, minimum confidence 0.60, minimum R:R 1.5, 1% risk per trade.

### `config/sniper_pro_2024_config.yaml` (1055 lines)
**Purpose:** Master config for SNIPER PRO 2024 4-bot orchestration system. Currently DISABLED. Defines account reference balance ($108.17), broker timezone (Africa/Nairobi, GMT+3), and extensive bot architecture settings.

### `config/unified_config.yaml` (246 lines)
**Purpose:** Unified trading bot config integrating ICT + AMD + traditional strategies. Primary strategy: `ict_2022`, primary symbol: XAUUSD, secondary: EURUSD/GBPUSD.

---

## Scripts

### `scripts/diagnose_filling_modes.py` (75 lines)
**Purpose:** Diagnostic utility that checks which MT5 order filling modes (FOK, IOC, RETURN) are supported for synthetic indices (Volatility 50/75/100, Crash 500/1000, Boom 300). Used to troubleshoot broker compatibility.

### `scripts/generate_v2_config.py` (78 lines)
**Purpose:** CLI tool that generates YAML configuration snippets for V2 strategy controllers. Supports `bollinger_v1` and `macd_bb_v1` with configurable parameters.

---

## MQL5 Expert Advisors

### `MQL5/Experts/AdvancedFunctions.mqh` (275 lines)
**Purpose:** MQL5 header file with advanced trading utility functions. Session detection (Asian, London, New York), shared global variables, enums, and helper functions. Included by main EA files.

### `MQL5/Experts/SNIPER_PRO_2024_EA.mq5` (667 lines)
**Purpose:** MQL5 Expert Advisor implementing ICT 2022 Mentorship Model. Trades during GMT+3 Killzones (London, New York), detects Fair Value Gaps (FVG) and Order Blocks. 1% risk per trade, 2% max daily loss, max 5 concurrent positions. Runs natively in MT5.

### `MQL5/Experts/SNIPER_PRO_2024_PatternEvidence_EA.mq5` (1411 lines)
**Purpose:** Advanced MQL5 EA (v2.00) with pattern evidence scoring. 6 bearish pullback templates + 4 bullish confirmation patterns. M15 timeframe, 180 bars history, 0.5% risk per trade. Pattern-based entry validation.

---

## Source Modules (src/)

### Core (`src/core/`)
| File | Purpose |
|------|---------|
| `unified_trading_bot.py` (1043 lines) | Main unified bot combining ICT 2022 (primary for XAUUSD), Power of 3/AMD Cycle, Trend Following, and Mean Reversion. Multi-timeframe analysis, killzone filtering, AMD cycle alignment. |
| `dynamic_strategy_orchestrator.py` (1022 lines) | 4-bot architecture: SNIPER SCOUT (analysis), PRECISION CONFIRMER (validation), EXECUTION SNIPER (orders), GUARDIAN (risk monitoring). |

### Connectors (`src/connectors/`)
| File | Purpose |
|------|---------|
| `mt5_connector.py` (283 lines) | MT5 API wrapper with unified `ExchangeConnector` interface. Timeframe mapping, graceful fallback. |
| `deriv_connector.py` (389 lines) | WebSocket connector to Deriv broker API. Real-time quotes, account info, order execution. |
| `base.py` (1.25 KB) | Base connector interface. |
| `manager.py` (5.49 KB) | Connector manager for switching between brokers. |

### Strategies (`src/strategies/`)
| File | Purpose |
|------|---------|
| `master_strategy_manager.py` (22.95 KB) | Central orchestrator for 110+ strategies. Integrates Technical, Breakout, Forex, Synthetic, Scalping, Swing, Pattern, Advanced, Smart Money, ICT, Supply-Demand strategies. |
| `technical_strategies_collection.py` (31.55 KB) | Collection of technical indicator-based strategies. |
| `breakout_strategies_collection.py` (21.43 KB) | Breakout strategy implementations. |
| `forex_specific_strategies.py` (18.65 KB) | Forex pair-specific strategies. |
| `pattern_recognition_strategies.py` (17.74 KB) | Chart pattern recognition strategies. |
| `smart_money_intermarket_strategies.py` (16.23 KB) | Smart money concepts + intermarket analysis. |
| `supply_demand_detector.py` (17.43 KB) | Supply and demand zone detection. |
| `supply_demand_strategy.py` (13.04 KB) | Supply and demand trading strategy. |
| `advanced_indicators_strategies.py` (25.21 KB) | Strategies using advanced indicators. |
| `synthetic_indices_strategies.py` (13.11 KB) | Synthetic indices strategies (Deriv). |
| `synthetic_strategies.py` (8.95 KB) | Additional synthetic strategies. |
| `scalping_swing_complete.py` (5.50 KB) | Complete scalping and swing strategies. |
| `professional_edge_integrator.py` (14.76 KB) | Professional trading edge integration. |
| `time_grid_strategies.py` (12.53 KB) | Time-based and grid strategies. |
| `strategy_conflict_manager.py` (21.23 KB) | Manages conflicts between strategies. |
| `mean_reversion.py` (2.30 KB) | Mean reversion strategy. |
| `stat_arb.py` (2.91 KB) | Statistical arbitrage. |
| `dca_smart.py` (2.17 KB) | Dollar cost averaging strategy. |
| `grid_advanced.py` (1.65 KB) | Advanced grid trading. |
| `combo_bot.py` (1.19 KB) | Combination strategy bot. |
| `prebuilt_library.py` (1.22 KB) | Prebuilt strategy library. |

### ICT (`src/ict/`)
| File | Purpose |
|------|---------|
| `ict_strategy.py` (17.72 KB) | ICT 2022 Mentorship Model. Daily bias (H4), Killzone filter, Liquidity sweep, Market structure shift, FVG entry, risk management. |
| `ict_2022_engine.py` (21.40 KB) | ICT 2022 engine implementation. |
| `liquidity_detector.py` (13.00 KB) | Liquidity pool detection. |
| `fvg_detector.py` (14.39 KB) | Fair Value Gap detection. |
| `market_structure.py` (14.53 KB) | Market structure analysis. |
| `killzone_filter.py` (15.40 KB) | Killzone session filtering. |

### Analysis (`src/analysis/`)
| File | Purpose |
|------|---------|
| `advanced_indicators.py` (36.26 KB) | Comprehensive TA-Lib indicator library. CRITICAL FOR PROFITABILITY. |
| `pattern_evidence_module.py` (29.97 KB) | Pattern evidence scoring system. |
| `pattern_recognition_advanced.py` (27.43 KB) | Advanced pattern recognition. |
| `order_blocks.py` (25.93 KB) | Order block detection. |
| `multi_timeframe_analyzer.py` (19.95 KB) | Multi-timeframe analysis. |
| `advanced_regime_detector.py` (18.03 KB) | Market regime detection. |
| `reversal_detector.py` (14.34 KB) | Reversal signal detection. |
| `wyckoff_analyzer.py` (14.67 KB) | Wyckoff method analysis. |
| `seasonality_analyzer.py` (15.93 KB) | Seasonal pattern analysis. |
| `session_analyzer.py` (11.42 KB) | Session analysis. |
| `market_regime.py` (11.25 KB) | Market regime classification. |
| `market_regime_advanced.py` (11.00 KB) | Advanced regime detection. |
| `fundamental_analysis.py` (12.38 KB) | Fundamental analysis integration. |
| `elliott_wave_analyzer.py` (13.17 KB) | Elliott Wave analysis. |
| `precious_metals_engine.py` (14.70 KB) | Precious metals (XAU/XAG) engine. |
| `carry_trade_analyzer.py` (5.51 KB) | Carry trade analysis. |
| `crisis_detector.py` (1.21 KB) | Market crisis detection. |
| `sentiment_analyzer.py` (0.72 KB) | Market sentiment analysis. |

### Risk (`src/risk/`)
| File | Purpose |
|------|---------|
| `smart_trade_filter.py` (17.19 KB) | Intelligent trade filtering inspired by top commercial EAs. Frequency limiting, adaptive risk scaling, volatility regime filtering, session-aware scoring, drawdown recovery. |
| `trading_circuit_breaker.py` (23.06 KB) | Circuit breaker for extreme market conditions. |
| `correlation_portfolio_manager.py` (21.22 KB) | Portfolio correlation management. |
| `forward_performance_validator.py` (13.59 KB) | Forward testing validation. |
| `runtime_var_engine.py` (9.28 KB) | Runtime VaR (Value at Risk) engine. |
| `portfolio_risk.py` (7.40 KB) | Portfolio risk calculation. |
| `correlation_matrix.py` (5.08 KB) | Pair correlation matrix. |
| `cooldown_manager.py` (3.97 KB) | Trade cooldown management. |
| `portfolio_heat.py` (1.75 KB) | Portfolio heat monitoring. |

### Execution (`src/execution/`)
| File | Purpose |
|------|---------|
| `multi_trigger_exit_manager.py` (30.02 KB) | Multi-trigger exit management (SL, TP, time, trailing). |
| `kelly_position_sizer.py` (22.21 KB) | Kelly Criterion position sizing. |
| `adaptive_position_sizer.py` (14.41 KB) | Adaptive position sizing. |
| `position_sizer.py` (15.36 KB) | Position sizing engine. |
| `realistic_paper_trading.py` (13.10 KB) | Paper trading simulation. |
| `advanced_position_sizing.py` (12.22 KB) | Advanced position sizing. |
| `trade_manager.py` (12.16 KB) | Trade management. |
| `dynamic_exit_manager.py` (11.55 KB) | Dynamic exit management. |
| `position_scaling.py` (10.88 KB) | Position scaling. |
| `slippage_model.py` (10.67 KB) | Slippage modeling. |
| `volatility_position_sizer.py` (2.41 KB) | Volatility-based position sizing. |
| `position_executor.py` (6.11 KB) | Position lifecycle management with triple-barrier risk controls. |

### AI/ML (`src/ai/`, `src/ml/`)
| File | Purpose |
|------|---------|
| `ml/feature_engineering.py` (13.31 KB) | ML feature engineering. |
| `ml/ml_strategy_selector.py` (21.61 KB) | ML-based strategy selection. |
| `ai/freqai_integration.py` (3.47 KB) | FreqAI integration. |
| `ai/strategy_designer.py` (3.75 KB) | AI strategy design. |
| `ai/agents/meta_agent.py` (4.15 KB) | Meta-agent for strategy coordination. |
| `ai/agents/regime_agent.py` (3.00 KB) | Regime detection agent. |
| `ai/agents/strategy_agents.py` (4.48 KB) | Individual strategy agents. |

### Strategy (`src/strategy/`)
| File | Purpose |
|------|---------|
| `confluence_engine.py` (17.80 KB) | Multi-signal confluence analysis. |
| `market_opening_sniper.py` (21.43 KB) | Market opening sniper strategy. |
| `multi_level_strategy.py` (20.92 KB) | Multi-level trading strategy. |
| `multi_timeframe_strategy.py` (15.61 KB) | Multi-timeframe strategy. |

### Monitoring (`src/monitoring/`)
| File | Purpose |
|------|---------|
| `performance_attribution.py` (25.36 KB) | Performance attribution analysis. |
| `psychology_monitor.py` (16.02 KB) | Trading psychology monitoring. |
| `order_lifecycle_tracker.py` (10.79 KB) | Order lifecycle tracking. |
| `execution_telemetry.py` (7.87 KB) | Execution telemetry. |
| `telegram_bot.py` (1.50 KB) | Telegram bot for alerts. |

### Other Modules
| Directory | Purpose |
|-----------|---------|
| `src/backtesting/` | Backtesting engine, validation tools, walk-forward analysis |
| `src/arbitrage/` | Arbitrage detection and execution |
| `src/data/` | Data ingestion, news filtering |
| `src/deployment/` | Local deployment runner |
| `src/hft/` | High-frequency trading (compounding, info arbitrage) |
| `src/marketplace/` | Strategy marketplace |
| `src/optimization/` | Hyperparameter optimization |
| `src/strategies/v2/` | V2 strategy controllers (Bollinger, Dman, MACD BB, Trend Follower) |
| `src/utils/` | Helpers, logger, validators |

---

## Unused/Legacy Files (_unused/)

### Trading Systems (Superseded by `src/` architecture)

| File | Lines | Purpose |
|------|-------|---------|
| `unified_trading_bot.py` | 587 | UNIFIED TRADING BOT v3 - Full-featured predecessor with auto-scan, web dashboard, user trade decisions, risk management, trade history, session indicators, Forex Factory news API. Ran on port 8088. |
| `unified_trading.py` | 393 | Earlier unified system with multi-strategy voting. Only entered trades when multiple strategies agreed. Superseded by `src/core/unified_trading_bot.py`. |
| `advanced_trading.py` | 486 | Advanced system combining trend-following with institutional liquidity detection. Superseded by `src/` architecture. |
| `complete_trading_system.py` | 474 | Complete system with BUY/SELL signals, smart SL/TP (2:1 R:R), high-probability setups, 1% risk, max 2 trades. Superseded by `web_controller.py`. |
| `improved_trading.py` | 404 | Improved system focused on selective high-probability setups. Filtered low-quality signals. Superseded by `src/` architecture. |

### Test Scripts

| File | Lines | Purpose |
|------|-------|---------|
| `test_strategies.py` | 722 | Comprehensive strategy test (v2). Tested all strategies independently against live MT5 data. |
| `execute_trade_test.py` | 255 | Automated test that opened actual trades in MT5 to verify order pipeline. |
| `test_simple.py` | 1.74 KB | Simple test script. |
| `debug_scan.py` | 1.55 KB | Debug script that imported web_controller bot and ran diagnostic checks (session, trade eligibility, news filtering, market data). |
| `diagnostic_test.py` | 5.67 KB | Minimal Flask diagnostic page for testing browser behavior and UI rendering. |

### JavaScript Files (Web debugging)

| File | Purpose |
|------|---------|
| `check_script.js` | Empty file, leftover from debugging. |
| `extracted_script.js` | Extracted JavaScript from web debugging. |
| `final_script.js` | Final version of extracted JS. |
| `temp_js.js` | Temporary JS file. |
| `temp_script.js` | Temporary script file. |
| `test_js.js` | JS test file. |

### Documentation & Misc

| File | Purpose |
|------|---------|
| `SYSTEM_IMPROVEMENTS.md` | Documentation for UNIFIED TRADING BOT v2. Workflow guide: auto-scan → show signals → user decides → bot executes → monitor. |
| `output.txt` | Empty output file. |

### Compiled Files (.pyc)

| File | Purpose |
|------|---------|
| `optimized_strategy.cpython-312.pyc` | Compiled Python bytecode. |
| `smart_risk_manager.cpython-312.pyc` | Compiled Python bytecode. |
| `unified_trading_bot.cpython-312.pyc` | Compiled Python bytecode. |
| `web_controller.cpython-312.pyc` | Compiled Python bytecode. |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE                          │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │  web_controller │    │   signals.py    │                 │
│  │   (Flask App)   │    │  (CLI Scanner)  │                 │
│  └────────┬────────┘    └────────┬────────┘                 │
│           │                      │                          │
│  ┌────────▼────────┐             │                          │
│  │  template.html  │             │                          │
│  │  (Dashboard UI) │             │                          │
│  └────────┬────────┘             │                          │
└───────────┼──────────────────────┼──────────────────────────┘
            │                      │
            ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    TRADING ENGINE                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  src/core/unified_trading_bot.py (Primary Bot)      │    │
│  │  - ICT 2022, AMD Cycle, Trend, Mean Reversion       │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  src/core/dynamic_strategy_orchestrator.py          │    │
│  │  - 4-bot: Scout, Confirmer, Sniper, Guardian        │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  src/strategies/master_strategy_manager.py          │    │
│  │  - 110+ strategies registry & dispatcher            │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│    RISK      │  │  EXECUTION   │  │   ANALYSIS   │
│  Management  │  │   Engine     │  │  Indicators  │
│              │  │              │  │              │
│ smart_trade  │  │ position_    │  │ advanced_    │
│ _filter.py   │  │ executor.py  │  │ indicators   │
│              │  │              │  │              │
│ circuit_     │  │ multi_trigger│  │ ict/         │
│ _breaker.py  │  │ _exit.py     │  │  strategy.py │
│              │  │              │  │              │
│ kelly_       │  │ trade_       │  │ order_       │
│ position.py  │  │ manager.py   │  │ blocks.py    │
└──────────────┘  └──────────────┘  └──────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   CONNECTORS │  │    MQL5      │  │   MONITORING │
│              │  │   EAs        │  │              │
│ mt5_         │  │ SNIPER_PRO_  │  │ telegram_    │
│ connector.py │  │ 2024_EA.mq5  │  │ bot.py       │
│              │  │              │  │              │
│ deriv_       │  │ Pattern      │  │ performance_ │
│ connector.py │  │ Evidence.mq5 │  │ attribution  │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## How to Run

### Web Dashboard (Active)
```bash
cd C:\Users\Samwel\Desktop\TradingBot\TradingBot
python web_controller.py
# Open http://127.0.0.1:5000 in browser
```

### Signal Scanner (CLI)
```bash
python signals.py
```

### MQL5 Expert Advisors
1. Copy `.mq5` and `.mqh` files to `MQL5/Experts/` in your MT5 installation
2. Compile in MetaEditor
3. Attach to chart in MT5

### Full src/ Architecture
```bash
python -m src.core.unified_trading_bot
```

---

## Trading Rules

### HOW IT WORKS (Human-in-the-Loop)
1. Bot scans pairs → displays signals on dashboard (http://127.0.0.1:5000)
2. Human reviews: H4 trend, H1 entry, RSI, ADX, spread, session
3. Human clicks "Execute" → trade placed
4. **NEVER auto-execute** - human always decides

### Entry Conditions (Human Checks)
- **H4 Trend:** EMA20 > EMA50 (BULL) or EMA20 < EMA50 (BEAR)
- **H1 Entry:** EMA9 > EMA21 (BUY) or EMA9 < EMA21 (SELL)
- **ADX:** > 18-20 for momentum confirmation
- **RSI:** 30-70 range (not overbought/oversold)
- **Spread:** < 300 pips (XAUUSD) or < 25 pips (forex)
- **Session:** LONDON, NEW_YORK, or OVERLAP preferred

### Risk Management (ENFORCED)
- **Risk per trade:** 1% of account balance
- **Max positions:** 2 (1 per pair)
- **Stop Loss:** 1.5x ATR (market volatility-based)
- **Take Profit:** 2x SL distance (2:1 R:R minimum)
- **Lot Size:** Calculated to risk exactly 1%
- **Daily Loss Limit:** 2% max → STOP TRADING if hit
- **Circuit Breaker:** 3 consecutive losses → 4hr pause
- **Trade Journal:** All trades recorded automatically

### Session Detection (UTC)
| Session | UTC Hours | Best Pairs |
|---------|-----------|------------|
| Sydney | 00:00 - 07:00 | AUDUSD, NZDUSD |
| Tokyo | 22:00 - 24:00 | USDJPY, AUDUSD |
| London | 08:00 - 12:00 | XAUUSD, EURUSD, GBPUSD |
| Overlap | 13:00 - 16:00 | EURUSD, GBPUSD, XAUUSD |
| New York | 16:00 - 22:00 | EURUSD, GBPUSD, USDCAD |

### Supported Pairs
XAUUSD, EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD

---

*Last Updated: 2026-04-08 | Version: v22 (Human-in-the-Loop)*
