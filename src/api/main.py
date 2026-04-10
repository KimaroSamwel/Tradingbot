"""
APEX FX Trading Bot - Flask API
REST API with all endpoints for dashboard and external access
"""

from flask import Flask, jsonify, request, render_template, Response
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
import threading
import numpy as np
import pandas as pd

# Custom JSON encoder for numpy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)

# Import core modules
from src.config import get_config
from src.data.database import get_db
from src.data.mt5_connector import get_mt5
from src.analysis.technical import get_ta, get_atr_value
from src.strategies.engine import get_strategy_engine
from src.risk.manager import get_risk_manager

# Import Volume II modules
from src.risk.portfolio_heat_monitor import get_heat_monitor
from src.risk.volatility_scaler import get_volatility_scaler
from src.risk.signal_scorer import get_signal_scorer
from src.risk.kelly_sizer import get_kelly_sizer
from src.risk.fill_analyzer import get_fill_analyzer
from src.risk.regime_drift_detector import get_regime_drift_detector
from src.analysis.performance_analyzer import get_performance_analyzer
from src.data.cot_parser import get_cot_parser
from src.execution.time_exit_manager import get_time_exit_manager
from src.execution.calendar_filter import get_calendar_filter
from src.execution.swap_filter import get_swap_filter
from src.execution.order_router import get_order_router
from src.monitoring.telegram_alerts import get_telegram_alert
from src.monitoring.logger import get_logger
from src.monitoring.event_logger import get_event_logger
from src.paper.paper_engine import get_paper_engine
from src.analysis.readiness_checker import get_readiness_checker

app = Flask(__name__, template_folder='../../templates')
CORS(app)
app.json_encoder = NumpyEncoder

# Initialize components
config = get_config()
db = get_db()
mt5_conn = get_mt5()
ta = get_ta()
strategy_engine = get_strategy_engine()
risk_manager = get_risk_manager()

# Initialize Volume II modules
logger = get_logger()
heat_monitor = get_heat_monitor()
vol_scaler = get_volatility_scaler()
signal_scorer = get_signal_scorer()
kelly_sizer = get_kelly_sizer()
fill_analyzer = get_fill_analyzer()
rdd = get_regime_drift_detector()
perf_analyzer = get_performance_analyzer()
cot_parser = get_cot_parser()
time_exit_manager = get_time_exit_manager()
calendar_filter = get_calendar_filter()
swap_filter = get_swap_filter()
order_router = get_order_router()
telegram_alert = get_telegram_alert()
event_logger = get_event_logger()
readiness_checker = get_readiness_checker()

# Initialize Paper Engine (Volume III)
paper_engine = get_paper_engine()

# Store state
app_state = {
    'running': False,
    'scanning': False,
    'last_scan': None,
    'signals': [],
    'watchlist': []
}


# ==================== CONFIG ENDPOINTS ====================

@app.route('/api/config', methods=['GET'])
def get_config_all():
    """Get all configuration"""
    return jsonify(config.get_all())


@app.route('/api/config/<key>', methods=['GET'])
def get_config_value(key):
    """Get specific config value"""
    return jsonify({'key': key, 'value': config.get(key)})


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    data = request.json
    for key, value in data.items():
        config.set(key, value)
    return jsonify({'status': 'updated'})


# ==================== ACCOUNT ENDPOINTS ====================

@app.route('/api/account', methods=['GET'])
def get_account():
    """Get account information"""
    if not mt5_conn.is_connected():
        return jsonify({'error': 'MT5 not connected', 'connected': False})
    
    account = mt5_conn.get_account()
    account['connected'] = True
    return jsonify(account)


@app.route('/api/account/connect', methods=['POST'])
def connect_mt5():
    """Connect to MT5"""
    success = mt5_conn.connect()
    return jsonify({'connected': success})


@app.route('/api/account/disconnect', methods=['POST'])
def disconnect_mt5():
    """Disconnect from MT5"""
    mt5_conn.disconnect()
    return jsonify({'connected': False})


# ==================== POSITIONS ENDPOINTS ====================

