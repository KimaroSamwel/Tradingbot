//+------------------------------------------------------------------+
//|                   SNIPER_PRO_2024_PatternEvidence_EA.mq5        |
//|   Direct MT5 Expert Advisor with Pattern Evidence scoring        |
//|   6 bearish pullback templates + 4 bullish confirmations         |
//+------------------------------------------------------------------+
#property copyright "SNIPER PRO 2024"
#property version   "2.00"
#property strict

#include <Trade/Trade.mqh>

input group "=== CORE SETTINGS ==="
input bool EnableTrading = true;
input long ExpertMagicNumber = 202602;
input ENUM_TIMEFRAMES SignalTimeframe = PERIOD_M15;
input int RequiredBars = 180;
input int CooldownBarsAfterEntry = 2;

input group "=== RISK / EXECUTION ==="
input double RiskPercentPerTrade = 0.50;
input double StopLossATRMultiplier = 1.60;
input double TakeProfitRR = 2.20;
input double MaxSpreadPoints = 45.0;
input int MaxSlippagePoints = 20;
input bool OnePositionPerSymbol = true;

input group "=== TRUE MULTI-TIMEFRAME CONFIRMATION ==="
input bool UseTrueMultiTimeframeConfirmation = true;
input ENUM_TIMEFRAMES ConfirmTimeframe1 = PERIOD_H1;
input ENUM_TIMEFRAMES ConfirmTimeframe2 = PERIOD_H4;
input ENUM_TIMEFRAMES ConfirmTimeframe3 = PERIOD_D1;
input bool RequireAllConfiguredTimeframes = true;
input int MinAlignedTimeframes = 3;
input double MinTimeframeConfidence = 55.0;

input group "=== ICT CONFLUENCE MODULE ==="
input bool EnableICTConfluence = true;
input bool UseFairValueGaps = true;
input bool UseOrderBlocks = true;
input bool UseLiquiditySweeps = true;
input bool UseMarketStructure = true;
input int MinICTConfluenceFactors = 2;
input int ICTOrderBlockLookback = 24;
input double MinFVGSizePips = 3.0;
input double MinSweepPips = 1.0;

input group "=== PATTERN EVIDENCE GATE ==="
input double MinEvidenceConfidence = 62.0;
input double MinRegimeConfidence = 30.0;
input bool RequireRegimeAlignment = true;
input double CounterSignalPenalty = 0.30;
input double BaseConfidenceBlend = 0.35;

input group "=== TRAILING MANAGEMENT ==="
input bool UseTrailingStop = true;
input double TrailingStopATRMultiplier = 2.0;

//--- Indicator handles
int g_ema21_handle = INVALID_HANDLE;
int g_ema50_handle = INVALID_HANDLE;
int g_rsi14_handle = INVALID_HANDLE;
int g_atr14_handle = INVALID_HANDLE;
int g_adx14_handle = INVALID_HANDLE;

//--- Runtime state
datetime g_last_bar_time = 0;
int g_last_trade_bar_count = -100000;
string g_last_status = "INITIALIZING";
string g_last_regime = "UNKNOWN";
double g_last_confidence = 0.0;
double g_last_bearish_score = 0.0;
double g_last_bullish_score = 0.0;
string g_last_mtf_summary = "N/A";
int g_last_mtf_pass = 0;
int g_last_mtf_total = 0;

CTrade g_trade;

//--- Template weights
double g_bearish_weights[6] = {1.00, 1.00, 0.95, 0.90, 0.85, 0.85};
double g_bullish_weights[4] = {1.00, 1.00, 0.95, 0.90};

//+------------------------------------------------------------------+
//| Utility                                                           |
//+------------------------------------------------------------------+
double Clamp(const double value, const double min_v, const double max_v)
{
   if(value < min_v) return min_v;
   if(value > max_v) return max_v;
   return value;
}

int DigitsForVolumeStep(const double step)
{
   if(step <= 0.0)
      return 2;

   int digits = 0;
   double x = step;
   while(digits < 8 && MathAbs(x - MathRound(x)) > 1e-8)
   {
      x *= 10.0;
      digits++;
   }
   return digits;
}

double NormalizePrice(const double price)
{
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   return NormalizeDouble(price, digits);
}

string TimeframeToString(const ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1: return "M1";
      case PERIOD_M5: return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1: return "H1";
      case PERIOD_H4: return "H4";
      case PERIOD_D1: return "D1";
      case PERIOD_W1: return "W1";
      case PERIOD_MN1: return "MN1";
      default: return IntegerToString((int)tf);
   }
}

void ReleaseIndicatorHandle(int &handle)
{
   if(handle != INVALID_HANDLE)
   {
      IndicatorRelease(handle);
      handle = INVALID_HANDLE;
   }
}

bool AddUniqueTimeframe(const ENUM_TIMEFRAMES timeframe, ENUM_TIMEFRAMES &values[], int &count)
{
   if((int)timeframe <= 0)
      return false;

   for(int i = 0; i < count; i++)
   {
      if(values[i] == timeframe)
         return false;
   }

   ArrayResize(values, count + 1);
   values[count] = timeframe;
   count++;
   return true;
}

