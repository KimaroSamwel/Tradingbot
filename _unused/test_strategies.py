"""
Strategy Test Script - Test all strategies independently
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

# Initialize MT5
if not mt5.initialize():
    print("MT5 initialization failed")
    exit()
    
print("=" * 60)
print("STRATEGY TEST SCRIPT v2")
print("=" * 60)

# Get account info
acc = mt5.account_info()
if acc:
    print(f"Account: {acc.login}")
    print(f"Balance: ${acc.balance}")
    print(f"Equity: ${acc.equity}")
else:
    print("Failed to get account info")
    mt5.shutdown()
    exit()

broker_tz = timezone(timedelta(hours=3))
trading_pairs = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD']

def get_contract_size(symbol):
    if 'XAU' in symbol or 'XAG' in symbol:
        return 100
    return 100000

def calculate_atr(df, period=14):
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    return np.mean(tr[-period:]) if len(tr) >= period else 0

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0).mean()
    loss = (-delta.clip(upper=0)).mean()
    rs = gain / loss if loss > 0 else 50
    return 100 - (100 / (1 + rs))

def calculate_stochastic(df, period=14):
    low_min = df['low'].rolling(period).min()
    high_max = df['high'].rolling(period).max()
    k = 100 * (df['close'] - low_min) / (high_max - low_min)
    return k.iloc[-1], k.rolling(3).mean().iloc[-1]

def calculate_adx(df, period=14):
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    n = len(high)
    if n < period + 1:
        return 0
    tr = np.zeros(n - 1)
    plus_dm = np.zeros(n - 1)
    minus_dm = np.zeros(n - 1)
    for i in range(1, n):
        tr[i-1] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        up_move = high[i] - high[i-1]
        down_move = low[i-1] - low[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i-1] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i-1] = down_move
    if len(tr) >= period:
        smoothed_tr = np.mean(tr[-period:])
        smoothed_plus = np.mean(plus_dm[-period:])
        smoothed_minus = np.mean(minus_dm[-period:])
        if smoothed_tr > 0:
            plus_di = 100 * smoothed_plus / smoothed_tr
            minus_di = 100 * smoothed_minus / smoothed_tr
            di_sum = plus_di + minus_di
            if di_sum > 0:
                return round(100 * abs(plus_di - minus_di) / di_sum, 1)
    return 0

def calculate_ema(df, span):
    return df['close'].ewm(span=span).mean().iloc[-1]

def calculate_risk(symbol, lot, sl_distance_pips):
    """Calculate risk in dollars based on SL distance in pips"""
    if 'XAU' in symbol or 'XAG' in symbol:
        # XAUUSD: $1 per point per lot (100 oz contract)
        return lot * sl_distance_pips * 100
    else:
        # Forex: $10 per pip per lot (100,000 units)
        return lot * sl_distance_pips * 10

def calculate_sl_price(symbol, entry, sl_distance_pips, direction, digits=5):
    """
    Calculate SL price based on SL distance in pips
    For XAUUSD: 1 pip = $1, 1 point = $0.01
    For EURUSD (5 digits): 1 pip = 10 points, 1 point = $0.10
    For USDJPY (3 digits): 1 pip = 1 point, 1 point = ~$0.67
    """
    if 'XAU' in symbol or 'XAG' in symbol:
        # Gold: price in dollars, 1 pip = $1
        sl_price = sl_distance_pips
        if direction == 'BUY':
            return entry - sl_price
        else:
            return entry + sl_price
    elif 'JPY' in symbol:
        # JPY pairs (3 digits): 1 pip = 1 point
        sl_price = sl_distance_pips * 0.01  # Convert pips to price
        if direction == 'BUY':
            return entry - sl_price
        else:
            return entry + sl_price
    else:
        # Non-JPY forex (5 digits): 1 pip = 10 points
        sl_price = sl_distance_pips * 0.0001  # Convert pips to price
        if direction == 'BUY':
            return entry - sl_price
        else:
            return entry + sl_price

def calculate_tp_price(symbol, entry, sl_distance_pips, direction, rr=2.0):
    """Calculate TP price based on SL distance * RR ratio"""
    tp_distance_pips = sl_distance_pips * rr
    return calculate_sl_price(symbol, entry, tp_distance_pips, direction)

def get_proper_sl_distance(symbol, risk_amount, min_lot=0.01):
    """
    Calculate SL distance in pips that results in the target risk amount
    """
    if 'XAU' in symbol or 'XAG' in symbol:
        # XAUUSD: risk = lot * pips * 100
        return risk_amount / (min_lot * 100)
    else:
        # Forex: risk = lot * pips * 10
        return risk_amount / (min_lot * 10)

# ============================================================
# STRATEGY 1: SWING H4H1
# ============================================================
def test_swing_h4h1(symbol, max_risk):
    print(f"\n{'='*60}")
    print(f"TESTING: Swing_H4H1 on {symbol}")
    print(f"{'='*60}")
    
    try:
        # Get data
        rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 100)
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        
        if rates_h4 is None or rates_h1 is None:
            print(f"  No data for {symbol}")
            return None
        
        df_h4 = pd.DataFrame(rates_h4)
        df_h1 = pd.DataFrame(rates_h1)
        
        tick = mt5.symbol_info_tick(symbol)
        sym_info = mt5.symbol_info(symbol)
        if not tick or not sym_info:
            print(f"  No tick data")
            return None
        
        digits = sym_info.digits
        
        # Calculate EMAs
        h4_ema20 = calculate_ema(df_h4, 20)
        h4_ema50 = calculate_ema(df_h4, 50)
        h1_ema9 = calculate_ema(df_h1, 9)
        h1_ema21 = calculate_ema(df_h1, 21)
        
        h4_bull = h4_ema20 > h4_ema50
        h4_bear = h4_ema20 < h4_ema50
        h1_bull = h1_ema9 > h1_ema21
        h1_bear = h1_ema9 < h1_ema21
        
        print(f"  H4 EMA20: {h4_ema20:.5f}, EMA50: {h4_ema50:.5f}")
        print(f"  H1 EMA9: {h1_ema9:.5f}, EMA21: {h1_ema21:.5f}")
        print(f"  H4 Trend: {'BULL' if h4_bull else 'BEAR' if h4_bear else 'NEUTRAL'}")
        print(f"  H1 Trend: {'BULL' if h1_bull else 'BEAR' if h1_bear else 'NEUTRAL'}")
        
        # ADX check for XAUUSD
        adx = calculate_adx(df_h1)
        print(f"  ADX: {adx}")
        if symbol == 'XAUUSD' and adx <= 18:
            print(f"  ADX too low ({adx} <= 18)")
            return None
        
        # Check spread
        spread = tick.ask - tick.bid
        spread_pips = spread / sym_info.point / 10 if digits in [3, 5] else spread / sym_info.point
        max_spread = 300 if symbol == 'XAUUSD' else 25
        print(f"  Spread: {spread_pips:.1f} pips (max: {max_spread})")
        if spread_pips > max_spread:
            print(f"  Spread too high")
            return None
        
        # Calculate SL distance
        sl_distance_pips = get_proper_sl_distance(symbol, max_risk, 0.01)
        print(f"  SL Distance (pips): {sl_distance_pips:.2f}")
        
        # Generate signal
        if h4_bull and h1_bull:
            direction = 'BUY'
            entry = tick.ask
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'BUY', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'BUY', 2.0)
            trend = 'BULL'
        elif h4_bear and h1_bear:
            direction = 'SELL'
            entry = tick.bid
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'SELL', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'SELL', 2.0)
            trend = 'BEAR'
        else:
            print(f"  No signal - trends not aligned")
            return None
        
        # Calculate risk
        lot = 0.01
        risk = calculate_risk(symbol, lot, sl_distance_pips)
        rr = 2.0
        
        print(f"\n  SIGNAL GENERATED:")
        print(f"  Direction: {direction}")
        print(f"  Entry: {entry:.5f}")
        print(f"  SL: {sl:.5f}")
        print(f"  TP: {tp:.5f}")
        print(f"  Lot: {lot}")
        print(f"  Risk: ${risk:.2f}")
        print(f"  Max Risk: ${max_risk:.2f}")
        print(f"  R:R: 1:{rr}")
        print(f"  Can Trade: {'YES' if risk <= max_risk else 'NO'}")
        
        return {
            'symbol': symbol, 'direction': direction, 'entry': entry,
            'sl': sl, 'tp': tp, 'lot': lot, 'risk': risk,
            'rr': rr, 'can_trade': risk <= max_risk, 'trend': trend,
            'strategy': 'Swing_H4H1'
        }
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================
# STRATEGY 2: TREND RIDER
# ============================================================
def test_trend_rider(symbol, max_risk):
    print(f"\n{'='*60}")
    print(f"TESTING: Trend_Rider on {symbol}")
    print(f"{'='*60}")
    
    try:
        rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 100)
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        
        if rates_h4 is None or rates_h1 is None:
            print(f"  No data for {symbol}")
            return None
        
        df_h4 = pd.DataFrame(rates_h4)
        df_h1 = pd.DataFrame(rates_h1)
        
        tick = mt5.symbol_info_tick(symbol)
        sym_info = mt5.symbol_info(symbol)
        if not tick or not sym_info:
            print(f"  No tick data")
            return None
        
        digits = sym_info.digits
        
        # Calculate EMAs
        h4_ema20 = calculate_ema(df_h4, 20)
        h4_ema50 = calculate_ema(df_h4, 50)
        
        h4_bull = h4_ema20 > h4_ema50
        
        # ADX check
        adx = calculate_adx(df_h1)
        print(f"  H4 EMA20: {h4_ema20:.5f}, EMA50: {h4_ema50:.5f}")
        print(f"  H4 Trend: {'BULL' if h4_bull else 'BEAR'}")
        print(f"  ADX: {adx}")
        
        if adx < 15:
            print(f"  ADX too low ({adx} < 15)")
            return None
        
        # Check spread
        spread = tick.ask - tick.bid
        spread_pips = spread / sym_info.point / 10 if digits in [3, 5] else spread / sym_info.point
        max_spread = 300 if symbol == 'XAUUSD' else 25
        print(f"  Spread: {spread_pips:.1f} pips")
        if spread_pips > max_spread:
            print(f"  Spread too high")
            return None
        
        # Calculate SL distance
        sl_distance_pips = get_proper_sl_distance(symbol, max_risk, 0.01)
        print(f"  SL Distance (pips): {sl_distance_pips:.2f}")
        
        if h4_bull:
            direction = 'BUY'
            entry = tick.ask
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'BUY', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'BUY', 2.0)
            trend = 'BULL'
        else:
            direction = 'SELL'
            entry = tick.bid
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'SELL', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'SELL', 2.0)
            trend = 'BEAR'
        
        lot = 0.01
        risk = calculate_risk(symbol, lot, sl_distance_pips)
        rr = 2.0
        
        print(f"\n  SIGNAL GENERATED:")
        print(f"  Direction: {direction}")
        print(f"  Entry: {entry:.5f}")
        print(f"  SL: {sl:.5f}")
        print(f"  TP: {tp:.5f}")
        print(f"  Lot: {lot}")
        print(f"  Risk: ${risk:.2f}")
        print(f"  Max Risk: ${max_risk:.2f}")
        print(f"  R:R: 1:{rr}")
        print(f"  Can Trade: {'YES' if risk <= max_risk else 'NO'}")
        
        return {
            'symbol': symbol, 'direction': direction, 'entry': entry,
            'sl': sl, 'tp': tp, 'lot': lot, 'risk': risk,
            'rr': rr, 'can_trade': risk <= max_risk, 'trend': trend,
            'strategy': 'Trend_Rider'
        }
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================
# STRATEGY 3: BREAKOUT HUNTER
# ============================================================
def test_breakout_hunter(symbol, max_risk):
    print(f"\n{'='*60}")
    print(f"TESTING: Breakout_Hunter on {symbol}")
    print(f"{'='*60}")
    
    try:
        rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 50)
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        
        if rates_h4 is None or rates_h1 is None:
            print(f"  No data for {symbol}")
            return None
        
        df_h4 = pd.DataFrame(rates_h4)
        df_h1 = pd.DataFrame(rates_h1)
        
        tick = mt5.symbol_info_tick(symbol)
        sym_info = mt5.symbol_info(symbol)
        if not tick or not sym_info:
            print(f"  No tick data")
            return None
        
        digits = sym_info.digits
        
        # Bollinger Bands on H4
        df_h4['bb_middle'] = df_h4['close'].rolling(20).mean()
        df_h4['bb_std'] = df_h4['close'].rolling(20).std()
        df_h4['bb_upper'] = df_h4['bb_middle'] + 2 * df_h4['bb_std']
        df_h4['bb_lower'] = df_h4['bb_middle'] - 2 * df_h4['bb_std']
        
        current_close = df_h1['close'].iloc[-1]
        bb_upper = df_h4['bb_upper'].iloc[-1]
        bb_lower = df_h4['bb_lower'].iloc[-1]
        
        print(f"  Current Close: {current_close:.5f}")
        print(f"  BB Upper: {bb_upper:.5f}")
        print(f"  BB Lower: {bb_lower:.5f}")
        
        # Check spread
        spread = tick.ask - tick.bid
        spread_pips = spread / sym_info.point / 10 if digits in [3, 5] else spread / sym_info.point
        max_spread = 300 if symbol == 'XAUUSD' else 25
        print(f"  Spread: {spread_pips:.1f} pips")
        if spread_pips > max_spread:
            print(f"  Spread too high")
            return None
        
        # Calculate SL distance
        sl_distance_pips = get_proper_sl_distance(symbol, max_risk, 0.01)
        print(f"  SL Distance (pips): {sl_distance_pips:.2f}")
        
        if current_close > bb_upper:
            direction = 'BUY'
            entry = tick.ask
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'BUY', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'BUY', 2.0)
            trend = 'BREAKOUT_UP'
            print(f"  Signal: BREAKOUT UP")
        elif current_close < bb_lower:
            direction = 'SELL'
            entry = tick.bid
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'SELL', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'SELL', 2.0)
            trend = 'BREAKOUT_DOWN'
            print(f"  Signal: BREAKOUT DOWN")
        else:
            print(f"  No breakout detected")
            return None
        
        lot = 0.01
        risk = calculate_risk(symbol, lot, sl_distance_pips)
        rr = 2.0
        
        print(f"\n  SIGNAL GENERATED:")
        print(f"  Direction: {direction}")
        print(f"  Entry: {entry:.5f}")
        print(f"  SL: {sl:.5f}")
        print(f"  TP: {tp:.5f}")
        print(f"  Lot: {lot}")
        print(f"  Risk: ${risk:.2f}")
        print(f"  Max Risk: ${max_risk:.2f}")
        print(f"  R:R: 1:{rr}")
        print(f"  Can Trade: {'YES' if risk <= max_risk else 'NO'}")
        
        return {
            'symbol': symbol, 'direction': direction, 'entry': entry,
            'sl': sl, 'tp': tp, 'lot': lot, 'risk': risk,
            'rr': rr, 'can_trade': risk <= max_risk, 'trend': trend,
            'strategy': 'Breakout_Hunter'
        }
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================
# STRATEGY 4: SMART MONEY
# ============================================================
def test_smart_money(symbol, max_risk):
    print(f"\n{'='*60}")
    print(f"TESTING: Smart_Money on {symbol}")
    print(f"{'='*60}")
    
    try:
        rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 50)
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        
        if rates_h4 is None or rates_h1 is None:
            print(f"  No data for {symbol}")
            return None
        
        df_h4 = pd.DataFrame(rates_h4)
        df_h1 = pd.DataFrame(rates_h1)
        
        tick = mt5.symbol_info_tick(symbol)
        sym_info = mt5.symbol_info(symbol)
        if not tick or not sym_info:
            print(f"  No tick data")
            return None
        
        digits = sym_info.digits
        
        # Calculate EMAs for trend
        h4_ema20 = calculate_ema(df_h4, 20)
        h4_ema50 = calculate_ema(df_h4, 50)
        
        h4_trend_up = h4_ema20 > h4_ema50
        
        print(f"  H4 EMA20: {h4_ema20:.5f}, EMA50: {h4_ema50:.5f}")
        print(f"  H4 Trend: {'BULL' if h4_trend_up else 'BEAR'}")
        
        # Check spread
        spread = tick.ask - tick.bid
        spread_pips = spread / sym_info.point / 10 if digits in [3, 5] else spread / sym_info.point
        max_spread = 300 if symbol == 'XAUUSD' else 25
        print(f"  Spread: {spread_pips:.1f} pips")
        if spread_pips > max_spread:
            print(f"  Spread too high")
            return None
        
        # Calculate SL distance
        sl_distance_pips = get_proper_sl_distance(symbol, max_risk, 0.01)
        print(f"  SL Distance (pips): {sl_distance_pips:.2f}")
        
        if h4_trend_up:
            direction = 'BUY'
            entry = tick.ask
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'BUY', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'BUY', 2.0)
            trend = 'BULL_OB'
        else:
            direction = 'SELL'
            entry = tick.bid
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'SELL', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'SELL', 2.0)
            trend = 'BEAR_OB'
        
        lot = 0.01
        risk = calculate_risk(symbol, lot, sl_distance_pips)
        rr = 2.0
        
        print(f"\n  SIGNAL GENERATED:")
        print(f"  Direction: {direction}")
        print(f"  Entry: {entry:.5f}")
        print(f"  SL: {sl:.5f}")
        print(f"  TP: {tp:.5f}")
        print(f"  Lot: {lot}")
        print(f"  Risk: ${risk:.2f}")
        print(f"  Max Risk: ${max_risk:.2f}")
        print(f"  R:R: 1:{rr}")
        print(f"  Can Trade: {'YES' if risk <= max_risk else 'NO'}")
        
        return {
            'symbol': symbol, 'direction': direction, 'entry': entry,
            'sl': sl, 'tp': tp, 'lot': lot, 'risk': risk,
            'rr': rr, 'can_trade': risk <= max_risk, 'trend': trend,
            'strategy': 'Smart_Money'
        }
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================
# STRATEGY 5: MEAN REVERSION
# ============================================================
def test_mean_reversion(symbol, max_risk):
    print(f"\n{'='*60}")
    print(f"TESTING: Mean_Reversion on {symbol}")
    print(f"{'='*60}")
    
    try:
        rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 50)
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        
        if rates_h4 is None or rates_h1 is None:
            print(f"  No data for {symbol}")
            return None
        
        df_h4 = pd.DataFrame(rates_h4)
        df_h1 = pd.DataFrame(rates_h1)
        
        tick = mt5.symbol_info_tick(symbol)
        sym_info = mt5.symbol_info(symbol)
        if not tick or not sym_info:
            print(f"  No tick data")
            return None
        
        digits = sym_info.digits
        
        # Calculate RSI and Stochastic
        rsi = calculate_rsi(df_h1)
        stoch_k, stoch_d = calculate_stochastic(df_h1)
        
        # H4 trend
        h4_ema20 = calculate_ema(df_h4, 20)
        h4_ema50 = calculate_ema(df_h4, 50)
        h4_bull = h4_ema20 > h4_ema50
        
        print(f"  RSI: {rsi:.1f}")
        print(f"  Stochastic K: {stoch_k:.1f}, D: {stoch_d:.1f}")
        print(f"  H4 Trend: {'BULL' if h4_bull else 'BEAR'}")
        
        buy_signal = rsi < 35 and stoch_k < 30
        sell_signal = rsi > 65 and stoch_k > 70
        
        print(f"  Buy Signal: {'YES' if buy_signal else 'NO'} (RSI<35 & StochK<30)")
        print(f"  Sell Signal: {'YES' if sell_signal else 'NO'} (RSI>65 & StochK>70)")
        
        # Check spread
        spread = tick.ask - tick.bid
        spread_pips = spread / sym_info.point / 10 if digits in [3, 5] else spread / sym_info.point
        max_spread = 300 if symbol == 'XAUUSD' else 25
        print(f"  Spread: {spread_pips:.1f} pips")
        if spread_pips > max_spread:
            print(f"  Spread too high")
            return None
        
        # Calculate SL distance
        sl_distance_pips = get_proper_sl_distance(symbol, max_risk, 0.01)
        print(f"  SL Distance (pips): {sl_distance_pips:.2f}")
        
        if buy_signal and h4_bull:
            direction = 'BUY'
            entry = tick.ask
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'BUY', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'BUY', 2.0)
            trend = 'OVERSOLD'
            print(f"  Signal: BUY - Oversold")
        elif sell_signal and not h4_bull:
            direction = 'SELL'
            entry = tick.bid
            sl = calculate_sl_price(symbol, entry, sl_distance_pips, 'SELL', digits)
            tp = calculate_tp_price(symbol, entry, sl_distance_pips, 'SELL', 2.0)
            trend = 'OVERBOUGHT'
            print(f"  Signal: SELL - Overbought")
        else:
            print(f"  No signal - conditions not met")
            return None
        
        lot = 0.01
        risk = calculate_risk(symbol, lot, sl_distance_pips)
        rr = 2.0
        
        print(f"\n  SIGNAL GENERATED:")
        print(f"  Direction: {direction}")
        print(f"  Entry: {entry:.5f}")
        print(f"  SL: {sl:.5f}")
        print(f"  TP: {tp:.5f}")
        print(f"  Lot: {lot}")
        print(f"  Risk: ${risk:.2f}")
        print(f"  Max Risk: ${max_risk:.2f}")
        print(f"  R:R: 1:{rr}")
        print(f"  Can Trade: {'YES' if risk <= max_risk else 'NO'}")
        
        return {
            'symbol': symbol, 'direction': direction, 'entry': entry,
            'sl': sl, 'tp': tp, 'lot': lot, 'risk': risk,
            'rr': rr, 'can_trade': risk <= max_risk, 'trend': trend,
            'strategy': 'Mean_Reversion'
        }
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================
# RUN TESTS
# ============================================================
print(f"\n{'='*60}")
print("TESTING ALL STRATEGIES")
print("=" * 60)

max_risk = acc.balance * (0.01)  # 1% risk
print(f"\nMax Risk per Trade: ${max_risk:.2f}")

# Test pairs
test_pairs = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD']

all_signals = []

for pair in test_pairs:
    print(f"\n{'#'*60}")
    print(f"# TESTING {pair}")
    print(f"{'#'*60}")
    
    # Test each strategy
    strategies = [
        ('Swing_H4H1', test_swing_h4h1),
        ('Trend_Rider', test_trend_rider),
        ('Breakout_Hunter', test_breakout_hunter),
        ('Smart_Money', test_smart_money),
        ('Mean_Reversion', test_mean_reversion),
    ]
    
    for name, func in strategies:
        signal = func(pair, max_risk)
        if signal:
            all_signals.append(signal)

# Summary
print(f"\n{'='*60}")
print("TEST SUMMARY")
print(f"{'='*60}")
print(f"\nTotal Signals Generated: {len(all_signals)}")
print(f"\n{'Strategy':<20} {'Symbol':<10} {'Direction':<10} {'Risk':<10} {'Can Trade'}")
print("-" * 60)
for s in all_signals:
    print(f"{s['strategy']:<20} {s['symbol']:<10} {s['direction']:<10} ${s['risk']:.2f}      {'YES' if s['can_trade'] else 'NO'}")

# Check for invalid prices
print(f"\n{'='*60}")
print("PRICE VALIDATION")
print(f"{'='*60}")
invalid = []
for s in all_signals:
    # Check if SL is reasonable
    if s['symbol'] == 'XAUUSD':
        if s['direction'] == 'BUY' and s['sl'] >= s['entry']:
            invalid.append(f"{s['strategy']} {s['symbol']} {s['direction']}: SL ({s['sl']}) >= Entry ({s['entry']})")
        if s['direction'] == 'SELL' and s['sl'] <= s['entry']:
            invalid.append(f"{s['strategy']} {s['symbol']} {s['direction']}: SL ({s['sl']}) <= Entry ({s['entry']})")
    else:
        # For forex, check if prices are in reasonable range
        if s['symbol'] == 'EURUSD':
            if s['entry'] < 0.5 or s['entry'] > 3:
                invalid.append(f"{s['strategy']} {s['symbol']}: Entry {s['entry']} out of range")
        elif s['symbol'] == 'USDJPY':
            if s['entry'] < 50 or s['entry'] > 300:
                invalid.append(f"{s['strategy']} {s['symbol']}: Entry {s['entry']} out of range")

if invalid:
    print("\nInvalid signals found:")
    for i in invalid:
        print(f"  - {i}")
else:
    print("\nAll signals have valid prices!")

print(f"\n{'='*60}")
print("TEST COMPLETE")
print("=" * 60)

mt5.shutdown()
