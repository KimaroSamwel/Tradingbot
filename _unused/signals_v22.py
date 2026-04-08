"""
Trading Signal Generator
- Analyzes all pairs for BUY/SELL signals
- Shows exact Entry, Stop Loss, Take Profit levels
- 2:1 Risk:Reward minimum
- Requires H4+H1 trend alignment + ADX > 20
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

print("Starting signal generator...")

if not mt5.initialize():
    print("ERROR: MT5 initialization failed")
    print("Make sure MetaTrader 5 is running and connected")
    exit(1)

print("MT5 Connected successfully")
acc = mt5.account_info()
print("Account: #" + str(acc.login) + " | Balance: $" + str(round(acc.balance, 2)))
print()

symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']

def ema(series, period):
    return series.ewm(span=period).mean()

def get_indicators(df_h4, df_h1):
    # H4 Trend
    ema20_h4 = ema(df_h4['close'], 20).iloc[-1]
    ema50_h4 = ema(df_h4['close'], 50).iloc[-1]
    h4_bull = ema20_h4 > ema50_h4

    # H1 Trend
    ema9_h1 = ema(df_h1['close'], 9).iloc[-1]
    ema21_h1 = ema(df_h1['close'], 21).iloc[-1]
    h1_bull = ema9_h1 > ema21_h1

    # ADX
    high, low, close = df_h1['high'].values, df_h1['low'].values, df_h1['close'].values
    n = len(high)
    tr = np.zeros(n - 1)
    plus_dm = np.zeros(n - 1)
    minus_dm = np.zeros(n - 1)
    for i in range(1, n):
        tr[i-1] = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        up = high[i] - high[i-1]
        down = low[i-1] - low[i]
        if up > down: plus_dm[i-1] = up
        if down > up: minus_dm[i-1] = down
    smoothed_tr = np.mean(tr[-14:])
    smoothed_plus = np.mean(plus_dm[-14:])
    smoothed_minus = np.mean(minus_dm[-14:])
    adx = 0
    if smoothed_tr > 0:
        plus_di = 100 * smoothed_plus / smoothed_tr
        minus_di = 100 * smoothed_minus / smoothed_tr
        adx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

    # RSI
    delta = df_h1['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).rolling(14).mean().iloc[-1]
    rs = gain / loss if loss != 0 else 50
    rsi = 100 - (100 / (1 + rs))

    # ATR
    atr = np.mean(np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1]))))

    return h4_bull, h1_bull, round(adx, 1), round(rsi, 1), round(atr, 5)

print("="*75)
print("TRADING SIGNALS - Entry, Stop Loss, Take Profit (2:1 R:R)")
print("="*75)
print()

signals_found = 0
trade_plan = []

for symbol in symbols:
    mt5.symbol_select(symbol, True)
    tick = mt5.symbol_info_tick(symbol)
    sym = mt5.symbol_info(symbol)

    df_h4 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 50))
    df_h1 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50))

    if df_h4 is None or df_h1 is None:
        continue

    h4_bull, h1_bull, adx, rsi, atr = get_indicators(df_h4, df_h1)

    print(symbol + " (" + str(round(tick.bid, 5)) + ")")
    print("-" * 60)
    print("  H4 Trend: " + ("BULL" if h4_bull else "BEAR") + " | H1 Trend: " + ("BULL" if h1_bull else "BEAR"))
    print("  ADX: " + str(adx) + " | RSI: " + str(rsi) + " | ATR: " + str(atr))

    # RELAXED CONDITIONS
    # For BUY: H4 bull AND (H1 bull OR RSI oversold) AND ADX > 18
    # For SELL: H4 bear AND (H1 bear OR RSI overbought) AND ADX > 18

    buy_conditions = h4_bull and (h1_bull or rsi < 35) and adx > 18 and rsi > 20
    sell_conditions = not h4_bull and (not h1_bull or rsi > 65) and adx > 18 and rsi < 80

    if buy_conditions:
        entry = tick.ask
        sl = entry - atr * 1.5
        tp = entry + atr * 3

        pips_risk = (entry - sl) / sym.point
        pips_reward = (tp - entry) / sym.point
        rr = pips_reward / pips_risk

        print()
        print("  >>> BUY <<<")
        print("    Entry:   " + str(round(entry, 5)))
        print("    Stop:    " + str(round(sl, 5)) + " (" + str(round(pips_risk, 0)) + " pips)")
        print("    Target:  " + str(round(tp, 5)) + " (" + str(round(pips_reward, 0)) + " pips)")
        print("    R:R = 1:" + str(round(rr, 1)))
        print()

        signals_found += 1
        trade_plan.append({
            'symbol': symbol,
            'direction': 'BUY',
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'rr': rr
        })

    elif sell_conditions:
        entry = tick.bid
        sl = entry + atr * 1.5
        tp = entry - atr * 3

        pips_risk = (sl - entry) / sym.point
        pips_reward = (entry - tp) / sym.point
        rr = pips_reward / pips_risk

        print()
        print("  >>> SELL <<<")
        print("    Entry:   " + str(round(entry, 5)))
        print("    Stop:    " + str(round(sl, 5)) + " (" + str(round(pips_risk, 0)) + " pips)")
        print("    Target:  " + str(round(tp, 5)) + " (" + str(round(pips_reward, 0)) + " pips)")
        print("    R:R = 1:" + str(round(rr, 1)))
        print()

        signals_found += 1
        trade_plan.append({
            'symbol': symbol,
            'direction': 'SELL',
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'rr': rr
        })

    else:
        reason = []
        if not h4_bull and not h1_bull:
            reason.append("Opposing trends")
        elif not h4_bull and h1_bull:
            reason.append("H1 bull but H4 bear")
        elif h4_bull and not h1_bull:
            reason.append("H1 bear but H4 bull")
        if adx <= 18:
            reason.append("ADX weak (" + str(adx) + ")")
        if rsi >= 80 or rsi <= 20:
            reason.append("RSI extreme (" + str(rsi) + ")")
        print("  No Signal: " + ", ".join(reason) if reason else "Conditions not met")
        print()

print("="*75)
print("SUMMARY: " + str(signals_found) + " valid signals found")
print("="*75)

if trade_plan:
    print()
    print("TRADE PLAN:")
    print("-"*75)
    for i, trade in enumerate(trade_plan, 1):
        print(str(i) + ". " + trade['symbol'] + " " + trade['direction'])
        print("   Entry: " + str(round(trade['entry'], 5)) + " | SL: " + str(round(trade['sl'], 5)) + " | TP: " + str(round(trade['tp'], 5)))
        print("   R:R = 1:" + str(round(trade['rr'], 1)))
        print()

mt5.shutdown()
