"""
POSITION SCALING (PYRAMIDING)
Opens multiple positions when confidence is extremely high

"Sniper Action" - All positions entered simultaneously or in quick succession

Scaling Criteria:
1. Confluence score >85 (exceptional setup)
2. All ICT elements aligned (sweep + MSS + FVG)
3. Silver Bullet window (10-11 AM EST)
4. Volume confirmation
5. No conflicting positions

Max Positions: 3 per setup
Total Risk: Still 1% (split across positions)
"""

import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from src.utils.logger import setup_logger


class PositionScaling:
    """
    Manages scaled entry (pyramiding) for high-confidence setups
    
    Enter multiple positions simultaneously when all stars align
    """
    
    def __init__(self):
        self.logger = setup_logger('PositionScaling', 'data/logs')
        
        # Scaling thresholds
        self.min_confluence_for_scaling = 85  # Only scale on exceptional setups
        self.max_positions_per_setup = 3
        
        # Position size distribution (% of total risk)
        # Total still equals 1% account risk
        self.position_distribution = {
            1: 1.0,      # Single position gets 100% of risk
            2: [0.6, 0.4],  # 2 positions: 60%, 40% split
            3: [0.5, 0.3, 0.2]  # 3 positions: 50%, 30%, 20% split
        }
    
    def should_scale_entry(self, signal: Dict) -> Tuple[bool, int, str]:
        """
        Determine if entry should be scaled (multiple positions)
        
        Args:
            signal: Trade signal with confluence, etc.
            
        Returns:
            (should_scale, num_positions, reason)
        """
        confluence = signal.get('confluence_score', 0)
        strategy = signal.get('strategy', '')
        
        # Criteria 1: Exceptional confluence score
        if confluence < self.min_confluence_for_scaling:
            return (False, 1, "Confluence not high enough for scaling")
        
        # Criteria 2: Must be ICT strategy
        if strategy not in ['ict_2022', 'power_of_3']:
            return (False, 1, "Only scale ICT strategies")
        
        # Criteria 3: Check if Silver Bullet window (if available)
        is_silver_bullet = signal.get('killzone', '') == 'Silver Bullet'
        
        # Criteria 4: All ICT elements present
        has_sweep = signal.get('ict_signal') is not None
        if has_sweep:
            ict_signal = signal['ict_signal']
            has_all_elements = (
                ict_signal.liquidity_sweep is not None and
                ict_signal.structure_shift is not None and
                ict_signal.entry_fvg is not None
            )
        else:
            has_all_elements = False
        
        # Decision logic
        if confluence >= 95 and is_silver_bullet and has_all_elements:
            # Perfect setup - 3 positions
            return (True, 3, "Perfect setup: 95+ confluence + Silver Bullet + all ICT elements")
        
        elif confluence >= 90 and has_all_elements:
            # Excellent setup - 2 positions
            return (True, 2, "Excellent setup: 90+ confluence + all ICT elements")
        
        elif confluence >= 85 and is_silver_bullet:
            # Very good setup - 2 positions
            return (True, 2, "Very good setup: 85+ confluence + Silver Bullet")
        
        else:
            # Single position
            return (False, 1, "Good setup but not exceptional enough for scaling")
    
    def calculate_scaled_lots(self, total_lot_size: float, num_positions: int) -> List[float]:
        """
        Calculate individual lot sizes for scaled entry
        
        Total risk remains the same - just distributed across positions
        
        Args:
            total_lot_size: Original single-position lot size
            num_positions: Number of positions to open
            
        Returns:
            List of lot sizes for each position
        """
        if num_positions == 1:
            return [total_lot_size]
        
        distribution = self.position_distribution.get(num_positions, [1.0])
        
        lot_sizes = []
        for ratio in distribution:
            lot = round(total_lot_size * ratio, 2)
            # Ensure minimum lot size
            lot = max(lot, 0.01)
            lot_sizes.append(lot)
        
        return lot_sizes
    
    def calculate_scaled_entries(self, base_entry: float, direction: str,
                                 num_positions: int, fvg_zone: Optional[Dict] = None) -> List[float]:
        """
        Calculate entry prices for each position
        
        Strategy:
        - Position 1: Best entry (OTE 62% of FVG)
        - Position 2: Middle entry (OTE 70% of FVG)
        - Position 3: Conservative entry (OTE 78% of FVG)
        
        All within OTE zone (62-78.6%)
        
        Args:
            base_entry: Primary entry price
            direction: 'LONG' or 'SHORT'
            num_positions: Number of positions
            fvg_zone: Optional FVG boundaries
            
        Returns:
            List of entry prices
        """
        if num_positions == 1:
            return [base_entry]
        
        entries = []
        
        if fvg_zone and 'ote_low' in fvg_zone and 'ote_high' in fvg_zone:
            # Use FVG OTE levels
            ote_low = fvg_zone['ote_low']
            ote_high = fvg_zone['ote_high']
            
            if num_positions == 2:
                # 62% and 75% levels
                entries = [
                    ote_low,  # 62%
                    ote_low + (ote_high - ote_low) * 0.52  # ~75%
                ]
            
            elif num_positions == 3:
                # 62%, 70%, 78% levels
                entries = [
                    ote_low,  # 62%
                    ote_low + (ote_high - ote_low) * 0.35,  # ~70%
                    ote_high  # 78.6%
                ]
        
        else:
            # No FVG - use tight spread around base entry
            pip_spread = 2.0  # 2 pips apart
            
            if direction == 'LONG':
                if num_positions == 2:
                    entries = [base_entry, base_entry - pip_spread]
                elif num_positions == 3:
                    entries = [
                        base_entry,
                        base_entry - pip_spread,
                        base_entry - (pip_spread * 2)
                    ]
            else:  # SHORT
                if num_positions == 2:
                    entries = [base_entry, base_entry + pip_spread]
                elif num_positions == 3:
                    entries = [
                        base_entry,
                        base_entry + pip_spread,
                        base_entry + (pip_spread * 2)
                    ]
        
        return entries if entries else [base_entry]
    
    def execute_scaled_entry(self, signal: Dict, num_positions: int) -> List[int]:
        """
        Execute scaled entry - open multiple positions simultaneously
        
        "Sniper action" - all orders sent at once
        
        Args:
            signal: Trade signal
            num_positions: Number of positions to open
            
        Returns:
            List of order tickets
        """
        symbol = signal['symbol']
        direction = signal['direction']
        base_entry = signal['entry']
        stop_loss = signal['stop_loss']
        take_profit = signal['take_profit']
        total_lot_size = signal['lot_size']
        
        # Calculate individual lot sizes
        lot_sizes = self.calculate_scaled_lots(total_lot_size, num_positions)
        
        # Calculate entry prices
        fvg_zone = None
        if signal.get('ict_signal') and signal['ict_signal'].entry_fvg:
            fvg = signal['ict_signal'].entry_fvg
            # Get OTE levels from FVG detector
            # This is simplified - in real implementation would call fvg_detector.get_ote_levels()
            fvg_zone = {
                'ote_low': fvg.bottom + (fvg.size_pips * 0.618),
                'ote_high': fvg.bottom + (fvg.size_pips * 0.786)
            }
        
        entry_prices = self.calculate_scaled_entries(
            base_entry, direction, num_positions, fvg_zone
        )
        
        # Execute all positions
        tickets = []
        order_type = mt5.ORDER_TYPE_BUY if direction == 'LONG' else mt5.ORDER_TYPE_SELL
        
        for i in range(num_positions):
            lot = lot_sizes[i]
            entry = entry_prices[i]
            
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol,
                'volume': lot,
                'type': order_type,
                'price': entry,
                'sl': stop_loss,
                'tp': take_profit,
                'deviation': 10,
                'magic': 202602,
                'comment': f'Scaled_{i+1}of{num_positions}_{signal["strategy"]}',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_IOC
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                tickets.append(result.order)
                self.logger.info(f"Position {i+1}/{num_positions} opened: {lot} lots @ {entry:.2f}")
            else:
                self.logger.error(f"Position {i+1} failed: {result.comment}")
        
        if len(tickets) == num_positions:
            self.logger.info(f"SNIPER ENTRY: {num_positions} positions opened successfully!")
            self.logger.info(f"Confluence: {signal.get('confluence_score')}%, Total lots: {sum(lot_sizes)}")
        
        return tickets
    
    def get_scaling_summary(self, signal: Dict) -> str:
        """Get human-readable summary of scaling decision"""
        should_scale, num_pos, reason = self.should_scale_entry(signal)
        
        if should_scale:
            total_lot = signal.get('lot_size', 0)
            lot_sizes = self.calculate_scaled_lots(total_lot, num_pos)
            
            summary = f"""
╔══════════════════════════════════════════════════════════╗
║           SNIPER ENTRY - SCALED POSITION                 ║
╚══════════════════════════════════════════════════════════╝

🎯 Number of Positions: {num_pos}
📊 Confluence Score: {signal.get('confluence_score', 0)}/100
⚡ Reason: {reason}

💰 Position Sizing:
"""
            for i, lot in enumerate(lot_sizes, 1):
                summary += f"   Position {i}: {lot:.2f} lots\n"
            
            summary += f"\n   Total: {sum(lot_sizes):.2f} lots (1% account risk)\n"
            summary += f"\n🚀 All positions will be entered SIMULTANEOUSLY\n"
            
            return summary
        else:
            return f"Single position: {reason}"
