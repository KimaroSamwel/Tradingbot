# UNIFIED TRADING BOT v2 - GUIDE

## WHAT IT DOES

1. **Auto-Scans** for trade signals (XAUUSD, EURUSD, GBPUSD)
2. **Shows You** the signals with Entry, SL, TP, and Risk/Reward ratio
3. **YOU Decide** which trades to enter
4. **Bot Executes** only your chosen trades
5. **Monitors** open positions automatically

---

## HOW TO RUN

```bash
python unified_trading_bot.py
```

Then open browser: **http://127.0.0.1:8088**

---

## WEB DASHBOARD CONTROLS

| Button | Action |
|--------|--------|
| **▶ Auto-Scan** | Start continuous scanning (every 5 min) |
| **■ Stop** | Stop auto-scanning |
| **🔍 Scan Now** | Scan immediately |
| **✕ Close All** | Close all positions |
| **↻ Refresh** | Refresh dashboard |

---

## HOW TO TRADE

1. Click **🔍 Scan Now** to find signals
2. Look at the **TRADE SIGNALS** section
3. Each signal shows:
   - Symbol (XAUUSD, EURUSD, etc.)
   - Direction (BUY/SELL)
   - Entry Price
   - Stop Loss
   - Take Profit
   - Risk/Reward Ratio
   - Risk Amount
   - Lot Size
   - H4 Trend
   - RSI

4. Click **✅ ENTER TRADE** on signals you want

---

## WHY THIS APPROACH IS SMART

For a **$264 account**, YOU should approve trades because:
- Human oversight prevents bad trades
- You can skip during news events
- You can avoid risky setups
- Builds trading experience

---

## RISK SETTINGS

| Setting | Value |
|---------|-------|
| Risk per trade | 1% |
| Max positions | 2 |
| Max daily loss | 2% |
| Max drawdown | 5% |

---

## PROTECTION FEATURES

- **News Filter**: Blocks trades during high-impact news
- **Session Filter**: Only trades during London/NY overlap, Silver Bullet
- **Drawdown Protection**: Stops if equity drops 5%
- **Daily Loss Limit**: Stops if daily loss reaches 2%

---

## TRADING PAIRS

| Pair | Priority | Why |
|------|----------|-----|
| XAUUSD | #1 | Best backtest results (+191%) |
| EURUSD | #2 | Medium - needs good setup |
| GBPUSD | #3 | High volatility - wider stops |

---

## SIGNAL RANKING

Signals are ranked by Risk/Reward ratio (best first):
- 1:2.0 or better = Excellent
- 1:1.5 to 1:2.0 = Good
- Below 1:1.5 = Skipped

---

## WHAT BLOCKS TRADES

| Reason | What It Means |
|--------|---------------|
| News at 10:00 | High-impact news - skip |
| Weak: TOKYO | Asian session - low volume |
| Max positions | Already 2 trades open |
| Daily loss limit | Already lost 2% today |
| Max drawdown | Equity down 5% |

---

## CURRENT STATUS

- **Timezone**: GMT+3 (Africa/Nairobi)
- **Session**: London (8am-5pm GMT+3)
- **News**: Blocks at 10:00, 14:00, 15:00, 18:00
- **Silver Bullet**: 18:00-19:00 GMT+3 (best for gold)

---

## FILES

| File | Purpose |
|------|---------|
| `unified_trading_bot.py` | Main bot (runs everything) |
| `web_controller.py` | Web dashboard |
| `config/` | Configuration |
| `src/` | Core modules |

---

*Last Updated: 2026-03-31*
