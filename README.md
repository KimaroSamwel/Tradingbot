# Trading Bot v22 - Human-in-the-Loop System

**Signal Scanner + Trade Journal + Strict Risk Management**

---

## Overview

This is a **human-in-the-loop trading system** - the bot scans and displays signals, but **you make the execution decisions**. No auto-trading.

### Why Human-in-the-Loop?

- **AI/ML bots learn from historical data** but Forex is driven by real-time news, politics, central bank decisions, and mass human emotion - none of which follow past patterns
- **Without a proven edge** (100+ trades with proper data), a bot has no stable foundation
- **Risk management gaps** - one or two catastrophic losses can wipe gains from many winning trades

### Solution

- Human executes trades (prevents emotional/automated mistakes)
- 2 simple, proven strategies (not 110+)
- Strict circuit breaker prevents wipeout
- Trade journal tracks all decisions for analysis

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the dashboard
python web_controller.py

# Open in browser
http://127.0.0.1:5000
```

---

## How It Works

1. **Bot scans** all pairs → displays signals on dashboard
2. **You review:** H4 trend, H1 entry, RSI, ADX, spread, session
3. **You click Execute** → trade placed (never auto-execute)
4. **Risk rules enforced** automatically

---

## Strategies (2 Only)

| Strategy | Description | Best For |
|----------|-------------|----------|
| **Swing_H4H1** (Primary) | H4 EMA20/50 + H1 EMA9/21 + RSI + ADX | XAUUSD, EURUSD, GBPUSD |
| **Trend_Rider** (Secondary) | ADX > 20 + EMA trend confirmation | Trending markets |

---

## Risk Management (Strict)

| Rule | Value |
|------|-------|
| Risk per trade | 1% of account |
| Max positions | 2 |
| Daily loss limit | 2% → STOP trading |
| Circuit breaker | 3 consecutive losses = 4hr pause |
| Stop Loss | 1.5x ATR (volatility-based) |
| Take Profit | 2:1 R:R minimum |

---

## Trade Journal

All trades automatically recorded with:
- Timestamp, symbol, direction
- Entry/exit prices, lot size
- Profit/loss, strategy used
- Status (OPEN/CLOSED)

View in dashboard under "Journal Stats"

---

## File Structure

```
TradingBot/
├── web_controller.py     # Main dashboard (v22)
├── signals.py            # CLI signal scanner
├── template.html         # Dashboard UI
├── CHANGELOG.md          # Version history
├── config/               # Configuration
├── _unused/              # Disabled/legacy code
├── src/                  # Reference library (not used for live)
├── MQL5/                 # MT5 Expert Advisors
└── requirements.txt      # Dependencies
```

---

## Requirements

- Python 3.8+
- MetaTrader5 terminal
- Demo account (start here!)

---

## Disclaimer

**Trading involves substantial risk.** Start with paper trading, track your win rate, and only trade with capital you can afford to lose.

---

*Last Updated: 2026-04-08 | Version: v22*