"""
TRADING PSYCHOLOGY & DISCIPLINE MODULE
Section I.D - Psychology & Discipline
- Cognitive Bias Detection & Mitigation
- Emotional Control Monitoring
- Trading Journal & Systematic Review
- Discipline Enforcement
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import os


class CognitiveBias(Enum):
    """Common cognitive biases in trading"""
    OVERCONFIDENCE = "overconfidence"
    LOSS_AVERSION = "loss_aversion"
    CONFIRMATION = "confirmation_bias"
    RECENCY = "recency_bias"
    ANCHORING = "anchoring"
    GAMBLER_FALLACY = "gamblers_fallacy"
    REVENGE_TRADING = "revenge_trading"
    FOMO = "fear_of_missing_out"


class EmotionalState(Enum):
    """Emotional states that affect trading"""
    CALM = "calm"
    CONFIDENT = "confident"
    ANXIOUS = "anxious"
    GREEDY = "greedy"
    FEARFUL = "fearful"
    FRUSTRATED = "frustrated"
    EUPHORIC = "euphoric"
    REGRETFUL = "regretful"


@dataclass
class TradeJournalEntry:
    """Complete trade journal entry"""
    trade_id: int
    timestamp: datetime
    pair: str
    action: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    profit_loss: float
    duration_minutes: int
    
    emotional_state_entry: EmotionalState
    emotional_state_exit: EmotionalState
    confidence_level: int
    
    technical_reason: str
    fundamental_support: bool
    risk_reward_ratio: float
    position_size_method: str
    
    followed_plan: bool
    rule_violations: List[str]
    lessons_learned: str
    
    account_balance_before: float
    account_balance_after: float
    consecutive_wins_before: int
    consecutive_losses_before: int


class BiasDetector:
    """Detect cognitive biases in real-time"""
    
    def __init__(self):
        self.trade_history = []
        self.recent_decisions = []
    
    def detect_overconfidence(self, confidence: int, actual_win_rate: float) -> Optional[str]:
        """Detect overconfidence bias"""
        if confidence >= 8 and actual_win_rate < 0.50:
            return f"⚠️ OVERCONFIDENCE: You rated confidence {confidence}/10 but win rate is {actual_win_rate*100:.0f}%"
        return None
    
    def detect_loss_aversion(self, open_positions: List[Dict]) -> Optional[str]:
        """Detect loss aversion (holding losers too long)"""
        if not open_positions:
            return None
        
        holding_losers = []
        for pos in open_positions:
            if 'unrealized_pl' in pos and pos['unrealized_pl'] < -pos.get('initial_risk', 0) * 1.5:
                holding_losers.append(pos['pair'])
        
        if holding_losers:
            return f"⚠️ LOSS AVERSION: Holding losing positions past acceptable loss: {', '.join(holding_losers)}"
        
        return None
    
    def detect_recency_bias(self, recent_trades: List[TradeJournalEntry]) -> Optional[str]:
        """Detect recency bias (overweighting recent results)"""
        if len(recent_trades) < 5:
            return None
        
        last_3 = recent_trades[-3:]
        last_3_wins = sum(1 for t in last_3 if t.profit_loss > 0)
        
        if last_3_wins == 3:
            return "⚠️ RECENCY BIAS: 3 consecutive wins. Don't let success make you reckless!"
        elif last_3_wins == 0:
            return "⚠️ RECENCY BIAS: 3 consecutive losses. Don't let fear stop good setups!"
        
        return None
    
    def detect_revenge_trading(self, last_trade: TradeJournalEntry, 
                              current_decision_time: datetime) -> Optional[str]:
        """Detect revenge trading"""
        if last_trade.profit_loss >= 0:
            return None
        
        time_since_loss = (current_decision_time - last_trade.timestamp).total_seconds() / 60
        
        if time_since_loss < 15:
            return "⚠️ REVENGE TRADING RISK: Trading immediately after loss. Take a break!"
        
        return None
    
    def detect_gamblers_fallacy(self, recent_trades: List[TradeJournalEntry]) -> Optional[str]:
        """Detect gambler's fallacy"""
        if len(recent_trades) < 4:
            return None
        
        last_4 = recent_trades[-4:]
        last_4_results = [1 if t.profit_loss > 0 else 0 for t in last_4]
        
        if sum(last_4_results) == 4:
            return "⚠️ GAMBLER'S FALLACY: 4 wins in a row. Each trade is independent!"
        elif sum(last_4_results) == 0:
            return "⚠️ GAMBLER'S FALLACY: 4 losses in a row. You're not 'due' for a win!"
        
        return None
    
    def check_all_biases(self, context: Dict) -> List[str]:
        """Check for all cognitive biases"""
        warnings = []
        
        if 'confidence' in context and 'win_rate' in context:
            warning = self.detect_overconfidence(context['confidence'], context['win_rate'])
            if warning:
                warnings.append(warning)
        
        if 'open_positions' in context:
            warning = self.detect_loss_aversion(context['open_positions'])
            if warning:
                warnings.append(warning)
        
        if 'recent_trades' in context:
            warning = self.detect_recency_bias(context['recent_trades'])
            if warning:
                warnings.append(warning)
        
        if 'last_trade' in context and 'current_time' in context:
            warning = self.detect_revenge_trading(context['last_trade'], context['current_time'])
            if warning:
                warnings.append(warning)
        
        if 'recent_trades' in context:
            warning = self.detect_gamblers_fallacy(context['recent_trades'])
            if warning:
                warnings.append(warning)
        
        return warnings