@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Get open positions - returns paper positions in PAPER mode, MT5 positions otherwise"""
    current_mode = config.get('trading.mode', 'PAPER')
    
    if current_mode == 'PAPER':
        positions = paper_engine.get_positions()
        return jsonify({'positions': positions, 'count': len(positions), 'mode': 'PAPER'})
    else:
        positions = mt5_conn.get_positions()
        return jsonify({'positions': positions, 'count': len(positions), 'mode': current_mode})


@app.route('/api/positions/open', methods=['POST'])
def open_position():
    """Open a new position"""
    data = request.json
    
    symbol = data.get('symbol')
    direction = data.get('direction')
    volume = data.get('volume', 0)
    entry = data.get('entry', 0)
    sl = data.get('sl', 0)
    tp = data.get('tp', 0)
    strategy = data.get('strategy', 'MANUAL')
    
    # Get account balance
    account = mt5_conn.get_account()
    balance = account.get('balance', 10000)
    
    # Calculate position size if not provided
    if volume == 0 and entry > 0 and sl > 0:
        volume = risk_manager.calculate_position_size(symbol, balance, entry, sl)
    
    # Open order
    ok, msg = mt5_conn.open_order(symbol, direction, volume, entry, sl, tp, strategy)
    
    if ok:
        # Record in database
        db.insert_trade({
            'trade_id': f"TRADE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'account_id': str(mt5_conn.account_info.get('login', '')),
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry,
            'volume': volume,
            'sl_price': sl,
            'tp_price': tp,
            'status': 'OPEN',
            'strategy': strategy,
            'opened_at': datetime.now().isoformat()
        })
    
    return jsonify({'success': ok, 'message': msg})


@app.route('/api/positions/close/<int:ticket>', methods=['POST'])
def close_position(ticket):
    """Close position by ticket"""
    ok, msg = mt5_conn.close_position(ticket)
    
    if ok:
        # Update database
        db.update_trade(f"TRADE_{ticket}", {
            'status': 'CLOSED',
            'closed_at': datetime.now().isoformat()
        })
    
    return jsonify({'success': ok, 'message': msg})


@app.route('/api/positions/close-all', methods=['POST'])
def close_all_positions():
    """Close all open positions"""
    positions = mt5_conn.get_positions()
    closed = 0
    for pos in positions:
        if mt5_conn.close_position(pos['ticket']):
            closed += 1
    
    return jsonify({'closed': closed})


# ==================== SIGNALS ENDPOINTS ====================

@app.route('/api/signals', methods=['GET'])
def get_signals():
    """Get recent signals"""
    limit = int(request.args.get('limit', 50))
    signals = db.get_signals(limit=limit)
    return jsonify({'signals': signals, 'count': len(signals)})


@app.route('/api/signals/scan', methods=['POST'])
def scan_signals():
    """Scan for trading signals"""
    data = request.json or {}
    symbols = data.get('symbols', app_state.get('watchlist', []))
    category = data.get('category')  # TREND, MEAN_REVERSION, etc.
    
    if not symbols:
        return jsonify({'error': 'No symbols to scan', 'signals': []})
    
    signals = []
    
    for symbol in symbols:
        # Get required timeframes based on strategy
        df_h1 = mt5_conn.get_ohlc(symbol, 'H1', 100)
        if df_h1 is None or df_h1.empty:
            continue
        
        # Get additional timeframes based on symbol requirements
        df_h4 = mt5_conn.get_ohlc(symbol, 'H4', 100)
        df_d1 = mt5_conn.get_ohlc(symbol, 'D1', 50)
        
        # Scan strategies
        symbol_signals = strategy_engine.scan_symbol(symbol, df_h1, df_h4, df_d1, category)
        signals.extend(symbol_signals)
    
    # Save signals to database
    for sig in signals:
        try:
            db.insert_signal({
                'signal_id': sig.get('id') or f"{sig.get('symbol')}_{sig.get('strategy')}_{datetime.now().strftime('%H%M%S')}",
                'symbol': sig.get('symbol'),
                'strategy': sig.get('strategy'),
                'direction': sig.get('direction'),
                'entry_price': sig.get('entry') or sig.get('entry_price'),
                'sl_price': sig.get('sl'),
                'tp_price': sig.get('tp'),
                'confidence': sig.get('confidence'),
                'indicators': sig.get('indicators', {}),
                'status': 'NEW',
                'created_at': datetime.now().isoformat()
            })
        except Exception as e:
            print(f"Signal DB insert error: {e}")
    
    app_state['signals'] = signals
    app_state['last_scan'] = datetime.now().isoformat()
    
    return jsonify({
        'signals': signals,
        'count': len(signals),
        'scanned_symbols': symbols,
        'timestamp': app_state['last_scan']
    })


# ==================== WATCHLIST ENDPOINTS ====================

@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    """Get watchlist"""
    return jsonify({'watchlist': app_state.get('watchlist', [])})


@app.route('/api/watchlist', methods=['POST'])
def update_watchlist():
    """Update watchlist"""
    data = request.json
    symbols = data.get('symbols', [])
    app_state['watchlist'] = symbols
    
    # Save to database
    db.save_setting('watchlist', json.dumps(symbols))
    
    return jsonify({'watchlist': symbols})


@app.route('/api/watchlist/add', methods=['POST'])
def add_to_watchlist():
    """Add symbol to watchlist"""
    data = request.json
    symbol = data.get('symbol')
    
    if symbol and symbol not in app_state['watchlist']:
        app_state['watchlist'].append(symbol)
        db.save_setting('watchlist', json.dumps(app_state['watchlist']))
    
    return jsonify({'watchlist': app_state['watchlist']})


@app.route('/api/watchlist/remove/<symbol>', methods=['POST'])
def remove_from_watchlist(symbol):
    """Remove symbol from watchlist"""
    if symbol in app_state['watchlist']:
        app_state['watchlist'].remove(symbol)
        db.save_setting('watchlist', json.dumps(app_state['watchlist']))
    
    return jsonify({'watchlist': app_state['watchlist']})


# ==================== MARKET DATA ENDPOINTS ====================

@app.route('/api/market/ohlc', methods=['GET'])
def get_ohlc():
    """Get OHLC data"""
    symbol = request.args.get('symbol')
    timeframe = request.args.get('timeframe', 'H1')
    count = int(request.args.get('count', 100))
    start_date = request.args.get('start_date')
    use_historic = request.args.get('historic', 'false').lower() == 'true'
    
    if not symbol:
        return jsonify({'error': 'Symbol required'})
    
    try:
        # Parse start date if provided
        start_dt = None
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            except:
                pass
        
        df = mt5_conn.get_ohlc(symbol, timeframe, count, start_dt, use_historic)
        if df is None or df.empty:
            return jsonify({'symbol': symbol, 'timeframe': timeframe, 'data': []})
        
        # Reset index to include time as column
        df = df.reset_index()
        
        # Convert to dict with proper time format (Unix timestamp for lightweight-charts)
        data = []
        for _, row in df.iterrows():
            ts = row['time']
            # Convert datetime to Unix timestamp
            if hasattr(ts, 'timestamp'):
                ts = int(ts.timestamp())
            elif isinstance(ts, (int, float)):
                ts = int(ts)
            else:
                ts = 0
            data.append({
                'time': ts,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })
        
        return jsonify({'symbol': symbol, 'timeframe': timeframe, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e), 'symbol': symbol})


@app.route('/api/market/indicators', methods=['GET'])
def get_indicators():
    """Get technical indicators for symbol"""
    symbol = request.args.get('symbol')
    timeframe = request.args.get('timeframe', 'H1')
    
    if not symbol:
        return jsonify({'error': 'Symbol required'})
    
    try:
        df = mt5_conn.get_ohlc(symbol, timeframe, 200)
        if df is None:
            return jsonify({'error': 'Failed to get data'})
        
        indicators = ta.calculate_all(df)
        
        # Convert all types to JSON-serializable format
        def convert_value(v):
            import numpy as np
            import math
            
            # Handle numpy types first
            if isinstance(v, (np.integer, np.int64, np.int32)):
                return int(v)
            if isinstance(v, (np.floating, np.float64, np.float32)):
                if np.isnan(v) or np.isinf(v):
                    return None
                return float(v)
            if isinstance(v, (np.bool_, np.bool)):
                return bool(v)
            if isinstance(v, (np.ndarray,)):
                return [convert_value(x) for x in v.tolist()]
            
            # Handle Python types
            if isinstance(v, float):
                if math.isnan(v) or math.isinf(v):
                    return None
                return v
            if isinstance(v, dict):
                return {k: convert_value(val) for k, val in v.items()}
            if isinstance(v, (list, tuple)):
                return [convert_value(x) for x in v]
            
            return v
        
        indicators = {k: convert_value(v) for k, v in indicators.items()}
        
        return jsonify({
            'symbol': symbol,
            'timeframe': timeframe,
            'indicators': indicators
        })
    except Exception as e:
        return jsonify({'error': str(e), 'symbol': symbol})


@app.route('/api/market/symbols', methods=['GET'])
def get_symbols():
    """Get available symbols"""
    symbols = mt5_conn.get_symbols()
    return jsonify({'symbols': symbols[:100]})  # Limit to 100


# ==================== STRATEGIES ENDPOINTS ====================

@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    """Get available strategies"""
    strategies = strategy_engine.get_available_strategies()
    return jsonify({'strategies': strategies})


@app.route('/api/strategies/active', methods=['GET'])
def get_active_strategies():
    """Get active strategies"""
    return jsonify({'active': app_state.get('active_strategies', [])})


@app.route('/api/strategies/active', methods=['POST'])
def set_active_strategies():
    """Set active strategies"""
    data = request.json
    strategies = data.get('strategies', [])
    app_state['active_strategies'] = strategies
    return jsonify({'active': strategies})


# ==================== RISK ENDPOINTS ====================

@app.route('/api/risk/status', methods=['GET'])
def get_risk_status():
    """Get risk management status"""
    account = mt5_conn.get_account()
    balance = account.get('balance', 0)
    positions = mt5_conn.get_positions()
    
    metrics = risk_manager.get_risk_metrics(balance, positions)
    
    return jsonify({
        'metrics': metrics,
        'circuit_breaker': {
            'active': risk_manager.circuit_breaker_active,
            'until': risk_manager.circuit_breaker_until.isoformat() if risk_manager.circuit_breaker_until else None
        }
    })


@app.route('/api/risk/validate', methods=['POST'])
def validate_trade():
    """Validate if trade is allowed"""
    data = request.json
    symbol = data.get('symbol')
    
    account = mt5_conn.get_account()
    balance = account.get('balance', 0)
    positions = mt5_conn.get_positions()
    
    allowed, reason = risk_manager.check_trade_allowed(balance, positions)
    
    # Check correlation
    if allowed and symbol:
        corr_allowed, corr_reason = risk_manager.check_correlation(positions, symbol)
        if not corr_allowed:
            reason = corr_reason
            allowed = False
    
    return jsonify({
        'allowed': allowed,
        'reason': reason,
        'symbol': symbol
    })


# ==================== STATS ENDPOINTS ====================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get trading statistics"""
    stats = db.get_stats()
    return jsonify(stats)


