"""
Improved Trading System - Selective Strategies
Only trade with proven high-probability setups
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time

def initialize():
    if not mt5.initialize():
        return False
    acc = mt5.account_info()
    print(f"Connected: Account #{acc.login}, Balance: ${acc.balance:.2f}")
    return True

def get_rates(symbol, timeframe, count=100):
    tf_map = {'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4, 'M15': mt5.TIMEFRAME_M15}
    rates = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, count)
    return pd.DataFrame(rates) if rates is not None else None

def ema(df, period):
    return df['close'].ewm(span=period).mean().iloc[-1]

def rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0).mean()
    loss = (-delta.clip(upper=0)).mean()
    rs = gain / loss if loss > 0 else 50
    return 100 - (100 / (1 + rs))

def adx(df, period=14):
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

def macd(df, fast=12, slow=26, signal=9):
    ema_fast = df['close'].ewm(span=fast).mean()
    ema_slow = df['close'].ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    return macd_line.iloc[-1], signal_line.iloc[-1]

def stoch(df, period=14):
    low_min = df['low'].rolling(period).min()
    high_max = df['high'].rolling(period).max()
    k = 100 * (df['close'] - low_min) / (high_max - low_min)
    return k.iloc[-1]

def bollinger(df, period=20):
    mid = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    return mid.iloc[-1], (mid + 2 * std).iloc[-1], (mid - 2 * std).iloc[-1]

# ============== STRATEGY 1: EMA Trend Master (Improved) ==============
def strategy_ema_trend(symbol):
    """Uses EMA 20/50 on H4 with RSI confirmation - High win rate in trends"""
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    # H4 strong trend
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4
    h4_bear = e20_h4 < e50_h4
    
    # ADX confirmation
    adx_val = adx(df_h1)
    if adx_val < 18:  # Need momentum
        return None
    
    # H1 alignment
    e9_h1 = ema(df_h1, 9)
    e21_h1 = ema(df_h1, 21)
    
    # RSI confirmation
    rsi_val = rsi(df_h1)
    
    if h4_bull and e9_h1 > e21_h1 and 30 < rsi_val < 70:
        return 'BUY'
    elif h4_bear and e9_h1 < e21_h1 and 30 < rsi_val < 70:
        return 'SELL'
    return None

# ============== STRATEGY 2: MACD Momentum ==============
def strategy_macd_momentum(symbol):
    """Uses MACD crossover with trend confirmation - Catches momentum shifts"""
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    # H4 trend
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4
    h4_bear = e20_h4 < e50_h4
    
    # MACD on H1
    macd_h1, signal_h1 = macd(df_h1)
    macd_bull = macd_h1 > signal_h1
    macd_bear = macd_h1 < signal_h1
    
    # ADX
    adx_val = adx(df_h1)
    if adx_val < 20:
        return None
    
    if h4_bull and macd_bull and macd_h1 > 0:
        return 'BUY'
    elif h4_bear and macd_bear and macd_h1 < 0:
        return 'SELL'
    return None

# ============== STRATEGY 3: RSI Divergence ==============
def strategy_rsi_divergence(symbol):
    """Identifies RSI divergences at key levels - High accuracy"""
    df_h4 = get_rates(symbol, 'H4', 50)
    df_h1 = get_rates(symbol, 'H1', 50)
    if df_h4 is None or df_h1 is None:
        return None
    
    # Need at least 10 candles for divergence
    if len(df_h1) < 10:
        return None
    
    # H4 trend
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4
    h4_bear = e20_h4 < e50_h4
    
    # RSI values
    rsi_curr = rsi(df_h1)
    rsi_prev = rsi(df_h1.iloc[:-1]) if len(df_h1) > 1 else 50
    
    # Price comparison
    price_curr = df_h1['close'].iloc[-1]
    price_prev = df_h1['close'].iloc[-2]
    
    # Simple divergence check
    # Bullish: price lower low, RSI higher low
    # Bearish: price higher high, RSI lower high
    
    if h4_bull and price_curr > price_prev and rsi_curr > rsi_prev and rsi_curr < 50:
        return 'BUY'
    elif h4_bear and price_curr < price_prev and rsi_curr < rsi_prev and rsi_curr > 50:
        return 'SELL'
    return None

# ============== STRATEGY 4: Stochastic Confluence ==============
def strategy_stoch_confluence(symbol):
    """Uses Stochastic with trend confirmation - Good for reversals"""
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    # H4 trend
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4
    h4_bear = e20_h4 < e50_h4
    
    # Stochastic on H1
    stoch_val = stoch(df_h1)
    
    # ADX
    adx_val = adx(df_h1)
    if adx_val < 18:
        return None
    
    # RSI
    rsi_val = rsi(df_h1)
    
    # Bull: Stochastic oversold + RSI confirms + trend up
    if h4_bull and stoch_val < 25 and rsi_val < 45:
        return 'BUY'
    # Bear: Stochastic overbought + RSI confirms + trend down
    elif h4_bear and stoch_val > 75 and rsi_val > 55:
        return 'SELL'
    return None

# ============== STRATEGY 5: Session Strength (NEW) ==============
def strategy_session_strength(symbol):
    """Trades with the major session momentum"""
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    # Strong H4 trend required
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4 and (e20_h4 - e50_h4) / e50_h4 > 0.001  # 0.1% separation
    h4_bear = e20_h4 < e50_h4 and (e50_h4 - e20_h4) / e50_h4 > 0.001
    
    # ADX must be strong
    adx_val = adx(df_h1)
    if adx_val < 25:
        return None
    
    # H1 EMA alignment
    e9_h1 = ema(df_h1, 9)
    e21_h1 = ema(df_h1, 21)
    
    # RSI in sweet spot
    rsi_val = rsi(df_h1)
    
    if h4_bull and e9_h1 > e21_h1 and 45 < rsi_val < 60:
        return 'BUY'
    elif h4_bear and e9_h1 < e21_h1 and 40 < rsi_val < 55:
        return 'SELL'
    return None


class ImprovedTradingSystem:
    def __init__(self):
        self.strategies = {
            'EMA_Trend': strategy_ema_trend,
            'MACD_Momentum': strategy_macd_momentum,
            'RSI_Divergence': strategy_rsi_divergence,
            'Stoch_Confluence': strategy_stoch_confluence,
            'Session_Strength': strategy_session_strength
        }
        self.min_agreement = 2  # Need 2+ strategies to agree
        self.max_positions = 3  # Max 3 open trades
        
    def analyze(self, symbol):
        results = {}
        votes = {'BUY': 0, 'SELL': 0}
        
        for name, func in self.strategies.items():
            try:
                signal = func(symbol)
                results[name] = signal
                if signal in votes:
                    votes[signal] += 1
            except Exception as e:
                results[name] = f'Err'
        
        return results, votes
    
    def should_trade(self, symbol):
        results, votes = self.analyze(symbol)
        max_vote = max(votes['BUY'], votes['SELL'])
        
        if max_vote < self.min_agreement:
            return None, results, votes, f"Weak agreement ({max_vote}/{self.min_agreement})"
        
        if votes['BUY'] > votes['SELL']:
            return 'BUY', results, votes, f"Strong BUY ({votes['BUY']}/5)"
        elif votes['SELL'] > votes['BUY']:
            return 'SELL', results, votes, f"Strong SELL ({votes['SELL']}/5)"
        return None, results, votes, "No clear direction"
    
    def calculate_trade(self, symbol, direction):
        tick = mt5.symbol_info_tick(symbol)
        sym = mt5.symbol_info(symbol)
        if not tick or not sym:
            return None, None, None
        
        acc = mt5.account_info()
        risk_amount = acc.balance * 0.01  # 1% risk
        
        if 'XAU' in symbol:
            sl_pips = risk_amount / 1  # $1 per pip
        elif 'JPY' in symbol:
            sl_pips = risk_amount / 0.1  # JPY
        else:
            sl_pips = risk_amount / 0.1  # Forex
        
        if direction == 'BUY':
            entry = tick.ask
            if 'XAU' in symbol:
                sl = entry - sl_pips
                tp = entry + sl_pips * 2
            elif 'JPY' in symbol:
                sl = entry - sl_pips * 0.01
                tp = entry + sl_pips * 0.01 * 2
            else:
                sl = entry - sl_pips * 0.0001
                tp = entry + sl_pips * 0.0001 * 2
        else:
            entry = tick.bid
            if 'XAU' in symbol:
                sl = entry + sl_pips
                tp = entry - sl_pips * 2
            elif 'JPY' in symbol:
                sl = entry + sl_pips * 0.01
                tp = entry - sl_pips * 0.01 * 2
            else:
                sl = entry + sl_pips * 0.0001
                tp = entry - sl_pips * 0.0001 * 2
        
        return entry, sl, tp
    
    def execute(self, symbol, direction, lot=0.01):
        entry, sl, tp = self.calculate_trade(symbol, direction)
        if entry is None:
            return False, "No prices"
        
        tick = mt5.symbol_info_tick(symbol)
        sym = mt5.symbol_info(symbol)
        
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': lot,
            'type': mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL,
            'price': tick.ask if direction == 'BUY' else tick.bid,
            'sl': round(sl, sym.digits),
            'tp': round(tp, sym.digits),
            'deviation': 10,
            'magic': 2026001,
            'comment': 'Improved Bot',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_FOK
        }
        
        result = mt5.order_send(request)
        if result and result.retcode == 10009:
            return True, f"#{result.deal} {symbol} {direction}"
        return False, f"Failed: {result.comment if result else 'No response'}"


def run_improved_scan():
    if not initialize():
        return
    
    symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
    bot = ImprovedTradingSystem()
    
    # Check current positions
    pos = mt5.positions_get()
    if pos:
        print(f"\nCurrent positions: {len(pos)}")
        for p in pos:
            print(f"  {p.symbol} {p.type}")
        print()
    
    print("=" * 60)
    print("IMPROVED TRADING SYSTEM - Conservative Approach")
    print("=" * 60)
    print(f"Strategies: {list(bot.strategies.keys())}")
    print(f"Min agreement: {bot.min_agreement}/5")
    print(f"Max positions: {bot.max_positions}")
    print()
    
    trades_opened = 0
    
    for symbol in symbols:
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            continue
        
        direction, results, votes, decision = bot.should_trade(symbol)
        
        print(f"\n{symbol} ({tick.bid:.5f})")
        print(f"  Decision: {decision}")
        print(f"  Votes: BUY={votes['BUY']}, SELL={votes['SELL']}")
        for name, sig in results.items():
            print(f"    {name}: {sig if sig else '-'}")
        
        if direction and trades_opened < bot.max_positions:
            entry, sl, tp = bot.calculate_trade(symbol, direction)
            if entry:
                print(f"  >>> TRADE: {direction} | Entry: {entry:.5f} | SL: {sl:.5f} | TP: {tp:.5f}")
                success, msg = bot.execute(symbol, direction)
                print(f"      Result: {msg}")
                if success:
                    trades_opened += 1
    
    print(f"\n{'='*60}")
    print(f"Trades opened: {trades_opened}")
    print("=" * 60)


if __name__ == '__main__':
    run_improved_scan()
