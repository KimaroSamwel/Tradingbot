"""
TRADING BOT v22 - HUMAN-IN-THE-LOOP SYSTEM
===========================================
Human makes execution decisions - bot only scans signals.
- Strategy 1: Swing_H4H1 (H4 EMA20/50 + H1 EMA9/21) - PRIMARY
- Strategy 2: Trend_Rider (ADX + EMA trend) - SECONDARY
- R:R >= 2.0, 1% risk per trade, max 2 positions
- Strict drawdown limits + Circuit breaker
- Trade journal for all trades
"""

import os
from flask import Flask, jsonify, request, render_template_string
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import threading
import time

app = Flask(__name__)

STRATEGIES = {
    'Swing_H4H1': {
        'name': 'Swing (Primary)',
        'description': 'H4 EMA20/50 + H1 EMA9/21 + RSI + ADX',
        'timeframes': ['H4', 'H1'],
        'indicators': ['EMA', 'RSI', 'ADX'],
        'best_for': 'XAUUSD, EURUSD, GBPUSD',
        'priority': 1
    },
    'Trend_Rider': {
        'name': 'Trend Rider (Secondary)',
        'description': 'ADX > 20 + EMA trend confirmation',
        'timeframes': ['H4', 'H1'],
        'indicators': ['EMA', 'ADX'],
        'best_for': 'Trending markets',
        'priority': 2
    }
}