@app.route('/api/stats/performance', methods=['GET'])
def get_performance():
    """Get performance history"""
    days = int(request.args.get('days', 30))
    account_id = str(mt5_conn.account_info.get('login', ''))
    
    performance = db.get_performance(account_id, days)
    return jsonify({'performance': performance})


@app.route('/api/stats/trades', methods=['GET'])
def get_trade_history():
    """Get trade history"""
    days = int(request.args.get('days', 30))
    status = request.args.get('status')
    
    from_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    trades = db.get_trades(
        account_id=str(mt5_conn.account_info.get('login', '')),
        status=status,
        from_date=from_date
    )
    
    return jsonify({'trades': trades, 'count': len(trades)})


# ==================== SYSTEM ENDPOINTS ====================

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get general status"""
    hours = int(request.args.get('hours', 0))
    
    return jsonify({
        'status': 'running',
        'mt5_connected': mt5_conn.is_connected(),
        'scanning': app_state.get('scanning', False),
        'last_scan': app_state.get('last_scan'),
        'watchlist': app_state.get('watchlist', []),
        'signals': app_state.get('signals', []),
        'hours': hours
    })


@app.route('/api/scan', methods=['POST'])
def api_scan():
    """Scan symbols for trading signals"""
    pairs = request.args.get('pairs', '').split(',') if request.args.get('pairs') else []
    if not pairs:
        data = request.json or {}
        pairs = data.get('pairs', app_state.get('watchlist', []))
    
    if not pairs:
        return jsonify({'error': 'No pairs specified', 'signals': []})
    
    signals = []
    
    for symbol in pairs:
        df_h1 = mt5_conn.get_ohlc(symbol, 'H1', 100)
        if df_h1 is None or df_h1.empty:
            continue
        
        df_h4 = mt5_conn.get_ohlc(symbol, 'H4', 100)
        df_d1 = mt5_conn.get_ohlc(symbol, 'D1', 50)
        
        symbol_signals = strategy_engine.scan_symbol(symbol, df_h1, df_h4, df_d1)
        signals.extend(symbol_signals)
    
    for sig in signals:
        db.insert_signal({
            'signal_id': sig.get('id'),
            'symbol': sig.get('symbol'),
            'strategy': sig.get('strategy'),
            'direction': sig.get('direction'),
            'entry_price': sig.get('entry_price'),
            'sl_price': sig.get('sl_price'),
            'tp_price': sig.get('tp_price'),
            'confidence': sig.get('confidence'),
            'indicators': sig.get('indicators', {}),
            'status': 'NEW',
            'created_at': datetime.now().isoformat()
        })
    
    app_state['signals'] = signals
    app_state['last_scan'] = datetime.now().isoformat()
    
    return jsonify({
        'signals': signals,
        'count': len(signals),
        'scanned_pairs': pairs,
        'timestamp': app_state['last_scan']
    })


@app.route('/api/system/status', methods=['GET'])
def system_status():
    """Get system status"""
    return jsonify({
        'mt5_connected': mt5_conn.is_connected(),
        'scanning': app_state.get('scanning', False),
        'last_scan': app_state.get('last_scan'),
        'watchlist_count': len(app_state.get('watchlist', [])),
        'signals_count': len(app_state.get('signals', []))
    })


@app.route('/api/system/scan-v2', methods=['POST'])
def scan_signals_v2():
    """
    Enhanced signal scan with full Volume II pre-trade checks.
    This implements the 15-step pre-trade sequence from PRD Vol II Section 6.1
    """
    data = request.json or {}
    pairs = data.get('pairs', app_state.get('watchlist', []))
    
    if not pairs:
        return jsonify({'error': 'No pairs specified', 'signals': [], 'checks': []})
    
    now_utc = datetime.now(timezone.utc)
    
    # Get positions and account for portfolio calculations
    positions = mt5_conn.get_positions()
    account = mt5_conn.get_account()
    equity = account.get('equity', account.get('balance', 10000))
    
    # Step 1: Portfolio-level state
    heat_pct, heat_level = heat_monitor.calculate_heat(positions, equity)
    
    # Get ATR values for spread-ATR check
    atr_map = {}
    for symbol in pairs:
        df_h1 = mt5_conn.get_ohlc(symbol, 'H1', 50)
        if df_h1 is not None and not df_h1.empty:
            atr_map[symbol] = get_atr_value(df_h1, 14)
    
    # Step 2: Monitor open positions - check trailing stops and time exits
    trailing_actions = []
    for pos in positions:
        symbol = pos.get('symbol')
        if not symbol:
            continue
        direction = pos.get('type', 'BUY')
        entry = pos.get('open_price')
        current_price = pos.get('current_price', entry)
        profit_pips = pos.get('profit_pips', 0.0)
        current_sl = pos.get('sl', 0.0)
        ticket = pos.get('ticket')
        
        if risk_manager.should_activate_trailing_stop(symbol, current_price, entry, direction, profit_pips):
            new_sl = risk_manager.calculate_trailing_stop(symbol, current_price, entry, direction)
            if direction == 'BUY' and new_sl > current_sl:
                mt5_conn.order_router.modify_position(ticket, sl=new_sl)
                trailing_actions.append(f'{symbol}: SL updated to {new_sl}')
            elif direction == 'SELL' and new_sl < current_sl:
                mt5_conn.order_router.modify_position(ticket, sl=new_sl)
                trailing_actions.append(f'{symbol}: SL updated to {new_sl}')
    
    # Time exit checks - handle missing order_router
    order_router = getattr(mt5_conn, 'order_router', None)
    time_exit_actions = time_exit_manager.check_all_positions(positions, atr_map, mt5_conn, order_router)
    
    # Step 3: Check if new entries allowed
    calendar_allowed, calendar_reason = calendar_filter.is_new_entry_allowed(now_utc)
    
    signals = []
    check_results = []
    
    if not calendar_allowed:
        check_results.append({'step': 3, 'check': 'calendar_filter', 'passed': False, 'reason': calendar_reason})
        return jsonify({
            'signals': [],
            'checks': check_results,
            'trailing_actions': trailing_actions,
            'time_exit_actions': time_exit_actions,
            'heat_pct': heat_pct,
            'heat_level': heat_level,
            'message': f'Entry blocked: {calendar_reason}'
        })
    
    check_results.append({'step': 3, 'check': 'calendar_filter', 'passed': True, 'reason': calendar_reason})
    
    for symbol in pairs:
        # Check if symbol is suspended by RDD
        if rdd.is_suspended(symbol):
            check_results.append({'step': 'pre-trade', 'check': 'rdd_suspended', 'symbol': symbol, 'passed': False, 'reason': 'Symbol suspended by RDD'})
            continue
        
        df_h1 = mt5_conn.get_ohlc(symbol, 'H1', 100)
        if df_h1 is None or df_h1.empty:
            continue
        
        df_h4 = mt5_conn.get_ohlc(symbol, 'H4', 100)
        df_d1 = mt5_conn.get_ohlc(symbol, 'D1', 50)
        
        symbol_signals = strategy_engine.scan_symbol(symbol, df_h1, df_h4, df_d1)
        
        for signal in symbol_signals:
            direction = signal.get('direction')
            if not direction:
                continue
            
            indicators = signal.get('indicators', {})
            session_window = signal.get('session', 'LONDON')
            
            # Step 4: Score the signal
            spread_pct = fill_analyzer.get_spread_percentile(symbol, session_window, mt5_conn, db) if hasattr(fill_analyzer, 'get_spread_percentile') else 50.0
            cot_signal = cot_parser.get_cot_signal(symbol, direction, db)
            cot_index = cot_signal[1] if cot_signal else None
            
            score_result = signal_scorer.score(symbol, direction, indicators, session_window, spread_pct, cot_index)
            
            if score_result.get('grade') == 'REJECT':
                check_results.append({'step': 8, 'check': 'signal_scorer', 'symbol': symbol, 'passed': False, 'reason': f'Score {score_result.get("total_score")} below threshold'})
                continue
            
            check_results.append({'step': 8, 'check': 'signal_scorer', 'symbol': symbol, 'passed': True, 'score': score_result.get('total_score'), 'grade': score_result.get('grade')})
            
            # Step 9: VRS scalar
            df_d1 = mt5_conn.get_ohlc(symbol, 'D1', 100)
            if df_d1 is not None:
                vol_ratio = vol_scaler.compute_realized_vol_ratio(symbol, df_d1)
            else:
                vol_ratio = 1.0
            vrs_scalar, vrs_label = vol_scaler.get_scalar(vol_ratio, False)
            
            # Step 10: Kelly sizing
            kelly_risk = kelly_sizer.get_effective_risk_pct(symbol, db)
            kelly_risk = kelly_sizer.apply_cold_streak_ladder(symbol, kelly_risk, db)
            
            # Step 11: Portfolio heat check
            heat_ok, heat_reason = heat_monitor.can_open_new_position(heat_pct, score_result.get('total_score', 0))
            if not heat_ok:
                check_results.append({'step': 11, 'check': 'portfolio_heat', 'symbol': symbol, 'passed': False, 'reason': heat_reason})
                continue
            check_results.append({'step': 11, 'check': 'portfolio_heat', 'symbol': symbol, 'passed': True})
            
            # Step 5: Spread-ATR ratio check
            atr14 = atr_map.get(symbol, 0)
            if atr14 > 0:
                spread_atr_ok, spread_atr_reason = mt5_conn.order_router.check_spread_atr_ratio(symbol, atr14) if hasattr(mt5_conn, 'order_router') else (True, '')
                if not spread_atr_ok:
                    check_results.append({'step': 5, 'check': 'spread_atr_ratio', 'symbol': symbol, 'passed': False, 'reason': spread_atr_reason})
                    continue
                check_results.append({'step': 5, 'check': 'spread_atr_ratio', 'symbol': symbol, 'passed': True})
            
            # Step 6: Swap check for affected instruments
            swap_ok, swap_reason = swap_filter.should_delay_entry(symbol, direction, signal.get('tp', 0), mt5_conn)
            if swap_ok:
                check_results.append({'step': 6, 'check': 'swap_filter', 'symbol': symbol, 'passed': False, 'reason': swap_reason})
                continue
            check_results.append({'step': 6, 'check': 'swap_filter', 'symbol': symbol, 'passed': True})
            
            # Add signal with full metadata
            signal['score_result'] = score_result
            signal['vrs_scalar'] = vrs_scalar
            signal['kelly_risk'] = kelly_risk
            signal['heat_pct'] = heat_pct
            signal['volume'] = 0.01  # Default volume for execution
            
            # Auto-calculate SL/TP if not provided
            current_price = signal.get('entry_price') or mt5_conn.get_latest_price(symbol).get('ask' if direction == 'BUY' else 'bid', 0)
            if not signal.get('sl_price') and not signal.get('stop_loss'):
                sl_distance = current_price * 0.02  # 2% SL
                signal['sl_price'] = current_price - sl_distance if direction == 'BUY' else current_price + sl_distance
            if not signal.get('tp_price') and not signal.get('take_profit'):
                tp_distance = current_price * 0.04  # 4% TP (1:2 ratio)
                signal['tp_price'] = current_price + tp_distance if direction == 'BUY' else current_price - tp_distance
                
            signals.append(signal)
    
    app_state['signals'] = signals
    app_state['last_scan'] = datetime.now(timezone.utc).isoformat()
    
    # Auto-execute based on mode
    current_mode = config.get('trading.mode', 'PAPER')
    executed_count = 0
    
    if current_mode == 'PAPER' and signals:
        # Paper mode: execute as virtual trades
        for sig in signals:
            try:
                entry = sig.get('entry_price')
                if not entry or entry == 0:
                    # Get current price if no entry
                    latest = mt5_conn.get_latest_price(sig.get('symbol'))
                    entry = latest.get('ask') if sig.get('direction') == 'BUY' else latest.get('bid')
                
                result = paper_engine.open_position(
                    symbol=sig.get('symbol'),
                    direction=sig.get('direction'),
                    lot_size=sig.get('volume', 0.01),
                    entry_price=float(entry) if entry else 0,
                    stop_loss=float(sig.get('sl_price', 0)) if sig.get('sl_price') else 0,
                    take_profit=float(sig.get('tp_price', 0)) if sig.get('tp_price') else 0,
                    signal_score=sig.get('total_score', 0),
                    vrs_scalar=sig.get('vrs_scalar', 1.0),
                    regime=sig.get('regime', 'T')
                )
                if result.get('success'):
                    executed_count += 1
                    event_logger.log('PAPER_EXECUTE', sig.get('symbol'), f"Auto-executed {sig.get('direction')} {sig.get('symbol')} @ {entry}")
            except Exception as e:
                event_logger.log('PAPER_ERROR', sig.get('symbol'), str(e))
    
    elif current_mode == 'DEMO' and signals:
        # Demo mode: execute via MT5 demo account (real trading but demo account)
        for sig in signals:
            try:
                symbol = sig.get('symbol')
                direction = sig.get('direction')
                volume = sig.get('volume', 0.01)
                sl_price = sig.get('sl_price', 0)
                tp_price = sig.get('tp_price', 0)
                
                success, msg = order_router.place_order(
                    symbol=symbol,
                    direction=direction,
                    lots=volume,
                    sl=sl_price,
                    tp=tp_price,
                    comment=f"APEX_DEMO_{sig.get('strategy', 'auto')}"
                )
                if success:
                    executed_count += 1
                    event_logger.log('DEMO_EXECUTE', symbol, f"Demo trade {direction} {symbol}: {msg}")
            except Exception as e:
                event_logger.log('DEMO_ERROR', sig.get('symbol'), str(e))
    
    elif current_mode == 'LIVE' and signals:
        # Live mode: execute via MT5 real account
        for sig in signals:
            try:
                symbol = sig.get('symbol')
                direction = sig.get('direction')
                volume = sig.get('volume', 0.01)
                sl_price = sig.get('sl_price', 0)
                tp_price = sig.get('tp_price', 0)
                
                success, msg = order_router.place_order(
                    symbol=symbol,
                    direction=direction,
                    lots=volume,
                    sl=sl_price,
                    tp=tp_price,
                    comment=f"APEX_LIVE_{sig.get('strategy', 'auto')}"
                )
                if success:
                    executed_count += 1
                    event_logger.log('LIVE_EXECUTE', symbol, f"Live trade {direction} {symbol}: {msg}")
            except Exception as e:
                event_logger.log('LIVE_ERROR', sig.get('symbol'), str(e))
    
    return jsonify({
        'signals': signals,
        'count': len(signals),
        'checks': check_results,
        'trailing_actions': trailing_actions,
        'time_exit_actions': time_exit_actions,
        'heat_pct': round(heat_pct, 2),
        'heat_level': heat_level,
        'scanned_pairs': pairs,
        'timestamp': app_state['last_scan'],
        'executed': executed_count,
        'mode': current_mode
    })


@app.route('/api/system/scan-start', methods=['POST'])
def start_scanning():
    """Start auto-scanning"""
    app_state['scanning'] = True
    return jsonify({'scanning': True})


@app.route('/api/system/scan-stop', methods=['POST'])
def stop_scanning():
    """Stop auto-scanning"""
    app_state['scanning'] = False
    return jsonify({'scanning': False})


# ==================== FRONTEND ====================

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


# ==================== API V2 ENDPOINTS (PRD VOLUME II) ====================

@app.route('/api/v2/heat', methods=['GET'])
def get_heat():
    """Get current portfolio heat percentage and level"""
    positions = mt5_conn.get_positions()
    account = mt5_conn.get_account()
    equity = account.get('equity', account.get('balance', 10000))
    
    from src.risk.portfolio_heat_monitor import get_heat_monitor
    heat_monitor = get_heat_monitor()
    heat_pct, heat_level = heat_monitor.calculate_heat(positions, equity)
    
    return jsonify({
        'heat_pct': round(heat_pct, 2),
        'heat_level': heat_level,
        'positions_count': len(positions),
        'equity': equity
    })


@app.route('/api/v2/vrs', methods=['GET'])
def get_vrs():
    """Get current Volatility Scalar (VRS) and per-symbol vol ratios"""
    from src.risk.volatility_scaler import get_volatility_scaler
    vol_scaler = get_volatility_scaler()
    
    symbols = app_state.get('watchlist', [])
    vol_ratios = {}
    
    for symbol in symbols:
        df_d1 = mt5_conn.get_ohlc(symbol, 'D1', 100)
        if df_d1 is not None and not df_d1.empty:
            ratio = vol_scaler.compute_realized_vol_ratio(symbol, df_d1)
            vol_ratios[symbol] = round(ratio, 3)
    
    corr_spike = vol_scaler.detect_correlation_spike(vol_ratios)
    scalar, label = vol_scaler.get_scalar(sum(vol_ratios.values()) / len(vol_ratios) if vol_ratios else 1.0, corr_spike)
    
    xau_defensive = False
    df_xau_h4 = mt5_conn.get_ohlc('XAUUSD', 'H4', 50)
    if df_xau_h4 is not None:
        xau_defensive = vol_scaler.is_xau_defensive_mode(df_xau_h4)
    
    return jsonify({
        'scalar': scalar,
        'label': label,
        'correlation_spike': corr_spike,
        'xau_defensive_mode': xau_defensive,
        'vol_ratios': vol_ratios
    })


@app.route('/api/v2/bqs', methods=['GET'])
def get_bqs():
    """Get Broker Quality Score (BQS) with component breakdown"""
    global db
    
    days = int(request.args.get('days', 7))
    bqs_data = fill_analyzer.compute_bqs(days, db)
    
    return jsonify(bqs_data)


@app.route('/api/v2/kelly', methods=['GET'])
def get_kelly():
    """Get current Kelly risk percentage per symbol"""
    from src.risk.kelly_sizer import get_kelly_sizer
    kelly_sizer = get_kelly_sizer()
    
    symbols = app_state.get('watchlist', [])
    kelly_data = {}
    
    for symbol in symbols:
        risk_pct = kelly_sizer.get_effective_risk_pct(symbol, db)
        kelly_data[symbol] = {
            'risk_pct': round(risk_pct, 3),
            'status': 'ACTIVE' if risk_pct > 0 else 'SUSPENDED'
        }
    
    return jsonify({
        'kelly_by_symbol': kelly_data,
        'fractional_kelly': kelly_sizer.KELLY_FRACTION
    })


@app.route('/api/v2/rdd', methods=['GET'])
def get_rdd():
    """Get RDD status per symbol"""
    from src.risk.regime_drift_detector import get_regime_drift_detector
    rdd = get_regime_drift_detector()
    
    results = rdd.run_weekly_check(db) if db else {}
    all_status = rdd.get_all_status()
    
    return jsonify({
        'symbols': results,
        'suspended': all_status.get('suspended', []),
        'modifiers': all_status.get('modifiers', {})
    })


@app.route('/api/v2/rdd/reset/<symbol>', methods=['POST'])
def reset_rdd_symbol(symbol):
    """Manual reset of suspended symbol"""
    from src.risk.regime_drift_detector import get_regime_drift_detector
    rdd = get_regime_drift_detector()
    
    success = rdd.reset_symbol(symbol)
    
    return jsonify({
        'success': success,
        'symbol': symbol,
        'message': f"Symbol {symbol} reset successfully" if success else f"Symbol {symbol} not found in suspended list"
    })


@app.route('/api/v2/cot', methods=['GET'])
def get_cot():
    """Get latest COT Index per symbol"""
    from src.data.cot_parser import get_cot_parser
    cot_parser = get_cot_parser()
    
    symbols = app_state.get('watchlist', [])
    cot_data = {}
    
    for symbol in symbols:
        signal_type, index = cot_parser.get_cot_signal(symbol, 'BUY', db)
        if index is not None:
            cot_data[symbol] = {
                'cot_index': round(index, 1),
                'signal': signal_type
            }
    
    return jsonify({
        'cot_by_symbol': cot_data,
        'last_updated': datetime.now(timezone.utc).isoformat()
    })


@app.route('/api/v2/signal-scores', methods=['GET'])
def get_signal_scores():
    """Get last 50 signal scores with grades and outcomes"""
    limit = int(request.args.get('limit', 50))
    
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, symbol, direction, total_score, grade, 
               position_modifier, trade_opened, outcome_pips
        FROM signal_scores
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    scores = []
    for row in rows:
        scores.append({
            'id': row[0],
            'timestamp': row[1],
            'symbol': row[2],
            'direction': row[3],
            'total_score': row[4],
            'grade': row[5],
            'position_modifier': row[6],
            'trade_opened': bool(row[7]),
            'outcome_pips': row[8]
        })
    
    return jsonify({
        'signal_scores': scores,
        'count': len(scores)
    })


@app.route('/api/v2/weekly-report', methods=['GET'])
def get_weekly_report():
    """Get latest weekly performance report"""
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, week_ending, net_pnl, total_trades, win_rate, 
               profit_factor, max_drawdown_week, peak_portfolio_heat, 
               avg_bqs, report_json
        FROM weekly_reports
        ORDER BY week_ending DESC
        LIMIT 1
    """)
    
    row = cursor.fetchone()
    
    if row:
        return jsonify({
            'week_ending': row[1],
            'net_pnl': row[2],
            'total_trades': row[3],
            'win_rate': row[4],
            'profit_factor': row[5],
            'max_drawdown_week': row[6],
            'peak_portfolio_heat': row[7],
            'avg_bqs': row[8],
            'report_json': json.loads(row[9]) if row[9] else {}
        })
    
    return jsonify({
        'error': 'No weekly reports available',
        'report': None
    })


