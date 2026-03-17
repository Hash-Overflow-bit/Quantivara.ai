"""
prediction_engine.py — Multi-Timeframe Signal Scoring Engine (Firestore Edition)
PSX Insider — Expected Movers for Day / Week / Month

SIGNALS:
  Day   → D1 Close Strength, D2 Vol Spike, D3 RSI Zone,
           D4 Gap Up, D5 Above MA20, D6 Sector Green
  Week  → W1 3-Day Accumulation, W2 52W Proximity,
           W3 RSI Trend, W4 Announcement, W5 MA50 Reclaim
  Month → M1 Sector Rotation, M2 52W Breakout,
           M3 Earnings Season, M4 PE Value, M5 Vol Trend
"""

import os
import json
import time
import requests
import pytz
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict
from shared import db, PKT, MARKET_OPEN_H, _BASE_DIR
# Import delayed to avoid circular issues
def get_scraper_utils():
    import scraper
    return scraper.get_announcements, scraper.get_all_stocks

# Import signal tracking module
try:
    from signal_tracker import log_signal_outcomes
except ImportError:
    def log_signal_outcomes(ranked, timeframe, run_date):
        pass  # Silently skip if not available

# --- Indicators & Helpers ---

def calc_rsi(closes: pd.Series, period: int = 14) -> float:
    """Calculate RSI."""
    delta = closes.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2) if not rsi.empty else 50.0

def calc_ma(closes: pd.Series, period: int) -> float:
    if len(closes) < period: return 0.0
    return round(float(closes.rolling(window=period).mean().iloc[-1]), 2)

def score_to_bias(score: float) -> str:
    if score >= 75:   return "STRONG_BULLISH"
    if score >= 60:   return "BULLISH"
    if score >= 45:   return "WATCH"
    if score >= 30:   return "NEUTRAL"
    if score >= 15:   return "WEAK"
    return "BEARISH"

def get_trend_regime(hist: pd.DataFrame) -> dict:
    """Analyze MA50/MA200 trend and slope for regime filter."""
    closes = hist['Close']
    if len(closes) < 200:
        return {"trend": "NEUTRAL", "multiplier": 1.0, "slope_50": 0, "slope_200": 0}
    
    ma50 = calc_ma(closes, 50)
    ma200 = calc_ma(closes, 200)
    
    # Calculate slopes (direction of MAs)
    ma50_prev = calc_ma(closes.iloc[:-1], 50)
    ma200_prev = calc_ma(closes.iloc[:-1], 200)
    slope_50 = ma50 - ma50_prev
    slope_200 = ma200 - ma200_prev
    
    current = closes.iloc[-1]
    
    # Determine regime
    if current > ma50 > ma200 and slope_50 > 0 and slope_200 > 0:
        return {"trend": "UPTREND", "multiplier": 1.2, "slope_50": slope_50, "slope_200": slope_200}
    elif current < ma50 < ma200 and slope_50 < 0 and slope_200 < 0:
        return {"trend": "DOWNTREND", "multiplier": 0.6, "slope_50": slope_50, "slope_200": slope_200}
    else:
        return {"trend": "NEUTRAL", "multiplier": 1.0, "slope_50": slope_50, "slope_200": slope_200}

def get_directional_volume(hist: pd.DataFrame, volume_multiple: float) -> dict:
    """
    Analyze volume direction: is it bullish (price up) or bearish (price down)?
    Not just "vol is high" but "high vol on UP day" vs "high vol on DOWN day"
    """
    closes = hist['Close']
    last_close = closes.iloc[-1]
    prev_close = closes.iloc[-2]
    
    price_direction = "UP" if last_close > prev_close else "DOWN" if last_close < prev_close else "FLAT"
    
    if price_direction == "UP":
        return {"direction": "BULLISH_VOLUME", "score_mult": 1.3, "msg": f"Vol {round(volume_multiple, 1)}x avg on UP day"}
    elif price_direction == "DOWN":
        return {"direction": "BEARISH_VOLUME", "score_mult": 0.5, "msg": f"Vol {round(volume_multiple, 1)}x avg on DOWN day (distribution)"}
    else:
        return {"direction": "NEUTRAL_VOLUME", "score_mult": 0.8, "msg": f"Vol {round(volume_multiple, 1)}x avg (no directional context)"}

def count_confluence_signals(signals: dict) -> int:
    """Count how many independent signal types have fired."""
    return len([s for s in signals.keys() if signals[s].get('score', 0) > 0])

