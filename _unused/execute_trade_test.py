"""
Execute Trade Test Script - Auto-test opening actual trades in MT5
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

if not mt5.initialize():
    print("MT5 initialization failed")
    exit()
    
print("=" * 60)
print("EXECUTE TRADE TEST SCRIPT - AUTO MODE")
print("=" * 60)

acc = mt5.account_info()
if acc:
    print(f"Account: {acc.login}, Balance: ${acc.balance}")
else:
    mt5.shutdown()
    exit()

max_risk = acc.balance * 0.01
print(f"Max Risk per Trade: ${max_risk:.2f}")

def calc_sl(symbol, entry, pips, direction):
    if 'XAU' in symbol:
        return entry - pips if direction == 'BUY' else entry + pips
    elif 'JPY' in symbol:
        return entry - pips * 0.01 if direction == 'BUY' else entry + pips * 0.01
    else:
        return entry - pips * 0.0001 if direction == 'BUY' else entry + pips * 0.0001

def calc_tp(symbol, entry, pips, direction):
    tp_pips = pips * 2
    if 'XAU' in symbol:
        return entry + tp_pips if direction == 'BUY' else entry - tp_pips
    elif 'JPY' in symbol:
        return entry + tp_pips * 0.01 if direction == 'BUY' else entry - tp_pips * 0.01
    else:
        return entry + tp_pips * 0.0001 if direction == 'BUY' else entry - tp_pips * 0.0001

def get_sl_pips(symbol, risk):
    if 'XAU' in symbol:
        return risk / (0.01 * 100)
    return risk / (0.01 * 10)

def calc_risk(symbol, lot, pips):
    if 'XAU' in symbol:
        return lot * pips * 100
    return lot * pips * 10

def ema(df, span):
    return df['close'].ewm(span=span).mean().iloc[-1]

def adx(df):
    high, low, close = df['high'].values, df['low'].values, df['close'].values
    n = len(high)
    if n < 15: return 0
    tr = np.zeros(n-1)
    plus_dm = np.zeros(n-1)
    minus_dm = np.zeros(n-1)
    for i in range(1, n):
        tr[i-1] = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        up = high[i]-high[i-1]
        down = low[i-1]-low[i]
        if up > down and up > 0: plus_dm[i-1] = up
        if down > up and down > 0: minus_dm[i-1] = down
    smoothed_tr = np.mean(tr[-14:])
    smoothed_plus = np.mean(plus_dm[-14:])
    smoothed_minus = np.mean(minus_dm[-14:])
    if smoothed_tr > 0:
        plus_di = 100 * smoothed_plus / smoothed_tr
        minus_di = 100 * smoothed_minus / smoothed_tr
        return round(100 * abs(plus_di - minus_di) / (plus_di + minus_di), 1)
    return 0

def rsi(df):
    delta = df['close'].diff()
    gain, loss = delta.clip(lower=0).mean(), (-delta.clip(upper=0)).mean()
    return 100 - (100 / (1 + gain/loss)) if loss > 0 else 50

def stoch(df):
    low_min = df['low'].rolling(14).min()
    high_max = df['high'].rolling(14).max()
    k = 100 * (df['close'] - low_min) / (high_max - low_min)
    return k.iloc[-1], k.rolling(3).mean().iloc[-1]

def execute(symbol, direction, entry, sl, tp, lot, strat):
    print(f"\n>>> EXECUTING: {strat} {symbol} {direction}")
    tick = mt5.symbol_info_tick(symbol)
    sym = mt5.symbol_info(symbol)
    if not tick or not sym: return None
    mt5.symbol_select(symbol, True)
    price = tick.ask if direction == 'BUY' else tick.bid
    print(f"    Entry: {entry:.5f}, Current: {price:.5f}")
    print(f"    SL: {sl:.5f}, TP: {tp:.5f}, Lot: {lot}")
    req = {
        'action': mt5.TRADE_ACTION_DEAL, 'symbol': symbol, 'volume': lot,
        'type': mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL,
        'price': price, 'sl': round(sl, sym.digits), 'tp': round(tp, sym.digits),
        'deviation': 10, 'magic': 2026001, 'comment': f"Test {strat}",
        'type_time': mt5.ORDER_TIME_GTC, 'type_filling': mt5.ORDER_FILLING_FOK
    }
    result = mt5.order_send(req)
    if result:
        print(f"    Result: retcode={result.retcode}, deal={result.deal}, comment={result.comment}")
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"    SUCCESS!")
            return result.deal
    return None

def get_positions():
    pos = mt5.positions_get()
    return [{'t': p.ticket, 's': p.symbol, 'v': p.volume, 'p': p.profit} for p in pos] if pos else []

def close_pos(ticket):
    pos = mt5.positions_get(ticket=ticket)
    if not pos: return False
    p = pos[0]
    tick = mt5.symbol_info_tick(p.symbol)
    if not tick: return False
    req = {
        'action': mt5.TRADE_ACTION_DEAL, 'symbol': p.symbol, 'volume': p.volume,
        'type': mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
        'position': ticket, 'price': tick.last, 'deviation': 5, 'magic': 2026001,
        'comment': 'Test close', 'type_time': mt5.ORDER_TIME_GTC, 'type_filling': mt5.ORDER_FILLING_FOK
    }
    result = mt5.order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"    Closed #{ticket}")
        return True
    return False

# Show current positions
print("\nCURRENT POSITIONS:")
for p in get_positions():
    print(f"  #{p['t']}: {p['s']} {p['v']} lots - ${p['p']:.2f}")
if not get_positions(): print("  None")

# Generate and execute signals
print("\n" + "="*60)
print("TESTING ALL STRATEGIES")
print("="*60)

trades = []
for pair in ['XAUUSD', 'EURUSD', 'USDJPY']:
    print(f"\n### {pair} ###")
    
    # Get data
    h4 = pd.DataFrame(mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_H4, 0, 100))
    h1 = pd.DataFrame(mt5.copy_rates_from_pos(pair, mt5.TIMEFRAME_H1, 0, 100))
    tick = mt5.symbol_info_tick(pair)
    sym = mt5.symbol_info(pair)
    if not tick or not sym: continue
    
    spread = (tick.ask - tick.bid) / sym.point / 10 if sym.digits in [3,5] else (tick.ask - tick.bid) / sym.point
    if spread > (300 if pair == 'XAUUSD' else 25): continue
    
    sl_pips = get_sl_pips(pair, max_risk)
    h4bull = ema(h4, 20) > ema(h4, 50)
    h1bull = ema(h1, 9) > ema(h1, 21)
    adx_val = adx(h1)
    
    # 1. Swing_H4H1
    if h4bull and h1bull and (pair != 'XAUUSD' or adx_val > 18):
        e, sl, tp = tick.ask, calc_sl(pair, tick.ask, sl_pips, 'BUY'), calc_tp(pair, tick.ask, sl_pips, 'BUY')
        deal = execute(pair, 'BUY', e, sl, tp, 0.01, 'Swing_H4H1')
        if deal: trades.append({'t': deal, 's': 'Swing_H4H1', 'pair': pair})
    elif not h4bull and not h1bull and (pair != 'XAUUSD' or adx_val > 18):
        e, sl, tp = tick.bid, calc_sl(pair, tick.bid, sl_pips, 'SELL'), calc_tp(pair, tick.bid, sl_pips, 'SELL')
        deal = execute(pair, 'SELL', e, sl, tp, 0.01, 'Swing_H4H1')
        if deal: trades.append({'t': deal, 's': 'Swing_H4H1', 'pair': pair})
    else:
        print(f"  Swing_H4H1: No signal (H4:{h4bull}, H1:{h1bull})")
    
    # 2. Trend_Rider
    if adx_val >= 15:
        if h4bull:
            e, sl, tp = tick.ask, calc_sl(pair, tick.ask, sl_pips, 'BUY'), calc_tp(pair, tick.ask, sl_pips, 'BUY')
            deal = execute(pair, 'BUY', e, sl, tp, 0.01, 'Trend_Rider')
            if deal: trades.append({'t': deal, 's': 'Trend_Rider', 'pair': pair})
        else:
            e, sl, tp = tick.bid, calc_sl(pair, tick.bid, sl_pips, 'SELL'), calc_tp(pair, tick.bid, sl_pips, 'SELL')
            deal = execute(pair, 'SELL', e, sl, tp, 0.01, 'Trend_Rider')
            if deal: trades.append({'t': deal, 's': 'Trend_Rider', 'pair': pair})
    else:
        print(f"  Trend_Rider: No signal (ADX={adx_val})")
    
    # 3. Breakout_Hunter
    h4['bb_mid'] = h4['close'].rolling(20).mean()
    h4['bb_std'] = h4['close'].rolling(20).std()
    bb_up = h4['bb_mid'].iloc[-1] + 2 * h4['bb_std'].iloc[-1]
    bb_low = h4['bb_mid'].iloc[-1] - 2 * h4['bb_std'].iloc[-1]
    close = h1['close'].iloc[-1]
    if close > bb_up:
        e, sl, tp = tick.ask, calc_sl(pair, tick.ask, sl_pips, 'BUY'), calc_tp(pair, tick.ask, sl_pips, 'BUY')
        deal = execute(pair, 'BUY', e, sl, tp, 0.01, 'Breakout_Hunter')
        if deal: trades.append({'t': deal, 's': 'Breakout_Hunter', 'pair': pair})
    elif close < bb_low:
        e, sl, tp = tick.bid, calc_sl(pair, tick.bid, sl_pips, 'SELL'), calc_tp(pair, tick.bid, sl_pips, 'SELL')
        deal = execute(pair, 'SELL', e, sl, tp, 0.01, 'Breakout_Hunter')
        if deal: trades.append({'t': deal, 's': 'Breakout_Hunter', 'pair': pair})
    else:
        print(f"  Breakout_Hunter: No signal (price in BB)")
    
    # 4. Smart_Money
    if h4bull:
        e, sl, tp = tick.ask, calc_sl(pair, tick.ask, sl_pips, 'BUY'), calc_tp(pair, tick.ask, sl_pips, 'BUY')
        deal = execute(pair, 'BUY', e, sl, tp, 0.01, 'Smart_Money')
        if deal: trades.append({'t': deal, 's': 'Smart_Money', 'pair': pair})
    else:
        e, sl, tp = tick.bid, calc_sl(pair, tick.bid, sl_pips, 'SELL'), calc_tp(pair, tick.bid, sl_pips, 'SELL')
        deal = execute(pair, 'SELL', e, sl, tp, 0.01, 'Smart_Money')
        if deal: trades.append({'t': deal, 's': 'Smart_Money', 'pair': pair})
    
    # 5. Mean_Reversion
    rsi_val = rsi(h1)
    stoch_val = stoch(h1)[0]
    if rsi_val < 35 and stoch_val < 30 and h4bull:
        e, sl, tp = tick.ask, calc_sl(pair, tick.ask, sl_pips, 'BUY'), calc_tp(pair, tick.ask, sl_pips, 'BUY')
        deal = execute(pair, 'BUY', e, sl, tp, 0.01, 'Mean_Reversion')
        if deal: trades.append({'t': deal, 's': 'Mean_Reversion', 'pair': pair})
        else: print(f"  Mean_Reversion: No signal (RSI={rsi_val}, Stoch={stoch_val})")
    elif rsi_val > 65 and stoch_val > 70 and not h4bull:
        e, sl, tp = tick.bid, calc_sl(pair, tick.bid, sl_pips, 'SELL'), calc_tp(pair, tick.bid, sl_pips, 'SELL')
        deal = execute(pair, 'SELL', e, sl, tp, 0.01, 'Mean_Reversion')
        if deal: trades.append({'t': deal, 's': 'Mean_Reversion', 'pair': pair})
        else: print(f"  Mean_Reversion: No signal (RSI={rsi_val}, Stoch={stoch_val})")
    else:
        print(f"  Mean_Reversion: No signal (RSI={rsi_val}, Stoch={stoch_val})")

# Summary
print("\n" + "="*60)
print("RESULTS")
print("="*60)
print(f"\nTrades executed: {len(trades)}")
for t in trades:
    print(f"  #{t['t']}: {t['s']} on {t['pair']}")

print("\nFINAL POSITIONS:")
for p in get_positions():
    print(f"  #{p['t']}: {p['s']} {p['v']} lots - ${p['p']:.2f}")
if not get_positions(): print("  None")

# Option to close
print("\n" + "="*60)
print("To close all test trades, run: close_all_test_trades()")
print("="*60)

def close_all_test_trades():
    for t in trades:
        close_pos(t['t'])

mt5.shutdown()