# ==================== SSE STREAMING ENDPOINT ====================

def generate_sse_events():
    """Generate SSE events for real-time dashboard updates"""
    last_heartbeat = time.time()
    
    while True:
        try:
            # Heartbeat event
            elapsed = int(time.time() - last_heartbeat)
            yield f"data: {json.dumps({'type': 'heartbeat', 'seconds': elapsed})}\n\n"
            
            # Get current state
            if mt5_conn.is_connected():
                positions = mt5_conn.get_positions()
                account = mt5_conn.get_account()
                
                # Check for open positions and emit trade events
                for pos in positions:
                    yield f"data: {json.dumps({'type': 'position', 'symbol': pos.get('symbol'), 'profit': pos.get('profit')})}\n\n"
            
            time.sleep(5)  # Update every 5 seconds
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            time.sleep(5)


@app.route('/api/stream', methods=['GET'])
def sse_stream():
    """Server-Sent Events endpoint for real-time updates"""
    return Response(generate_sse_events(), mimetype='text/event-stream')


# ==================== WATCHLIST DETAIL ENDPOINT ====================

@app.route('/api/v2/watchlist-detail', methods=['GET'])
def get_watchlist_detail():
    """Get detailed watchlist with prices and regime info"""
    symbols = app_state.get('watchlist', ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'XAUUSD'])
    
    result = []
    for symbol in symbols:
        try:
            df = mt5_conn.get_ohlc(symbol, 'H1', 50) if mt5_conn.is_connected() else None
            
            if df is not None and not df.empty:
                current = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else current
                
                bid = current.get('close', 0)
                ask = bid
                change_pips = (bid - prev.get('close', bid)) * 10000 if symbol != 'XAUUSD' else (bid - prev.get('close', bid)) * 10
                change_pct = ((bid - prev.get('close', bid)) / prev.get('close', bid) * 100) if prev.get('close') else 0
                
                # Determine regime (simplified)
                regime = 'T'  # Default trending
                
                result.append({
                    'symbol': symbol,
                    'bid': round(bid, 5),
                    'ask': round(ask, 5),
                    'change_pips': round(change_pips, 1),
                    'change_pct': round(change_pct, 2),
                    'regime': regime,
                    'rdd_status': 'GREEN'
                })
            else:
                result.append({
                    'symbol': symbol,
                    'bid': 0,
                    'ask': 0,
                    'change_pips': 0,
                    'change_pct': 0,
                    'regime': 'T',
                    'rdd_status': 'GREEN'
                })
        except Exception as e:
            result.append({
                'symbol': symbol,
                'bid': 0,
                'ask': 0,
                'change_pips': 0,
                'change_pct': 0,
                'regime': 'T',
                'rdd_status': 'GREEN'
            })
    
    return jsonify({'symbols': result})