bool LoadSignalDataForTimeframe(
   const ENUM_TIMEFRAMES timeframe,
   const int required_bars,
   MqlRates &rates[],
   double &ema21[],
   double &ema50[],
   double &rsi14[],
   double &atr14[],
   double &adx14[],
   string &reason
)
{
   int bars = Bars(_Symbol, timeframe);
   if(bars < required_bars)
   {
      reason = "insufficient_bars_" + TimeframeToString(timeframe);
      return false;
   }

   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, timeframe, 0, required_bars, rates);
   if(copied < 80)
   {
      reason = "copy_rates_failed_" + TimeframeToString(timeframe);
      return false;
   }

   int ema21_handle = iMA(_Symbol, timeframe, 21, 0, MODE_EMA, PRICE_CLOSE);
   int ema50_handle = iMA(_Symbol, timeframe, 50, 0, MODE_EMA, PRICE_CLOSE);
   int rsi14_handle = iRSI(_Symbol, timeframe, 14, PRICE_CLOSE);
   int atr14_handle = iATR(_Symbol, timeframe, 14);
   int adx14_handle = iADX(_Symbol, timeframe, 14);

   if(
      ema21_handle == INVALID_HANDLE ||
      ema50_handle == INVALID_HANDLE ||
      rsi14_handle == INVALID_HANDLE ||
      atr14_handle == INVALID_HANDLE ||
      adx14_handle == INVALID_HANDLE
   )
   {
      reason = "indicator_init_failed_" + TimeframeToString(timeframe);
      ReleaseIndicatorHandle(ema21_handle);
      ReleaseIndicatorHandle(ema50_handle);
      ReleaseIndicatorHandle(rsi14_handle);
      ReleaseIndicatorHandle(atr14_handle);
      ReleaseIndicatorHandle(adx14_handle);
      return false;
   }

   ArraySetAsSeries(ema21, true);
   ArraySetAsSeries(ema50, true);
   ArraySetAsSeries(rsi14, true);
   ArraySetAsSeries(atr14, true);
   ArraySetAsSeries(adx14, true);

   int need = MathMax(80, MathMin(copied, required_bars));
   bool copied_ok = (
      CopyBuffer(ema21_handle, 0, 0, need, ema21) >= 80 &&
      CopyBuffer(ema50_handle, 0, 0, need, ema50) >= 80 &&
      CopyBuffer(rsi14_handle, 0, 0, need, rsi14) >= 80 &&
      CopyBuffer(atr14_handle, 0, 0, need, atr14) >= 80 &&
      CopyBuffer(adx14_handle, 0, 0, need, adx14) >= 80
   );

   ReleaseIndicatorHandle(ema21_handle);
   ReleaseIndicatorHandle(ema50_handle);
   ReleaseIndicatorHandle(rsi14_handle);
   ReleaseIndicatorHandle(atr14_handle);
   ReleaseIndicatorHandle(adx14_handle);

   if(!copied_ok)
   {
      reason = "indicator_copy_failed_" + TimeframeToString(timeframe);
      return false;
   }

   reason = "ok";
   return true;
}

double WeightedScore(const bool &conditions[], const double &weights[])
{
   int n = ArraySize(conditions);
   if(n <= 0 || n != ArraySize(weights))
      return 0.0;

   double total = 0.0;
   double earned = 0.0;
   for(int i = 0; i < n; i++)
   {
      total += MathMax(weights[i], 0.0);
      if(conditions[i])
         earned += MathMax(weights[i], 0.0);
   }

   if(total <= 0.0)
      return 0.0;

   return Clamp((earned / total) * 100.0, 0.0, 100.0);
}

double WeightedAverage(const double &scores[], const double &weights[])
{
   int n = ArraySize(scores);
   if(n <= 0 || n != ArraySize(weights))
      return 0.0;

   double weighted = 0.0;
   double total = 0.0;
   for(int i = 0; i < n; i++)
   {
      double w = MathMax(weights[i], 0.0);
      total += w;
      weighted += Clamp(scores[i], 0.0, 100.0) * w;
   }

   if(total <= 0.0)
      return 0.0;

   return Clamp(weighted / total, 0.0, 100.0);
}

double HighestHigh(const MqlRates &rates[], int start, int length)
{
   int size = ArraySize(rates);
   if(size <= 0 || start >= size || length <= 0)
      return 0.0;

   int end = MathMin(start + length, size);
   double v = rates[start].high;
   for(int i = start + 1; i < end; i++)
   {
      if(rates[i].high > v)
         v = rates[i].high;
   }
   return v;
}

double LowestLow(const MqlRates &rates[], int start, int length)
{
   int size = ArraySize(rates);
   if(size <= 0 || start >= size || length <= 0)
      return 0.0;

   int end = MathMin(start + length, size);
   double v = rates[start].low;
   for(int i = start + 1; i < end; i++)
   {
      if(rates[i].low < v)
         v = rates[i].low;
   }
   return v;
}

double AverageTickVolume(const MqlRates &rates[], int start, int length)
{
   int size = ArraySize(rates);
   if(size <= 0 || start >= size || length <= 0)
      return 0.0;

   int end = MathMin(start + length, size);
   double total = 0.0;
   int count = 0;

   for(int i = start; i < end; i++)
   {
      total += (double)rates[i].tick_volume;
      count++;
   }

   return (count > 0) ? (total / count) : 0.0;
}

bool IsNewBar()
{
   datetime now_bar = iTime(_Symbol, SignalTimeframe, 0);
   if(now_bar <= 0)
      return false;

   if(now_bar != g_last_bar_time)
   {
      g_last_bar_time = now_bar;
      return true;
   }
   return false;
}

bool HasOpenPositionForSymbolMagic()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      if(!PositionSelectByTicket(ticket))
         continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      long magic = PositionGetInteger(POSITION_MAGIC);
      if(symbol == _Symbol && magic == ExpertMagicNumber)
         return true;
   }

   return false;
}