def get_confluence_multiplier(signal_count: int) -> float:
    """
    Confluence bonus: multiple signals confirming = stronger score.
    1 signal = 1.0x (baseline)
    2 signals = 1.4x 
    3+ signals = 1.8x
    """
    if signal_count <= 1:
        return 1.0
    elif signal_count == 2:
        return 1.4
    else:
        return 1.8

# --- Signal Logic ---

def calculate_day_signals(hist: pd.DataFrame, info: dict, symbol: str, current_price: float = None, sector_data: dict = None) -> Dict:
    signals = {}
    
    # Use scraped current_price as the primary source of truth for "now"
    # If missing, fallback to yf close
    last_c = current_price if current_price and current_price > 0 else float(hist['Close'].iloc[-1])
    
    # Price Re-anchoring: If scraped price differs significantly from yf, 
    # we need to adjust the history relatively to keep MA/RSI valid.
    yf_last = float(hist['Close'].iloc[-1])
    adjustment_ratio = last_c / yf_last if yf_last > 0 else 1.0
    
    adj_closes = hist['Close'] * adjustment_ratio
    adj_highs = hist['High'] * adjustment_ratio
    adj_lows = hist['Low'] * adjustment_ratio
    
    # PROBLEM 4 FIX: Get trend regime to apply multipliers to bullish signals
    trend_regime = get_trend_regime(hist)
    trend_mult = trend_regime["multiplier"]
    
    # D1: Close Strength (25 pts)
    # User feedback: Only fire if pos >= 0.75. 0% is day's LOW.
    h, l = adj_highs.iloc[-1], adj_lows.iloc[-1]
    rng = h - l
    if rng > 0:
        pos = (last_c - l) / rng
        if pos >= 0.75:
            # Message fix: "Closed top 10% of range" (1-pos)
            top_pct = round((1 - pos) * 100)
            base_score = round(pos * 25, 1)
            final_score = base_score * trend_mult  # Apply trend filter
            signals["D1_close_strength"] = {
                "score": final_score, 
                "base_score": base_score,
                "msg": f"Closed top {top_pct}% of range [{trend_regime['trend']} regime]",
                "trend_adjusted": trend_mult
            }

    # D2: Volume Spike with DIRECTIONAL analysis (20 pts)
    # PROBLEM 3 FIX: Don't just fire on volume multiple - check if it's bullish or bearish
    avg_30 = hist['Volume'].tail(30).mean()
    last_vol = hist['Volume'].iloc[-1]
    if last_vol > 2 * avg_30:
        vol_multiple = last_vol / avg_30
        vol_direction = get_directional_volume(hist, vol_multiple)
        
        base_score = min(vol_multiple * 4, 20)
        final_score = base_score * vol_direction["score_mult"]
        
        signals["D2_vol_spike"] = {
            "score": final_score,
            "base_score": base_score,
            "msg": vol_direction["msg"],
            "direction": vol_direction["direction"]
        }

    # D3: RSI Zone (15 pts) - Use adjusted closes
    # Oversold bounce (RSI oversold + bouncing) scores higher than overbought continuation
    rsi = calc_rsi(adj_closes)
    rsi_prev = calc_rsi(adj_closes.iloc[:-1]) if len(adj_closes) > 1 else rsi
    
    if 30 <= rsi <= 70:  # Expanded zone
        if rsi < 35 and rsi > rsi_prev:  # Oversold bouncing = higher confidence
            signals["D3_rsi_momentum"] = {"score": 18, "msg": f"RSI {round(rsi)} oversold bounce"}
        elif 55 <= rsi <= 75:
            signals["D3_rsi_momentum"] = {"score": 15, "msg": f"RSI {round(rsi)} momentum zone"}
        elif rsi > 70 and last_c > calc_ma(adj_closes, 20):  # Overbought but above MA20 = confirmation
            signals["D3_rsi_momentum"] = {"score": 12, "msg": f"RSI {round(rsi)} overbought confirmation"}

    # D4: Trend Alignment Score (new signal)
    # Price position relative to MAs - only bullish if aligned with trend
    ma20 = calc_ma(adj_closes, 20)
    ma50 = calc_ma(adj_closes, 50)
    
    if last_c > ma20 > ma50 and trend_regime["trend"] in ["UPTREND", "NEUTRAL"]:
        signals["D4_trend_aligned"] = {
            "score": 12,
            "msg": f"Price above MA20 > MA50 [{trend_regime['trend']}]"
        }
    elif last_c < ma20 < ma50 and trend_regime["trend"] in ["DOWNTREND"]:
        # Bearish but aligned with downtrend = not a buy signal
        pass

    # D5: Above MA20 (10 pts) - Use adjusted closes
    ma20 = calc_ma(adj_closes, 20)
    if last_c > ma20:
        signals["D5_above_ma20"] = {"score": 10, "msg": f"Above MA20 ({round(ma20, 1)})"}

    # D6: Sector Green (15 pts)
    if sector_data and info.get('sector'):
        # Map yf sector name to PSX sector name if possible
        yf_sector = info.get('sector')
        for s in sector_data.get('sectors', []):
            # Partial match for sectors (e.g. "Banks" in "Commercial Banks")
            if s['name'].lower() in yf_sector.lower() or yf_sector.lower() in s['name'].lower():
                if s['change'] > 0:
                    signals["D6_sector_green"] = {"score": 15, "msg": f"Sector {s['name']} is Green (+{s['change']}%)"}
                    break

    return signals