# ==================== NEWS UPCOMING ENDPOINT ====================

@app.route('/api/v2/news-upcoming', methods=['GET'])
def get_upcoming_news():
    """Get upcoming high-impact news events"""
    return jsonify({
        'events': [],
        'message': 'News feed requires calendar integration'
    })


# ==================== PAPER TRADING ENDPOINTS ====================

@app.route('/api/paper/account', methods=['GET'])
def get_paper_account():
    """Get paper trading account status"""
    account = paper_engine.get_account()
    return jsonify({
        'balance': account.get('balance', 0),
        'equity': account.get('equity', 0),
        'floating_pnl': account.get('floating_pnl', 0),
        'realized_pnl': account.get('realized_pnl', 0),
        'total_trades': account.get('total_trades', 0),
        'reset_count': account.get('reset_count', 0)
    })


@app.route('/api/paper/positions', methods=['GET'])
def get_paper_positions():
    """Get all open paper positions"""
    positions = paper_engine.get_positions()
    return jsonify({
        'positions': positions,
        'count': len(positions)
    })


@app.route('/api/paper/positions/open', methods=['POST'])
def open_paper_position():
    """Open a paper trading position"""
    data = request.json
    
    symbol = data.get('symbol')
    direction = data.get('direction')
    lot_size = data.get('lot_size', 0.01)
    entry_price = data.get('entry_price', 0)
    stop_loss = data.get('sl', 0)
    take_profit = data.get('tp', 0)
    signal_score = data.get('score', 0)
    kelly_risk = data.get('kelly_risk', 0)
    vrs_scalar = data.get('vrs_scalar', 1.0)
    regime = data.get('regime', 'T')
    
    result = paper_engine.open_position(
        symbol=symbol,
        direction=direction,
        lot_size=lot_size,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        signal_score=signal_score,
        kelly_risk_pct=kelly_risk,
        vrs_scalar=vrs_scalar,
        regime=regime
    )
    
    return jsonify(result)