double CurrentSpreadPoints()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0.0 || bid <= 0.0)
      return 0.0;

   return (ask - bid) / _Point;
}

bool CanTradeNow()
{
   if(!EnableTrading)
   {
      g_last_status = "Trading disabled by input";
      return false;
   }

   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      g_last_status = "Terminal or EA trade permission disabled";
      return false;
   }

   if(CurrentSpreadPoints() > MaxSpreadPoints)
   {
      g_last_status = "Spread too high";
      return false;
   }

   if(OnePositionPerSymbol && HasOpenPositionForSymbolMagic())
   {
      g_last_status = "Existing position for symbol/magic";
      return false;
   }

   int current_bars = Bars(_Symbol, SignalTimeframe);
   if(current_bars - g_last_trade_bar_count <= CooldownBarsAfterEntry)
   {
      g_last_status = "Cooldown bars active";
      return false;
   }

   return true;
}

double CalculateLotByRisk(const double stop_distance_price)
{
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(step <= 0.0)
      step = 0.01;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_money = balance * (RiskPercentPerTrade / 100.0);

   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick_value <= 0.0 || tick_size <= 0.0 || stop_distance_price <= 0.0)
      return min_lot;

   double stop_ticks = stop_distance_price / tick_size;
   double money_per_lot = stop_ticks * tick_value;
   if(money_per_lot <= 0.0)
      return min_lot;

   double lot = risk_money / money_per_lot;
   lot = MathFloor(lot / step) * step;
   lot = MathMax(min_lot, MathMin(max_lot, lot));

   int lot_digits = DigitsForVolumeStep(step);
   return NormalizeDouble(lot, lot_digits);
}

bool ModifyPositionSLTP(const ulong ticket, const double new_sl, const double new_tp)
{
   MqlTradeRequest req;
   MqlTradeResult res;
   ZeroMemory(req);
   ZeroMemory(res);

   req.action = TRADE_ACTION_SLTP;
   req.symbol = _Symbol;
   req.position = ticket;
   req.sl = NormalizePrice(new_sl);
   req.tp = NormalizePrice(new_tp);

   return OrderSend(req, res);
}

//+------------------------------------------------------------------+
//| Template scorers                                                  |
//+------------------------------------------------------------------+
double ScoreBearishEngulfingRejection(const MqlRates &rates[], const double atr)
{
   if(ArraySize(rates) < 35)
      return 0.0;

   MqlRates curr = rates[0];
   MqlRates prev = rates[1];
   double recent_high = HighestHigh(rates, 1, 30);
   double prev_body = MathAbs(prev.close - prev.open);
   double curr_body = MathAbs(curr.close - curr.open);

   bool conds[];
   double w[];
   ArrayResize(conds, 5);
   ArrayResize(w, 5);

   conds[0] = prev.close > prev.open;
   conds[1] = curr.close < curr.open;
   conds[2] = (curr.open >= prev.close && curr.close <= prev.open);
   conds[3] = curr_body >= MathMax(prev_body * 0.90, _Point);
   conds[4] = (recent_high - MathMax(curr.open, curr.close)) <= MathMax(atr * 1.2, _Point);

   w[0] = 1.0; w[1] = 1.0; w[2] = 1.4; w[3] = 0.9; w[4] = 0.9;
   return WeightedScore(conds, w);
}

double ScoreLowerHighBreakdown(const MqlRates &rates[], const double atr, const double ema21, const double ema50)
{
   if(ArraySize(rates) < 10)
      return 0.0;

   MqlRates curr = rates[0];
   double body = MathAbs(curr.close - curr.open);

   bool conds[];
   double w[];
   ArrayResize(conds, 5);
   ArrayResize(w, 5);

   conds[0] = curr.high < rates[2].high;
   conds[1] = curr.close < rates[1].low;
   conds[2] = ema21 < ema50;
   conds[3] = curr.close < curr.open;
   conds[4] = body >= MathMax(atr * 0.35, _Point);

   w[0] = 1.1; w[1] = 1.2; w[2] = 1.1; w[3] = 0.8; w[4] = 0.8;
   return WeightedScore(conds, w);
}

double ScoreEma21PullbackReject(const MqlRates &rates[], const double atr, const double ema21_now, const double ema21_prev, const double ema50_now)
{
   if(ArraySize(rates) < 8)
      return 0.0;

   MqlRates curr = rates[0];
   double upper_wick = curr.high - MathMax(curr.open, curr.close);
   double body = MathAbs(curr.close - curr.open);
   double touched = HighestHigh(rates, 1, 4);

   bool conds[];
   double w[];
   ArrayResize(conds, 5);
   ArrayResize(w, 5);

   conds[0] = ema21_now < ema50_now;
   conds[1] = touched >= ema21_prev;
   conds[2] = curr.close < ema21_now;
   conds[3] = curr.close < curr.open;
   conds[4] = upper_wick > body * 0.8 && upper_wick > MathMax(atr * 0.1, _Point);

   w[0] = 1.2; w[1] = 1.0; w[2] = 1.1; w[3] = 0.8; w[4] = 0.8;
   return WeightedScore(conds, w);
}

