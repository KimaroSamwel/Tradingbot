"""
Diagnostic script to check MT5 filling modes for synthetic indices.
Run this to see which filling modes are actually supported.
"""
import MetaTrader5 as mt5

def diagnose_symbol_filling_modes():
    """Check filling mode support for all symbols."""
    if not mt5.initialize():
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    # Symbols to check
    symbols_to_check = [
        "Volatility 50 Index",
        "Volatility 75 Index", 
        "Volatility 100 Index",
        "Crash 500 Index",
        "Crash 1000 Index",
        "Boom 300 Index",
        "Boom 500 Index",
        "Boom 1000 Index",
        "EURUSD",
        "XAUUSD",
    ]
    
    print("\n" + "="*80)
    print("MT5 FILLING MODE DIAGNOSTICS")
    print("="*80)
    
    # Filling mode constants
    SYMBOL_FILLING_FOK = 1     # 0x01
    SYMBOL_FILLING_IOC = 2     # 0x02  
    SYMBOL_FILLING_RETURN = 4  # 0x04
    
    ORDER_FILLING_FOK = mt5.ORDER_FILLING_FOK
    ORDER_FILLING_IOC = mt5.ORDER_FILLING_IOC
    ORDER_FILLING_RETURN = mt5.ORDER_FILLING_RETURN
    
    print(f"\nMT5 Constants:")
    print(f"  ORDER_FILLING_FOK = {ORDER_FILLING_FOK}")
    print(f"  ORDER_FILLING_IOC = {ORDER_FILLING_IOC}")
    print(f"  ORDER_FILLING_RETURN = {ORDER_FILLING_RETURN}")
    
    for symbol in symbols_to_check:
        info = mt5.symbol_info(symbol)
        if info is None:
            print(f"\n[{symbol}] NOT AVAILABLE")
            continue
        
        filling_mode = info.filling_mode
        
        print(f"\n[{symbol}]")
        print(f"  filling_mode (raw) = {filling_mode} (binary: {bin(filling_mode)})")
        print(f"  Supports FOK     (bit 0): {bool(filling_mode & SYMBOL_FILLING_FOK)}")
        print(f"  Supports IOC     (bit 1): {bool(filling_mode & SYMBOL_FILLING_IOC)}")
        print(f"  Supports RETURN  (bit 2): {bool(filling_mode & SYMBOL_FILLING_RETURN)}")
        
        # Recommend which ORDER_FILLING mode to use
        if filling_mode & SYMBOL_FILLING_RETURN:
            recommended = f"ORDER_FILLING_RETURN ({ORDER_FILLING_RETURN})"
        elif filling_mode & SYMBOL_FILLING_IOC:
            recommended = f"ORDER_FILLING_IOC ({ORDER_FILLING_IOC})"
        elif filling_mode & SYMBOL_FILLING_FOK:
            recommended = f"ORDER_FILLING_FOK ({ORDER_FILLING_FOK})"
        else:
            recommended = "UNKNOWN - try all modes"
        
        print(f"  Recommended: {recommended}")
    
    print("\n" + "="*80)
    mt5.shutdown()

if __name__ == "__main__":
    diagnose_symbol_filling_modes()