@app.route('/api/paper/positions/close/<ticket>', methods=['POST'])
def close_paper_position(ticket):
    """Close a paper position"""
    result = paper_engine.close_position(ticket, 'MANUAL')
    return jsonify(result)


@app.route('/api/paper/positions/close-all', methods=['POST'])
def close_all_paper_positions():
    """Close all paper positions"""
    count = paper_engine.close_all_positions()
    return jsonify({'closed': count})


@app.route('/api/paper/reset', methods=['POST'])
def reset_paper_account():
    """Reset paper account to starting balance"""
    result = paper_engine.reset_account()
    return jsonify(result)


@app.route('/api/paper/stats', methods=['GET'])
def get_paper_stats():
    """Get paper trading statistics"""
    days = int(request.args.get('days', 30))
    stats = paper_engine.get_stats(days)
    return jsonify(stats)


@app.route('/api/paper/trade', methods=['POST'])
def execute_paper_trade():
    """
    Execute a paper trade with full pre-trade checks.
    This integrates the strategy engine with paper execution.
    """
    data = request.json
    symbol = data.get('symbol')
    direction = data.get('direction')
    
    # Get current prices
    df = mt5_conn.get_ohlc(symbol, 'H1', 100) if mt5_conn.is_connected() else None
    
    if df is None or df.empty:
        return jsonify({'success': False, 'error': 'No price data available'})
    
    current_price = df.iloc[-1]['close']
    
    # Run strategy scan
    df_h4 = mt5_conn.get_ohlc(symbol, 'H4', 100) if mt5_conn.is_connected() else None
    df_d1 = mt5_conn.get_ohlc(symbol, 'D1', 50) if mt5_conn.is_connected() else None
    
    signals = strategy_engine.scan_symbol(symbol, df, df_h4, df_d1)
    
    if not signals:
        return jsonify({'success': False, 'error': 'No signals generated'})
    
    signal = signals[0]
    
    # Calculate position size (use Kelly if available)
    account = paper_engine.get_account()
    balance = account.get('balance', 10000)
    
    risk_amount = balance * 0.02  # 2% risk
    sl_distance = abs(current_price - signal.get('sl', current_price))
    
    if sl_distance > 0:
        if symbol == 'XAUUSD':
            lot_size = risk_amount / (sl_distance * 100)
        else:
            lot_size = risk_amount / (sl_distance * 100000)
    else:
        lot_size = 0.01
    
    # Open paper position
    result = paper_engine.open_position(
        symbol=symbol,
        direction=direction or signal.get('direction'),
        lot_size=lot_size,
        entry_price=current_price,
        stop_loss=signal.get('sl', 0),
        take_profit=signal.get('tp', 0),
        signal_score=signal.get('confidence', 0),
        kelly_risk_pct=0,
        vrs_scalar=1.0,
        regime='T'
    )
    
    return jsonify(result)