double ScoreFib618Rejection(const MqlRates &rates[], const double atr, const double rsi, const double ema21, const double ema50)
{
   if(ArraySize(rates) < 45)
      return 0.0;

   MqlRates curr = rates[0];
   double swing_high = HighestHigh(rates, 5, 30);
   double swing_low = LowestLow(rates, 5, 30);
   double leg = MathMax(swing_high - swing_low, _Point);
   double retrace = (curr.close - swing_low) / leg;

   bool conds[];
   double w[];
   ArrayResize(conds, 6);
   ArrayResize(w, 6);

   conds[0] = (retrace >= 0.48 && retrace <= 0.72);
   conds[1] = curr.close < curr.open;
   conds[2] = ema21 < ema50;
   conds[3] = curr.high >= (swing_low + leg * 0.55);
   conds[4] = rsi < 55.0;
   conds[5] = (curr.high - curr.low) >= MathMax(atr * 0.35, _Point);

   w[0] = 1.3; w[1] = 1.0; w[2] = 1.0; w[3] = 0.8; w[4] = 0.7; w[5] = 0.7;
   return WeightedScore(conds, w);
}

double ScoreInsideBarBreakdown(const MqlRates &rates[], const double atr, const double ema21, const double ema50)
{
   if(ArraySize(rates) < 8)
      return 0.0;

   MqlRates mother = rates[2];
   MqlRates inside = rates[1];
   MqlRates curr = rates[0];

   double body = MathAbs(curr.close - curr.open);
   double inside_range = MathMax(inside.high - inside.low, _Point);

   bool conds[];
   double w[];
   ArrayResize(conds, 6);
   ArrayResize(w, 6);

   conds[0] = inside.high < mother.high && inside.low > mother.low;
   conds[1] = curr.close < inside.low;
   conds[2] = curr.close < curr.open;
   conds[3] = body > inside_range * 0.40;
   conds[4] = ema21 < ema50;
   conds[5] = (curr.high - curr.low) >= MathMax(atr * 0.30, _Point);

   w[0] = 1.2; w[1] = 1.3; w[2] = 0.8; w[3] = 0.8; w[4] = 0.9; w[5] = 0.6;
   return WeightedScore(conds, w);
}

double ScoreRsiFailureSwingBear(const MqlRates &rates[], const double atr, const double &rsi_vals[], const double ema21, const double ema50)
{
   if(ArraySize(rates) < 10 || ArraySize(rsi_vals) < 10)
      return 0.0;

   double max_rsi = rsi_vals[1];
   for(int i = 1; i <= 8 && i < ArraySize(rsi_vals); i++)
   {
      if(rsi_vals[i] > max_rsi)
         max_rsi = rsi_vals[i];
   }

   bool conds[];
   double w[];
   ArrayResize(conds, 6);
   ArrayResize(w, 6);

   conds[0] = max_rsi > 60.0;
   conds[1] = rsi_vals[0] < 50.0;
   conds[2] = rates[0].high <= rates[2].high;
   conds[3] = rates[0].close < rates[1].close;
   conds[4] = ema21 < ema50;
   conds[5] = atr > 0.0;

   w[0] = 1.1; w[1] = 1.1; w[2] = 0.9; w[3] = 0.9; w[4] = 1.0; w[5] = 0.5;
   return WeightedScore(conds, w);
}

double ScoreBullishEngulfingSupport(const MqlRates &rates[], const double atr)
{
   if(ArraySize(rates) < 35)
      return 0.0;

   MqlRates curr = rates[0];
   MqlRates prev = rates[1];
   double recent_low = LowestLow(rates, 1, 30);
   double prev_body = MathAbs(prev.close - prev.open);
   double curr_body = MathAbs(curr.close - curr.open);

   bool conds[];
   double w[];
   ArrayResize(conds, 5);
   ArrayResize(w, 5);

   conds[0] = prev.close < prev.open;
   conds[1] = curr.close > curr.open;
   conds[2] = (curr.open <= prev.close && curr.close >= prev.open);
   conds[3] = curr_body >= MathMax(prev_body * 0.90, _Point);
   conds[4] = (MathMin(curr.open, curr.close) - recent_low) <= MathMax(atr * 1.2, _Point);

   w[0] = 1.0; w[1] = 1.0; w[2] = 1.4; w[3] = 0.9; w[4] = 0.9;
   return WeightedScore(conds, w);
}

double ScoreHigherLowBreakout(const MqlRates &rates[], const double atr, const double ema21, const double ema50)
{
   if(ArraySize(rates) < 10)
      return 0.0;

   MqlRates curr = rates[0];
   double body = MathAbs(curr.close - curr.open);

   bool conds[];
   double w[];
   ArrayResize(conds, 5);
   ArrayResize(w, 5);

   conds[0] = rates[1].low > rates[3].low;
   conds[1] = curr.close > rates[1].high;
   conds[2] = ema21 > ema50;
   conds[3] = curr.close > curr.open;
   conds[4] = body >= MathMax(atr * 0.35, _Point);

   w[0] = 1.1; w[1] = 1.2; w[2] = 1.1; w[3] = 0.8; w[4] = 0.8;
   return WeightedScore(conds, w);
}

double ScoreEma21ReclaimContinuation(const MqlRates &rates[], const double atr, const double ema21_now, const double ema21_prev, const double ema50_now)
{
   if(ArraySize(rates) < 8)
      return 0.0;

   MqlRates curr = rates[0];
   double lower_wick = MathMin(curr.open, curr.close) - curr.low;
   double body = MathAbs(curr.close - curr.open);
   double min_recent_low = LowestLow(rates, 1, 4);

   bool conds[];
   double w[];
   ArrayResize(conds, 5);
   ArrayResize(w, 5);

   conds[0] = ema21_now > ema50_now;
   conds[1] = min_recent_low <= ema21_prev;
   conds[2] = curr.close > ema21_now;
   conds[3] = curr.close > curr.open;
   conds[4] = lower_wick > body * 0.5 && lower_wick > MathMax(atr * 0.1, _Point);

   w[0] = 1.2; w[1] = 1.0; w[2] = 1.1; w[3] = 0.8; w[4] = 0.8;
   return WeightedScore(conds, w);
}

