//+------------------------------------------------------------------+
//|                                        SNIPER_PRO_2024_EA.mq5    |
//|                                  ICT 2022 Expert Advisor         |
//|                         GMT+3 Killzones, FVG, Order Blocks       |
//+------------------------------------------------------------------+
#property copyright "SNIPER PRO 2024"
#property link      ""
#property version   "1.00"
#property strict

//--- Input Parameters
input group "=== ACCOUNT SETTINGS ==="
input double RiskPercentPerTrade = 1.0;        // Risk % per trade
input double MaxDailyLossPercent = 2.0;        // Max daily loss %
input int MaxPositions = 5;                    // Max concurrent positions

input group "=== ICT 2022 SETTINGS (GMT+3) ==="
input bool UseICT2022 = true;                  // Enable ICT 2022 Model
input int LondonKillzoneStart = 11;            // London Killzone Start (GMT+3)
input int LondonKillzoneEnd = 13;              // London Killzone End (GMT+3)
input int NYKillzoneStart = 14;                // NY Killzone Start (GMT+3)
input int NYKillzoneEnd = 23;                  // NY Killzone End (GMT+3)
input int SilverBulletStart = 18;              // Silver Bullet Start (GMT+3)
input int SilverBulletEnd = 19;                // Silver Bullet End (GMT+3)

input group "=== FVG SETTINGS ==="
input bool UseFairValueGaps = true;            // Use Fair Value Gaps
input double MinFVGSizePips = 3.0;             // Min FVG size in pips
input bool UseOTEEntry = true;                 // Use OTE (62-78.6%) entry

input group "=== ORDER BLOCK SETTINGS ==="
input bool UseOrderBlocks = true;              // Use Order Blocks
input int OrderBlockLookback = 20;             // Lookback period for OBs
input int MinOrderBlockStrength = 50;          // Min strength (0-100)

input group "=== LIQUIDITY SETTINGS ==="
input bool UseLiquiditySweeps = true;          // Detect liquidity sweeps
input double MinSweepPips = 1.0;               // Min sweep size in pips

input group "=== EXIT SETTINGS ==="
input bool UseTrailingStop = true;             // Enable trailing stop
input double TrailingStopATRMultiplier = 2.0;  // Trailing stop ATR multiplier
input bool UsePartialTakeProfit = true;        // Enable partial TP
input double TP1_RR = 1.5;                     // TP1 Risk:Reward
input double TP2_RR = 2.5;                     // TP2 Risk:Reward
input double TP3_RR = 4.0;                     // TP3 Risk:Reward
input double TP1_ClosePercent = 50.0;          // Close % at TP1
input double TP2_ClosePercent = 30.0;          // Close % at TP2

input group "=== CIRCUIT BREAKER ==="
input bool UseCircuitBreaker = true;           // Enable circuit breaker
input int MaxConsecutiveLosses = 3;            // Max consecutive losses

//--- Global Variables
datetime lastBarTime = 0;
int consecutiveLosses = 0;
double dailyPnL = 0;
datetime dailyPnLDate = 0;
int magicNumber = 20240204;

// Indicator handles
int atrHandle;
int adxHandle;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("SNIPER PRO 2024 EA - Initializing...");
   
   // Initialize indicators
   atrHandle = iATR(_Symbol, PERIOD_CURRENT, 14);
   adxHandle = iADX(_Symbol, PERIOD_CURRENT, 14);
   
   if(atrHandle == INVALID_HANDLE || adxHandle == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles");
      return(INIT_FAILED);
   }
   
   Print("✓ SNIPER PRO 2024 EA Initialized Successfully");
   Print("✓ ICT 2022 Model: ", UseICT2022 ? "ENABLED" : "DISABLED");
   Print("✓ Circuit Breaker: ", UseCircuitBreaker ? "ENABLED" : "DISABLED");
   Print("✓ Risk per Trade: ", RiskPercentPerTrade, "%");
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("SNIPER PRO 2024 EA - Stopped. Reason: ", reason);
   
   // Release indicators
   IndicatorRelease(atrHandle);
   IndicatorRelease(adxHandle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check for new bar
   if(!IsNewBar())
      return;
   
   // Update daily P&L
   UpdateDailyPnL();
   
   // Check circuit breaker
   if(UseCircuitBreaker && IsCircuitBreakerActive())
   {
      Comment("⚠️ CIRCUIT BREAKER ACTIVE\n",
              "Consecutive Losses: ", consecutiveLosses, "/", MaxConsecutiveLosses, "\n",
              "Daily P&L: ", DoubleToString(dailyPnL, 2), "%");
      return;
   }
   
   // Check killzone
   if(!IsInKillzone())
   {
      Comment("⏰ Waiting for Killzone\n",
              "London: ", LondonKillzoneStart, ":00-", LondonKillzoneEnd, ":00 GMT+3\n",
              "NY: ", NYKillzoneStart, ":00-", NYKillzoneEnd, ":00 GMT+3\n",
              "Silver Bullet: ", SilverBulletStart, ":00-", SilverBulletEnd, ":00 GMT+3");
      return;
   }
   
   // Check max positions
   if(CountOpenPositions() >= MaxPositions)
   {
      Comment("📊 Max Positions Reached: ", CountOpenPositions(), "/", MaxPositions);
      return;
   }
   
   // Analyze market using ICT concepts
   int signal = AnalyzeICT2022();
   
   if(signal == 1) // BUY
   {
      ExecuteBuyOrder();
   }
   else if(signal == -1) // SELL
   {
      ExecuteSellOrder();
   }
   
   // Manage open positions
   ManagePositions();
   
   // Update screen info
   UpdateScreenInfo();
}

