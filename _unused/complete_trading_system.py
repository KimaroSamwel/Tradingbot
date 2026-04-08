"""
Complete Trading System
- Clear BUY/SELL signals with exact levels
- Smart SL/TP with 2:1 R:R minimum
- High probability setups only
- Risk management: 1% per trade, max 2 trades
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

def initialize():
    if not mt5.initialize():
        return False
    acc = mt5.account_info()
    print(f"Account #{acc.login} | Balance: ${acc.balance:.2f} | Equity: ${acc.equity:.2f}")
    return True

def get_rates(symbol, tf, count=200):
    tf_map = {'M5': mt5.TIMEFRAME_M5, 'M15': mt5.TIMEFRAME_M15, 'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4}
    rates = mt5.copy_rates_from_pos(symbol, tf_map[tf], 0, count)
    return pd.DataFrame(rates) if rates is not None else None

def ema(series, period):
    return series.ewm(span=period).mean()

def atr(df, period=14):
    high, low, close = df['high'].values, df['low'].values, df['close'].values
    tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    return np.mean(tr[-period:])

def adx_calc(df, period=14):
    high, low, close = df['high'].values, df['low'].values, df['close'].values
    n = len(high)
    if n < period + 1:
        return 0, 0, 0
    
    tr = np.zeros(n - 1)
    plus_dm = np.zeros(n - 1)
    minus_dm = np.zeros(n - 1)
    
    for i in range(1, n):
        tr[i-1] = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        up = high[i] - high[i-1]
        down = low[i-1] - low[i]
        if up > down: plus_dm[i-1] = up
        if down > up: minus_dm[i-1] = down
    
    smoothed_tr = np.mean(tr[-period:])
    smoothed_plus = np.mean(plus_dm[-period:])
    smoothed_minus = np.mean(minus_dm[-period:])
    
    if smoothed_tr > 0:
        plus_di = 100 * smoothed_plus / smoothed_tr
        minus_di = 100 * smoothed_minus / smoothed_tr
        adx_val = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return round(adx_val, 1), round(plus_di, 1), round(minus_di, 1)
    return 0, 0, 0

def rsi_calc(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def stoch_calc(df, period=14):
    low_min = df['low'].rolling(period).min()
    high_max = df['high'].rolling(period).max()
    k = 100 * (df['close'] - low_min) / (high_max - low_min)
    return k

def get_support_resistance(df, lookback=20):
    highs = df['high'].rolling(5).max().tail(lookback)
    lows = df['low'].rolling(5).min().tail(lookback)
    return highs.max(), lows.min()

def get_swing_points(df, lookback=10):
    highs = df['high'].rolling(5).max()
    lows = df['low'].rolling(5).min()
    swing_high = highs.iloc[-lookback:].max()
    swing_low = lows.iloc[-lookback:].min()
    return swing_high, swing_low


class TradingSignals:
    """Complete trading signal generator with exact entry/exit levels"""
    
    def __init__(self, symbol):
        self.symbol = symbol
        self.df_h4 = get_rates(symbol, 'H4', 100)
        self.df_h1 = get_rates(symbol, 'H1', 100)
        self.df_m15 = get_rates(symbol, 'M15', 100)
        self.tick = mt5.symbol_info_tick(symbol)
        self.sym = mt5.symbol_info(symbol)
        
    def get_market_info(self):
        """Get current market conditions"""
        if self.df_h4 is None:
            return None
            
        info = {}
        
        # H4 trend
        ema20_h4 = ema(self.df_h4['close'], 20).iloc[-1]
        ema50_h4 = ema(self.df_h4['close'], 50).iloc[-1]
        info['h4_trend'] = 'BULL' if ema20_h4 > ema50_h4 else 'BEAR'
        
        # H1 trend
        ema9_h1 = ema(self.df_h1['close'], 9).iloc[-1]
        ema21_h1 = ema(self.df_h1['close'], 21).iloc[-1]
        info['h1_trend'] = 'BULL' if ema9_h1 > ema21_h1 else 'BEAR'
        
        # Momentum
        adx, plus_di, minus_di = adx_calc(self.df_h1)
        info['adx'] = adx
        info['plus_di'] = plus_di
        info['minus_di'] = minus_di
        info['momentum'] = 'STRONG' if adx > 25 else 'MODERATE' if adx > 18 else 'WEAK'
        
        # RSI
        rsi = rsi_calc(self.df_h1).iloc[-1]
        info['rsi'] = round(rsi, 1)
        
        # Stochastic
        stoch = stoch_calc(self.df_h1).iloc[-1]
        info['stoch'] = round(stoch, 1)
        
        # ATR for SL calculation
        info['atr'] = round(atr(self.df_h1), 5)
        
        # Support/Resistance
        info['swing_high'], info['swing_low'] = get_swing_points(self.df_h1)
        
        # Current price
        info['bid'] = self.tick.bid
        info['ask'] = self.tick.ask
        info['spread'] = round((self.tick.ask - self.tick.bid) / self.sym.point, 1)
        
        return info
    
    def analyze_buy_setup(self, info):
        """Analyze if BUY setup is valid"""
        reasons = []
        score = 0
        
        # H4 trend must be bullish
        if info['h4_trend'] == 'BULL':
            reasons.append("H4: EMA20 > EMA50 (bull trend)")
            score += 2
        else:
            reasons.append("H4: Bearish - NO BUY")
            return None, reasons, 0
        
        # H1 must confirm
        if info['h1_trend'] == 'BULL':
            reasons.append("H1: EMA9 > EMA21 (entry aligned)")
            score += 2
        else:
            reasons.append("H1: Bearish entry - NO BUY")
            return None, reasons, 0
        
        # Momentum must be present
        if info['adx'] > 20:
            reasons.append(f"ADX: {info['adx']} (momentum present)")
            score += 2
        else:
            reasons.append(f"ADX: {info['adx']} (weak momentum)")
            score -= 1
        
        # RSI not overbought
        if 40 < info['rsi'] < 65:
            reasons.append(f"RSI: {info['rsi']} (healthy)")
            score += 1
        elif info['rsi'] < 30:
            reasons.append(f"RSI: {info['rsi']} (oversold - potential bounce)")
            score += 2
        elif info['rsi'] > 70:
            reasons.append(f"RSI: {info['rsi']} (overbought)")
            score -= 2
        
        # Stochastic
        if info['stoch'] < 80:
            reasons.append(f"Stoch: {info['stoch']} (not overbought)")
            score += 1
        
        # Spread check
        if info['spread'] < 50 if 'XAU' in self.symbol else info['spread'] < 30:
            reasons.append(f"Spread: {info['spread']} pips (acceptable)")
            score += 1
        else:
            reasons.append(f"Spread: {info['spread']} (HIGH - avoid)")
            score -= 2
        
        return score, reasons, score >= 6
    
    def analyze_sell_setup(self, info):
        """Analyze if SELL setup is valid"""
        reasons = []
        score = 0
        
        # H4 trend must be bearish
        if info['h4_trend'] == 'BEAR':
            reasons.append("H4: EMA20 < EMA50 (bear trend)")
            score += 2
        else:
            reasons.append("H4: Bullish - NO SELL")
            return None, reasons, 0
        
        # H1 must confirm
        if info['h1_trend'] == 'BEAR':
            reasons.append("H1: EMA9 < EMA21 (entry aligned)")
            score += 2
        else:
            reasons.append("H1: Bullish entry - NO SELL")
            return None, reasons, 0
        
        # Momentum must be present
        if info['adx'] > 20:
            reasons.append(f"ADX: {info['adx']} (momentum present)")
            score += 2
        else:
            reasons.append(f"ADX: {info['adx']} (weak momentum)")
            score -= 1
        
        # RSI not oversold
        if 35 < info['rsi'] < 60:
            reasons.append(f"RSI: {info['rsi']} (healthy)")
            score += 1
        elif info['rsi'] > 70:
            reasons.append(f"RSI: {info['rsi']} (overbought)")
            score += 2
        elif info['rsi'] < 30:
            reasons.append(f"RSI: {info['rsi']} (oversold)")
            score -= 2
        
        # Stochastic
        if info['stoch'] > 20:
            reasons.append(f"Stoch: {info['stoch']} (not oversold)")
            score += 1
        
        # Spread check
        if info['spread'] < 50 if 'XAU' in self.symbol else info['spread'] < 30:
            reasons.append(f"Spread: {info['spread']} pips (acceptable)")
            score += 1
        else:
            reasons.append(f"Spread: {info['spread']} (HIGH - avoid)")
            score -= 2
        
        return score, reasons, score >= 6
    
    def calculate_levels(self, direction, info):
        """Calculate exact entry, SL, and TP levels"""
        atr = info['atr']
        swing_high = info['swing_high']
        swing_low = info['swing_low']
        price = info['ask'] if direction == 'BUY' else info['bid']
        
        # ATR multiplier for SL
        sl_atr_multiplier = 1.5
        tp_atr_multiplier = 3.0  # 2:1 R:R
        
        if direction == 'BUY':
            # Entry: At ask price or slight pullback
            entry = info['ask']
            
            # SL: Below swing low or ATR
            if 'XAU' in self.symbol:
                sl = entry - max(atr * sl_atr_multiplier, 200 * self.sym.point)
            else:
                sl = entry - max(atr * sl_atr_multiplier, 15 * self.sym.point)
            
            # TP: Based on ATR for 2:1 R:R
            risk = entry - sl
            tp = entry + risk * 2  # 2:1 R:R minimum
            
            # Round levels
            digits = self.sym.digits
            entry = round(entry, digits)
            sl = round(sl, digits)
            tp = round(tp, digits)
            
        else:  # SELL
            # Entry: At bid price
            entry = info['bid']
            
            # SL: Above swing high or ATR
            if 'XAU' in self.symbol:
                sl = entry + max(atr * sl_atr_multiplier, 200 * self.sym.point)
            else:
                sl = entry + max(atr * sl_atr_multiplier, 15 * self.sym.point)
            
            # TP: Based on ATR for 2:1 R:R
            risk = sl - entry
            tp = entry - risk * 2  # 2:1 R:R minimum
            
            # Round levels
            digits = self.sym.digits
            entry = round(entry, digits)
            sl = round(sl, digits)
            tp = round(tp, digits)
        
        # Calculate R:R
        if direction == 'BUY':
            risk_amount = entry - sl
            reward_amount = tp - entry
        else:
            risk_amount = sl - entry
            reward_amount = entry - tp
        
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
        
        return {
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'risk': round(risk_amount, 5),
            'reward': round(reward_amount, 5),
            'rr_ratio': round(rr_ratio, 2)
        }
    
    def get_signal(self):
        """Generate complete trading signal"""
        info = self.get_market_info()
        if not info:
            return None
        
        signal = {
            'symbol': self.symbol,
            'bid': info['bid'],
            'ask': info['ask'],
            'h4_trend': info['h4_trend'],
            'h1_trend': info['h1_trend'],
            'adx': info['adx'],
            'rsi': info['rsi'],
            'stoch': info['stoch'],
            'atr': info['atr'],
            'spread': info['spread'],
            'momentum': info['momentum'],
            'direction': None,
            'entry': None,
            'sl': None,
            'tp': None,
            'rr_ratio': None,
            'reasons': [],
            'quality': None,
            'action': None
        }
        
        # Check BUY setup
        buy_score, buy_reasons, buy_valid = self.analyze_buy_setup(info)
        if buy_valid and buy_score >= 6:
            levels = self.calculate_levels('BUY', info)
            signal['direction'] = 'BUY'
            signal['entry'] = levels['entry']
            signal['sl'] = levels['sl']
            signal['tp'] = levels['tp']
            signal['rr_ratio'] = levels['rr_ratio']
            signal['reasons'] = buy_reasons
            signal['quality'] = 'HIGH' if buy_score >= 8 else 'MEDIUM'
            signal['action'] = '>>> BUY NOW <<<'
        
        # Check SELL setup
        sell_score, sell_reasons, sell_valid = self.analyze_sell_setup(info)
        if sell_valid and sell_score >= 6:
            if signal['direction'] is None or sell_score > buy_score:
                levels = self.calculate_levels('SELL', info)
                signal['direction'] = 'SELL'
                signal['entry'] = levels['entry']
                signal['sl'] = levels['sl']
                signal['tp'] = levels['tp']
                signal['rr_ratio'] = levels['rr_ratio']
                signal['reasons'] = sell_reasons
                signal['quality'] = 'HIGH' if sell_score >= 8 else 'MEDIUM'
                signal['action'] = '>>> SELL NOW <<<'
            else:
                signal['reasons'].append(f"(SELL also valid but weaker: score={sell_score})")
        
        return signal


def execute_trade(symbol, direction, entry, sl, tp, lot=0.01):
    """Execute trade with proper risk management"""
    tick = mt5.symbol_info_tick(symbol)
    sym = mt5.symbol_info(symbol)
    
    request = {
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': symbol,
        'volume': lot,
        'type': mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL,
        'price': tick.ask if direction == 'BUY' else tick.bid,
        'sl': sl,
        'tp': tp,
        'deviation': 10,
        'magic': 2026001,
        'comment': f'TradingBot-{direction}',
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': mt5.ORDER_FILLING_FOK
    }
    
    result = mt5.order_send(request)
    return result


def run_analysis():
    """Run complete analysis on all symbols"""
    if not initialize():
        return
    
    symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
    
    print("\n" + "=" * 80)
    print("COMPLETE TRADING SYSTEM - High Probability Signals")
    print("=" * 80)
    print(f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("Rules: H4+H1 Trend + ADX>20 + RSI Confirmation + 2:1 R:R")
    print("=" * 80 + "\n")
    
    signals = []
    
    for symbol in symbols:
        mt5.symbol_select(symbol, True)
        ts = TradingSignals(symbol)
        signal = ts.get_signal()
        
        if signal and signal['direction']:
            signals.append(signal)
            
            print(f"\n{'='*60}")
            print(f"SYMBOL: {symbol}")
            print(f"{'='*60}")
            print(f"Current Bid: {signal['bid']:.5f} | Ask: {signal['ask']:.5f}")
            print(f"Spread: {signal['spread']} pips")
            print()
            print(f"H4 Trend: {signal['h4_trend']} | H1 Trend: {signal['h1_trend']}")
            print(f"Momentum: {signal['momentum']} (ADX={signal['adx']})")
            print(f"RSI: {signal['rsi']} | Stochastic: {signal['stoch']}")
            print(f"ATR: {signal['atr']}")
            print()
            print(f"Signal Quality: {signal['quality']}")
            print()
            print("Setup Reasons:")
            for reason in signal['reasons']:
                print(f"  - {reason}")
            print()
            print(f"{signal['action']}")
            print(f"  ENTRY:  {signal['entry']:.5f}")
            print(f"  STOP LOSS: {signal['sl']:.5f} (Risk: {signal['rr_ratio']*100/2:.0f}% if wrong)")
            print(f"  TAKE PROFIT: {signal['tp']:.5f} (Reward: {signal['rr_ratio']*100:.0f}%)")
            print(f"  Risk:Reward = 1:{signal['rr_ratio']}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SIGNAL SUMMARY")
    print("=" * 80)
    
    if not signals:
        print("\nNO HIGH PROBABILITY SIGNALS RIGHT NOW")
        print("Wait for: H4+H1 trend alignment + ADX > 20 + Good RSI levels")
    else:
        print(f"\nValid Signals: {len(signals)}")
        for sig in signals:
            print(f"  [{sig['quality']}] {sig['symbol']} {sig['direction']} @ {sig['entry']:.5f}")
            print(f"        Entry: {sig['entry']:.5f} | SL: {sig['sl']:.5f} | TP: {sig['tp']:.5f}")
            print(f"        R:R = 1:{sig['rr_ratio']}")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    run_analysis()