class DisciplineEnforcer:
    """Enforces trading plan discipline"""
    
    def __init__(self, trading_plan: Dict):
        self.plan = trading_plan
        self.violations = []
    
    def check_trading_hours(self, current_time: datetime) -> Tuple[bool, str]:
        """Check if current time is within allowed trading hours"""
        if 'trading_hours' not in self.plan:
            return (True, "No time restrictions")
        
        current_hour = current_time.hour
        allowed_hours = self.plan['trading_hours']
        
        if current_hour not in allowed_hours:
            return (False, f"Outside trading hours. Allowed: {allowed_hours}")
        
        return (True, "Within trading hours")
    
    def check_max_trades_per_day(self, trades_today: int) -> Tuple[bool, str]:
        """Check if max daily trades reached"""
        max_trades = self.plan.get('max_trades_per_day', 999)
        
        if trades_today >= max_trades:
            return (False, f"Max daily trades reached: {trades_today}/{max_trades}")
        
        return (True, f"Trades today: {trades_today}/{max_trades}")
    
    def check_max_positions(self, current_positions: int) -> Tuple[bool, str]:
        """Check if max open positions reached"""
        max_positions = self.plan.get('max_open_positions', 5)
        
        if current_positions >= max_positions:
            return (False, f"Max positions reached: {current_positions}/{max_positions}")
        
        return (True, f"Positions: {current_positions}/{max_positions}")
    
    def check_risk_limits(self, new_risk: float, total_risk: float,
                         account_balance: float) -> Tuple[bool, str]:
        """Check if risk limits exceeded"""
        max_risk_per_trade = self.plan.get('max_risk_per_trade_pct', 2.0) / 100
        max_portfolio_risk = self.plan.get('max_portfolio_risk_pct', 5.0) / 100
        
        risk_pct = new_risk / account_balance
        if risk_pct > max_risk_per_trade:
            return (False, f"Trade risk too high: {risk_pct*100:.1f}% > {max_risk_per_trade*100:.1f}%")
        
        total_risk_pct = (total_risk + new_risk) / account_balance
        if total_risk_pct > max_portfolio_risk:
            return (False, f"Portfolio risk too high: {total_risk_pct*100:.1f}% > {max_portfolio_risk*100:.1f}%")
        
        return (True, "Risk within limits")
    
    def check_min_risk_reward(self, rr_ratio: float) -> Tuple[bool, str]:
        """Check if risk-reward ratio meets minimum"""
        min_rr = self.plan.get('min_risk_reward_ratio', 1.5)
        
        if rr_ratio < min_rr:
            return (False, f"R:R too low: {rr_ratio:.2f} < {min_rr:.2f}")
        
        return (True, f"R:R acceptable: {rr_ratio:.2f}")
    
    def enforce_all_rules(self, trade_context: Dict) -> Tuple[bool, List[str]]:
        """Enforce all trading plan rules"""
        violations = []
        
        checks = [
            self.check_trading_hours(trade_context.get('current_time', datetime.now())),
            self.check_max_trades_per_day(trade_context.get('trades_today', 0)),
            self.check_max_positions(trade_context.get('current_positions', 0)),
            self.check_risk_limits(
                trade_context.get('new_risk', 0),
                trade_context.get('total_risk', 0),
                trade_context.get('account_balance', 10000)
            ),
            self.check_min_risk_reward(trade_context.get('risk_reward_ratio', 0))
        ]
        
        for can_proceed, message in checks:
            if not can_proceed:
                violations.append(message)
        
        can_trade = len(violations) == 0
        return (can_trade, violations)