double ScoreVolumeMomentumBreakout(const MqlRates &rates[], const double rsi_now, const double ema21, const double ema50)
{
   if(ArraySize(rates) < 30)
      return 0.0;

   MqlRates curr = rates[0];
   double prior_high = HighestHigh(rates, 1, 21);
   double avg_vol = AverageTickVolume(rates, 1, 20);
   double vol_ratio = (avg_vol > 0.0) ? ((double)curr.tick_volume / avg_vol) : 1.0;

   bool conds[];
   double w[];
   ArrayResize(conds, 5);
   ArrayResize(w, 5);

   conds[0] = curr.close > prior_high;
   conds[1] = rsi_now > 55.0;
   conds[2] = vol_ratio >= 1.05;
   conds[3] = ema21 > ema50;
   conds[4] = curr.close > rates[3].close;

   w[0] = 1.4; w[1] = 1.0; w[2] = 1.0; w[3] = 0.9; w[4] = 0.7;
   return WeightedScore(conds, w);
}

int DetectFairValueGapFromRates(const MqlRates &rates[])
{
   if(ArraySize(rates) < 3 || !UseFairValueGaps)
      return 0;

   double min_gap_size = MinFVGSizePips * _Point * 10.0;

   if(rates[0].low > rates[2].high)
   {
      if((rates[0].low - rates[2].high) >= min_gap_size)
         return 1;
   }

   if(rates[0].high < rates[2].low)
   {
      if((rates[2].low - rates[0].high) >= min_gap_size)
         return -1;
   }

   return 0;
}

int DetectOrderBlockFromRates(const MqlRates &rates[])
{
   if(!UseOrderBlocks)
      return 0;

   int size = ArraySize(rates);
   int bars = MathMin(size, MathMax(ICTOrderBlockLookback, 8));
   if(bars < 8)
      return 0;

   for(int i = 5; i < bars - 3; i++)
   {
      if(rates[i].close < rates[i].open)
      {
         int up_candles = 0;
         for(int j = i - 1; j >= i - 3; j--)
         {
            if(rates[j].close > rates[j].open)
               up_candles++;
         }
         if(up_candles >= 2)
            return 1;
      }
   }

   for(int i = 5; i < bars - 3; i++)
   {
      if(rates[i].close > rates[i].open)
      {
         int down_candles = 0;
         for(int j = i - 1; j >= i - 3; j--)
         {
            if(rates[j].close < rates[j].open)
               down_candles++;
         }
         if(down_candles >= 2)
            return -1;
      }
   }

   return 0;
}

int DetectLiquiditySweepFromRates(const MqlRates &rates[])
{
   if(!UseLiquiditySweeps)
      return 0;

   int size = ArraySize(rates);
   if(size < 20)
      return 0;

   int lookback = MathMin(20, size);
   double swing_high = rates[1].high;
   double swing_low = rates[1].low;

   for(int i = 2; i < lookback; i++)
   {
      swing_high = MathMax(swing_high, rates[i].high);
      swing_low = MathMin(swing_low, rates[i].low);
   }

   double min_sweep = MinSweepPips * _Point * 10.0;

   if(rates[0].high > swing_high && rates[0].close < swing_high)
   {
      if((rates[0].high - swing_high) >= min_sweep)
         return -1;
   }

   if(rates[0].low < swing_low && rates[0].close > swing_low)
   {
      if((swing_low - rates[0].low) >= min_sweep)
         return 1;
   }

   return 0;
}

int AnalyzeMarketStructureFromRates(const MqlRates &rates[])
{
   if(!UseMarketStructure)
      return 0;

   int size = ArraySize(rates);
   if(size < 50)
      return 0;

   bool higher_highs = true;
   bool higher_lows = true;
   bool lower_highs = true;
   bool lower_lows = true;

   for(int i = 10; i < 40 && (i + 10) < size; i += 10)
   {
      if(rates[i].high <= rates[i + 10].high)
         higher_highs = false;
      if(rates[i].low <= rates[i + 10].low)
         higher_lows = false;

      if(rates[i].high >= rates[i + 10].high)
         lower_highs = false;
      if(rates[i].low >= rates[i + 10].low)
         lower_lows = false;
   }

   if(higher_highs && higher_lows)
      return 1;
   if(lower_highs && lower_lows)
      return -1;

   return 0;
}

int AnalyzeICTConfluenceFromRates(const MqlRates &rates[])
{
   if(!EnableICTConfluence)
      return 0;

   int bullish = 0;
   int bearish = 0;
   int confluence = 0;

   int fvg_signal = DetectFairValueGapFromRates(rates);
   if(fvg_signal == 1) { bullish++; confluence++; }
   else if(fvg_signal == -1) { bearish++; confluence++; }

   int ob_signal = DetectOrderBlockFromRates(rates);
   if(ob_signal == 1) { bullish++; confluence++; }
   else if(ob_signal == -1) { bearish++; confluence++; }

   int liq_signal = DetectLiquiditySweepFromRates(rates);
   if(liq_signal == 1) { bullish++; confluence++; }
   else if(liq_signal == -1) { bearish++; confluence++; }

   int structure_signal = AnalyzeMarketStructureFromRates(rates);
   if(structure_signal == 1) { bullish++; confluence++; }
   else if(structure_signal == -1) { bearish++; confluence++; }

   if(confluence < MathMax(1, MinICTConfluenceFactors))
      return 0;

   if(bullish > bearish && bullish >= 2)
      return 1;
   if(bearish > bullish && bearish >= 2)
      return -1;

   return 0;
}

