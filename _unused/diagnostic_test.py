"""
DIAGNOSTIC TEST - Minimal page to test browser behavior
"""
from flask import Flask, jsonify, render_template_string
import MetaTrader5 as mt5

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Diagnostic Test</title>
    <style>
        body { font-family: Arial; background: #111; color: #fff; padding: 20px; }
        .box { background: #222; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .green { color: #0f0; }
        .red { color: #f00; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; margin: 5px; }
    </style>
</head>
<body>
    <h1 style="color:#0ff;">DIAGNOSTIC TEST</h1>
    
    <div class="box">
        <h3>Step 1: Click to fetch data</h3>
        <button onclick="fetchData()">FETCH /api/status</button>
        <div id="step1"></div>
    </div>
    
    <div class="box">
        <h3>Step 2: Auto-fetch on page load</h3>
        <div id="step2">Loading...</div>
    </div>
    
    <div class="box">
        <h3>Step 3: Full dashboard</h3>
        <div id="step3"></div>
    </div>
    
    <script>
        console.log('Script starting...');
        
        function log(msg) {
            console.log(msg);
            document.body.innerHTML += '<div>' + msg + '</div>';
        }
        
        function fetchData() {
            log('Fetching /api/status...');
            fetch('/api/status')
                .then(r => {
                    log('Response status: ' + r.status);
                    return r.json();
                })
                .then(d => {
                    log('<span class="green">SUCCESS! Got data:</span>');
                    log('Balance: ' + d.balance);
                    log('Session: ' + d.session.code);
                })
                .catch(err => {
                    log('<span class="red">ERROR: ' + err + '</span>');
                });
        }
        
        // Auto-fetch
        log('Step 2: Auto-fetching...');
        fetch('/api/status')
            .then(r => r.json())
            .then(d => {
                document.getElementById('step2').innerHTML = 
                    '<span class="green">Loaded!</span><br>' +
                    'Balance: $' + d.balance + '<br>' +
                    'Session: ' + d.session.code + '<br>' +
                    'Positions: ' + d.positions + '<br>' +
                    'MT5: ' + (d.mt5_connected ? 'Connected' : 'Disconnected');
                log('Step 2 complete');
            })
            .catch(err => {
                document.getElementById('step2').innerHTML = '<span class="red">Error: ' + err + '</span>';
                log('Step 2 error: ' + err);
            });
        
        // Full dashboard after 2 seconds
        setTimeout(function() {
            log('Step 3: Loading full dashboard...');
            fetch('/api/status')
                .then(r => r.json())
                .then(d => {
                    let html = '<table border="1" style="width:100%; border-collapse:collapse;">';
                    html += '<tr><th>Field</th><th>Value</th></tr>';
                    html += '<tr><td>MT5 Connected</td><td>' + d.mt5_connected + '</td></tr>';
                    html += '<tr><td>Balance</td><td>$' + d.balance + '</td></tr>';
                    html += '<tr><td>Equity</td><td>$' + d.equity + '</td></tr>';
                    html += '<tr><td>Profit</td><td>$' + d.profit + '</td></tr>';
                    html += '<tr><td>Positions</td><td>' + d.positions + '</td></tr>';
                    html += '<tr><td>Session</td><td>' + d.session.code + '</td></tr>';
                    html += '<tr><td>Session Name</td><td>' + d.session.name + '</td></tr>';
                    html += '<tr><td>Best Pairs</td><td>' + (d.session.best_pairs || []).join(', ') + '</td></tr>';
                    html += '<tr><td>Can Trade</td><td>' + d.is_tradeable + '</td></tr>';
                    html += '<tr><td>Trade Reason</td><td>' + (d.trade_reason || 'N/A') + '</td></tr>';
                    html += '<tr><td>Market Directions</td><td>' + Object.keys(d.market_directions || {}).length + ' pairs</td></tr>';
                    html += '<tr><td>Scan Results</td><td>' + (d.scan_results || []).length + ' signals</td></tr>';
                    html += '<tr><td>Open Positions</td><td>' + (d.open_positions || []).length + ' positions</td></tr>';
                    html += '<tr><td>Trade History</td><td>' + (d.trade_history || []).length + ' trades</td></tr>';
                    html += '</table>';
                    document.getElementById('step3').innerHTML = html;
                    log('Step 3 complete');
                });
        }, 2000);
        
        log('Script loaded');
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/status")
def status():
    if not mt5.initialize():
        return jsonify({"error": "MT5 not connected"})
    acc = mt5.account_info()
    return jsonify({
        "mt5_connected": True,
        "balance": acc.balance if acc else 0,
        "equity": acc.equity if acc else 0,
        "profit": acc.profit if acc else 0,
        "positions": 0,
        "session": {"code": "OVERLAP", "name": "London/NY Overlap", "best_pairs": ["EURUSD", "GBPUSD", "XAUUSD"]},
        "is_tradeable": True,
        "trade_reason": None,
        "market_directions": {},
        "scan_results": [],
        "open_positions": [],
        "trade_history": []
    })

if __name__ == "__main__":
    print("Starting diagnostic server on port 8089...")
    if mt5.initialize():
        acc = mt5.account_info()
        if acc:
            print(f"MT5: Account {acc.login}, Balance: ${acc.balance}")
    app.run(host="127.0.0.1", port=8089, debug=False)
