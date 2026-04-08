# CHANGELOG - Trading Bot System

All notable changes to this trading system are documented here.

## [v22] - 2026-04-08 - HUMAN-IN-THE-LOOP REBUILD

### Changed
- **Mode**: Switched from auto-trading to human-in-the-loop. Bot only scans and displays signals; human makes execution decisions
- **Strategies**: Reduced from 5 to 2 proven strategies
  - `Swing_H4H1` (Primary): H4 EMA20/50 + H1 EMA9/21 + RSI + ADX confirmation
  - `Trend_Rider` (Secondary): ADX > 20 + EMA trend following
- **Removed**: Breakout_Hunter, Smart_Money, Mean_Reversion (moved to _unused)

### Added
- **Strict Risk Management**:
  - Daily loss limit: 2% max
  - Circuit breaker: Triggered after 3 consecutive losses (4-hour pause)
  - 24-hour pause if daily loss limit exceeded
- **Trade Journal**: All trades recorded with timestamp, entry/exit, profit/loss, strategy, notes

### Rationale
Previous approach relied on:
- 110+ strategies (fitting noise, not patterns)
- Auto-execution without proven edge
- Weak risk enforcement

New approach:
- Human decision-maker prevents emotional/automated mistakes
- 2 simple, clear strategies (trend-following)
- Strict circuit breaker prevents catastrophic losses
- Trade journal tracks all decisions for analysis

---

## [v21] - Previous Version

- 5 strategies (Swing_H4H1, Trend_Rider, Breakout_Hunter, Smart_Money, Mean_Reversion)
- Auto-trading enabled
- Basic risk (1% per trade, max 3 positions)
- No circuit breaker or daily limits
- No trade journal

---

## FILE STRUCTURE

```
TradingBot/
├── web_controller.py     # Main dashboard (v22 - Human-in-loop)
├── signals.py            # CLI signal scanner
├── template.html         # Dashboard UI
├── config/               # Configuration files
├── _unused/              # Disabled/legacy code
│   └── (5 removed strategies)
├── src/                  # Full strategy library (for reference)
├── MQL5/                 # MT5 Expert Advisors
└── CHANGELOG.md          # This file
```

---

## RULES FOR TRADING

### Entry (Human Decision)
1. Bot scans pairs → displays signals on dashboard
2. Human reviews: H4 trend, H1 entry, RSI, ADX, spread
3. Human clicks "Execute" → trade placed
4. NEVER auto-execute

### Risk Rules
- Max 2% daily loss → stop trading
- 3 consecutive losses → circuit breaker (4hr pause)
- 2 max open positions
- 1% risk per trade
- SL always required (ATR-based)
- TP at 2:1 minimum

### Journal
- All trades recorded in journal
- Review weekly: win rate, avg risk, mistakes
- If win rate < 40% after 20 trades → disable strategy

---

## NEXT STEPS

1. Paper trade for 2+ weeks
2. Track win rate on each strategy
3. If win rate > 50% → consider slight increase
4. If win rate < 40% → investigate or disable
5. NEVER add more strategies without proof