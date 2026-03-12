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
    
    # D1: Close Strength (25 pts)
    # User feedback: Only fire if pos >= 0.75. 0% is day's LOW.
    h, l = adj_highs.iloc[-1], adj_lows.iloc[-1]
    rng = h - l
    if rng > 0:
        pos = (last_c - l) / rng
        if pos >= 0.75:
            # Message fix: "Closed top 10% of range" (1-pos)
            top_pct = round((1 - pos) * 100)
            signals["D1_close_strength"] = {"score": round(pos * 25, 1), "msg": f"Closed top {top_pct}% of range"}

    # D2: Volume Spike (20 pts)
    avg_30 = hist['Volume'].tail(30).mean()
    last_vol = hist['Volume'].iloc[-1]
    if last_vol > 2 * avg_30:
        signals["D2_vol_spike"] = {"score": min((last_vol/avg_30)*4, 20), "msg": f"Vol {round(last_vol/avg_30, 1)}x avg"}

    # D3: RSI Zone (15 pts) - Use adjusted closes
    rsi = calc_rsi(adj_closes)
    if 55 <= rsi <= 75:
        signals["D3_rsi_momentum"] = {"score": 15, "msg": f"RSI {round(rsi)} momentum zone"}

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
    """Scores KSE-100 stocks and updates Firestore."""
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
                
            total_score = min(sum(s['score'] for s in signals.values()), 100)
            
            if total_score > 0:
                results.append({
                    "symbol": symbol,
                    "score": total_score,
                    "bias": score_to_bias(total_score),
                    "signals_fired": [f"{s['msg']}" for s in signals.values()],
                    "price_at_run": round(float(curr_p if curr_p else hist['Close'].iloc[-1]), 2),
                    "timeframe": timeframe,
                    "run_date": run_date
                })
        except Exception as e:
            print(f"Error scoring {symbol}: {e}")
            continue
            
    # Sort and save top 20
    ranked = sorted(results, key=lambda x: x['score'], reverse=True)[:20]
    
    if db:
        # 1. Save summary doc for quick frontend access
        db.collection("predictions").document(f"latest_{timeframe}").set({
            "updated_at": datetime.now(PKT).isoformat(),
            "timeframe": timeframe,
            "data": ranked
        })
        
        # 2. Save detailed historical records for performance tracking
        for r in results:
            doc_id = f"{r['symbol']}_{r['run_date']}_{r['timeframe']}"
            db.collection("prediction_history").document(doc_id).set(r)
            
        print(f"Saved {len(ranked)} {timeframe} predictions and {len(results)} historical records to Firestore.")

if __name__ == "__main__":
    # Test run
    # run_prediction_engine("day")
    pass
