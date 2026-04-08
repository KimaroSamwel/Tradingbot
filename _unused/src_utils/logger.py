"""
Professional Logging System
Structured logging for trading operations
"""

import logging
import os
from datetime import datetime
from typing import Dict, Optional
import json


def setup_logger(name: str = 'TradingBot', log_dir: str = 'data/logs') -> logging.Logger:
    """
    Setup professional logging system
    
    Args:
        name: Logger name
        log_dir: Directory for log files
    
    Returns:
        Configured logger
    """
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        return logger
    
    log_file = os.path.join(log_dir, f'trading_{datetime.now().strftime("%Y%m%d")}.log')
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def log_trade(logger: logging.Logger, trade_data: Dict, log_dir: str = 'data/logs/trades'):
    """
    Log trade details to JSON file
    
    Args:
        logger: Logger instance
        trade_data: Trade information
        log_dir: Directory for trade logs
    """
    os.makedirs(log_dir, exist_ok=True)
    
    trade_file = os.path.join(log_dir, f'trades_{datetime.now().strftime("%Y%m")}.json')
    
    try:
        if os.path.exists(trade_file):
            with open(trade_file, 'r') as f:
                trades = json.load(f)
        else:
            trades = []
        
        trade_data['logged_at'] = datetime.now().isoformat()
        trades.append(trade_data)
        
        with open(trade_file, 'w') as f:
            json.dump(trades, f, indent=2)
        
        logger.info(f"Trade logged: {trade_data.get('action', 'UNKNOWN')} {trade_data.get('symbol', 'UNKNOWN')}")
    
    except Exception as e:
        logger.error(f"Failed to log trade: {e}")
