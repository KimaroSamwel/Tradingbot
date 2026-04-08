"""
SIMPLE TEST - Debug version
"""
from flask import Flask, jsonify, render_template_string
import MetaTrader5 as mt5

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TEST</title>
</head>
<body style="background:#111; color:#fff; font-family:Arial; padding:20px;">
    <h1 style="color:#0f0;">TEST PAGE v1</h1>
    <button onclick="loadData()" style="padding:10px 20px; font-size:16px; cursor:pointer;">LOAD DATA</button>
    <div id="result" style="margin-top:20px; padding:20px; background:#222; border-radius:8px;"></div>
    
    <script>
        function loadData() {
            document.getElementById('result').innerHTML = 'Loading...';
            fetch('/api/status').then(r => r.json()).then(d => {
                document.getElementById('result').innerHTML = '<pre>' + JSON.stringify(d, null, 2) + '</pre>';
            }).catch(err => {
                document.getElementById('result').innerHTML = '<span style="color:#f00;">Error: ' + err + '</span>';
            });
        }
        // Auto load on page load
        loadData();
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
        "equity": acc.equity if acc else 0
    })

if __name__ == "__main__":
    print("Starting test server...")
    if mt5.initialize():
        acc = mt5.account_info()
        if acc:
            print(f"MT5 Connected: Account {acc.login}, Balance: {acc.balance}")
    app.run(host="127.0.0.1", port=8088, debug=False)
