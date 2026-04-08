//+------------------------------------------------------------------+
//|                                           AdvancedFunctions.mqh  |
//|                      Advanced Trading Functions for MQL5 EA      |
//|    All global variables, enums, and constants are accessible    |
//|    from the main EA file when this header is included           |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Get current trading session                                      |
//+------------------------------------------------------------------+
string GetCurrentSession()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int hour = dt.hour;
   
   if(hour >= InpAsianStart && hour < InpAsianEnd)
      return "ASIAN";
   else if(hour >= InpLondonStart && hour < InpLondonEnd)
      return "LONDON";
   else if(hour >= InpNewYorkStart && hour < InpNewYorkEnd)
      return "NY";
   else
      return "OFF_HOURS";
  }

//+------------------------------------------------------------------+
//| Detect reversal signals (8-signal system)                        |
//+------------------------------------------------------------------+
int DetectReversalSignals()
  {
   int signals = 0;
   
   // Get indicator data
   double rsi[], adx[], stochK[], stochD[];
   double emaFast[], emaMedium[], emaSlow[];
   MqlRates rates[];
   
   if(CopyBuffer(ExtRSIHandle, 0, 0, 5, rsi) < 5) return 0;
   if(CopyBuffer(ExtADXHandle, 0, 0, 5, adx) < 5) return 0;
   if(CopyBuffer(ExtStochHandle, 0, 0, 5, stochK) < 5) return 0;
   if(CopyBuffer(ExtStochHandle, 1, 0, 5, stochD) < 5) return 0;
   if(CopyBuffer(ExtEMAHandles[0], 0, 0, 5, emaFast) < 5) return 0;
   if(CopyBuffer(ExtEMAHandles[1], 0, 0, 5, emaMedium) < 5) return 0;
   if(CopyBuffer(ExtEMAHandles[2], 0, 0, 5, emaSlow) < 5) return 0;
   if(CopyRates(_Symbol, InpTimeframe1, 0, 10, rates) < 10) return 0;
   
   // Signal 1: RSI Divergence
   if((rsi[0] > rsi[2] && rates[0].close < rates[2].close) ||
      (rsi[0] < rsi[2] && rates[0].close > rates[2].close))
      signals++;
   
   // Signal 2: RSI Extreme
   if(rsi[0] < 30 || rsi[0] > 70)
      signals++;
   
   // Signal 3: Stochastic Crossover
   if((stochK[1] < stochD[1] && stochK[0] > stochD[0]) ||
      (stochK[1] > stochD[1] && stochK[0] < stochD[0]))
      signals++;
   
   // Signal 4: EMA Crossover
   if((emaFast[1] < emaMedium[1] && emaFast[0] > emaMedium[0]) ||
      (emaFast[1] > emaMedium[1] && emaFast[0] < emaMedium[0]))
      signals++;
   
   // Signal 5: Price vs EMA
   double currentPrice = rates[0].close;
   if((currentPrice < emaSlow[0] && rates[1].close > emaSlow[1]) ||
      (currentPrice > emaSlow[0] && rates[1].close < emaSlow[1]))
      signals++;
   
   // Signal 6: Candlestick Pattern (Hammer/Shooting Star)
   double body = MathAbs(rates[0].close - rates[0].open);
   double range = rates[0].high - rates[0].low;
   double upperWick = rates[0].high - MathMax(rates[0].open, rates[0].close);
   double lowerWick = MathMin(rates[0].open, rates[0].close) - rates[0].low;
   
   if(lowerWick > body * 2 && upperWick < body * 0.5) // Hammer
      signals++;
   else if(upperWick > body * 2 && lowerWick < body * 0.5) // Shooting Star
      signals++;
   
   // Signal 7: Volume Spike
   if(rates[0].tick_volume > rates[1].tick_volume * 1.5)
      signals++;
   
   // Signal 8: ADX Trend Weakening
   if(adx[0] < adx[2])
      signals++;
   
   return signals;
  }

//+------------------------------------------------------------------+
//| Detect candlestick patterns and return reliability              |
//+------------------------------------------------------------------+
double DetectPatterns()
  {
   MqlRates rates[];
   if(CopyRates(_Symbol, InpTimeframe1, 0, InpPatternLookback, rates) < InpPatternLookback)
      return 0;
   
   double reliability = 0;
   int patternCount = 0;
   
   // Check last 3 candles for patterns
   for(int i = 2; i < 5 && i < InpPatternLookback; i++)
     {
      double body = MathAbs(rates[i].close - rates[i].open);
      double range = rates[i].high - rates[i].low;
      double upperWick = rates[i].high - MathMax(rates[i].open, rates[i].close);
      double lowerWick = MathMin(rates[i].open, rates[i].close) - rates[i].low;
      
      // Hammer Pattern
      if(lowerWick > body * 2 && upperWick < body * 0.5 && body > 0)
        {
         reliability += 75;
         patternCount++;
        }
      
      // Shooting Star
      else if(upperWick > body * 2 && lowerWick < body * 0.5 && body > 0)
        {
         reliability += 75;
         patternCount++;
        }
      
      // Engulfing Pattern
      if(i > 0)
        {
         double prevBody = MathAbs(rates[i-1].close - rates[i-1].open);
         if(body > prevBody * 1.5)
           {
            reliability += 80;
            patternCount++;
           }
        }
      
      // Doji
      if(body < range * 0.1)
        {
         reliability += 65;
         patternCount++;
        }
     }
   
   if(patternCount > 0)
      return reliability / patternCount;
   
   return 0;
  }