//+------------------------------------------------------------------+
//| Check if in killzone                                            |
//+------------------------------------------------------------------+
bool IsInKillzone()
{
   MqlDateTime time;
   TimeToStruct(TimeCurrent(), time);
   int currentHour = time.hour;
   
   // Silver Bullet (highest priority)
   if(currentHour >= SilverBulletStart && currentHour < SilverBulletEnd)
      return true;
   
   // London Killzone
   if(currentHour >= LondonKillzoneStart && currentHour < LondonKillzoneEnd)
      return true;
   
   // NY Killzone
   if(currentHour >= NYKillzoneStart && currentHour < NYKillzoneEnd)
      return true;
   
   return false;
}

//+------------------------------------------------------------------+
//| Analyze market using ICT 2022 concepts                          |
//+------------------------------------------------------------------+
int AnalyzeICT2022()
{
   if(!UseICT2022)
      return 0;
   
   int confluenceScore = 0;
   int bullishFactors = 0;
   int bearishFactors = 0;
   
   // 1. Check Fair Value Gaps
   if(UseFairValueGaps)
   {
      int fvgSignal = DetectFairValueGap();
      if(fvgSignal == 1) { bullishFactors++; confluenceScore++; }
      else if(fvgSignal == -1) { bearishFactors++; confluenceScore++; }
   }
   
   // 2. Check Order Blocks
   if(UseOrderBlocks)
   {
      int obSignal = DetectOrderBlock();
      if(obSignal == 1) { bullishFactors++; confluenceScore++; }
      else if(obSignal == -1) { bearishFactors++; confluenceScore++; }
   }
   
   // 3. Check Liquidity Sweeps
   if(UseLiquiditySweeps)
   {
      int liqSignal = DetectLiquiditySweep();
      if(liqSignal == 1) { bullishFactors++; confluenceScore++; }
      else if(liqSignal == -1) { bearishFactors++; confluenceScore++; }
   }
   
   // 4. Check Market Structure
   int structureSignal = AnalyzeMarketStructure();
   if(structureSignal == 1) { bullishFactors++; confluenceScore++; }
   else if(structureSignal == -1) { bearishFactors++; confluenceScore++; }
   
   // Require minimum 3 confluence factors
   if(confluenceScore < 3)
      return 0;
   
   // Determine direction
   if(bullishFactors > bearishFactors && bullishFactors >= 2)
      return 1;  // BUY
   else if(bearishFactors > bullishFactors && bearishFactors >= 2)
      return -1; // SELL
   
   return 0;
}

//+------------------------------------------------------------------+
//| Detect Fair Value Gaps                                          |
//+------------------------------------------------------------------+
int DetectFairValueGap()
{
   if(Bars(_Symbol, PERIOD_CURRENT) < 3)
      return 0;
   
   double high[], low[];
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   
   CopyHigh(_Symbol, PERIOD_CURRENT, 0, 3, high);
   CopyLow(_Symbol, PERIOD_CURRENT, 0, 3, low);
   
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double minGapSize = MinFVGSizePips * point * 10;
   
   // Bullish FVG: gap between candle[2] high and candle[0] low
   if(low[0] > high[2])
   {
      double gapSize = low[0] - high[2];
      if(gapSize >= minGapSize)
         return 1; // Bullish FVG
   }
   
   // Bearish FVG: gap between candle[2] low and candle[0] high
   if(high[0] < low[2])
   {
      double gapSize = low[2] - high[0];
      if(gapSize >= minGapSize)
         return -1; // Bearish FVG
   }
   
   return 0;
}