def calculate_week_signals(hist: pd.DataFrame, info: dict, symbol: str) -> Dict:
    signals = {}
    closes = hist['Close']
    vols = hist['Volume']
    
    # W1: 3-Day Volume Accumulation (25 pts)
    if len(vols) >= 3:
        if vols.iloc[-1] > vols.iloc[-2] > vols.iloc[-3]:
            signals["W1_accumulation"] = {"score": 25, "msg": "3-day vol rising"}
        elif vols.iloc[-1] > vols.iloc[-2]:
            signals["W1_accumulation"] = {"score": 12, "msg": "2-day vol rising"}

    # W2: 52W Proximity (20 pts)
    high_52w = info.get("fiftyTwoWeekHigh", 0)
    if high_52w > 0:
        prox = closes.iloc[-1] / high_52w
        if prox >= 0.95:
            signals["W2_52w_prox"] = {"score": round(prox * 20, 1), "msg": f"{round((1-prox)*100, 1)}% from 52w high"}

    # W3: RSI Trend (15 pts) - Rising for 3 days
    if len(closes) >= 5:
        rsi1 = calc_rsi(closes.iloc[:-2])
        rsi2 = calc_rsi(closes.iloc[:-1])
        rsi3 = calc_rsi(closes)
        if rsi3 > rsi2 > rsi1:
            signals["W3_rsi_trend"] = {"score": 15, "msg": f"RSI rising trend: {round(rsi3)}"}

    # W5: MA50 Reclaim (15 pts)
    ma50 = calc_ma(closes, 50)
    if closes.iloc[-1] > ma50 and closes.iloc[-3] < ma50:
        signals["W5_ma50_reclaim"] = {"score": 15, "msg": "Reclaimed MA50"}

    return signals

def calculate_month_signals(hist: pd.DataFrame, info: dict, symbol: str) -> Dict:
    signals = {}
    closes = hist['Close']
    
    # M2: 52W Breakout (25 pts)
    high_52w = info.get("fiftyTwoWeekHigh", 0)
    if high_52w > 0 and closes.iloc[-1] > high_52w * 1.01:
        signals["M2_52w_breakout"] = {"score": 25, "msg": "Breakout above 52w high"}
        
    # M4: Fundamental Value (15 pts - Mocked check vs fixed PE)
    pe = info.get("trailingPE", 100)
    if 0 < pe < 12:
        signals["M4_value"] = {"score": 15, "msg": f"Low PE ratio: {round(pe, 1)}"}

    return signals

# --- Engine ---

