"""
APEX FX Trading Bot - Flask API
REST API with all endpoints for dashboard and external access
"""

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# Import core modules
from src.config import get_config
from src.data.database import get_db
from src.data.mt5_connector import get_mt5
from src.analysis.technical import get_ta
from src.strategies.engine import get_strategy_engine
from src.risk.manager import get_risk_manager

app = Flask(__name__)
CORS(app)

# Initialize components
config = get_config()
db = get_db()
mt5_conn = get_mt5()
ta = get_ta()
strategy_engine = get_strategy_engine()
risk_manager = get_risk_manager()

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
    """Get open positions"""
    positions = mt5_conn.get_positions()
    return jsonify({'positions': positions, 'count': len(positions)})


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
        # Get data
        df = mt5_conn.get_ohlc(symbol, 'H1', 100)
        if df is None or df.empty:
            continue
        
        # Get indicators
        indicators = ta.calculate_all(df)
        
        # Scan strategies
        symbol_signals = strategy_engine.scan_symbol(symbol, df, category)
        signals.extend(symbol_signals)
    
    # Save signals to database
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
    
    if not symbol:
        return jsonify({'error': 'Symbol required'})
    
    df = mt5_conn.get_ohlc(symbol, timeframe, count)
    if df is None:
        return jsonify({'error': 'Failed to get data'})
    
    # Convert to dict
    data = df.to_dict(orient='records')
    for d in data:
        d['time'] = str(d.get('time', ''))
    
    return jsonify({'symbol': symbol, 'timeframe': timeframe, 'data': data})


@app.route('/api/market/indicators', methods=['GET'])
def get_indicators():
    """Get technical indicators for symbol"""
    symbol = request.args.get('symbol')
    timeframe = request.args.get('timeframe', 'H1')
    
    if not symbol:
        return jsonify({'error': 'Symbol required'})
    
    df = mt5_conn.get_ohlc(symbol, timeframe, 200)
    if df is None:
        return jsonify({'error': 'Failed to get data'})
    
    indicators = ta.calculate_all(df)
    
    return jsonify({
        'symbol': symbol,
        'timeframe': timeframe,
        'indicators': indicators
    })


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