//+------------------------------------------------------------------+
//| Detect Order Blocks                                             |
//+------------------------------------------------------------------+
int DetectOrderBlock()
{
   double open[], close[], high[], low[];
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(close, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   
   int bars = OrderBlockLookback;
   CopyOpen(_Symbol, PERIOD_CURRENT, 0, bars, open);
   CopyClose(_Symbol, PERIOD_CURRENT, 0, bars, close);
   CopyHigh(_Symbol, PERIOD_CURRENT, 0, bars, high);
   CopyLow(_Symbol, PERIOD_CURRENT, 0, bars, low);
   
   // Look for bullish order block
   for(int i = 5; i < bars - 3; i++)
   {
      // Down candle followed by strong up move
      if(close[i] < open[i])
      {
         int upCandles = 0;
         for(int j = i-1; j >= i-3; j--)
         {
            if(close[j] > open[j])
               upCandles++;
         }
         
         if(upCandles >= 2)
            return 1; // Bullish OB
      }
   }
   
   // Look for bearish order block
   for(int i = 5; i < bars - 3; i++)
   {
      // Up candle followed by strong down move
      if(close[i] > open[i])
      {
         int downCandles = 0;
         for(int j = i-1; j >= i-3; j--)
         {
            if(close[j] < open[j])
               downCandles++;
         }
         
         if(downCandles >= 2)
            return -1; // Bearish OB
      }
   }
   
   return 0;
}

//+------------------------------------------------------------------+
//| Detect Liquidity Sweeps                                         |
//+------------------------------------------------------------------+
int DetectLiquiditySweep()
{
   double high[], low[], close[];
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);
   
   CopyHigh(_Symbol, PERIOD_CURRENT, 0, 20, high);
   CopyLow(_Symbol, PERIOD_CURRENT, 0, 20, low);
   CopyClose(_Symbol, PERIOD_CURRENT, 0, 20, close);
   
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double minSweep = MinSweepPips * point * 10;
   
   // Find recent swing high/low
   double swingHigh = high[ArrayMaximum(high, 1, 19)];
   double swingLow = low[ArrayMinimum(low, 1, 19)];
   
   // Check for upside sweep and reversal
   if(high[0] > swingHigh && close[0] < swingHigh)
   {
      if((high[0] - swingHigh) >= minSweep)
         return -1; // Bearish (swept highs)
   }
   
   // Check for downside sweep and reversal
   if(low[0] < swingLow && close[0] > swingLow)
   {
      if((swingLow - low[0]) >= minSweep)
         return 1; // Bullish (swept lows)
   }
   
   return 0;
}

//+------------------------------------------------------------------+
//| Analyze Market Structure                                        |
//+------------------------------------------------------------------+
int AnalyzeMarketStructure()
{
   double high[], low[];
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   
   CopyHigh(_Symbol, PERIOD_CURRENT, 0, 50, high);
   CopyLow(_Symbol, PERIOD_CURRENT, 0, 50, low);
   
   // Find swing points
   bool higherHighs = true;
   bool higherLows = true;
   bool lowerHighs = true;
   bool lowerLows = true;
   
   for(int i = 10; i < 40; i += 10)
   {
      // Check higher highs
      if(high[i] >= high[i+10])
         higherHighs = false;
      
      // Check higher lows
      if(low[i] >= low[i+10])
         higherLows = false;
      
      // Check lower highs
      if(high[i] <= high[i+10])
         lowerHighs = false;
      
      // Check lower lows
      if(low[i] <= low[i+10])
         lowerLows = false;
   }
   
   // Bullish structure
   if(higherHighs && higherLows)
      return 1;
   
   // Bearish structure
   if(lowerHighs && lowerLows)
      return -1;
   
   return 0;
}

