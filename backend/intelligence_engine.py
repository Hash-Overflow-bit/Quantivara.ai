import os
import json
import logging
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from shared import db, PKT
try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

logger = logging.getLogger(__name__)

def find_similar_historical_setup(symbol="^KSE100"):
    """
    Find historical dates with similar technical/flow patterns.
    """
    try:
        # Pull last 3 years of daily data
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3y", interval="1d")
        if hist.empty: return []

        closes = hist["Close"]
        volumes = hist["Volume"]
        
        # 1. Technical Indicators for matching
        ma20 = closes.rolling(20).mean()
        # Proximity to MA20
        proximity = abs((closes - ma20) / ma20) * 100
        
        # 2. Identify potential 'Near MA20' clusters
        near_ma20_dates = proximity[proximity < 0.8].index
        
        # 3. Pull Foreign Flow context if available (mocked for historical deep dive or from DB if we have enough)
        # For now, we'll focus on Price + Volume + Trend
        
        matches = []
        for dt in near_ma20_dates:
            idx = hist.index.get_loc(dt)
            # Ensure we have enough data before and after
            if idx < 30 or idx > len(hist) - 15:
                continue
            
            # Pattern: 3-day pullback before the date
            three_day_ret = (closes.iloc[idx] - closes.iloc[idx-3]) / closes.iloc[idx-3] * 100
            
            # Volume condition: below 20-day avg
            vol_avg = volumes.iloc[idx-20:idx].mean()
            vol_today = volumes.iloc[idx]
            
            if three_day_ret < -0.5 and vol_today < vol_avg:
                # Calculate outcome (next 10 days)
                future_high = closes.iloc[idx+1:idx+11].max()
                future_return = (future_high - closes.iloc[idx]) / closes.iloc[idx] * 100
                
                matches.append({
                    "date": dt.strftime("%B %d, %Y"),
                    "index_level": int(closes.iloc[idx]),
                    "setup": "MA20 Support + Volume Drop",
                    "outcome_10d": round(future_return, 2),
                    "is_bullish": future_return > 1.0
                })
        
        # Return unique-ish dates (at least 2 weeks apart)
        final_matches = []
        last_dt: Optional[datetime] = None
        for m in sorted(matches, key=lambda x: str(x['date']), reverse=True):
            curr_dt = datetime.strptime(str(m['date']), "%B %d, %Y")
            if last_dt is None or (last_dt - curr_dt).days > 14:
                final_matches.append(m)
                last_dt = curr_dt
            if len(final_matches) >= 3: break
            
        return final_matches
    except Exception as e:
        logger.error(f"Historical setup error: {e}")
        return []

async def get_chart_intelligence(symbol, mode, timeframe, current_data=None):
    """
    Main entry point for generating conversational intelligence.
    Modes: 'base', 'smart_money', 'catalysts', 'beginner', 'history', 'digest'
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key or not HAS_GROQ:
        return "Intelligence Engine offline. Please check API keys."

    client = Groq(api_key=groq_key)
    
    # 1. Compile Context
    context = ""
    if current_data:
        stats = current_data.get('stats', {})
        breadth = current_data.get('breadth', {})
        flow = current_data.get('foreign_flow', [])[-1] if current_data.get('foreign_flow') else {}
        ma20_list = current_data.get('ma20', [])
        ma20_val = ma20_list[-1].get('value') if ma20_list else 'N/A'
        
        context = f"""
        SYMBOL: {symbol}
        TIMEFRAME: {timeframe}
        PRICE: {stats.get('current')} ({stats.get('change_pct')}% change)
        BREADTH: {breadth.get('advances')} Up, {breadth.get('declines')} Down, {breadth.get('unchanged')} Unchanged
        FOREIGN FLOW: {flow.get('value')}M today
        TECHNICALS: Sitting on MA20={ma20_val}. 
        """

    system_prompts = {
        "base": f"Act as Zain, a senior market strategist at PSX. Analyze the current chart situation for {symbol}. Format with professional headers: SITUATION, TECHNICAL READ, BREADTH, FOREIGN FLOW, WHAT TO WATCH. Be specific with levels.",
        "smart_money": "Interpret institutional behavior. Combine foreign flow, volume, and breadth. Use 'Smart money signals are [MIXED/BULLISH/BEARISH]'. List specific SELLING and BUYING signals.",
        "catalysts": "List three upcoming events or triggers (SBP policy, earnings, flow reversal) that could move this stock/index this week. Assign probabilities if possible.",
        "beginner": "Explain the current chart as if to a complete novice. Use analogies like 'report cards' or 'school scores'. Explain what MA20 or Red Bars mean simply. Keep it encouraging but realistic.",
        "history": "Based on historical matches provided, explain the probability of a bounce or further decline. Compare today's flow/volume to the historical setup.",
        "digest": "Generate a 'DAILY CHART DIGEST' card. Use a box-drawing character style (━━━━━━━━). Summarize Close, Volume, Breadth, Movers, Technicals, and 'Zain's Take' in exactly 3 concise points."
    }

    prompt = f"Context: {context}\n\nTask: {system_prompts.get(mode, system_prompts['base'])}\n\n"
    
    if mode == 'history':
        history_setups = find_similar_historical_setup("^KSE100" if "KSE" in symbol else f"{symbol}.KA")
        prompt += f"Historical Matches: {json.dumps(history_setups)}\n\n"

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=800
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Intelligence generation error: {e}")
        return "Failed to generate intelligence. Still watching the pulse."
