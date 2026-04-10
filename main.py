"""
APEX FX Trading Bot - Main Entry Point
======================================
Full execution loop integrating all Volume I and Volume II modules
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    from src.api.main import app, initialize_app
    
    initialize_app()
    print("\n" + "="*60)
    print("APEX FX TRADING BOT")
    print("Open http://localhost:5000 in your browser")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