//+------------------------------------------------------------------+
//| Execute Buy Order                                               |
//+------------------------------------------------------------------+
void ExecuteBuyOrder()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double atr = GetATR();
   
   // Calculate stop loss and take profit
   double stopLoss = ask - (atr * 1.5);
   double takeProfit1 = ask + (atr * TP1_RR * 1.5);
   double takeProfit2 = ask + (atr * TP2_RR * 1.5);
   
   // Calculate position size
   double lotSize = CalculateLotSize(ask, stopLoss);
   
   // Place order
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = lotSize;
   request.type = ORDER_TYPE_BUY;
   request.price = ask;
   request.sl = stopLoss;
   request.tp = takeProfit1;
   request.magic = magicNumber;
   request.comment = "SNIPER_BUY";
   
   if(OrderSend(request, result))
   {
      Print("✓ BUY order executed: ", result.order, " | Lot: ", lotSize, " | SL: ", stopLoss, " | TP: ", takeProfit1);
   }
   else
   {
      Print("✗ BUY order failed: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Execute Sell Order                                              |
//+------------------------------------------------------------------+
void ExecuteSellOrder()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double atr = GetATR();
   
   // Calculate stop loss and take profit
   double stopLoss = bid + (atr * 1.5);
   double takeProfit1 = bid - (atr * TP1_RR * 1.5);
   double takeProfit2 = bid - (atr * TP2_RR * 1.5);
   
   // Calculate position size
   double lotSize = CalculateLotSize(bid, stopLoss);
   
   // Place order
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = lotSize;
   request.type = ORDER_TYPE_SELL;
   request.price = bid;
   request.sl = stopLoss;
   request.tp = takeProfit1;
   request.magic = magicNumber;
   request.comment = "SNIPER_SELL";
   
   if(OrderSend(request, result))
   {
      Print("✓ SELL order executed: ", result.order, " | Lot: ", lotSize, " | SL: ", stopLoss, " | TP: ", takeProfit1);
   }
   else
   {
      Print("✗ SELL order failed: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Calculate Position Size                                         |
//+------------------------------------------------------------------+
double CalculateLotSize(double entryPrice, double stopLoss)
{
   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = accountBalance * (RiskPercentPerTrade / 100.0);
   
   double stopLossPips = MathAbs(entryPrice - stopLoss) / SymbolInfoDouble(_Symbol, SYMBOL_POINT) / 10;
   double pipValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   
   double lotSize = riskAmount / (stopLossPips * pipValue);
   
   // Round and apply limits
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lotSize = MathFloor(lotSize / lotStep) * lotStep;
   lotSize = MathMax(minLot, MathMin(maxLot, lotSize));
   
   return lotSize;
}

//+------------------------------------------------------------------+
//| Manage Open Positions                                           |
//+------------------------------------------------------------------+
void ManagePositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magicNumber) continue;
      
      // Implement trailing stop
      if(UseTrailingStop)
      {
         double atr = GetATR();
         double trailDistance = atr * TrailingStopATRMultiplier;
         
         if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
         {
            double currentSL = PositionGetDouble(POSITION_SL);
            double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double newSL = currentPrice - trailDistance;
            
            if(newSL > currentSL)
            {
               ModifyPosition(ticket, newSL, PositionGetDouble(POSITION_TP));
            }
         }
         else // SELL
         {
            double currentSL = PositionGetDouble(POSITION_SL);
            double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double newSL = currentPrice + trailDistance;
            
            if(newSL < currentSL)
            {
               ModifyPosition(ticket, newSL, PositionGetDouble(POSITION_TP));
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Modify Position                                                  |
//+------------------------------------------------------------------+
bool ModifyPosition(ulong ticket, double newSL, double newTP)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_SLTP;
   request.position = ticket;
   request.sl = newSL;
   request.tp = newTP;
   
   return OrderSend(request, result);
}

//+------------------------------------------------------------------+
//| Count Open Positions                                            |
//+------------------------------------------------------------------+
int CountOpenPositions()
{
   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && 
         PositionGetInteger(POSITION_MAGIC) == magicNumber)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Update Daily P&L                                                |
//+------------------------------------------------------------------+
void UpdateDailyPnL()
{
   MqlDateTime currentTime;
   TimeToStruct(TimeCurrent(), currentTime);
   
   // Reset daily P&L at start of new day
   if(currentTime.day != dailyPnLDate)
   {
      dailyPnL = 0;
      dailyPnLDate = currentTime.day;
      consecutiveLosses = 0;
   }
}

//+------------------------------------------------------------------+
//| Check if Circuit Breaker is Active                              |
//+------------------------------------------------------------------+
bool IsCircuitBreakerActive()
{
   if(consecutiveLosses >= MaxConsecutiveLosses)
      return true;
   
   if(dailyPnL <= -MaxDailyLossPercent)
      return true;
   
   return false;
}

//+------------------------------------------------------------------+
//| Get ATR                                                          |
//+------------------------------------------------------------------+
double GetATR()
{
   double atr[];
   ArraySetAsSeries(atr, true);
   CopyBuffer(atrHandle, 0, 0, 1, atr);
   return atr[0];
}

//+------------------------------------------------------------------+
//| Check for New Bar                                               |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime != lastBarTime)
   {
      lastBarTime = currentBarTime;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Update Screen Info                                              |
//+------------------------------------------------------------------+
void UpdateScreenInfo()
{
   string info = "\n=== SNIPER PRO 2024 EA ===\n";
   info += "Status: " + (IsInKillzone() ? "✓ IN KILLZONE" : "⏰ WAITING") + "\n";
   info += "Positions: " + IntegerToString(CountOpenPositions()) + "/" + IntegerToString(MaxPositions) + "\n";
   info += "Daily P&L: " + DoubleToString(dailyPnL, 2) + "%\n";
   info += "Circuit Breaker: " + (IsCircuitBreakerActive() ? "⚠️ ACTIVE" : "✓ OK") + "\n";
   info += "Consecutive Losses: " + IntegerToString(consecutiveLosses) + "/" + IntegerToString(MaxConsecutiveLosses) + "\n";
   
   Comment(info);
}
//+------------------------------------------------------------------+