class TradingBot:
    def __init__(self):
        self.broker_tz = timezone(timedelta(hours=3))
        self.running = False
        self.thread = None
        self.scan_results = []
        self.last_scan_time = None
        self.signal_created_at = None
        self.trading_pairs = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
        self.max_risk = 1.0
        self.max_positions = 2
        self.good_sessions = ['LONDON', 'NEW_YORK', 'OVERLAP']
        self.active_strategies = ['Swing_H4H1', 'Trend_Rider']
        self._market_dir_cache = {}
        self._market_dir_cache_time = 0
        self._cache_ttl = 10
        self.peak_equity = 0
        
        # STRICT RISK MANAGEMENT (v22)
        self.daily_loss_limit = 2.0  # 2% max daily loss
        self.max_consecutive_losses = 3  # Circuit breaker trigger
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None
        self.consecutive_losses = 0
        self.daily_start_balance = 0
        self.daily_trades = []
        self.trade_journal = []  # Complete trade history
        
    def _save_journal_entry(self, trade_data):
        """Save trade to journal"""
        entry = {
            'timestamp': datetime.now(self.broker_tz).isoformat(),
            'symbol': trade_data.get('symbol'),
            'direction': trade_data.get('direction'),
            'entry_price': trade_data.get('entry'),
            'exit_price': trade_data.get('exit_price'),
            'lot_size': trade_data.get('lot'),
            'profit': trade_data.get('profit', 0),
            'sl': trade_data.get('sl'),
            'tp': trade_data.get('tp'),
            'strategy': trade_data.get('strategy'),
            'status': trade_data.get('status', 'CLOSED'),
            'duration_hours': trade_data.get('duration_hours'),
            'notes': trade_data.get('notes', '')
        }
        self.trade_journal.append(entry)
        
    def _check_circuit_breaker(self):
        """Check if circuit breaker should be triggered"""
        if self.circuit_breaker_active:
            if datetime.now(self.broker_tz) < self.circuit_breaker_until:
                return True, f"Circuit breaker active until {self.circuit_breaker_until.strftime('%H:%M')}"
            else:
                self.circuit_breaker_active = False
                self.consecutive_losses = 0
                print("Circuit breaker RESET")
        return False, "OK"
    
    def _trigger_circuit_breaker(self, hours=4):
        """Activate circuit breaker"""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now(self.broker_tz) + timedelta(hours=hours)
        print(f"⚠️ CIRCUIT BREAKER TRIGGERED! Paused for {hours} hours")
        
    def _check_daily_drawdown(self):
        """Check if daily loss limit exceeded"""
        if self.daily_start_balance <= 0:
            acc = mt5.account_info()
            if acc:
                self.daily_start_balance = acc.balance
            return False, "OK"
        
        acc = mt5.account_info()
        if not acc:
            return False, "OK"
        
        current_balance = acc.balance
        daily_loss_pct = ((self.daily_start_balance - current_balance) / self.daily_start_balance) * 100
        
        if daily_loss_pct >= self.daily_loss_limit:
            return True, f"Daily loss {daily_loss_pct:.1f}% exceeds {self.daily_loss_limit}%"
        
        return False, "OK"

    def initialize(self):
        print("Initializing MT5 connection...")
        if not mt5.initialize():
            print("ERROR: MT5 initialization failed!")
            return False
        acc = mt5.account_info()
        if acc:
            print(f"MT5 connected: Account {acc.login}, Balance: ${acc.balance:.2f}")
            print(f"Max risk per trade: {self.max_risk}% (${acc.balance * self.max_risk / 100:.2f})")
            self.peak_equity = acc.equity
        return True

    def is_connected(self):
        return mt5.terminal_info() is not None

    def get_broker_time(self):
        return datetime.now(self.broker_tz)

    def get_account(self):
        acc = mt5.account_info()
        if not acc:
            return {'balance': 0, 'equity': 0, 'profit': 0, 'drawdown': 0, 'margin_free': 0}

        self.peak_equity = max(self.peak_equity, acc.equity)
        dd = ((self.peak_equity - acc.equity) / self.peak_equity * 100) if self.peak_equity > 0 else 0

        return {
            'balance': acc.balance,
            'equity': acc.equity,
            'profit': acc.profit,
            'drawdown': min(dd, 100),
            'margin_free': acc.margin_free
        }

    def get_current_session(self):
        # Convert broker time (GMT+3) to UTC for session detection
        utc_now = datetime.now(timezone.utc)
        hour = utc_now.hour

        # Session times in UTC
        if 0 <= hour < 7:
            code, name = 'SYDNEY', 'Sydney Session'
            best = ['AUDUSD', 'NZDUSD']
        elif 7 <= hour < 8:
            code, name = 'SILVER_BULLET', 'Silver Bullet (7-8AM UTC)'
            best = ['XAUUSD']
        elif 8 <= hour < 12:
            code, name = 'LONDON', 'London Session'
            best = ['XAUUSD', 'EURUSD', 'GBPUSD']
        elif 12 <= hour < 13:
            code, name = 'LUNCH', 'Lunch Lull'
            best = []
        elif 13 <= hour < 16:
            code, name = 'OVERLAP', 'London/NY Overlap'
            best = ['EURUSD', 'GBPUSD', 'XAUUSD']
        elif 16 <= hour < 22:
            code, name = 'NEW_YORK', 'NY Session'
            best = ['EURUSD', 'GBPUSD', 'USDCAD']
        elif 22 <= hour < 24:
            code, name = 'TOKYO', 'Tokyo Session'
            best = ['USDJPY', 'AUDUSD']
        else:
            code, name = 'OFF_HOURS', 'Off Hours'
            best = []

        return {'code': code, 'name': name, 'is_good': code in self.good_sessions, 'best_pairs': best}

    def can_trade(self):
        # Check circuit breaker first
        cb_active, cb_reason = self._check_circuit_breaker()
        if cb_active:
            return False, f"CIRCUIT BREAKER: {cb_reason}"
        
        # Check daily drawdown
        dd_active, dd_reason = self._check_daily_drawdown()
        if dd_active:
            self._trigger_circuit_breaker(24)
            return False, f"DAILY LIMIT: {dd_reason}"
        
        acc = mt5.account_info()
        if not acc:
            return False, "MT5 not connected"
        if acc.margin_level > 0 and acc.margin_level < 150:
            return False, f"Margin level low ({acc.margin_level:.0f}%)"
        if acc.margin_free < 50:
            return False, f"Low free margin (${acc.margin_free:.2f})"
        return True, "OK"

    # ==================== INDICATORS ====================

    def _calculate_adx(self, df, period=14):
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

    def _calculate_rsi(self, df, period=14):
        delta = df['close'].diff()
        gain = delta.clip(lower=0).rolling(period).mean().iloc[-1]
        loss = (-delta.clip(upper=0)).rolling(period).mean().iloc[-1]
        rs = gain / loss if loss > 0 else 50
        return 100 - (100 / (1 + rs))

    def _calculate_stochastic(self, df, period=14):
        low_min = df['low'].rolling(period).min()
        high_max = df['high'].rolling(period).max()
        k = 100 * (df['close'] - low_min) / (high_max - low_min)
        d = k.rolling(3).mean()
        return k.iloc[-1], d.iloc[-1]

    def _calculate_atr(self, df, period=14):
        high = df['high']
        low = df['low']
        close = df['close']
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]

    # ==================== MARKET DIRECTION ====================

    def get_market_direction(self, symbol, timeframe='H4'):
        try:
            tf_map = {'M30': mt5.TIMEFRAME_M30, 'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4}
            tf = tf_map.get(timeframe, mt5.TIMEFRAME_H4)
            lookback = 200 if timeframe == 'H4' else 100

            rates = mt5.copy_rates_from_pos(symbol, tf, 0, lookback)
            if rates is None or len(rates) < 50:
                return {'trend': 'NEUTRAL', 'adx': 0, 'timeframe': timeframe}

            df = pd.DataFrame(rates)
            ema20 = df['close'].ewm(span=20).mean().iloc[-1]
            ema50 = df['close'].ewm(span=50).mean().iloc[-1]
            adx = self._calculate_adx(df)

            if ema20 > ema50:
                trend = 'BULLISH'
            elif ema20 < ema50:
                trend = 'BEARISH'
            else:
                trend = 'NEUTRAL'

            return {
                'trend': trend, 'adx': adx,
                'ema_fast': round(ema20, 5), 'ema_slow': round(ema50, 5),
                'timeframe': timeframe
            }
        except Exception as e:
            print(f"Market direction error for {symbol} {timeframe}: {e}")
            return {'trend': 'NEUTRAL', 'adx': 0, 'timeframe': timeframe}

    def get_all_market_directions(self, symbol):
        now = time.time()
        if symbol in self._market_dir_cache and (now - self._market_dir_cache_time) < self._cache_ttl:
            return self._market_dir_cache[symbol]
        result = {
            'H4': self.get_market_direction(symbol, 'H4'),
            'H1': self.get_market_direction(symbol, 'H1'),
            'M30': self.get_market_direction(symbol, 'M30')
        }
        self._market_dir_cache[symbol] = result
        self._market_dir_cache_time = now
        return result

    def get_signal_expiry_seconds(self):
        now = datetime.now(self.broker_tz)
        current_hour = now.hour
        minutes = now.minute
        seconds = now.second
        current_4h_slot = (current_hour // 4) * 4
        next_4h_slot = current_4h_slot + 4
        if next_4h_slot >= 24:
            next_4h_slot = 0
        time_to_next = ((next_4h_slot - current_hour) * 3600) - (minutes * 60) - seconds
        if time_to_next <= 0:
            time_to_next += 14400
        return max(int(time_to_next), 1)

    # ==================== POSITIONS & HISTORY ====================

    def get_open_positions(self):
        positions = mt5.positions_get()
        if positions is None:
            return []

        result = []
        for pos in positions:
            tick = mt5.symbol_info_tick(pos.symbol)
            result.append({
                'ticket': int(pos.ticket),
                'symbol': str(pos.symbol),
                'type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                'volume': float(pos.volume),
                'entry': float(round(pos.price_open, 5)),
                'current': float(round(tick.last if tick else pos.price_current, 5)),
                'profit': float(round(pos.profit, 2)),
                'sl': float(round(pos.sl, 5)) if pos.sl > 0 else None,
                'tp': float(round(pos.tp, 5)) if pos.tp > 0 else None
            })
        return result

    def get_trade_history(self, days=7, hours=0):
        if hours > 0:
            to_dt = datetime.now(self.broker_tz)
            from_dt = to_dt - timedelta(hours=hours)
        else:
            from_dt = datetime.now(self.broker_tz).replace(hour=0, minute=0, second=0, microsecond=0)
            to_dt = from_dt + timedelta(days=days)

        deals = mt5.history_deals_get(from_dt, to_dt)
        if deals is None:
            return []

        history = []
        for deal in deals:
            if deal.profit != 0:
                history.append({
                    'ticket': int(deal.ticket),
                    'symbol': str(deal.symbol or 'Unknown'),
                    'type': 'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL',
                    'volume': float(deal.volume),
                    'entry': float(round(deal.price, 5)),
                    'profit': float(round(deal.profit + deal.commission + deal.swap, 2)),
                    'time': datetime.fromtimestamp(deal.time, tz=self.broker_tz).strftime('%Y-%m-%d %H:%M')
                })

        history.sort(key=lambda x: x['time'], reverse=True)
        return history[:50]

    # ==================== RISK CALCULATIONS ====================

    def _get_contract_size(self, symbol):
        if 'XAU' in symbol or 'XAG' in symbol:
            return 100
        return 100000

    def _get_pip_value(self, symbol):
        if 'JPY' in symbol:
            return 0.01
        return 0.0001

    def _calculate_risk(self, symbol, lot, sl_distance_pips):
        """Calculate dollar risk for a trade"""
        if 'XAU' in symbol or 'XAG' in symbol:
            return lot * sl_distance_pips * 100
        else:
            return lot * sl_distance_pips * 10

    def _get_pip_value_per_lot(self, symbol):
        """Dollar value per pip per 1.0 lot"""
        if 'XAU' in symbol or 'XAG' in symbol:
            return 100
        else:
            return 10

    def _calculate_lot_size(self, symbol, sl_distance_pips, max_risk):
        """Calculate lot size that risks exactly max_risk dollars"""
        pip_value = self._get_pip_value_per_lot(symbol)
        lot = max_risk / (sl_distance_pips * pip_value)
        return max(0.01, round(lot, 2))

    def _calculate_sl_price(self, symbol, entry, sl_distance_pips, direction):
        """Calculate stop loss price from pip distance"""
        if 'XAU' in symbol or 'XAG' in symbol:
            sl_price = sl_distance_pips
        elif 'JPY' in symbol:
            sl_price = sl_distance_pips * 0.01
        else:
            sl_price = sl_distance_pips * 0.0001

        if direction == 'BUY':
            return entry - sl_price
        else:
            return entry + sl_price

    def _calculate_tp_price(self, symbol, entry, sl_distance_pips, direction, rr=2.0):
        """Calculate take profit price with proper R:R ratio"""
        tp_distance_pips = sl_distance_pips * rr
        if 'XAU' in symbol or 'XAG' in symbol:
            tp_price = tp_distance_pips
        elif 'JPY' in symbol:
            tp_price = tp_distance_pips * 0.01
        else:
            tp_price = tp_distance_pips * 0.0001

        if direction == 'BUY':
            return entry + tp_price
        else:
            return entry - tp_price

    def _get_proper_sl_distance(self, symbol, atr):
        """Get SL distance in pips based on ATR (market volatility)"""
        if 'XAU' in symbol or 'XAG' in symbol:
            return atr * 1.5
        elif 'JPY' in symbol:
            return atr * 1.5 / 0.01
        else:
            return atr * 1.5 / 0.0001

    # ==================== STRATEGY SCANNERS ====================

    def scan_pair(self, symbol):
        """Swing_H4H1 Strategy: H4 trend + H1 entry confirmation"""
        try:
            rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 100)
            rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)

            if rates_h4 is None or rates_h1 is None:
                return None

            df_h4 = pd.DataFrame(rates_h4)
            df_h4['ema20'] = df_h4['close'].ewm(span=20).mean()
            df_h4['ema50'] = df_h4['close'].ewm(span=50).mean()

            df_h1 = pd.DataFrame(rates_h1)
            df_h1['ema9'] = df_h1['close'].ewm(span=9).mean()
            df_h1['ema21'] = df_h1['close'].ewm(span=21).mean()

            h4_bull = df_h4['ema20'].iloc[-1] > df_h4['ema50'].iloc[-1]
            h4_bear = df_h4['ema20'].iloc[-1] < df_h4['ema50'].iloc[-1]
            h1_bull = df_h1['ema9'].iloc[-1] > df_h1['ema21'].iloc[-1]
            h1_bear = df_h1['ema9'].iloc[-1] < df_h1['ema21'].iloc[-1]

            tick = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if not tick or not sym_info:
                return None

            point = sym_info.point
            digits = sym_info.digits
            spread = tick.ask - tick.bid
            spread_pips = spread / point / 10 if digits in [3, 5] else spread / point

            max_spread = 300 if symbol == 'XAUUSD' else 25
            if spread_pips > max_spread:
                return None

            acc = mt5.account_info()
            if not acc:
                return None
            balance = acc.balance
            max_risk = balance * (self.max_risk / 100)

            rsi = self._calculate_rsi(df_h1)
            adx = self._calculate_adx(df_h1)
            atr = self._calculate_atr(df_h1)

            adx_ok = True
            if symbol == 'XAUUSD':
                adx_ok = adx > 18

            if not (h4_bull and h1_bull) and not (h4_bear and h1_bear):
                return None

            if not adx_ok:
                return None

            sl_distance_pips = self._get_proper_sl_distance(symbol, atr)

            if h4_bull and h1_bull:
                direction = 'BUY'
                entry = tick.ask
                h4_trend = 'BULL'
            else:
                direction = 'SELL'
                entry = tick.bid
                h4_trend = 'BEAR'

            sl = self._calculate_sl_price(symbol, entry, sl_distance_pips, direction)
            tp = self._calculate_tp_price(symbol, entry, sl_distance_pips, direction, 2.0)
            rr = 2.0

            lot = self._calculate_lot_size(symbol, sl_distance_pips, max_risk)
            risk = self._calculate_risk(symbol, lot, sl_distance_pips)

            can_trade = risk <= max_risk * 1.05 and lot >= 0.01
            reason = 'OK' if can_trade else ('Risk > 1%' if risk > max_risk * 1.05 else 'Invalid lot')

            return {
                'symbol': symbol, 'direction': direction, 'entry': round(entry, 5),
                'sl': round(sl, 5), 'tp': round(tp, 5), 'rr_ratio': round(rr, 1),
                'lot': lot, 'risk_amount': round(risk, 2), 'spread': round(spread_pips, 1),
                'h4_trend': h4_trend, 'h1_rsi': round(rsi, 1), 'adx': round(adx, 1),
                'can_trade': bool(can_trade), 'trade_reason': reason,
                'strategy': 'Swing_H4H1'
            }
        except Exception as e:
            print('Swing_H4H1 scan error:', e)
            return None

    def scan_trend_rider(self, symbol):
        """Trend_Rider Strategy: H4 trend + ADX + H1 EMA alignment"""
        try:
            rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 100)
            rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)

            if rates_h4 is None or rates_h1 is None:
                return None

            df_h4 = pd.DataFrame(rates_h4)
            df_h4['ema20'] = df_h4['close'].ewm(span=20).mean()
            df_h4['ema50'] = df_h4['close'].ewm(span=50).mean()

            df_h1 = pd.DataFrame(rates_h1)
            df_h1['ema9'] = df_h1['close'].ewm(span=9).mean()
            df_h1['ema21'] = df_h1['close'].ewm(span=21).mean()

            tick = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if not tick or not sym_info:
                return None

            point = sym_info.point
            digits = sym_info.digits
            spread = tick.ask - tick.bid
            spread_pips = spread / point / 10 if digits in [3, 5] else spread / point

            max_spread = 300 if symbol == 'XAUUSD' else 25
            if spread_pips > max_spread:
                return None

            adx = self._calculate_adx(df_h1)
            if adx < 20:
                return None

            h4_bull = df_h4['ema20'].iloc[-1] > df_h4['ema50'].iloc[-1]
            h1_bull = df_h1['ema9'].iloc[-1] > df_h1['ema21'].iloc[-1]

            if h4_bull and h1_bull:
                direction = 'BUY'
                entry = tick.ask
                h4_trend = 'BULL'
            elif not h4_bull and not h1_bull:
                direction = 'SELL'
                entry = tick.bid
                h4_trend = 'BEAR'
            else:
                return None

            acc = mt5.account_info()
            if not acc:
                return None
            balance = acc.balance
            max_risk = balance * (self.max_risk / 100)

            atr = self._calculate_atr(df_h1)
            sl_distance_pips = self._get_proper_sl_distance(symbol, atr)
            sl = self._calculate_sl_price(symbol, entry, sl_distance_pips, direction)
            tp = self._calculate_tp_price(symbol, entry, sl_distance_pips, direction, 2.0)
            rr = 2.0

            lot = self._calculate_lot_size(symbol, sl_distance_pips, max_risk)
            risk = self._calculate_risk(symbol, lot, sl_distance_pips)

            can_trade = risk <= max_risk * 1.05 and lot >= 0.01
            reason = 'OK' if can_trade else ('Risk > 1%' if risk > max_risk * 1.05 else 'Invalid lot')

            rsi = self._calculate_rsi(df_h1)

            return {
                'symbol': symbol, 'direction': direction, 'entry': round(entry, 5),
                'sl': round(sl, 5), 'tp': round(tp, 5), 'rr_ratio': round(rr, 1),
                'lot': lot, 'risk_amount': round(risk, 2), 'spread': round(spread_pips, 1),
                'h4_trend': h4_trend, 'h1_rsi': round(rsi, 1), 'adx': round(adx, 1),
                'can_trade': bool(can_trade), 'trade_reason': reason,
                'strategy': 'Trend_Rider'
            }
        except Exception as e:
            print('Trend_Rider scan error:', e)
            return None

    def scan_breakout(self, symbol):
        """Breakout_Hunter Strategy: Bollinger Band breakout"""
        try:
            rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 50)
            rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)

            if rates_h4 is None or rates_h1 is None:
                return None

            df_h4 = pd.DataFrame(rates_h4)
            df_h1 = pd.DataFrame(rates_h1)

            tick = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if not tick or not sym_info:
                return None

            point = sym_info.point
            digits = sym_info.digits
            spread = tick.ask - tick.bid
            spread_pips = spread / point / 10 if digits in [3, 5] else spread / point

            max_spread = 300 if symbol == 'XAUUSD' else 25
            if spread_pips > max_spread:
                return None

            df_h4['bb_middle'] = df_h4['close'].rolling(20).mean()
            df_h4['bb_std'] = df_h4['close'].rolling(20).std()
            df_h4['bb_upper'] = df_h4['bb_middle'] + 2 * df_h4['bb_std']
            df_h4['bb_lower'] = df_h4['bb_middle'] - 2 * df_h4['bb_std']

            current_close = df_h4['close'].iloc[-1]
            bb_upper = df_h4['bb_upper'].iloc[-1]
            bb_lower = df_h4['bb_lower'].iloc[-1]

            if current_close > bb_upper:
                direction = 'BUY'
                entry = tick.ask
                h4_trend = 'BREAKOUT_UP'
            elif current_close < bb_lower:
                direction = 'SELL'
                entry = tick.bid
                h4_trend = 'BREAKOUT_DOWN'
            else:
                return None

            acc = mt5.account_info()
            if not acc:
                return None
            balance = acc.balance
            max_risk = balance * (self.max_risk / 100)

            atr = self._calculate_atr(df_h1)
            sl_distance_pips = self._get_proper_sl_distance(symbol, atr)
            sl = self._calculate_sl_price(symbol, entry, sl_distance_pips, direction)
            tp = self._calculate_tp_price(symbol, entry, sl_distance_pips, direction, 2.0)
            rr = 2.0

            lot = self._calculate_lot_size(symbol, sl_distance_pips, max_risk)
            risk = self._calculate_risk(symbol, lot, sl_distance_pips)

            can_trade = risk <= max_risk * 1.05 and lot >= 0.01
            reason = 'OK' if can_trade else ('Risk > 1%' if risk > max_risk * 1.05 else 'Invalid lot')

            adx = self._calculate_adx(df_h1)
            rsi = self._calculate_rsi(df_h1)

            return {
                'symbol': symbol, 'direction': direction, 'entry': round(entry, 5),
                'sl': round(sl, 5), 'tp': round(tp, 5), 'rr_ratio': round(rr, 1),
                'lot': lot, 'risk_amount': round(risk, 2), 'spread': round(spread_pips, 1),
                'h4_trend': h4_trend, 'h1_rsi': round(rsi, 1), 'adx': round(adx, 1),
                'can_trade': bool(can_trade), 'trade_reason': reason,
                'strategy': 'Breakout_Hunter'
            }
        except Exception as e:
            print('Breakout_Hunter scan error:', e)
            return None

    def scan_smart_money(self, symbol):
        """Smart_Money Strategy: H4 trend + H1 EMA alignment"""
        try:
            rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 50)
            rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)

            if rates_h4 is None or rates_h1 is None:
                return None

            df_h4 = pd.DataFrame(rates_h4)
            df_h4['ema20'] = df_h4['close'].ewm(span=20).mean()
            df_h4['ema50'] = df_h4['close'].ewm(span=50).mean()

            df_h1 = pd.DataFrame(rates_h1)
            df_h1['ema9'] = df_h1['close'].ewm(span=9).mean()
            df_h1['ema21'] = df_h1['close'].ewm(span=21).mean()

            tick = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if not tick or not sym_info:
                return None

            point = sym_info.point
            digits = sym_info.digits
            spread = tick.ask - tick.bid
            spread_pips = spread / point / 10 if digits in [3, 5] else spread / point

            max_spread = 300 if symbol == 'XAUUSD' else 25
            if spread_pips > max_spread:
                return None

            h4_bull = df_h4['ema20'].iloc[-1] > df_h4['ema50'].iloc[-1]
            h1_bull = df_h1['ema9'].iloc[-1] > df_h1['ema21'].iloc[-1]

            if h4_bull and h1_bull:
                direction = 'BUY'
                entry = tick.ask
                h4_trend = 'BULL_OB'
            elif not h4_bull and not h1_bull:
                direction = 'SELL'
                entry = tick.bid
                h4_trend = 'BEAR_OB'
            else:
                return None

            acc = mt5.account_info()
            if not acc:
                return None
            balance = acc.balance
            max_risk = balance * (self.max_risk / 100)

            atr = self._calculate_atr(df_h1)
            sl_distance_pips = self._get_proper_sl_distance(symbol, atr)
            sl = self._calculate_sl_price(symbol, entry, sl_distance_pips, direction)
            tp = self._calculate_tp_price(symbol, entry, sl_distance_pips, direction, 2.0)
            rr = 2.0

            lot = self._calculate_lot_size(symbol, sl_distance_pips, max_risk)
            risk = self._calculate_risk(symbol, lot, sl_distance_pips)

            can_trade = risk <= max_risk * 1.05 and lot >= 0.01
            reason = 'OK' if can_trade else ('Risk > 1%' if risk > max_risk * 1.05 else 'Invalid lot')

            adx = self._calculate_adx(df_h1)
            rsi = self._calculate_rsi(df_h1)

            return {
                'symbol': symbol, 'direction': direction, 'entry': round(entry, 5),
                'sl': round(sl, 5), 'tp': round(tp, 5), 'rr_ratio': round(rr, 1),
                'lot': lot, 'risk_amount': round(risk, 2), 'spread': round(spread_pips, 1),
                'h4_trend': h4_trend, 'h1_rsi': round(rsi, 1), 'adx': round(adx, 1),
                'can_trade': bool(can_trade), 'trade_reason': reason,
                'strategy': 'Smart_Money'
            }
        except Exception as e:
            print('Smart_Money scan error:', e)
            return None

    def scan_mean_reversion(self, symbol):
        """Mean_Reversion Strategy: RSI + Stochastic reversal"""
        try:
            rates_h4 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 50)
            rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)

            if rates_h4 is None or rates_h1 is None:
                return None

            df_h4 = pd.DataFrame(rates_h4)
            df_h4['ema20'] = df_h4['close'].ewm(span=20).mean()
            df_h4['ema50'] = df_h4['close'].ewm(span=50).mean()

            df_h1 = pd.DataFrame(rates_h1)

            tick = mt5.symbol_info_tick(symbol)
            sym_info = mt5.symbol_info(symbol)
            if not tick or not sym_info:
                return None

            point = sym_info.point
            digits = sym_info.digits
            spread = tick.ask - tick.bid
            spread_pips = spread / point / 10 if digits in [3, 5] else spread / point

            max_spread = 300 if symbol == 'XAUUSD' else 25
            if spread_pips > max_spread:
                return None

            rsi = self._calculate_rsi(df_h1)
            stoch_k, stoch_d = self._calculate_stochastic(df_h1)

            h4_bull = df_h4['ema20'].iloc[-1] > df_h4['ema50'].iloc[-1]

            buy_signal = rsi < 35 and stoch_k < 30
            sell_signal = rsi > 65 and stoch_k > 70

            if buy_signal and h4_bull:
                direction = 'BUY'
                entry = tick.ask
                h4_trend = 'OVERSOLD'
            elif sell_signal and not h4_bull:
                direction = 'SELL'
                entry = tick.bid
                h4_trend = 'OVERBOUGHT'
            else:
                return None

            acc = mt5.account_info()
            if not acc:
                return None
            balance = acc.balance
            max_risk = balance * (self.max_risk / 100)

            atr = self._calculate_atr(df_h1)
            sl_distance_pips = self._get_proper_sl_distance(symbol, atr)
            sl = self._calculate_sl_price(symbol, entry, sl_distance_pips, direction)
            tp = self._calculate_tp_price(symbol, entry, sl_distance_pips, direction, 2.0)
            rr = 2.0

            lot = self._calculate_lot_size(symbol, sl_distance_pips, max_risk)
            risk = self._calculate_risk(symbol, lot, sl_distance_pips)

            can_trade = risk <= max_risk * 1.05 and lot >= 0.01
            reason = 'OK' if can_trade else ('Risk > 1%' if risk > max_risk * 1.05 else 'Invalid lot')

            adx = self._calculate_adx(df_h1)

            return {
                'symbol': symbol, 'direction': direction, 'entry': round(entry, 5),
                'sl': round(sl, 5), 'tp': round(tp, 5), 'rr_ratio': round(rr, 1),
                'lot': lot, 'risk_amount': round(risk, 2), 'spread': round(spread_pips, 1),
                'h4_trend': h4_trend, 'h1_rsi': round(rsi, 1), 'adx': round(adx, 1),
                'can_trade': bool(can_trade), 'trade_reason': reason,
                'strategy': 'Mean_Reversion'
            }
        except Exception as e:
            print('Mean_Reversion scan error:', e)
            return None

    # ==================== SCAN ALL ====================

    def scan_all_pairs(self, pairs=None):
        if pairs is None:
            pairs = self.trading_pairs
        print(f"Scanning {len(pairs)} pairs: {pairs} with strategies: {self.active_strategies}...")
        self.scan_results = []

        for pair in pairs:
            results = []
            for strat in self.active_strategies:
                if strat == 'Swing_H4H1':
                    result = self.scan_pair(pair)
                elif strat == 'Trend_Rider':
                    result = self.scan_trend_rider(pair)
                elif strat == 'Breakout_Hunter':
                    result = self.scan_breakout(pair)
                elif strat == 'Mean_Reversion':
                    result = self.scan_mean_reversion(pair)
                elif strat == 'Smart_Money':
                    result = self.scan_smart_money(pair)
                else:
                    result = self.scan_pair(pair)

                if result:
                    result['strategy'] = strat
                    results.append(result)
                    print(f"  {pair} {result['direction']} ({strat}) R:R 1:{result['rr_ratio']}")

            for r in results:
                self.scan_results.append(r)

        self.last_scan_time = datetime.now(self.broker_tz)
        print(f"Scan complete: {len(self.scan_results)} signals found")

    # ==================== TRADE EXECUTION ====================

    def execute_trade(self, idx):
        if idx < 0 or idx >= len(self.scan_results):
            return False, "Invalid signal index"

        sig = self.scan_results[idx]

        if not sig.get('can_trade', False):
            return False, f"Signal not tradeable: {sig.get('trade_reason', 'Unknown')}. Use /api/execute-override/{idx} to force."

        symbol = sig['symbol']
        positions = self.get_open_positions()

        # Check if already have position on this pair
        for pos in positions:
            if pos['symbol'] == symbol:
                return False, f"Already have {pos['type']} position on {symbol}. Close it first."

        # Max 3 total positions across all pairs
        if len(positions) >= 3:
            return False, f"Max 3 positions reached. Close one to open new trade."

        can_trade, reason = self.can_trade()
        if not can_trade:
            return False, reason

        lot = float(sig.get('lot', 0.01))
        direction = sig['direction']

        if not mt5.symbol_select(symbol, True):
            return False, f"Failed to select symbol {symbol}"

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False, f"Failed to get tick for {symbol}"

        if direction == 'BUY':
            order_type = mt5.ORDER_TYPE_BUY
            price = float(tick.ask)
            sl = float(sig['sl'])
            tp = float(sig['tp'])
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = float(tick.bid)
            sl = float(sig['sl'])
            tp = float(sig['tp'])

        sym_info = mt5.symbol_info(symbol)
        digits = sym_info.digits if sym_info else 5

        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': lot,
            'type': order_type,
            'price': price,
            'sl': round(sl, digits),
            'tp': round(tp, digits),
            'deviation': 10,
            'magic': 2026001,
            'comment': f"TradingBot {direction}",
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_FOK
        }

        print(f"[EXECUTE] {symbol} {direction} Lot:{lot} Price:{price} SL:{sl} TP:{tp}")
        result = mt5.order_send(request)

        if result is None:
            err = mt5.last_error()
            print(f"[EXECUTE ERROR] {symbol}: No response, Last error: {err}")
            return False, f"No response from MT5 (error {err})"

        print(f"[EXECUTE RESULT] {symbol}: retcode={result.retcode}, deal={result.deal}, order={result.order}")

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_codes = {
                10014: "Invalid volume",
                10015: "Invalid price",
                10016: "Invalid SL/TP",
                10019: "Market closed",
                10030: "Trade disabled",
                10031: "Market closed",
                10032: "Trading allowed only for LIVE accounts",
                10033: "No connection",
                10034: "Too many requests",
                10035: "Trade disabled by broker",
                10036: "Margin check failed",
                10038: "Stop limit check failed",
                10006: "No connection",
                10001: "Internal error"
            }
            error_msg = error_codes.get(result.retcode, f"Error {result.retcode}")
            print(f"[EXECUTE FAILED] {symbol}: {error_msg}")
            return False, f"Trade failed: {error_msg}"

        print(f"[SUCCESS] Trade executed: {symbol} {direction} {lot} lots @ {price}")
        
        # Record to journal
        self._save_journal_entry({
            'symbol': symbol,
            'direction': direction,
            'entry': price,
            'lot': lot,
            'sl': sl,
            'tp': tp,
            'strategy': sig['strategy'],
            'status': 'OPEN',
            'profit': 0
        })
        
        # Check for consecutive losses on next close
        return True, f"Trade executed: {symbol} {direction} @ {price}"

    def close_position(self, ticket):
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False

        pos = positions[0]
        direction = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            return False

        price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask

        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': pos.symbol,
            'volume': pos.volume,
            'type': direction,
            'position': ticket,
            'price': price,
            'deviation': 10,
            'magic': 2026001,
            'comment': "Bot close",
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_FOK
        }

        result = mt5.order_send(request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            # Update journal with exit
            self._save_journal_entry({
                'symbol': pos.symbol,
                'direction': 'CLOSE',
                'entry': pos.price_open,
                'exit_price': price,
                'lot': pos.volume,
                'profit': pos.profit,
                'sl': pos.sl,
                'tp': pos.tp,
                'strategy': 'TradingBot',
                'status': 'CLOSED',
                'notes': f"Ticket {ticket} closed"
            })
            
            # Update consecutive losses for circuit breaker
            if pos.profit < 0:
                self.consecutive_losses += 1
                if self.consecutive_losses >= self.max_consecutive_losses:
                    self._trigger_circuit_breaker(4)
            else:
                self.consecutive_losses = 0
                
        return result and result.retcode == mt5.TRADE_RETCODE_DONE

    def close_profitable(self):
        closed = 0
        for pos in self.get_open_positions():
            if pos['profit'] > 0 and self.close_position(pos['ticket']):
                closed += 1
        return closed

    # ==================== DATA SANITIZATION ====================

    def _to_native(self, val):
        if isinstance(val, (np.bool_, np.int64, np.float64)):
            return val.item()
        return val

    def _sanitize_signals(self, signals):
        clean = []
        for s in signals:
            can_trade = bool(s.get('can_trade', False))
            risk_amount = float(s.get('risk_amount', 0))
            clean.append({
                'symbol': s.get('symbol'),
                'direction': s.get('direction'),
                'entry': float(s.get('entry', 0)),
                'sl': float(s.get('sl', 0)),
                'tp': float(s.get('tp', 0)),
                'rr_ratio': float(s.get('rr_ratio', 0)),
                'lot': float(s.get('lot', 0.01)),
                'risk_amount': risk_amount,
                'spread': float(s.get('spread', 0)),
                'h4_trend': str(s.get('h4_trend', 'NEUTRAL')),
                'h1_rsi': float(s.get('h1_rsi', 50)),
                'adx': float(s.get('adx', 0)),
                'can_trade': can_trade,
                'trade_reason': str(s.get('trade_reason', 'Unknown')),
                'strategy': str(s.get('strategy', 'Unknown'))
            })
        return clean

    # ==================== STATUS & RUN LOOP ====================

    def get_journal_stats(self):
        """Get trade journal statistics"""
        if not self.trade_journal:
            return {'total_trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'total_profit': 0}
        
        closed = [t for t in self.trade_journal if t['status'] == 'CLOSED']
        wins = len([t for t in closed if t['profit'] > 0])
        losses = len([t for t in closed if t['profit'] < 0])
        total_profit = sum(t['profit'] for t in closed)
        
        return {
            'total_trades': len(closed),
            'wins': wins,
            'losses': losses,
            'win_rate': round((wins / len(closed) * 100), 1) if closed else 0,
            'total_profit': round(total_profit, 2)
        }
    
    def get_status(self, history_days=7, history_hours=0):
        metrics = self.get_account()
        can_trade, reason = self.can_trade()
        session = self.get_current_session()
        market_dirs = {s: self.get_all_market_directions(s) for s in self.trading_pairs}
        signal_expiry = self.get_signal_expiry_seconds()
        
        # Check circuit breaker status
        cb_active, cb_reason = self._check_circuit_breaker()
        
        return {
            'running': bool(self.running),
            'mt5_connected': bool(self.is_connected()),
            'balance': float(round(metrics.get('balance', 0), 2)),
            'equity': float(round(metrics.get('equity', 0), 2)),
            'profit': float(round(metrics.get('profit', 0), 2)),
            'drawdown': float(round(metrics.get('drawdown', 0), 1)),
            'margin_free': float(round(metrics.get('margin_free', 0), 2)),
            'positions': int(len(self.get_open_positions())),
            'open_positions': self.get_open_positions(),
            'session': session,
            'is_tradeable': bool(can_trade),
            'trade_reason': reason,
            'scan_results': self._sanitize_signals(self.scan_results),
            'last_scan': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'signal_expiry_seconds': int(signal_expiry),
            'market_directions': market_dirs,
            'trade_history': self.get_trade_history(history_days, history_hours),
            'broker_time': self.get_broker_time().isoformat(),
            'trading_pairs': self.trading_pairs,
            'available_strategies': STRATEGIES,
            'active_strategies': self.active_strategies,
            'risk_settings': {
                'daily_loss_limit': self.daily_loss_limit,
                'max_consecutive_losses': self.max_consecutive_losses,
                'circuit_breaker_active': cb_active,
                'consecutive_losses': self.consecutive_losses
            },
            'journal_stats': self.get_journal_stats(),
            'trade_journal': self.trade_journal[-20:]  # Last 20 trades
        }

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def _run_loop(self):
        while self.running:
            try:
                self.scan_all_pairs()
                sleep_time = self.get_signal_expiry_seconds() + 5
                time.sleep(min(sleep_time, 14400))
            except Exception as e:
                print(f'Auto-scan error: {e}')
                time.sleep(30)


bot = TradingBot()
bot.initialize()


@app.route("/")
def index():
    template_path = os.path.join(os.path.dirname(__file__), 'template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    return render_template_string(template_content)


@app.route("/api/status")
def get_status():
    hours = int(request.args.get('hours', 0))
    return jsonify(bot.get_status(1, hours))


@app.route("/api/scan", methods=["POST"])
def scan():
    pairs_param = request.args.get('pairs', '')
    if pairs_param:
        pairs = pairs_param.split(',')
        bot.scan_all_pairs(pairs)
    else:
        bot.scan_all_pairs()
    return jsonify({"ok": True, "found": len(bot.scan_results), "pairs": pairs_param.split(',') if pairs_param else bot.trading_pairs})


@app.route("/api/start", methods=["POST"])
def start():
    bot.start()
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def stop():
    bot.stop()
    return jsonify({"ok": True})


@app.route("/api/execute/<int:idx>", methods=["POST"])
def execute(idx):
    ok, msg = bot.execute_trade(idx)
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/execute-override/<int:idx>", methods=["POST"])
def execute_override(idx):
    bot.scan_results[idx]['can_trade'] = True
    ok, msg = bot.execute_trade(idx)
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/close/<int:ticket>", methods=["POST"])
def close_position(ticket):
    ok = bot.close_position(ticket)
    return jsonify({"ok": ok, "message": "Position closed" if ok else "Failed to close"})


@app.route("/api/close-profitable", methods=["POST"])
def close_profitable():
    closed = bot.close_profitable()
    return jsonify({"ok": True, "closed": closed, "message": f"Closed {closed} positions"})


@app.route("/api/close-all", methods=["POST"])
def close_all():
    closed = 0
    for pos in bot.get_open_positions():
        if bot.close_position(pos['ticket']):
            closed += 1
    return jsonify({"ok": True, "closed": closed, "message": f"Closed {closed} positions"})


@app.route("/api/pairs", methods=["POST"])
def set_pairs():
    pairs_param = request.args.get('pairs', '')
    if pairs_param:
        bot.trading_pairs = pairs_param.split(',')
    return jsonify({"ok": True, "pairs": bot.trading_pairs})


@app.route("/api/strategies", methods=["POST"])
def set_strategies():
    strategies_param = request.args.get('strategies', '')
    if strategies_param:
        bot.active_strategies = strategies_param.split(',')
    return jsonify({"ok": True, "active_strategies": bot.active_strategies})


if __name__ == "__main__":
    print("=" * 60)
    print("TRADING BOT v22 - HUMAN-IN-THE-LOOP")
    print("=" * 60)
    print("Mode: Signal Scanner (Human Executes)")
    print("Strategies: Swing_H4H1 (Primary), Trend_Rider (Secondary)")
    print(f"Risk: {bot.max_risk}% per trade, Max {bot.max_positions} positions")
    print(f"Daily Loss Limit: {bot.daily_loss_limit}%")
    print(f"Circuit Breaker: {bot.max_consecutive_losses} consecutive losses = pause")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)