//+------------------------------------------------------------------+
//| Evidence + regime                                                 |
//+------------------------------------------------------------------+
string DetectRegime(const double ema21, const double ema50, const double adx, double &confidence)
{
   double gap_points = MathAbs(ema21 - ema50) / _Point;
   confidence = Clamp((gap_points / 140.0) * 100.0, 0.0, 100.0);

   if(ema21 > ema50)
   {
      if(adx >= 25.0)
         return "STRONG_UPTREND";
      if(adx >= 18.0)
         return "MODERATE_UPTREND";
      return "TRANSITION";
   }

   if(ema21 < ema50)
   {
      if(adx >= 25.0)
         return "STRONG_DOWNTREND";
      if(adx >= 18.0)
         return "MODERATE_DOWNTREND";
      return "TRANSITION";
   }

   return "RANGING";
}

bool RegimeAllowsDirection(const string regime, const int direction)
{
   if(!RequireRegimeAlignment)
      return true;

   if(direction > 0)
   {
      return (regime == "STRONG_UPTREND" || regime == "MODERATE_UPTREND" || regime == "TRANSITION" || regime == "RANGING");
   }

   if(direction < 0)
   {
      return (regime == "STRONG_DOWNTREND" || regime == "MODERATE_DOWNTREND" || regime == "TRANSITION" || regime == "RANGING");
   }

   return false;
}

bool BuildPatternEvidence(
   const MqlRates &rates[],
   const double &ema21[],
   const double &ema50[],
   const double &rsi14[],
   const double &atr14[],
   const double &adx14[],
   int &direction,
   double &confidence,
   string &reason
)
{
   int count = ArraySize(rates);
   if(count < 60)
   {
      reason = "insufficient_data";
      return false;
   }

   double atr = MathMax(atr14[0], _Point);
   double adx = MathMax(adx14[0], 0.0);

   double bearish_scores[];
   ArrayResize(bearish_scores, 6);
   bearish_scores[0] = ScoreBearishEngulfingRejection(rates, atr);
   bearish_scores[1] = ScoreLowerHighBreakdown(rates, atr, ema21[0], ema50[0]);
   bearish_scores[2] = ScoreEma21PullbackReject(rates, atr, ema21[0], ema21[1], ema50[0]);
   bearish_scores[3] = ScoreFib618Rejection(rates, atr, rsi14[0], ema21[0], ema50[0]);
   bearish_scores[4] = ScoreInsideBarBreakdown(rates, atr, ema21[0], ema50[0]);
   bearish_scores[5] = ScoreRsiFailureSwingBear(rates, atr, rsi14, ema21[0], ema50[0]);

   double bullish_scores[];
   ArrayResize(bullish_scores, 4);
   bullish_scores[0] = ScoreBullishEngulfingSupport(rates, atr);
   bullish_scores[1] = ScoreHigherLowBreakout(rates, atr, ema21[0], ema50[0]);
   bullish_scores[2] = ScoreEma21ReclaimContinuation(rates, atr, ema21[0], ema21[1], ema50[0]);
   bullish_scores[3] = ScoreVolumeMomentumBreakout(rates, rsi14[0], ema21[0], ema50[0]);

   double bearish_family = WeightedAverage(bearish_scores, g_bearish_weights);
   double bullish_family = WeightedAverage(bullish_scores, g_bullish_weights);

   g_last_bearish_score = bearish_family;
   g_last_bullish_score = bullish_family;

   double regime_conf = 0.0;
   string regime = DetectRegime(ema21[0], ema50[0], adx, regime_conf);
   g_last_regime = regime;

   int best_direction = 0;
   double primary_score = 0.0;
   double counter_score = 0.0;

   if(bullish_family > bearish_family)
   {
      best_direction = 1;
      primary_score = bullish_family;
      counter_score = bearish_family;
   }
   else if(bearish_family > bullish_family)
   {
      best_direction = -1;
      primary_score = bearish_family;
      counter_score = bullish_family;
   }
   else
   {
      reason = "no_direction_edge";
      confidence = 0.0;
      g_last_confidence = confidence;
      return false;
   }

   bool regime_allowed = RegimeAllowsDirection(regime, best_direction) && regime_conf >= MinRegimeConfidence;

   double base_conf = Clamp(adx * 2.0, 0.0, 100.0);
   double blended = primary_score * (1.0 - BaseConfidenceBlend) + base_conf * BaseConfidenceBlend;
   double final_conf = blended - (counter_score * CounterSignalPenalty);
   final_conf += regime_allowed ? 5.0 : -25.0;
   final_conf = Clamp(final_conf, 0.0, 100.0);

   confidence = final_conf;
   g_last_confidence = confidence;

   if(!regime_allowed)
   {
      reason = "regime_block";
      return false;
   }

   if(final_conf < MinEvidenceConfidence)
   {
      reason = "confidence_below_threshold";
      return false;
   }

   direction = best_direction;
   reason = "pattern_evidence_pass";
   return true;
}

