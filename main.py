"""
APEX FX Trading Bot
===================
Main entry point for the trading system
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.main import app, initialize_app


if __name__ == '__main__':
    initialize_app()
    print("\n" + "="*60)
    print("APEX FX TRADING BOT")
    print("Open http://localhost:5000 in your browser")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)