//+------------------------------------------------------------------+
//| Calculate 100-point confluence score                             |
//+------------------------------------------------------------------+
double CalculateConfluenceScore(int signal)
  {
   double score = 0;
   
   // 1. MTF Alignment (30 points max)
   int mtfAlignment = 0;
   for(int tf = 0; tf < 4; tf++)
     {
      double tfEmaFast[], tfEmaMedium[];
      int baseIdx = tf * 4;
      
      if(CopyBuffer(ExtEMAHandles[baseIdx], 0, 0, 2, tfEmaFast) < 2) continue;
      if(CopyBuffer(ExtEMAHandles[baseIdx+1], 0, 0, 2, tfEmaMedium) < 2) continue;
      
      if(signal == SIGNAL_BUY && tfEmaFast[0] > tfEmaMedium[0])
         mtfAlignment++;
      else if(signal == SIGNAL_SELL && tfEmaFast[0] < tfEmaMedium[0])
         mtfAlignment++;
     }
   score += (mtfAlignment / 4.0) * InpMTFWeight;
   
   // 2. Market Regime (25 points max)
   if(ExtCurrentRegime == REGIME_STRONG_TREND)
      score += InpRegimeWeight;
   else if(ExtCurrentRegime == REGIME_WEAK_TREND)
      score += InpRegimeWeight * 0.6;
   else if(ExtCurrentRegime == REGIME_RANGING)
      score += InpRegimeWeight * 0.3;
   
   // 3. Pattern Recognition (20 points max)
   if(ExtPatternReliability > 0)
      score += (ExtPatternReliability / 100.0) * InpPatternWeight;
   
   // 4. Volume Confirmation (15 points max)
   MqlRates rates[];
   if(CopyRates(_Symbol, InpTimeframe1, 0, 5, rates) >= 5)
     {
      double avgVolume = 0;
      for(int i = 1; i < 5; i++)
         avgVolume += (double)rates[i].tick_volume;
      avgVolume /= 4.0;
      
      if(rates[0].tick_volume > avgVolume * 1.2)
         score += InpVolumeWeight;
      else if(rates[0].tick_volume > avgVolume)
         score += InpVolumeWeight * 0.6;
     }
   
   // 5. Session Quality (10 points max)
   if(ExtCurrentSession == "LONDON" || ExtCurrentSession == "NY")
      score += InpSessionWeight;
   else if(ExtCurrentSession == "ASIAN")
      score += InpSessionWeight * 0.5;
   
   return score;
  }

//+------------------------------------------------------------------+
//| Update volatility factor for adaptive sizing                     |
//+------------------------------------------------------------------+
void UpdateVolatilityFactor()
  {
   double atr[];
   if(CopyBuffer(ExtATRHandle, 0, 0, 20, atr) < 20)
      return;
   
   double avgATR = 0;
   for(int i = 0; i < 20; i++)
      avgATR += atr[i];
   avgATR /= 20;
   
   if(avgATR > 0)
      ExtVolatilityFactor = atr[0] / avgATR;
   else
      ExtVolatilityFactor = 1.0;
  }

//+------------------------------------------------------------------+
//| Track trade results for psychology monitoring                    |
//+------------------------------------------------------------------+
void UpdateTradingPsychology(bool isWin, double profit)
  {
   if(isWin)
     {
      ExtConsecutiveLosses = 0;
      ExtWins++;
     }
   else
     {
      ExtConsecutiveLosses++;
      ExtLosses++;
      
      // Update daily loss
      datetime today = TimeCurrent();
      MqlDateTime dt;
      TimeToStruct(today, dt);
      dt.hour = 0;
      dt.min = 0;
      dt.sec = 0;
      datetime todayStart = StructToTime(dt);
      
      if(ExtLastTradeDay < todayStart)
        {
         ExtDailyLoss = 0;
         ExtLastTradeDay = todayStart;
        }
      
      ExtDailyLoss += MathAbs(profit / ExtAccount.Balance() * 100);
     }
   
   // Update drawdown
   double currentBalance = ExtAccount.Balance();
   if(currentBalance < ExtInitialBalance)
     {
      ExtCurrentDrawdown = ((ExtInitialBalance - currentBalance) / ExtInitialBalance) * 100;
      if(ExtCurrentDrawdown > ExtMaxDrawdown)
         ExtMaxDrawdown = ExtCurrentDrawdown;
     }
  }