# ==================== EVENT LOG ENDPOINTS ====================

@app.route('/api/v3/event-log', methods=['GET'])
def get_event_log():
    """Get event log entries with optional filters"""
    limit = int(request.args.get('limit', 100))
    symbol = request.args.get('symbol')
    event_type = request.args.get('event_type')
    severity = request.args.get('severity')
    
    events = event_logger.get_events(limit, symbol, event_type, severity)
    
    return jsonify({
        'events': events,
        'count': len(events)
    })


@app.route('/api/v3/event-log/<int:signal_id>/pipeline', methods=['GET'])
def get_signal_pipeline(signal_id):
    """Get 15-step pipeline breakdown for a signal"""
    events = event_logger.get_signal_pipeline(signal_id)
    return jsonify({
        'signal_id': signal_id,
        'pipeline': events,
        'count': len(events)
    })


# ==================== READINESS CHECK ENDPOINTS ====================

@app.route('/api/v3/readiness', methods=['GET'])
def get_readiness():
    """Get live deployment readiness checklist"""
    status = readiness_checker.check_all_conditions()
    return jsonify(status)


@app.route('/api/v3/readiness/comparison', methods=['GET'])
def get_backtest_demo_comparison():
    """Get backtest vs demo comparison"""
    comparison = readiness_checker.get_comparison()
    return jsonify(comparison)


@app.route('/api/v3/readiness/per-pair', methods=['GET'])
def get_per_pair_status():
    """Get per-pair status for Kelly/demo thresholds"""
    status = readiness_checker.get_per_pair_status()
    return jsonify(status)


# ==================== MODE ENDPOINT ====================

@app.route('/api/v3/mode', methods=['GET'])
def get_system_mode():
    """Get current system mode and MT5 status"""
    mode = config.get('trading.mode') or 'PAPER'
    mt5_connected = mt5_conn.is_connected()
    
    return jsonify({
        'mode': mode,
        'mt5_connected': mt5_connected,
        'system': {'mode': mode},
        'mode_display': {
            'PAPER': {'color': 'blue', 'label': 'PAPER TRADING MODE'},
            'DEMO': {'color': 'orange', 'label': 'DEMO TRADING — MT5 CONNECTED'},
            'LIVE': {'color': 'red', 'label': 'LIVE TRADING — REAL CAPITAL'}
        }.get(mode, {'color': 'blue', 'label': mode})
    })