bool EvaluateTimeframeSignal(
   const ENUM_TIMEFRAMES timeframe,
   int &direction,
   double &confidence,
   double &atr_value,
   string &reason
)
{
   direction = 0;
   confidence = 0.0;
   atr_value = 0.0;

   MqlRates rates[];
   double ema21[];
   double ema50[];
   double rsi14[];
   double atr14[];
   double adx14[];
   string load_reason = "";

   if(!LoadSignalDataForTimeframe(timeframe, RequiredBars, rates, ema21, ema50, rsi14, atr14, adx14, load_reason))
   {
      reason = load_reason;
      return false;
   }

   int pattern_direction = 0;
   double pattern_confidence = 0.0;
   string pattern_reason = "";
   bool pattern_pass = BuildPatternEvidence(
      rates,
      ema21,
      ema50,
      rsi14,
      atr14,
      adx14,
      pattern_direction,
      pattern_confidence,
      pattern_reason
   );

   if(!pattern_pass)
   {
      reason = "pattern_" + pattern_reason;
      return false;
   }

   if(pattern_confidence < MinTimeframeConfidence)
   {
      reason = "pattern_conf_low";
      return false;
   }

   if(EnableICTConfluence)
   {
      int ict_signal = AnalyzeICTConfluenceFromRates(rates);
      if(ict_signal == 0)
      {
         reason = "ict_no_edge";
         return false;
      }
      if(ict_signal != pattern_direction)
      {
         reason = "ict_pattern_mismatch";
         return false;
      }
   }

   direction = pattern_direction;
   confidence = pattern_confidence;
   atr_value = MathMax(atr14[0], _Point);
   reason = "pass";
   return true;
}

bool EvaluateMultiTimeframeConsensus(
   int &direction,
   double &confidence,
   double &signal_atr,
   string &reason
)
{
   direction = 0;
   confidence = 0.0;
   signal_atr = MathMax(signal_atr, _Point);

   ENUM_TIMEFRAMES timeframes[];
   int tf_count = 0;
   AddUniqueTimeframe(SignalTimeframe, timeframes, tf_count);

   if(UseTrueMultiTimeframeConfirmation)
   {
      AddUniqueTimeframe(ConfirmTimeframe1, timeframes, tf_count);
      AddUniqueTimeframe(ConfirmTimeframe2, timeframes, tf_count);
      AddUniqueTimeframe(ConfirmTimeframe3, timeframes, tf_count);
   }

   if(tf_count <= 0)
   {
      reason = "no_timeframes_configured";
      return false;
   }

   int aligned = 0;
   int base_direction = 0;
   double confidence_sum = 0.0;
   bool signal_tf_passed = false;
   string summary = "";

   for(int i = 0; i < tf_count; i++)
   {
      ENUM_TIMEFRAMES tf = timeframes[i];
      int tf_direction = 0;
      double tf_confidence = 0.0;
      double tf_atr = 0.0;
      string tf_reason = "";
      string tf_label = TimeframeToString(tf);

      bool tf_pass = EvaluateTimeframeSignal(tf, tf_direction, tf_confidence, tf_atr, tf_reason);
      if(!tf_pass)
      {
         summary += tf_label + ":FAIL(" + tf_reason + ") ";
         continue;
      }

      if(tf == SignalTimeframe)
      {
         signal_tf_passed = true;
         signal_atr = MathMax(tf_atr, _Point);
      }

      string tf_direction_text = (tf_direction > 0 ? "BUY" : "SELL");
      if(base_direction == 0)
      {
         base_direction = tf_direction;
         aligned = 1;
         confidence_sum += tf_confidence;
         summary += tf_label + ":PASS_" + tf_direction_text + "_" + DoubleToString(tf_confidence, 1) + " ";
         continue;
      }

      if(tf_direction == base_direction)
      {
         aligned++;
         confidence_sum += tf_confidence;
         summary += tf_label + ":PASS_" + tf_direction_text + "_" + DoubleToString(tf_confidence, 1) + " ";
      }
      else
      {
         summary += tf_label + ":FAIL(direction_mismatch) ";
      }
   }

   int required = 1;
   if(UseTrueMultiTimeframeConfirmation)
   {
      required = tf_count;
      if(!RequireAllConfiguredTimeframes)
         required = MathMax(1, MathMin(MinAlignedTimeframes, tf_count));
   }

   g_last_mtf_total = tf_count;
   g_last_mtf_pass = aligned;
   g_last_mtf_summary = summary;

   if(!signal_tf_passed)
   {
      reason = "signal_tf_not_confirmed";
      return false;
   }

   if(base_direction == 0)
   {
      reason = "no_direction";
      return false;
   }

   if(aligned < required)
   {
      reason = "mtf_alignment_" + IntegerToString(aligned) + "/" + IntegerToString(required);
      return false;
   }

   direction = base_direction;
   confidence = confidence_sum / MathMax(1, aligned);
   reason = "mtf_pass";
   return true;
}

bool ExecuteSignal(const int direction, const double atr, const double confidence)
{
   if(direction == 0)
      return false;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0.0 || bid <= 0.0)
   {
      g_last_status = "Invalid bid/ask";
      return false;
   }

   double stop_distance = MathMax(atr * StopLossATRMultiplier, _Point * 20.0);
   double lot = CalculateLotByRisk(stop_distance);
   if(lot <= 0.0)
   {
      g_last_status = "Lot size <= 0";
      return false;
   }

   double entry = (direction > 0) ? ask : bid;
   double sl = (direction > 0) ? (entry - stop_distance) : (entry + stop_distance);
   double tp = (direction > 0) ? (entry + stop_distance * TakeProfitRR) : (entry - stop_distance * TakeProfitRR);

   entry = NormalizePrice(entry);
   sl = NormalizePrice(sl);
   tp = NormalizePrice(tp);

   g_trade.SetExpertMagicNumber(ExpertMagicNumber);
   g_trade.SetDeviationInPoints(MaxSlippagePoints);

   string comment = StringFormat("SNIPER_PE %.1f", confidence);
   bool ok = false;
   if(direction > 0)
      ok = g_trade.Buy(lot, _Symbol, entry, sl, tp, comment);
   else
      ok = g_trade.Sell(lot, _Symbol, entry, sl, tp, comment);

   if(ok)
   {
      g_last_trade_bar_count = Bars(_Symbol, SignalTimeframe);
      g_last_status = StringFormat("Trade placed (%s) lot=%.2f conf=%.1f", (direction > 0 ? "BUY" : "SELL"), lot, confidence);
      return true;
   }

   g_last_status = StringFormat("Order send failed: %d", (int)g_trade.ResultRetcode());
   return false;
}

