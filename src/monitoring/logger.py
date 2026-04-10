"""
APEX FX Trading Bot - Structured Logging
Section 6: Monitoring Layer - Structured JSON logs
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import sys


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class TradeLogger:
    """Specialized logger for trade events"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.trade_logger = self._setup_logger('apex.trades', 'trades.log')
        self.signal_logger = self._setup_logger('apex.signals', 'signals.log')
        self.risk_logger = self._setup_logger('apex.risk', 'risk.log')
        self.error_logger = self._setup_logger('apex.errors', 'errors.log')
    
    def _setup_logger(self, name: str, filename: str) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        file_handler = logging.FileHandler(self.log_dir / filename)
        file_handler.setFormatter(JsonFormatter())
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def log_trade(self, action: str, symbol: str, direction: str, 
                  lots: float, entry: float, sl: float = None, tp: float = None,
                  metadata: Dict = None):
        """Log trade event"""
        data = {
            'action': action,  # OPEN, CLOSE, MODIFY
            'symbol': symbol,
            'direction': direction,
            'lots': lots,
            'entry_price': entry,
            'sl': sl,
            'tp': tp,
            'metadata': metadata or {}
        }
        self.trade_logger.info(json.dumps(data), extra={'extra_fields': data})
    
    def log_signal(self, symbol: str, strategy: str, direction: str,
                   confidence: int, regime: str, reason: str = ""):
        """Log trading signal"""
        data = {
            'symbol': symbol,
            'strategy': strategy,
            'direction': direction,
            'confidence': confidence,
            'regime': regime,
            'reason': reason
        }
        self.signal_logger.info(json.dumps(data), extra={'extra_fields': data})
    
    def log_risk_event(self, event_type: str, details: Dict):
        """Log risk event (circuit breaker, drawdown, etc.)"""
        data = {
            'event_type': event_type,
            'details': details
        }
        self.risk_logger.warning(json.dumps(data), extra={'extra_fields': data})
    
    def log_error(self, error: str, context: Dict = None):
        """Log error"""
        data = {
            'error': error,
            'context': context or {}
        }
        self.error_logger.error(json.dumps(data), extra={'extra_fields': data})


_trade_logger = None


def get_trade_logger(log_dir: str = "logs") -> TradeLogger:
    """Get global trade logger instance"""
    global _trade_logger
    if _trade_logger is None:
        _trade_logger = TradeLogger(log_dir)
    return _trade_logger


import logging

_logger = None


def get_logger(name: str = "apex") -> logging.Logger:
    """Get global logger instance"""
    global _logger
    if _logger is None:
        _logger = logging.getLogger(name)
        if not _logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            _logger.addHandler(handler)
            _logger.setLevel(logging.INFO)
    return _logger