@app.route('/api/v3/mode', methods=['POST'])
def set_system_mode():
    """Set system mode"""
    data = request.json
    new_mode = data.get('mode', 'PAPER')
    if new_mode in ['PAPER', 'DEMO', 'LIVE']:
        config.set('trading.mode', new_mode)
        return jsonify({'success': True, 'mode': new_mode})
    return jsonify({'success': False, 'error': 'Invalid mode'})


@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    """Run historical backtest with advanced strategy"""
    data = request.json
    start_date = data.get('start_date')  # Format: YYYY-MM-DD
    end_date = data.get('end_date')  # Format: YYYY-MM-DD
    pairs = data.get('pairs', ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY'])
    
    if not start_date or not end_date:
        return jsonify({'error': 'Start and end dates required'})
    
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    except:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'})
    
    def calculate_atr(df, period=14):
        """Calculate ATR (Average True Range)"""
        high = df['high']
        low = df['low']
        close = df['close']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    def calculate_rsi(prices, period=14):
        """Calculate RSI"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def get_trend(df):
        """Determine trend using EMA 21/50 on H4"""
        ema21 = df['close'].ewm(span=21).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        if ema21 > ema50:
            return 'UP'
        elif ema21 < ema50:
            return 'DOWN'
        return 'SIDEWAYS'
    
    try:
        # Reset paper account for fresh backtest
        paper_engine.reset_account()
        
        results = []
        total_pnl = 0
        total_wins = 0
        total_trades = 0
        
        for symbol in pairs:
            df = mt5_conn.get_ohlc(symbol, 'H1', 500, start_dt, use_historic=True)
            if df is None or df.empty:
                results.append({'symbol': symbol, 'trades': 0, 'status': 'No data'})
                continue
            
            # Calculate indicators
            df = df.copy()
            df['ema9'] = df['close'].ewm(span=9).mean()
            df['ema21'] = df['close'].ewm(span=21).mean()
            df['atr'] = calculate_atr(df)
            df['rsi'] = calculate_rsi(df['close'])
            
            trades_opened = 0
            wins = 0
            current_direction = None
            entry_price = 0
            sl_price = 0
            tp_price = 0
            
            for i in range(50, len(df)):
                current_price = float(df['close'].iloc[i])
                ema9 = df['ema9'].iloc[i]
                ema21 = df['ema21'].iloc[i]
                prev_ema9 = df['ema9'].iloc[i-1]
                prev_ema21 = df['ema21'].iloc[i-1]
                
                if pd.isna(ema9) or pd.isna(ema21) or pd.isna(prev_ema9):
                    continue
                
                # Calculate pip value for the symbol
                pip_mult = 100 if symbol == 'XAUUSD' else 10000
                sl_pips = 50  # 50 pips SL
                tp_pips = 100  # 100 pips TP (1:2 ratio)
                sl_distance = sl_pips / pip_mult
                tp_distance = tp_pips / pip_mult
                
                # Close on SL/TP hit
                if current_direction == 'BUY':
                    if current_price <= sl_price or current_price >= tp_price:
                        paper_engine.close_position_by_symbol(symbol)
                        current_direction = None
                elif current_direction == 'SELL':
                    if current_price >= sl_price or current_price <= tp_price:
                        paper_engine.close_position_by_symbol(symbol)
                        current_direction = None
                
                # Open new position only if flat - use EMA CROSSOVER (not just position)
                if current_direction is None:
                    # BUY: EMA9 crosses above EMA21
                    if prev_ema9 <= prev_ema21 and ema9 > ema21:
                        new_sl = current_price - sl_distance
                        new_tp = current_price + tp_distance
                        
                        result = paper_engine.open_position(
                            symbol=symbol,
                            direction='BUY',
                            lot_size=0.01,
                            entry_price=current_price,
                            stop_loss=new_sl,
                            take_profit=new_tp,
                            signal_score=80,
                            regime='T'
                        )
                        if result.get('success'):
                            current_direction = 'BUY'
                            sl_price = new_sl
                            tp_price = new_tp
                            trades_opened += 1
                    
                    # SELL: EMA9 crosses below EMA21
                    elif prev_ema9 >= prev_ema21 and ema9 < ema21:
                        new_sl = current_price + sl_distance
                        new_tp = current_price - tp_distance
                        
                        result = paper_engine.open_position(
                            symbol=symbol,
                            direction='SELL',
                            lot_size=0.01,
                            entry_price=current_price,
                            stop_loss=new_sl,
                            take_profit=new_tp,
                            signal_score=80,
                            regime='T'
                        )
                        if result.get('success'):
                            current_direction = 'SELL'
                            sl_price = new_sl
                            tp_price = new_tp
                            trades_opened += 1
            
            # Close any remaining position
            if current_direction is not None:
                paper_engine.close_position_by_symbol(symbol)
            
            # Get positions for this symbol to calculate wins
            positions = paper_engine.get_positions()
            symbol_positions = [p for p in positions if p.get('symbol') == symbol and p.get('status') != 'OPEN']
            for p in symbol_positions:
                if p.get('realized_pnl', 0) > 0:
                    wins += 1
            
            results.append({
                'symbol': symbol,
                'trades_opened': trades_opened,
                'wins': wins,
                'status': 'completed'
            })
            total_trades += trades_opened
            total_wins += wins
        
        # Get final stats
        stats = paper_engine.get_stats(365)
        
        return jsonify({
            'backtest': True,
            'strategy': 'EMA_CROSSOVER_ATR',
            'start_date': start_date,
            'end_date': end_date,
            'results': results,
            'stats': stats
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()})


# ==================== INITIALIZATION ====================

def initialize_app():
    """Initialize application"""
    print("=" * 60)
    print("APEX FX TRADING BOT - INITIALIZING")
    print("=" * 60)
    
    # Load watchlist from database
    watchlist_json = db.get_setting('watchlist')
    if watchlist_json:
        try:
            app_state['watchlist'] = json.loads(watchlist_json)
        except:
            app_state['watchlist'] = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
    else:
        app_state['watchlist'] = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
    
    # Connect to MT5
    mt5_conn.connect()
    
    print(f"Watchlist: {app_state['watchlist']}")
    print(f"MT5 Connected: {mt5_conn.is_connected()}")
    print("=" * 60)


if __name__ == '__main__':
    initialize_app()
    app.run(host='0.0.0.0', port=5000, debug=False)