void ManageTrailingStops(const double atr)
{
   if(!UseTrailingStop || atr <= 0.0)
      return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double trail = atr * TrailingStopATRMultiplier;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(!PositionSelectByTicket(ticket))
         continue;

      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != ExpertMagicNumber)
         continue;

      long type = PositionGetInteger(POSITION_TYPE);
      double current_sl = PositionGetDouble(POSITION_SL);
      double current_tp = PositionGetDouble(POSITION_TP);

      if(type == POSITION_TYPE_BUY)
      {
         double new_sl = NormalizePrice(bid - trail);
         if(new_sl > current_sl && new_sl < bid)
            ModifyPositionSLTP(ticket, new_sl, current_tp);
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double new_sl = NormalizePrice(ask + trail);
         if((current_sl <= 0.0 || new_sl < current_sl) && new_sl > ask)
            ModifyPositionSLTP(ticket, new_sl, current_tp);
      }
   }
}

void UpdateChartComment()
{
   string txt = "SNIPER PRO 2024 Pattern Evidence EA\n";
   txt += "Status: " + g_last_status + "\n";
   txt += "MTF aligned: " + IntegerToString(g_last_mtf_pass) + "/" + IntegerToString(g_last_mtf_total) + "\n";
   txt += "MTF detail: " + g_last_mtf_summary + "\n";
   txt += "Regime: " + g_last_regime + "\n";
   txt += "Confidence: " + DoubleToString(g_last_confidence, 1) + "\n";
   txt += "Bearish score: " + DoubleToString(g_last_bearish_score, 1) + "\n";
   txt += "Bullish score: " + DoubleToString(g_last_bullish_score, 1) + "\n";
   txt += "Spread(points): " + DoubleToString(CurrentSpreadPoints(), 1);
   Comment(txt);
}

//+------------------------------------------------------------------+
//| Expert lifecycle                                                  |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(ExpertMagicNumber);

   g_ema21_handle = iMA(_Symbol, SignalTimeframe, 21, 0, MODE_EMA, PRICE_CLOSE);
   g_ema50_handle = iMA(_Symbol, SignalTimeframe, 50, 0, MODE_EMA, PRICE_CLOSE);
   g_rsi14_handle = iRSI(_Symbol, SignalTimeframe, 14, PRICE_CLOSE);
   g_atr14_handle = iATR(_Symbol, SignalTimeframe, 14);
   g_adx14_handle = iADX(_Symbol, SignalTimeframe, 14);

   if(g_ema21_handle == INVALID_HANDLE ||
      g_ema50_handle == INVALID_HANDLE ||
      g_rsi14_handle == INVALID_HANDLE ||
      g_atr14_handle == INVALID_HANDLE ||
      g_adx14_handle == INVALID_HANDLE)
   {
      Print("SNIPER EA init failed: indicator handle creation failed");
      return INIT_FAILED;
   }

   g_last_status = "READY";
   Print("SNIPER Pattern Evidence EA initialized");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_ema21_handle != INVALID_HANDLE) IndicatorRelease(g_ema21_handle);
   if(g_ema50_handle != INVALID_HANDLE) IndicatorRelease(g_ema50_handle);
   if(g_rsi14_handle != INVALID_HANDLE) IndicatorRelease(g_rsi14_handle);
   if(g_atr14_handle != INVALID_HANDLE) IndicatorRelease(g_atr14_handle);
   if(g_adx14_handle != INVALID_HANDLE) IndicatorRelease(g_adx14_handle);

   Comment("");
   Print("SNIPER Pattern Evidence EA deinitialized. reason=", reason);
}

void OnTick()
{
   if(!IsNewBar())
      return;

   int bars = Bars(_Symbol, SignalTimeframe);
   if(bars < RequiredBars)
   {
      g_last_status = "Waiting for bars";
      UpdateChartComment();
      return;
   }

   double trail_atr = _Point;
   double trail_atr_buf[];
   ArraySetAsSeries(trail_atr_buf, true);
   if(CopyBuffer(g_atr14_handle, 0, 0, 1, trail_atr_buf) > 0)
      trail_atr = MathMax(trail_atr_buf[0], _Point);

   ManageTrailingStops(trail_atr);

   if(!CanTradeNow())
   {
      UpdateChartComment();
      return;
   }

   int direction = 0;
   double confidence = 0.0;
   double signal_atr = trail_atr;
   string reason = "";

   bool pass = EvaluateMultiTimeframeConsensus(direction, confidence, signal_atr, reason);
   if(!pass)
   {
      g_last_status = "No trade: " + reason;
      UpdateChartComment();
      return;
   }

   ExecuteSignal(direction, MathMax(signal_atr, _Point), confidence);
   UpdateChartComment();
}
