"""
Advanced Trading System with Liquidity Algorithm
Combines trend-following with institutional liquidity detection
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

def get_rates(symbol, timeframe, count=200):
    tf_map = {'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4, 'M15': mt5.TIMEFRAME_M15, 'M5': mt5.TIMEFRAME_M5}
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

# ============== STRATEGY 1: EMA Trend Master ==============
def strategy_ema_trend(symbol):
    """H4 EMA 20/50 + H1 EMA 9/21 + RSI confirmation"""
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4
    h4_bear = e20_h4 < e50_h4
    
    adx_val = adx(df_h1)
    if adx_val < 18:
        return None
    
    e9_h1 = ema(df_h1, 9)
    e21_h1 = ema(df_h1, 21)
    rsi_val = rsi(df_h1)
    
    if h4_bull and e9_h1 > e21_h1 and 30 < rsi_val < 70:
        return 'BUY'
    elif h4_bear and e9_h1 < e21_h1 and 30 < rsi_val < 70:
        return 'SELL'
    return None

# ============== STRATEGY 2: MACD Momentum ==============
def strategy_macd_momentum(symbol):
    """MACD crossover with trend confirmation"""
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4
    h4_bear = e20_h4 < e50_h4
    
    macd_h1, signal_h1 = macd(df_h1)
    macd_bull = macd_h1 > signal_h1
    macd_bear = macd_h1 < signal_h1
    
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
    """RSI divergence at key levels"""
    df_h4 = get_rates(symbol, 'H4', 50)
    df_h1 = get_rates(symbol, 'H1', 50)
    if df_h4 is None or df_h1 is None or len(df_h1) < 10:
        return None
    
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4
    h4_bear = e20_h4 < e50_h4
    
    rsi_curr = rsi(df_h1)
    price_curr = df_h1['close'].iloc[-1]
    price_prev = df_h1['close'].iloc[-2]
    
    if h4_bull and price_curr > price_prev and rsi_curr < 50:
        return 'BUY'
    elif h4_bear and price_curr < price_prev and rsi_curr > 50:
        return 'SELL'
    return None

# ============== STRATEGY 4: Stochastic Confluence ==============
def strategy_stoch_confluence(symbol):
    """Stochastic with trend confirmation"""
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4
    h4_bear = e20_h4 < e50_h4
    
    stoch_val = stoch(df_h1)
    adx_val = adx(df_h1)
    rsi_val = rsi(df_h1)
    
    if adx_val < 18:
        return None
    
    if h4_bull and stoch_val < 25 and rsi_val < 45:
        return 'BUY'
    elif h4_bear and stoch_val > 75 and rsi_val > 55:
        return 'SELL'
    return None

# ============== STRATEGY 5: LIQUIDITY ALGORITHM (NEW) ==============
def strategy_liquidity_algo(symbol):
    """
    Institutional Liquidity Detection Algorithm
    
    Detects:
    1. Sweep of recent highs/lows (liquidity pools)
    2. Order blocks (institutional order zones)
    3. Fair Value Gaps (imbalance zones)
    4. Trade in direction of market structure after liquidity grab
    """
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    df_m15 = get_rates(symbol, 'M15', 50)
    
    if df_h4 is None or df_h1 is None or df_m15 is None:
        return None
    
    # H4 market structure
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4
    h4_bear = e20_h4 < e50_h4
    
    if not h4_bull and not h4_bear:
        return None
    
    # Get recent highs/lows for liquidity zones
    recent_highs = df_h1['high'].tail(20).max()
    recent_lows = df_h1['low'].tail(20).min()
    current_price = df_h1['close'].iloc[-1]
    
    # ADX for momentum
    adx_val = adx(df_h1)
    if adx_val < 20:
        return None
    
    # Find swing high/low in last 10 candles
    swing_high = df_h1['high'].rolling(5).max().iloc[-1]
    swing_low = df_h1['low'].rolling(5).min().iloc[-1]
    
    # Check for liquidity grab conditions
    # Liquidity above (sweep of buy stops)
    liquidity_sweep_up = False
    liquidity_sweep_down = False
    
    # Price within 0.1% of recent high = potential liquidity grab
    if h4_bear and current_price >= recent_highs * 0.999:
        liquidity_sweep_up = True
    
    # Price within 0.1% of recent low = potential liquidity grab  
    if h4_bull and current_price <= recent_lows * 1.001:
        liquidity_sweep_down = True
    
    # Detect Order Blocks (last bearish/bullish candle before strong move)
    order_block_bull = None
    order_block_bear = None
    
    for i in range(5, 15):
        if len(df_h1) > i:
            # Bullish order block: bearish candle followed by bullish move
            if df_h1['close'].iloc[-i] < df_h1['open'].iloc[-i]:  # Bearish candle
                if df_h1['close'].iloc[-(i-1)] > df_h1['open'].iloc[-(i-1)]:
                    order_block_bull = df_h1['low'].iloc[-i]
            
            # Bearish order block: bullish candle followed by bearish move
            if df_h1['close'].iloc[-i] > df_h1['open'].iloc[-i]:  # Bullish candle
                if df_h1['close'].iloc[-(i-1)] < df_h1['open'].iloc[-(i-1)]:
                    order_block_bear = df_h1['high'].iloc[-i]
    
    # Fair Value Gap detection
    fvg_up = None
    fvg_down = None
    
    for i in range(2, 8):
        if len(df_h1) > i:
            # Bullish FVG: gap between current high and previous low
            gap = df_h1['low'].iloc[-1] - df_h1['high'].iloc[-i]
            if gap > 0:
                fvg_up = df_h1['high'].iloc[-i] + gap/2
            
            # Bearish FVG: gap between current low and previous high
            gap = df_h1['high'].iloc[-1] - df_h1['low'].iloc[-i]
            if gap > 0:
                fvg_down = df_h1['low'].iloc[-i] - gap/2
    
    # Trading signals based on liquidity detection
    rsi_val = rsi(df_h1)
    e9_h1 = ema(df_h1, 9)
    e21_h1 = ema(df_h1, 21)
    
    # BULLISH: Price swept below low, now recovering
    if h4_bull and liquidity_sweep_down:
        # Price grabbed liquidity below, now bullish
        if rsi_val < 50 and e9_h1 > e21_h1:
            return 'BUY'
    
    # BEARISH: Price swept above high, now falling
    if h4_bear and liquidity_sweep_up:
        # Price grabbed liquidity above, now bearish
        if rsi_val > 50 and e9_h1 < e21_h1:
            return 'SELL'
    
    # Order block trade entry
    if h4_bull and order_block_bull and current_price >= order_block_bull:
        if rsi_val < 55 and e9_h1 > e21_h1:
            return 'BUY'
    
    if h4_bear and order_block_bear and current_price <= order_block_bear:
        if rsi_val > 45 and e9_h1 < e21_h1:
            return 'SELL'
    
    # Fair Value Gap fill
    if h4_bull and fvg_up and current_price <= fvg_up:
        if rsi_val < 50 and adx_val > 25:
            return 'BUY'
    
    if h4_bear and fvg_down and current_price >= fvg_down:
        if rsi_val > 50 and adx_val > 25:
            return 'SELL'
    
    return None

# ============== STRATEGY 6: Session Strength ==============
def strategy_session_strength(symbol):
    """Strong H4 trend with ADX confirmation"""
    df_h4 = get_rates(symbol, 'H4', 100)
    df_h1 = get_rates(symbol, 'H1', 100)
    if df_h4 is None or df_h1 is None:
        return None
    
    e20_h4 = ema(df_h4, 20)
    e50_h4 = ema(df_h4, 50)
    h4_bull = e20_h4 > e50_h4 and (e20_h4 - e50_h4) / e50_h4 > 0.001
    h4_bear = e20_h4 < e50_h4 and (e50_h4 - e20_h4) / e50_h4 > 0.001
    
    adx_val = adx(df_h1)
    if adx_val < 22:
        return None
    
    e9_h1 = ema(df_h1, 9)
    e21_h1 = ema(df_h1, 21)
    rsi_val = rsi(df_h1)
    
    if h4_bull and e9_h1 > e21_h1 and 45 < rsi_val < 60:
        return 'BUY'
    elif h4_bear and e9_h1 < e21_h1 and 40 < rsi_val < 55:
        return 'SELL'
    return None


class AdvancedTradingSystem:
    def __init__(self):
        self.strategies = {
            'EMA_Trend': strategy_ema_trend,
            'MACD_Momentum': strategy_macd_momentum,
            'RSI_Divergence': strategy_rsi_divergence,
            'Stoch_Confluence': strategy_stoch_confluence,
            'Liquidity_Algo': strategy_liquidity_algo,
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
                results[name] = '-'
        
        return results, votes
    
    def should_trade(self, symbol):
        results, votes = self.analyze(symbol)
        max_vote = max(votes['BUY'], votes['SELL'])
        
        if max_vote < self.min_agreement:
            return None, results, votes, f"Weak ({max_vote}/{self.min_agreement})"
        
        if votes['BUY'] > votes['SELL']:
            return 'BUY', results, votes, f"BUY ({votes['BUY']}/6)"
        elif votes['SELL'] > votes['BUY']:
            return 'SELL', results, votes, f"SELL ({votes['SELL']}/6)"
        return None, results, votes, "Neutral"
    
    def calculate_trade(self, symbol, direction):
        tick = mt5.symbol_info_tick(symbol)
        sym = mt5.symbol_info(symbol)
        if not tick or not sym:
            return None, None, None
        
        acc = mt5.account_info()
        risk_amount = acc.balance * 0.01
        
        # Minimum SL in pips based on symbol type
        if 'XAU' in symbol:
            min_sl_pips = 300  # $3 SL minimum for XAUUSD
            sl_pips = max(risk_amount, min_sl_pips)
        elif 'JPY' in symbol:
            min_sl_pips = 300  # 3 pips minimum for JPY pairs
            sl_pips = max(risk_amount / 0.01, min_sl_pips)
        else:
            min_sl_pips = 300  # 3 pips minimum for forex
            sl_pips = max(risk_amount / 0.01, min_sl_pips)
        
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
            'comment': 'Advanced Bot',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_FOK
        }
        
        result = mt5.order_send(request)
        if result and result.retcode == 10009:
            return True, f"#{result.deal} {symbol} {direction}"
        return False, f"Failed: {result.comment if result else 'No response'}"


def run_advanced_scan():
    if not initialize():
        return
    
    symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
    bot = AdvancedTradingSystem()
    
    print("\n" + "=" * 70)
    print("ADVANCED TRADING SYSTEM - 6 Strategies with Liquidity Algorithm")
    print("=" * 70)
    print(f"Strategies: {list(bot.strategies.keys())}")
    print(f"Min agreement: {bot.min_agreement}/6 | Max positions: {bot.max_positions}")
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
            status = "[OK]" if sig in ['BUY', 'SELL'] else "[--]"
            print(f"    {status} {name}: {sig if sig else '-'}")
        
        if direction and trades_opened < bot.max_positions:
            entry, sl, tp = bot.calculate_trade(symbol, direction)
            if entry:
                print(f"  >>> TRADE: {direction} | Entry: {entry:.5f} | SL: {sl:.5f} | TP: {tp:.5f}")
                success, msg = bot.execute(symbol, direction)
                print(f"      Result: {msg}")
                if success:
                    trades_opened += 1
    
    print(f"\n{'='*70}")
    print(f"Trades opened: {trades_opened}")
    print("=" * 70)


if __name__ == '__main__':
    run_advanced_scan()