class TradingJournal:
    """Complete trading journal system"""
    
    def __init__(self, journal_file: str = "data/logs/trading_journal.json"):
        self.journal_file = journal_file
        self.entries = []
        self.load_journal()
    
    def add_entry(self, entry: TradeJournalEntry):
        """Add journal entry"""
        self.entries.append(entry)
        self.save_journal()
    
    def save_journal(self):
        """Save journal to file"""
        try:
            os.makedirs(os.path.dirname(self.journal_file), exist_ok=True)
            
            entries_dict = []
            for entry in self.entries:
                entry_dict = {
                    'trade_id': entry.trade_id,
                    'timestamp': entry.timestamp.isoformat(),
                    'pair': entry.pair,
                    'action': entry.action,
                    'entry_price': entry.entry_price,
                    'exit_price': entry.exit_price,
                    'profit_loss': entry.profit_loss,
                    'emotional_state_entry': entry.emotional_state_entry.value,
                    'emotional_state_exit': entry.emotional_state_exit.value,
                    'confidence_level': entry.confidence_level,
                    'followed_plan': entry.followed_plan,
                    'rule_violations': entry.rule_violations,
                    'lessons_learned': entry.lessons_learned
                }
                entries_dict.append(entry_dict)
            
            with open(self.journal_file, 'w') as f:
                json.dump(entries_dict, f, indent=2)
        except Exception as e:
            print(f"Error saving journal: {e}")
    
    def load_journal(self):
        """Load journal from file"""
        try:
            with open(self.journal_file, 'r') as f:
                data = json.load(f)
                print(f"Loaded {len(data)} journal entries")
        except FileNotFoundError:
            print("No existing journal found, starting fresh")
        except Exception as e:
            print(f"Error loading journal: {e}")
    
    def get_recent_analysis(self, days: int = 30) -> Dict:
        """Analyze recent trading performance"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [e for e in self.entries if e.timestamp > cutoff]
        
        if not recent:
            return {'error': 'No recent trades'}
        
        total_trades = len(recent)
        winners = [e for e in recent if e.profit_loss > 0]
        losers = [e for e in recent if e.profit_loss < 0]
        
        win_rate = len(winners) / total_trades if total_trades > 0 else 0
        avg_win = np.mean([e.profit_loss for e in winners]) if winners else 0
        avg_loss = np.mean([abs(e.profit_loss) for e in losers]) if losers else 0
        
        plan_adherence = sum(1 for e in recent if e.followed_plan) / total_trades
        avg_confidence = np.mean([e.confidence_level for e in recent])
        
        all_violations = []
        for e in recent:
            all_violations.extend(e.rule_violations)
        
        from collections import Counter
        violation_counts = Counter(all_violations)
        
        return {
            'period_days': days,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': avg_win / avg_loss if avg_loss > 0 else 0,
            'plan_adherence_rate': plan_adherence,
            'avg_confidence': avg_confidence,
            'top_violations': violation_counts.most_common(3)
        }


class PsychologyMonitor:
    """Complete psychology monitoring system"""
    
    def __init__(self, trading_plan: Dict):
        self.bias_detector = BiasDetector()
        self.discipline_enforcer = DisciplineEnforcer(trading_plan)
        self.journal = TradingJournal()
        
        # Track consecutive wins/losses
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.last_trade_result = None  # 'WIN', 'LOSS', or None
    
    def pre_trade_check(self, trade_context: Dict) -> Tuple[bool, List[str]]:
        """Complete pre-trade psychological check"""
        all_warnings = []
        
        bias_warnings = self.bias_detector.check_all_biases(trade_context)
        all_warnings.extend(bias_warnings)
        
        can_trade, violations = self.discipline_enforcer.enforce_all_rules(trade_context)
        
        if not can_trade:
            all_warnings.extend([f"🚫 {v}" for v in violations])
            return (False, all_warnings)
        
        emotional_state = trade_context.get('emotional_state')
        if emotional_state in [EmotionalState.FRUSTRATED, EmotionalState.EUPHORIC, 
                              EmotionalState.FEARFUL, EmotionalState.GREEDY]:
            all_warnings.append(f"⚠️ EMOTIONAL STATE: {emotional_state.value.upper()} - Review decision carefully")
        
        return (True, all_warnings)
    
    def record_trade_decision(self, action: str, confidence: float, strategy: str):
        """Record a trade decision (for tracking)"""
        # Simple recording method for bot integration
        pass
    
    def update_trade_result(self, profit_loss: float):
        """Update consecutive wins/losses after trade closes"""
        if profit_loss > 0:
            # Win
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.last_trade_result = 'WIN'
        else:
            # Loss
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.last_trade_result = 'LOSS'
    
    def post_trade_review(self, journal_entry: TradeJournalEntry):
        """Post-trade review and learning"""
        self.journal.add_entry(journal_entry)
        
        # Update consecutive tracking
        self.update_trade_result(journal_entry.profit_loss)
        
        if not journal_entry.followed_plan:
            print(f"\n⚠️ DISCIPLINE VIOLATION: Trade #{journal_entry.trade_id}")
            print(f"   Violations: {', '.join(journal_entry.rule_violations)}")
        
        if journal_entry.profit_loss < 0:
            print(f"\n📝 LEARNING OPPORTUNITY: Loss on {journal_entry.pair}")
            print(f"   Lesson: {journal_entry.lessons_learned}")
