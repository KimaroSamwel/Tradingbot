"""
APEX FX Trading Bot - Telegram Alert System
Section 8.2: Monitoring & Alerting
Real-time trade alerts, circuit breakers, daily reports
"""

import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, time
from dataclasses import dataclass
from enum import Enum
import json


class AlertType(Enum):
    TRADE_OPEN = "TRADE_OPEN"
    TRADE_CLOSE = "TRADE_CLOSE"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    TAKE_PROFIT_HIT = "TAKE_PROFIT_HIT"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    ERROR = "ERROR"
    DAILY_REPORT = "DAILY_REPORT"
    HEARTBEAT = "HEARTBEAT"
    SIGNAL = "SIGNAL"


@dataclass
class TradeAlert:
    """Trade alert message"""
    alert_type: AlertType
    symbol: str
    direction: str
    entry_price: float
    lots: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    pnl: Optional[float] = None
    reason: Optional[str] = None
    timestamp: datetime = None


class TelegramAlert:
    """
    PRD Section 8.2 - Telegram Bot Alerts:
    - Trade open/close notifications
    - Stop-loss/take-profit triggers
    - Circuit breaker activation
    - Daily performance summary
    - Health heartbeat (every 5 min)
    """
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else None
        self.enabled = bool(bot_token and chat_id)
        
        self.last_heartbeat = None
        self.heartbeat_interval = 300  # 5 minutes
        self.daily_report_time = time(22, 0)  # 22:00 UTC
    
    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Send a message via Telegram"""
        if not self.enabled:
            print(f"[TELEGRAM DISABLED] {message}")
            return False
        
        try:
            url = f"{self.api_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram send error: {e}")
            return False
    
    def send_trade_alert(self, alert: TradeAlert) -> bool:
        """Send trade-related alert"""
        emoji = "📈" if alert.direction == "BUY" else "📉"
        
        if alert.alert_type == AlertType.TRADE_OPEN:
            message = f"{emoji} *TRADE OPEN*\n\n"
            message += f"Pair: `{alert.symbol}`\n"
            message += f"Direction: {alert.direction}\n"
            message += f"Entry: {alert.entry_price:.5f}\n"
            message += f"Lots: {alert.lots}\n"
            if alert.sl:
                message += f"SL: {alert.sl:.5f}\n"
            if alert.tp:
                message += f"TP: {alert.tp:.5f}\n"
            message += f"\n_Time: {alert.timestamp.strftime('%H:%M UTC')}_"
            
        elif alert.alert_type == AlertType.TRADE_CLOSE:
            pnl_str = f"${alert.pnl:.2f}" if alert.pnl else "N/A"
            emoji_pnl = "✅" if alert.pnl and alert.pnl > 0 else "❌"
            message = f"{emoji_pnl} *TRADE CLOSED*\n\n"
            message += f"Pair: `{alert.symbol}`\n"
            message += f"Direction: {alert.direction}\n"
            message += f"Exit: {alert.entry_price:.5f}\n"
            message += f"P&L: {pnl_str}\n"
            if alert.reason:
                message += f"Reason: {alert.reason}\n"
            message += f"\n_Time: {alert.timestamp.strftime('%H:%M UTC')}_"
            
        elif alert.alert_type == AlertType.STOP_LOSS_HIT:
            message = f"🔴 *STOP LOSS HIT*\n\n"
            message += f"Pair: `{alert.symbol}`\n"
            message += f"P&L: ${alert.pnl:.2f}\n"
            message += f"\n_Time: {alert.timestamp.strftime('%H:%M UTC')}_"
            
        elif alert.alert_type == AlertType.TAKE_PROFIT_HIT:
            message = f"🟢 *TAKE PROFIT HIT*\n\n"
            message += f"Pair: `{alert.symbol}`\n"
            message += f"P&L: ${alert.pnl:.2f}\n"
            message += f"\n_Time: {alert.timestamp.strftime('%H:%M UTC')}_"
        
        else:
            message = f"⚠️ *ALERT*: {alert.alert_type.value}\n{alert.symbol}"
        
        return self.send_message(message)
    
    def send_circuit_breaker_alert(self, reason: str, duration_hours: int) -> bool:
        """Send circuit breaker activation alert - PRD Section 8.2"""
        message = f"🚨 *CIRCUIT BREAKER ACTIVATED*\n\n"
        message += f"Reason: {reason}\n"
        message += f"Duration: {duration_hours} hours\n"
        message += f"\n_All trading paused. Manual review required._"
        
        return self.send_message(message)
    
    def send_error_alert(self, error_msg: str, context: str = "") -> bool:
        """Send error notification"""
        message = f"❌ *SYSTEM ERROR*\n\n"
        message += f"Error: {error_msg}\n"
        if context:
            message += f"Context: {context}\n"
        message += f"\n_Time: {datetime.now().strftime('%H:%M UTC')}_"
        
        return self.send_message(message)
    
    def send_daily_report(self, stats: Dict[str, Any]) -> bool:
        """Send daily performance report - PRD Section 8.2"""
        message = "📊 *DAILY PERFORMANCE REPORT*\n\n"
        message += f"📅 Date: {stats.get('date', 'N/A')}\n\n"
        message += f"💰 *Account*\n"
        message += f"  Balance: ${stats.get('balance', 0):.2f}\n"
        message += f"  Equity: ${stats.get('equity', 0):.2f}\n"
        message += f"  P&L: ${stats.get('daily_pnl', 0):.2f}\n\n"
        
        message += f"📈 *Trades*\n"
        message += f"  Total: {stats.get('total_trades', 0)}\n"
        message += f"  Wins: {stats.get('wins', 0)}\n"
        message += f"  Losses: {stats.get('losses', 0)}\n"
        message += f"  Win Rate: {stats.get('win_rate', 0):.1f}%\n\n"
        
        message += f"📉 *Risk*\n"
        message += f"  Drawdown: {stats.get('drawdown_pct', 0):.1f}%\n"
        message += f"  Max Drawdown: {stats.get('max_drawdown_pct', 0):.1f}%\n"
        
        return self.send_message(message)
    
    def send_heartbeat(self) -> bool:
        """Send health heartbeat - PRD Section 8.2"""
        now = datetime.now()
        
        if self.last_heartbeat:
            elapsed = (now - self.last_heartbeat).total_seconds()
            if elapsed < self.heartbeat_interval:
                return True
        
        self.last_heartbeat = now
        message = f"💚 *HEARTBEAT*\n\n"
        message += f"Status: Online\n"
        message += f"Time: {now.strftime('%H:%M:%S UTC')}\n"
        message += f"MT5: Connected\n"
        
        return self.send_message(message)
    
    def send_signal_alert(self, signal: Dict) -> bool:
        """Send trading signal notification"""
        emoji = "🟢" if signal.get('direction') == 'BUY' else "🔴"
        message = f"📡 *SIGNAL DETECTED*\n\n"
        message += f"{emoji} {signal.get('symbol')} {signal.get('direction')}\n\n"
        message += f"Strategy: {signal.get('strategy', 'N/A')}\n"
        message += f"Confidence: {signal.get('confidence', 0)}%\n"
        message += f"Entry: {signal.get('entry', 'N/A')}\n"
        if signal.get('reason'):
            message += f"Reason: {signal.get('reason')}\n"
        
        return self.send_message(message)


_telegram_alert = None


def get_telegram_alert(bot_token: str = None, chat_id: str = None) -> TelegramAlert:
    """Get global Telegram alert instance"""
    global _telegram_alert
    if _telegram_alert is None:
        _telegram_alert = TelegramAlert(bot_token, chat_id)
    return _telegram_alert