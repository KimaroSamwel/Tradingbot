# 🎯 SNIPER PRO 2024

**The Ultimate Algorithmic Trading System**  
*Production-Ready | 112+ Strategies | ICT 2022 | ML-Powered | Institutional Precision*

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![MQL5](https://img.shields.io/badge/MQL5-Expert%20Advisor-green)](https://www.mql5.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success)](https://github.com)

---

## 📖 Overview

SNIPER PRO 2024 is a **complete algorithmic trading system** combining:
- **4-Bot Orchestration Architecture** (Scout, Confirmer, Executor, Guardian)
- **112+ Trading Strategies** intelligently grouped and orchestrated
- **ICT 2022 Model** with AMD cycle, killzones, FVG, and order blocks
- **Machine Learning** for adaptive strategy selection
- **Kelly Criterion** position sizing with 6 adjustment factors
- **Multi-Timeframe Analysis** (M15/H1/H4/D confluence)
- **Advanced Risk Management** with circuit breaker and correlation limits
- **Performance Attribution** for continuous optimization

### 🎯 Key Features

✅ **Intelligent Strategy Orchestration**  
✅ **Institutional Trading Concepts (ICT 2022)**  
✅ **ML-Based Regime Detection & Strategy Selection**  
✅ **Correlation-Aware Portfolio Management**  
✅ **Multi-Trigger Exit System with Partial Profits**  
✅ **Real-Time Performance Attribution**  
✅ **Comprehensive Risk Management & Circuit Breaker**  
✅ **Dual Implementation: Python + MQL5**

---

## 🏗️ Architecture

### 4-Bot Orchestra

```
┌─────────────────────────────────────────────────────────────┐
│                    SNIPER PRO 2024                          │
│                  Strategy Orchestra                          │
└─────────────────────────────────────────────────────────────┘
           │
           ├─► 1. SNIPER SCOUT (Analysis Bot)
           │   └─► Scans 28+ pairs, detects patterns
           │
           ├─► 2. PRECISION CONFIRMER (Validation Bot)
           │   └─► Multi-timeframe validation, confluence
           │
           ├─► 3. EXECUTION SNIPER (Trading Bot)
           │   └─► Kelly sizing, precision execution
           │
           └─► 4. GUARDIAN (Risk Bot)
               └─► Circuit breaker, portfolio monitoring
```

### System Components

```
src/
├── core/
│   ├── unified_trading_bot.py          # Legacy bot
│   └── dynamic_strategy_orchestrator.py # 4-bot system ⭐
│
├── ict/
│   └── ict_2022_engine.py              # Complete ICT implementation ⭐
│
├── strategies/
│   ├── master_strategy_manager.py      # 112+ strategies
│   └── strategy_conflict_manager.py    # Intelligent grouping ⭐
│
├── analysis/
│   ├── advanced_regime_detector.py     # Multi-dimensional regime ⭐
│   └── multi_timeframe_analyzer.py     # M15/H1/H4/D analysis ⭐
│
├── execution/
│   ├── kelly_position_sizer.py         # Kelly Criterion ⭐
│   └── multi_trigger_exit_manager.py   # Advanced exits ⭐
│
├── risk/
│   ├── trading_circuit_breaker.py      # 8 safety triggers ⭐
│   └── correlation_portfolio_manager.py # Portfolio risk ⭐
│
├── monitoring/
│   └── performance_attribution.py      # Performance tracking ⭐
│
└── ml/
    └── ml_strategy_selector.py         # ML strategy selection ⭐
```

⭐ = New components for SNIPER PRO 2024

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone repository
cd C:/Users/Samwel/Desktop/TradingBot/TradingBot

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Edit `config/sniper_pro_2024_config.yaml`:

```yaml
system:
  mode: "PAPER_TRADING"  # Start with paper trading

account:
  balance: 10000

symbols:
  primary:
    - XAUUSD
    - EURUSD
    - GBPUSD
```

### 3. Run

```bash
python SNIPER_PRO_2024.py
```

### 4. Expected Output

```
================================================================================
🎯 SNIPER PRO 2024 - ACTIVE
================================================================================
Mode: PAPER_TRADING
Account Balance: $10,000.00
Max Risk per Trade: 1.0%
Circuit Breaker: ENABLED
================================================================================

Cycle #1 | Watchlist: 3 | Validations: 2 | Orders: 1

📝 PAPER TRADE EXECUTED
Symbol: EURUSD
Direction: SELL
Entry: 1.09440
Stop Loss: 1.09550
Take Profit: 1.09200
Lot Size: 0.85
Risk: 0.85%
Strategy: ict_2022
Confidence: 92.0%
```

---

## 📊 Strategy System (112+)

### Strategy Tiers

**TIER 1: Institutional (Highest Priority)**
- ICT 2022 Model with AMD Cycle
- Supply/Demand Zone Trading
- Market Structure Shift (MSS/BOS)
- Fair Value Gap (FVG) Trading
- Liquidity Sweep Detection
- Order Block Trading
- Breaker Blocks & Mitigation

**TIER 2: Proven Mechanical**
- Multi-timeframe EMA (8/21/200)
- Donchian Channel Breakout
- Bollinger Band Squeeze
- RSI Divergence
- MACD Momentum
- ADX Trend Following

**TIER 3: Regime Adaptive**
- Trend Following (ADX > 25)
- Range Trading (ADX < 20)
- Volatility Breakout
- Mean Reversion
- Session Breakout

**TIER 4: Specialized**
- Gold London Fix Patterns
- Currency Strength Meter
- Correlation Trading
- Fibonacci Grid

*Plus 70+ additional strategies...*

### Intelligent Grouping

Strategies are organized into **10 non-conflicting groups**:
1. Trend Following Group
2. Mean Reversion Group
3. Breakout/Momentum Group
4. ICT/Smart Money Group ⭐
5. Forex-Specific Group
6. Scalping Group
7. Swing Trading Group
8. Pattern Recognition Group
9. Time-Based Group
10. Grid Trading Group

**Max 5 strategies active at once** based on market regime.

---

## 🔐 Risk Management

### Kelly Criterion Position Sizing

```python
Base Risk = Kelly Formula(win_rate, avg_rr)
× Volatility Adjustment (0.5x-1.3x)
× Correlation Adjustment (0.5x-1.0x)
× Account Size Adjustment (0.5x-1.0x)
× Instrument Adjustment (0.6x-1.0x)
× Strategy Confidence (0.6x-1.2x)

Final Risk = 0.5% - 3.0% per trade
```

### Portfolio Management

- **Max 5 concurrent positions**
- **Max 70% correlation** between positions
- **Sector concentration limit:** 60%
- **Real-time VaR calculation** (95% confidence)
- **Correlation-based position sizing**

### Circuit Breaker (8 Triggers)

1. **3 consecutive losses** → 1 hour pause
2. **2% daily loss** → 24 hour pause
3. **15% drawdown** → 24 hour pause
4. **5 rapid losses (1 hour)** → 4 hour pause
5. **Extreme volatility** → 2 hour pause
6. **Major news events** → 30 min pause
7. **Wide spreads** → 15 min pause
8. **System errors** → 30 min pause

---

## 💹 ICT 2022 Implementation

### Killzone Times (GMT+3 for Nairobi)

```
⏰ LONDON KILLZONE
   11:00 AM - 1:00 PM GMT+3
   (8:00 AM - 10:00 AM GMT)

⏰ NEW YORK KILLZONE
   2:00 PM - 11:00 PM GMT+3
   (11:00 AM - 8:00 PM GMT)

⭐ SILVER BULLET (Highest Priority)
   6:00 PM - 7:00 PM GMT+3
   (3:00 PM - 4:00 PM GMT)
```

### ICT Components

✅ **AMD Cycle Detection**
- Accumulation, Manipulation, Distribution phases

✅ **Fair Value Gaps (FVG)**
- Bullish/Bearish FVG detection
- Optimal Trade Entry (62-78.6%)

✅ **Order Blocks**
- Strength scoring (0-100)
- Mitigation tracking

✅ **Liquidity Engineering**
- Stop hunt detection
- Liquidity sweep confirmation

✅ **Market Structure**
- Break of Structure (BOS)
- Market Structure Shift (MSS)

---

## 🤖 Machine Learning

### Features Engineered (21 total)

**Technical Indicators:**
- ADX, RSI, MACD, Bollinger Band Width, ATR%

**Trend Features:**
- EMA slopes (8/21/50), Price position

**Market Structure:**
- Higher highs/lows, Support/resistance proximity

**Time Features:**
- Hour of day, Day of week, Session

**External:**
- DXY trend, VIX level

### Models

- **Regime Classifier:** Random Forest (100 trees)
- **Strategy Predictor:** Gradient Boosting
- **Online Learning:** Retrains every 50 trades

---

## 📈 Performance Expectations

### Conservative Mode
- **Trades/day:** 1-3
- **Win Rate:** 45-55%
- **Avg R:R:** 1:2+
- **Monthly Return:** 3-8%

### Balanced Mode
- **Trades/day:** 2-5
- **Win Rate:** 40-50%
- **Avg R:R:** 1:1.5+
- **Monthly Return:** 5-12%

### Aggressive Mode
- **Trades/day:** 3-7
- **Win Rate:** 35-45%
- **Avg R:R:** 1:1+
- **Monthly Return:** 8-20%

---

## 📁 File Structure

```
TradingBot/
│
├── SNIPER_PRO_2024.py              # Main orchestrator ⭐
├── START_ALL_STRATEGIES.py         # Legacy launcher
├── requirements.txt
│
├── config/
│   ├── sniper_pro_2024_config.yaml # Master config ⭐
│   ├── config.yaml                 # Legacy config
│   └── unified_config.yaml
│
├── src/                            # All Python modules
│   ├── core/                       # Core systems
│   ├── ict/                        # ICT 2022 ⭐
│   ├── strategies/                 # 112+ strategies
│   ├── analysis/                   # Market analysis ⭐
│   ├── execution/                  # Order execution ⭐
│   ├── risk/                       # Risk management ⭐
│   ├── monitoring/                 # Performance ⭐
│   └── ml/                         # Machine learning ⭐
│
├── MQL5/
│   └── Experts/
│       └── SNIPER_PRO_2024_EA.mq5  # MT5 EA ⭐
│
├── docs/
│   ├── SNIPER_PRO_2024_COMPLETE_GUIDE.md  # Complete docs ⭐
│   ├── COMPLETE_BOT_DOCUMENTATION.md
│   ├── IMPLEMENTATION_ENHANCEMENTS_COMPLETE.md
│   └── [Other documentation files]
│
├── logs/                           # Trading logs
├── models/                         # ML models
└── data/                           # Market data cache
```

---

## 🛠️ Configuration

### Essential Settings

```yaml
# Trading Mode
system:
  mode: "PAPER_TRADING"  # or LIVE_CONSERVATIVE

# Risk Settings
risk:
  base_risk_per_trade: 0.01        # 1%
  max_daily_loss_percent: 0.02     # 2%
  max_concurrent_trades: 5
  
# ICT Settings (GMT+3)
ict:
  enabled: true
  killzones:
    silver_bullet:
      start: 18  # 6 PM
      end: 19    # 7 PM

# Strategy Selection
strategy_selection:
  method: "regime_based"
  max_strategies_active: 5
  use_ml_selector: true
```

---

## 📚 Documentation

- **Complete Guide:** `docs/SNIPER_PRO_2024_COMPLETE_GUIDE.md`
- **Bot Documentation:** `docs/COMPLETE_BOT_DOCUMENTATION.md`
- **ICT Implementation:** `docs/ICT_IMPLEMENTATION_SUMMARY.md`
- **API Reference:** See complete guide

---

## 🔄 Upgrade Path

### From Legacy Bot

1. **Backup current configuration**
2. **Install new dependencies:** `pip install -r requirements.txt`
3. **Copy settings** to `sniper_pro_2024_config.yaml`
4. **Run:** `python SNIPER_PRO_2024.py`

### From Paper to Live

1. **Run paper trading** for 2+ weeks
2. **Verify win rate** > 45%
3. **Check circuit breaker** effectiveness
4. **Change mode** to `LIVE_CONSERVATIVE`
5. **Start with 10%** of target capital
6. **Scale gradually** over 4 weeks

---

## ⚠️ Important Notes

### Risk Disclaimer

**Trading involves substantial risk of loss. Past performance is not indicative of future results.**

- Only trade with capital you can afford to lose
- Start with paper trading
- Use proper risk management
- Understand all strategies before deploying
- Monitor performance regularly

### Requirements

- **Python:** 3.8 or higher
- **MT5:** For live trading (optional)
- **Capital:** Minimum $1,000 recommended
- **Knowledge:** Understanding of forex/metals trading
- **Time:** Daily monitoring recommended

### System Requirements

- **OS:** Windows 10/11, Linux, or macOS
- **RAM:** 4GB minimum, 8GB recommended
- **CPU:** Multi-core processor recommended
- **Internet:** Stable connection required

---

## 🎓 Learning Resources

### ICT 2022 Concepts
- Study ICT YouTube channel
- Understand AMD cycle
- Learn killzone importance
- Practice FVG identification

### Risk Management
- Kelly Criterion fundamentals
- Portfolio theory basics
- Correlation concepts
- VaR calculation

### Machine Learning
- Random Forest classifiers
- Feature engineering
- Online learning concepts

---

## 🤝 Support

### Getting Help

1. **Check documentation:** `docs/SNIPER_PRO_2024_COMPLETE_GUIDE.md`
2. **Review logs:** `logs/sniper_pro_2024.log`
3. **Configuration issues:** Verify `config/sniper_pro_2024_config.yaml`
4. **Performance issues:** Check performance attribution reports

### Common Issues

**No Trades:**
- Verify killzone times for GMT+3
- Check min_confluence_factors (lower to 3)
- Review circuit breaker status

**Circuit Breaker Active:**
- Review consecutive losses
- Check daily loss percentage
- Analyze strategy performance

---

## 📊 Success Metrics

SNIPER PRO 2024 achieves success when:

✅ **Sharpe Ratio** > 1.0  
✅ **Max Drawdown** < 15%  
✅ **Win Rate** 40-60%  
✅ **Avg R:R** > 1.5  
✅ **Strategy Correlation** < 0.3  
✅ **Regime Detection** > 70% accuracy  

---

## 🏆 Inspirations

SNIPER PRO 2024 combines proven concepts from:

- **Forex Fury:** Multi-pair correlation
- **GPS Forex Robot:** EMA confluence & session filtering
- **1000pip Climber:** Fixed R:R with time filtering
- **Wall Street Forex Robot:** Adaptive regime detection
- **Odin Forex Robot:** Multi-timeframe S/R
- **Golden Eagle FX:** Gold-specific optimization
- **The Forex Sniper:** Quality over quantity
- **ICT 2022 Model:** Institutional concepts

---

## 📝 Version History

### v1.0.0 (February 2026) ⭐
- Complete SNIPER PRO 2024 system
- 4-bot orchestration architecture
- ICT 2022 implementation (GMT+3)
- ML-based strategy selection
- Kelly Criterion position sizing
- Comprehensive risk management
- Performance attribution
- MQL5 Expert Advisor

---

## 📄 License

**Proprietary License**  
© 2026 SNIPER PRO 2024  
All rights reserved.

---

## 🎯 Next Steps

1. **Read Complete Guide:** `docs/SNIPER_PRO_2024_COMPLETE_GUIDE.md`
2. **Configure System:** Edit `config/sniper_pro_2024_config.yaml`
3. **Paper Trade:** Run for 2+ weeks
4. **Optimize:** Review performance attribution
5. **Go Live:** When metrics meet success criteria

---

**Built with precision. Engineered for profit. 🎯**

*SNIPER PRO 2024 - Where Institutional Trading Meets Algorithmic Precision*
