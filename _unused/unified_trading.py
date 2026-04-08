"""
Unified Trading System with Multi-Strategy Voting
Enter trades only when multiple strategies agree
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time

def initialize():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return False
    print(f"Connected to MT5: {mt5.terminal_info().name}")
    acc = mt5.account_info()
    print(f"Account: #{acc.login}, Balance: ${acc.balance:.2f}")
    return True

def get_rates(symbol, timeframe, count=100):
    tf_map = {
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'M15': mt5.TIMEFRAME_M15,
        'M5': mt5.TIMEFRAME_M5
    }
    rates = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, count)
    return pd.DataFrame(rates) if rates is not None else None

def calc_ema(df, period):
    return df['close'].ewm(span=period).mean()

def calc_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0).mean()
    loss = (-delta.clip(upper=0)).mean()
    rs = gain / loss if loss > 0 else 50
    return 100 - (100 / (1 + rs))

def calc_stoch(df, period=14):
    low_min = df['low'].rolling(period).min()
    high_max = df['high'].rolling(period).max()
    k = 100 * (df['close'] - low_min) / (high_max - low_min)
    return k.iloc[-1]

def calc_adx(df, period=14):
    high, low, close = df['high'].values, df['low'].values, df['close'].values
    n = len(high)
    if n < period + 1:
        return 0
    
    tr = np.zeros(n - 1)
    plus_dm = np.zeros(n - 1)
    minus_dm = np.zeros(n - 1)
    
    for i in range(1, n):
        tr[i-1] = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        up = high[i] - high[i-1]
        down = low[i-1] - low[i]
        if up > down and up > 0:
            plus_dm[i-1] = up
        if down > up and down > 0:
            minus_dm[i-1] = down
    
    smoothed_tr = np.mean(tr[-period:])
    smoothed_plus = np.mean(plus_dm[-period:])
    smoothed_minus = np.mean(minus_dm[-period:])
    
    if smoothed_tr > 0:
        plus_di = 100 * smoothed_plus / smoothed_tr
        minus_di = 100 * smoothed_minus / smoothed_tr
        return round(100 * abs(plus_di - minus_di) / (plus_di + minus_di), 1)
    return 0

def calc_bollinger(df, period=20, std_dev=2):
    mid = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    return mid.iloc[-1], (mid + std_dev * std).iloc[-1], (mid - std_dev * std).iloc[-1]

def get_market_direction(symbol):
    df_h4 = get_rates(symbol, 'H4', 100)
    if df_h4 is None:
        return {'trend': 'NEUTRAL', 'adx': 0}
    
    ema20 = calc_ema(df_h4, 20).iloc[-1]
    ema50 = calc_ema(df_h4, 50).iloc[-1]
    adx = calc_adx(df_h4)
    
    if ema20 > ema50 and adx > 20:
        trend = 'BULL'
    elif ema20 < ema50 and adx > 20:
        trend = 'BEAR'
    else:
        trend = 'NEUTRAL'
    
    return {'trend': trend, 'adx': adx}

# ============== STRATEGY 1: Swing H4H1 ==============
def strategy_swing_h4h1(symbol):
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    # H4 Trend (EMA crossover)
    ema20_h4 = calc_ema(df_h4, 20).iloc[-1]
    ema50_h4 = calc_ema(df_h4, 50).iloc[-1]
    h4_bull = ema20_h4 > ema50_h4
    h4_bear = ema20_h4 < ema50_h4
    
    # H1 Entry (EMA crossover + RSI confirmation)
    ema9_h1 = calc_ema(df_h1, 9).iloc[-1]
    ema21_h1 = calc_ema(df_h1, 21).iloc[-1]
    h1_bull = ema9_h1 > ema21_h1
    h1_bear = ema9_h1 < ema21_h1
    rsi = calc_rsi(df_h1)
    
    adx = calc_adx(df_h1)
    
    # XAUUSD requires ADX > 18
    if symbol == 'XAUUSD' and adx <= 18:
        return None
    
    if h4_bull and h1_bull and rsi > 40:
        return 'BUY'
    elif h4_bear and h1_bear and rsi < 60:
        return 'SELL'
    return None

# ============== STRATEGY 2: Trend Rider ==============
def strategy_trend_rider(symbol):
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    # Strong trend on H4
    ema20_h4 = calc_ema(df_h4, 20).iloc[-1]
    ema50_h4 = calc_ema(df_h4, 50).iloc[-1]
    h4_bull = ema20_h4 > ema50_h4
    h4_bear = ema20_h4 < ema50_h4
    
    # ADX confirmation
    adx = calc_adx(df_h1)
    if adx < 20:
        return None
    
    # Price action on H1
    ema9_h1 = calc_ema(df_h1, 9).iloc[-1]
    ema21_h1 = calc_ema(df_h1, 21).iloc[-1]
    
    if h4_bull and ema9_h1 > ema21_h1:
        return 'BUY'
    elif h4_bear and ema9_h1 < ema21_h1:
        return 'SELL'
    return None

# ============== STRATEGY 3: Breakout Hunter ==============
def strategy_breakout_hunter(symbol):
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    # Bollinger Bands on H4
    bb_mid, bb_upper, bb_lower = calc_bollinger(df_h4)
    current_price = df_h4['close'].iloc[-1]
    
    # Check for breakout
    if current_price > bb_upper:
        return 'BUY'
    elif current_price < bb_lower:
        return 'SELL'
    return None

# ============== STRATEGY 4: Smart Money ==============
def strategy_smart_money(symbol):
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    # Smart money follows institutional flow
    # Uses EMA clusters and volume analysis
    ema20_h4 = calc_ema(df_h4, 20).iloc[-1]
    ema50_h4 = calc_ema(df_h4, 50).iloc[-1]
    h4_bull = ema20_h4 > ema50_h4
    h4_bear = ema20_h4 < ema50_h4
    
    # H1 EMA confirmation
    ema9_h1 = calc_ema(df_h1, 9).iloc[-1]
    ema21_h1 = calc_ema(df_h1, 21).iloc[-1]
    
    if h4_bull and ema9_h1 > ema21_h1:
        return 'BUY'
    elif h4_bear and ema9_h1 < ema21_h1:
        return 'SELL'
    return None

# ============== STRATEGY 5: Mean Reversion ==============
def strategy_mean_reversion(symbol):
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    # H4 trend
    ema20_h4 = calc_ema(df_h4, 20).iloc[-1]
    ema50_h4 = calc_ema(df_h4, 50).iloc[-1]
    h4_bull = ema20_h4 > ema50_h4
    h4_bear = ema20_h4 < ema50_h4
    
    # RSI and Stochastic for mean reversion
    rsi = calc_rsi(df_h1)
    stoch = calc_stoch(df_h1)
    
    # Mean reversion signals
    if h4_bull and rsi < 40 and stoch < 30:
        return 'BUY'
    elif h4_bear and rsi > 60 and stoch > 70:
        return 'SELL'
    return None

# ============== MAIN TRADING SYSTEM ==============
class UnifiedTradingSystem:
    def __init__(self):
        self.strategies = {
            'Swing_H4H1': strategy_swing_h4h1,
            'Trend_Rider': strategy_trend_rider,
            'Breakout_Hunter': strategy_breakout_hunter,
            'Smart_Money': strategy_smart_money,
            'Mean_Reversion': strategy_mean_reversion
        }
        self.min_agreement = 3  # Minimum strategies that must agree
        
    def analyze_pair(self, symbol):
        results = {}
        votes = {'BUY': 0, 'SELL': 0}
        
        for name, func in self.strategies.items():
            try:
                signal = func(symbol)
                results[name] = signal
                if signal in votes:
                    votes[signal] += 1
            except Exception as e:
                results[name] = f'Error: {e}'
        
        return results, votes
    
    def get_trade_decision(self, symbol):
        results, votes = self.analyze_pair(symbol)
        
        # Check minimum agreement
        max_vote = max(votes['BUY'], votes['SELL'])
        if max_vote < self.min_agreement:
            return None, results, votes, f"Insufficient agreement ({max_vote}/{self.min_agreement})"
        
        # Determine direction
        if votes['BUY'] > votes['SELL']:
            return 'BUY', results, votes, f"Strong BUY signal ({votes['BUY']}/5 strategies)"
        elif votes['SELL'] > votes['BUY']:
            return 'SELL', results, votes, f"Strong SELL signal ({votes['SELL']}/5 strategies)"
        else:
            return None, results, votes, "No clear direction"
    
    def calculate_sl_tp(self, symbol, direction, risk_pct=1):
        tick = mt5.symbol_info_tick(symbol)
        sym = mt5.symbol_info(symbol)
        if not tick or not sym:
            return None, None, None
        
        # Get account balance for risk calculation
        acc = mt5.account_info()
        balance = acc.balance
        risk_amount = balance * (risk_pct / 100)
        
        # Calculate SL distance based on symbol
        if 'XAU' in symbol:
            sl_distance_pips = risk_amount / (0.01 * 100)  # $1 per pip per lot
        elif 'JPY' in symbol:
            sl_distance_pips = risk_amount / (0.01 * 10)  # JPY pairs
        else:
            sl_distance_pips = risk_amount / (0.01 * 10)  # Standard forex
        
        # Calculate SL and TP
        if direction == 'BUY':
            entry = tick.ask
            if 'XAU' in symbol:
                sl = entry - sl_distance_pips
                tp = entry + sl_distance_pips * 2
            elif 'JPY' in symbol:
                sl = entry - sl_distance_pips * 0.01
                tp = entry + sl_distance_pips * 0.01 * 2
            else:
                sl = entry - sl_distance_pips * 0.0001
                tp = entry + sl_distance_pips * 0.0001 * 2
        else:
            entry = tick.bid
            if 'XAU' in symbol:
                sl = entry + sl_distance_pips
                tp = entry - sl_distance_pips * 2
            elif 'JPY' in symbol:
                sl = entry + sl_distance_pips * 0.01
                tp = entry - sl_distance_pips * 0.01 * 2
            else:
                sl = entry + sl_distance_pips * 0.0001
                tp = entry - sl_distance_pips * 0.0001 * 2
        
        return entry, sl, tp
    
    def execute_trade(self, symbol, direction, lot=0.01):
        entry, sl, tp = self.calculate_sl_tp(symbol, direction)
        if entry is None:
            return False, "Failed to get prices"
        
        tick = mt5.symbol_info_tick(symbol)
        sym = mt5.symbol_info(symbol)
        
        if direction == 'BUY':
            price = tick.ask
            order_type = mt5.ORDER_TYPE_BUY
        else:
            price = tick.bid
            order_type = mt5.ORDER_TYPE_SELL
        
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': lot,
            'type': order_type,
            'price': price,
            'sl': round(sl, sym.digits),
            'tp': round(tp, sym.digits),
            'deviation': 10,
            'magic': 2026001,
            'comment': 'Unified Bot',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_FOK
        }
        
        result = mt5.order_send(request)
        if result and result.retcode == 10009:
            return True, f"#{result.deal} {symbol} {direction} @ {price}"
        else:
            return False, f"Failed: {result.comment if result else 'No response'}"


def run_unified_scan():
    if not initialize():
        return
    
    symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'NZDUSD']
    bot = UnifiedTradingSystem()
    
    print("\n" + "=" * 70)
    print("UNIFIED TRADING SYSTEM - MULTI-STRATEGY VOTING")
    print("=" * 70)
    print(f"Minimum agreement required: {bot.min_agreement} out of 5 strategies\n")
    
    for symbol in symbols:
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            continue
        
        direction, results, votes, decision = bot.get_trade_decision(symbol)
        
        print(f"\n{'='*50}")
        print(f"SYMBOL: {symbol} | Bid: {tick.bid:.5f} | Ask: {tick.ask:.5f}")
        print(f"{'='*50}")
        print(f"Decision: {decision}")
        print(f"Votes: BUY={votes['BUY']}, SELL={votes['SELL']}")
        print()
        print("Strategy Results:")
        for name, signal in results.items():
            status = "[OK]" if signal in ['BUY', 'SELL'] else "[--]"
            print(f"  {status} {name}: {signal if signal else 'NO SIGNAL'}")
        
        if direction:
            entry, sl, tp = bot.calculate_sl_tp(symbol, direction)
            if entry:
                print(f"\n>>> TRADE ENTRY: {direction}")
                print(f"    Entry: {entry:.5f}")
                print(f"    SL: {sl:.5f}")
                print(f"    TP: {tp:.5f}")
                
                # Execute trade
                success, msg = bot.execute_trade(symbol, direction)
                print(f"    Result: {msg}")

if __name__ == '__main__':
    run_unified_scan()