def run_prediction_engine(timeframe: str = "day"):
    """Scores KSE-100 stocks and updates Firestore with improved scoring."""
    print(f"Running {timeframe} prediction engine...")
    get_annc, get_stocks = get_scraper_utils()
    ann_list = get_annc()
    
    # Fetch real-time price snapshot from scraper's latest state
    all_stocks_list = get_stocks()
    scraped_prices = {s['symbol']: s['price'] for s in all_stocks_list}
    
    # Fetch sector performance from Firestore
    sector_data = None
    if db:
        sec_doc = db.collection("market_sectors").document("latest").get()
        if sec_doc.exists:
            sector_data = sec_doc.to_dict()

    kse100_path = os.path.join(os.path.dirname(__file__), "kse100.json")
    if not os.path.exists(kse100_path): return
    
    with open(kse100_path, 'r') as f:
        tickers = json.load(f)
        
    results = []
    run_date = datetime.now(PKT).strftime('%Y-%m-%d')
    
    for symbol in tickers:
        try:
            ticker = yf.Ticker(f"{symbol}.KA")
            hist = ticker.history(period="6mo", interval="1d", auto_adjust=False)
            if hist.empty: continue
            
            info = ticker.info
            curr_p = scraped_prices.get(symbol)
            
            if timeframe == "day":
                signals = calculate_day_signals(hist, info, symbol, current_price=curr_p, sector_data=sector_data)
            elif timeframe == "week":
                signals = calculate_week_signals(hist, info, symbol)
                # W4: Announcement this week
                upcoming = [a for a in ann_list if a['symbol'] == symbol]
                if upcoming:
                    signals["W4_announcement"] = {"score": 25, "msg": f"Annc: {upcoming[0]['headline'][:30]}..."}
            else:
                signals = calculate_month_signals(hist, info, symbol)
                # M3: Earnings this month (same logic as W4 for MVP)
                upcoming = [a for a in ann_list if a['symbol'] == symbol]
                if upcoming:
                    signals["M3_earnings"] = {"score": 20, "msg": "Earnings due this month"}
            
            # PROBLEM 2 FIX: Apply confluence multiplier (multiple signals = higher confidence)
            signal_count = count_confluence_signals(signals)
            confluence_mult = get_confluence_multiplier(signal_count)
            
            # Calculate base score and apply confluence multiplier
            base_score = sum(s['score'] for s in signals.values())
            final_score = min(base_score * confluence_mult, 100)
            
            if final_score > 0:
                results.append({
                    "symbol": symbol,
                    "score": round(final_score, 1),
                    "base_score": round(base_score, 1),
                    "confluence_count": signal_count,
                    "confluence_multiplier": round(confluence_mult, 2),
                    "bias": score_to_bias(final_score),
                    "signals_fired": [f"{s['msg']}" for s in signals.values()],
                    "price_at_run": round(float(curr_p if curr_p else hist['Close'].iloc[-1]), 2),
                    "timeframe": timeframe,
                    "run_date": run_date,
                    "run_timestamp": datetime.now(PKT).isoformat()
                })
        except Exception as e:
            print(f"Error scoring {symbol}: {e}")
            continue
    
    # PROBLEM 1 FIX: Add percentile ranking for relative context
    if results:
        # Sort by score
        ranked = sorted(results, key=lambda x: x['score'], reverse=True)
        
        # Calculate percentiles across the full universe
        total_count = len(ranked)
        for idx, r in enumerate(ranked):
            percentile = round((idx / total_count) * 100, 1)
            r['percentile'] = percentile
            r['percentile_label'] = f"Top {round(100 - percentile)}% of today's {total_count} stocks"
        
        top_20 = ranked[:20]
    else:
        top_20 = []
        ranked = []
    
    # Save to Firestore
    if db:
        # 1. Save summary doc for quick frontend access (top 20)
        db.collection("predictions").document(f"latest_{timeframe}").set({
            "updated_at": datetime.now(PKT).isoformat(),
            "timeframe": timeframe,
            "data": top_20,
            "methodology": "Confluence-scored with trend filter and directional volume analysis"
        })
        
        # 2. Save detailed historical records for ALL scored stocks (not just top 20)
        # This is crucial for signal outcome tracking
        for r in ranked:  # Save full ranked list, not just top 20
            doc_id = f"{r['symbol']}_{r['run_date']}_{r['timeframe']}"
            db.collection("prediction_history").document(doc_id).set(r)
        
        # 3. Log signals for outcome tracking (track performance of each signal type)
        log_signal_outcomes(ranked, timeframe, run_date)
            
        print(f"Saved {len(top_20)} top predictions and {len(ranked)} historical records (percentile-ranked)")
        return top_20
    
    return top_20


def get_signal_accuracy_report(timeframe: str = "day") -> dict:
    """
    Fetch signal accuracy report from signal_tracker.
    Shows which signals are actually working on PSX.
    """
    try:
        from signal_tracker import get_signal_accuracy_report as fetch_report
        return fetch_report(timeframe)
    except Exception as e:
        print(f"Could not fetch accuracy report: {e}")
        return {}


if __name__ == "__main__":
    # Test runs
    # run_prediction_engine("day")
    # run_prediction_engine("week")
    # run_prediction_engine("month")
    pass
