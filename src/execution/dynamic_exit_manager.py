"""
DYNAMIC EXIT MANAGER
Monitors trades for reversal signals and closes positions proactively

Exit Triggers:
1. Market structure reversal (MSS against position)
2. Opposite liquidity sweep detected
3. Break of key support/resistance
4. Volume divergence
5. Momentum exhaustion (RSI extremes)
6. Adverse price action patterns
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime

from src.ict import ICTMarketStructure, ICTLiquidityDetector
from src.utils.logger import setup_logger


class DynamicExitManager:
    """
    Monitors open positions and closes them if reversal detected
    
    More aggressive than stop-loss - exits on early warning signs
    """
    
    def __init__(self):
        self.logger = setup_logger('DynamicExitManager', 'data/logs')
        
        # ICT components for reversal detection
        self.structure_detector = ICTMarketStructure()
        self.liquidity_detector = ICTLiquidityDetector()
        
        # Exit thresholds
        self.min_profit_for_exit_pct = 0.5  # Only consider dynamic exit if in profit
        self.rsi_overbought = 75  # Exit longs
        self.rsi_oversold = 25    # Exit shorts
        
    def check_for_exit(self, position: Dict, df_current: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check if position should be closed due to reversal
        
        Args:
            position: Open position dict with entry, direction, etc.
            df_current: Current market data (M15 or M5)
            
        Returns:
            (should_exit, reason)
        """
        direction = position['direction']
        entry_price = position['entry']
        current_price = df_current.iloc[-1]['close']
        
        # Calculate current P&L
        if direction == 'LONG':
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:  # SHORT
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        # Check each exit condition
        exit_checks = [
            self._check_structure_reversal(position, df_current),
            self._check_opposite_liquidity_sweep(position, df_current),
            self._check_key_level_break(position, df_current),
            self._check_momentum_exhaustion(position, df_current),
            self._check_adverse_patterns(position, df_current)
        ]
        
        # If in profit and any reversal signal, exit
        if pnl_pct > self.min_profit_for_exit_pct:
            for should_exit, reason in exit_checks:
                if should_exit:
                    self.logger.info(f"Dynamic exit triggered: {reason} (P&L: +{pnl_pct:.2f}%)")
                    return (True, reason)
        
        # If in loss but strong reversal, also exit (cut losses early)
        elif pnl_pct < -0.3:  # -0.3% loss
            # Only check structure reversal and opposite sweep in loss
            for should_exit, reason in exit_checks[:2]:
                if should_exit:
                    self.logger.warning(f"Emergency exit: {reason} (P&L: {pnl_pct:.2f}%)")
                    return (True, f"Emergency: {reason}")
        
        return (False, "No exit signal")
    
    def _check_structure_reversal(self, position: Dict, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check if market structure has reversed against position
        
        LONG position: Exit if bearish MSS detected
        SHORT position: Exit if bullish MSS detected
        """
        direction = position['direction']
        
        # Analyze structure
        analysis = self.structure_detector.analyze_structure(df)
        latest_shift = self.structure_detector.get_latest_shift()
        
        if not latest_shift:
            return (False, "")
        
        # Check if shift is recent (within last 5 bars)
        # This is approximate - in real implementation would check timestamps
        
        # LONG position - exit on bearish MSS
        if direction == 'LONG' and latest_shift.shift_type == 'MSS' and latest_shift.direction == 'bearish':
            return (True, "Bearish MSS detected - structure reversed against LONG")
        
        # SHORT position - exit on bullish MSS
        if direction == 'SHORT' and latest_shift.shift_type == 'MSS' and latest_shift.direction == 'bullish':
            return (True, "Bullish MSS detected - structure reversed against SHORT")
        
        return (False, "")
    
    def _check_opposite_liquidity_sweep(self, position: Dict, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check if opposite-direction liquidity sweep occurred
        
        LONG: Exit if new BSL sweep (sell-side liquidity taken)
        SHORT: Exit if new SSL sweep (buy-side liquidity taken)
        """
        direction = position['direction']
        
        # Detect liquidity pools and sweeps
        pools = self.liquidity_detector.identify_liquidity_pools(df)
        sweeps = self.liquidity_detector.detect_sweeps(df, pools)
        
        if not sweeps:
            return (False, "")
        
        latest_sweep = sweeps[-1]
        
        # LONG position - exit if BSL sweep (upside sweep = bearish signal)
        if direction == 'LONG' and latest_sweep.sweep_type == 'BSL' and latest_sweep.rejection_confirmed:
            return (True, "BSL sweep detected - reversal signal against LONG")
        
        # SHORT position - exit if SSL sweep (downside sweep = bullish signal)
        if direction == 'SHORT' and latest_sweep.sweep_type == 'SSL' and latest_sweep.rejection_confirmed:
            return (True, "SSL sweep detected - reversal signal against SHORT")
        
        return (False, "")
    
    def _check_key_level_break(self, position: Dict, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check if price broke key support/resistance against position
        
        Uses EMA 50 as dynamic level
        """
        direction = position['direction']
        current_price = df.iloc[-1]['close']
        
        if len(df) < 50:
            return (False, "")
        
        # Calculate EMA 50
        ema_50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        
        # LONG position - exit if close below EMA 50
        if direction == 'LONG' and current_price < ema_50:
            return (True, f"Price broke below EMA50 ({ema_50:.2f})")
        
        # SHORT position - exit if close above EMA 50
        if direction == 'SHORT' and current_price > ema_50:
            return (True, f"Price broke above EMA50 ({ema_50:.2f})")
        
        return (False, "")
    
    def _check_momentum_exhaustion(self, position: Dict, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check if momentum is exhausted (RSI extremes)
        """
        direction = position['direction']
        
        if len(df) < 14:
            return (False, "")
        
        # Calculate RSI
        rsi = self._calculate_rsi(df, 14)
        
        # LONG position - exit if RSI overbought
        if direction == 'LONG' and rsi > self.rsi_overbought:
            return (True, f"RSI overbought ({rsi:.1f}) - momentum exhausted")
        
        # SHORT position - exit if RSI oversold
        if direction == 'SHORT' and rsi < self.rsi_oversold:
            return (True, f"RSI oversold ({rsi:.1f}) - momentum exhausted")
        
        return (False, "")
    
    def _check_adverse_patterns(self, position: Dict, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check for adverse candlestick patterns
        
        - Engulfing against position
        - Large rejection wicks
        """
        if len(df) < 3:
            return (False, "")
        
        direction = position['direction']
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Bearish engulfing (exit LONG)
        if direction == 'LONG':
            if (current['open'] > previous['close'] and 
                current['close'] < previous['open'] and
                current['close'] < current['open']):  # Bearish candle
                
                body_current = abs(current['close'] - current['open'])
                body_previous = abs(previous['close'] - previous['open'])
                
                if body_current > body_previous * 1.2:  # 20% larger
                    return (True, "Bearish engulfing pattern detected")
        
        # Bullish engulfing (exit SHORT)
        if direction == 'SHORT':
            if (current['open'] < previous['close'] and 
                current['close'] > previous['open'] and
                current['close'] > current['open']):  # Bullish candle
                
                body_current = abs(current['close'] - current['open'])
                body_previous = abs(previous['close'] - previous['open'])
                
                if body_current > body_previous * 1.2:
                    return (True, "Bullish engulfing pattern detected")
        
        # Check for large rejection wick
        high = current['high']
        low = current['low']
        open_price = current['open']
        close = current['close']
        
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        body = abs(close - open_price)
        
        # LONG - large upper wick = rejection
        if direction == 'LONG' and body > 0:
            if upper_wick > body * 2:
                return (True, "Large rejection wick at highs")
        
        # SHORT - large lower wick = rejection
        if direction == 'SHORT' and body > 0:
            if lower_wick > body * 2:
                return (True, "Large rejection wick at lows")
        
        return (False, "")
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI"""
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = -delta.where(delta < 0, 0).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def close_position(self, position_ticket: int, reason: str) -> bool:
        """
        Close position immediately
        
        Args:
            position_ticket: MT5 position ticket
            reason: Reason for exit
            
        Returns:
            True if closed successfully
        """
        position = mt5.positions_get(ticket=position_ticket)
        if not position or len(position) == 0:
            return False
        
        pos = position[0]
        symbol = pos.symbol
        volume = pos.volume
        
        # Determine close order type
        if pos.type == mt5.ORDER_TYPE_BUY:
            close_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            close_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask
        
        # Close request
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': close_type,
            'position': position_ticket,
            'price': price,
            'deviation': 10,
            'magic': 202602,
            'comment': f'Dynamic_Exit: {reason}',
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.info(f"Position {position_ticket} closed: {reason}")
            return True
        else:
            self.logger.error(f"Failed to close {position_ticket}: {result.comment}")
            return False
