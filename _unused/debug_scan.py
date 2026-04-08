from web_controller import bot
bot.initialize()

print('=== DEBUGGING AUTO-SCAN ===')
print()

print('1. Session:', bot.get_current_session())
print('2. Can Trade:', bot.can_trade())
print()

for pair in ['XAUUSD', 'EURUSD', 'GBPUSD']:
    print('Checking ' + pair + ':')
    print('  News blocked:', bot.check_news(pair))
    
    df_h4 = bot.get_market_data(pair, 4, 50)
    df_h1 = bot.get_market_data(pair, 1, 100)
    
    if df_h4 is not None:
        df_h4['ema_50'] = df_h4['close'].ewm(span=50, adjust=False).mean()
        h4_close = df_h4['close'].iloc[-1]
        h4_ema50 = df_h4['ema_50'].iloc[-1]
        trend = 'BULLISH' if h4_close > h4_ema50 else 'BEARISH'
        print('  H4: Close=' + str(round(h4_close, 5)) + ' EMA50=' + str(round(h4_ema50, 5)) + ' Trend=' + trend)
    
    if df_h1 is not None:
        df_h1['ema_21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
        h1_close = df_h1['close'].iloc[-1]
        h1_ema21 = df_h1['ema_21'].iloc[-1]
        print('  H1: Close=' + str(round(h1_close, 5)) + ' EMA21=' + str(round(h1_ema21, 5)))
    
    tick = bot.get_market_data(pair, 1, 1)
    if tick is not None:
        pass
    
    signal = bot.analyze_symbol(pair)
    print('  Signal found:', signal is not None)
    if signal:
        print('    -> ' + signal['symbol'] + ' ' + signal['direction'] + ' R:R 1:' + str(signal['rr_ratio']))
    print()

print('=== FINAL SCAN ===')
results = bot.scan_all_pairs()
print('Total signals:', len(results))
for r in results:
    print('  - ' + r['symbol'] + ' ' + r['direction'] + ' 1:' + str(r['rr_ratio']))
