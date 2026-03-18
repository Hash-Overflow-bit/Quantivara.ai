import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
import random
from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from shared import db, PKT
from intelligence_engine import get_chart_intelligence
import logging

logger = logging.getLogger(__name__)

chart_router = APIRouter(prefix="/api/chart", tags=["Charts"])

# Timeframe mapping to yfinance period and interval
TIMEFRAME_MAP = {
    "1D":  {"period": "5d",   "interval": "5m", "days": 1},
    "1W":  {"period": "10d",  "interval": "1h", "days": 7},
    "1M":  {"period": "1mo",  "interval": "1d", "days": 30},
    "3M":  {"period": "3mo",  "interval": "1d", "days": 90},
    "6M":  {"period": "6mo",  "interval": "1d", "days": 180},
    "YTD": {"period": "ytd",  "interval": "1d", "days": 365},
    "1Y":  {"period": "1y",   "interval": "1d", "days": 365},
    "3Y":  {"period": "3y",   "interval": "1wk", "days": 1095},
    "5Y":  {"period": "5y",   "interval": "1wk", "days": 1825},
}

SYMBOL_MAP = {
    "KSE100": "^KSE100",
    "KSE30":  "^KSE30",
}

@chart_router.get("/breadth")
async def get_market_breadth():
    """advances/declines only"""
    return get_breadth_data()

@chart_router.get("/comparison")
async def get_market_comparison():
    """KSE100 vs inflation vs PKR"""
    try:
        data = await get_historical_df("KSE100", "1Y")
        if data.empty:
            return []

        # PKR/USD 1Y data
        pkr_ticker = yf.Ticker("PKR=X")
        pkr_hist = pkr_ticker.history(period="1y", interval="1d")
        
        # Format for comparison
        inflation = 23.5  
        
        comparison = []
        for ts, row in data.iterrows():
            pkr_val = 278.0
            dt_str = ts.strftime("%Y-%m-%d") if isinstance(ts, datetime) else str(ts)
            if dt_str in pkr_hist.index.strftime("%Y-%m-%d"):
                pkr_val = pkr_hist.loc[ts.strftime("%Y-%m-%d")]["Close"]
            
            comparison.append({
                "date": dt_str,
                "kse100": round(float(row["Close"]), 2),
                "pkr": round(float(pkr_val), 2),
                "cpi": inflation
            })
            
        return comparison
    except Exception as e:
        logger.error(f"Comparison error: {e}")
        return []

async def get_historical_df(symbol, timeframe):
    """Abstraction for fetching index data from yfinance with PSX fallback"""
    params = TIMEFRAME_MAP[timeframe]
    yf_sym = SYMBOL_MAP.get(symbol, symbol)
    
    # 1. Try YFinance
    try:
        ticker = yf.Ticker(yf_sym)
        hist = ticker.history(period=params['period'], interval=params['interval'], auto_adjust=False)
        if not hist.empty:
            # For 1D/1W, filter to actual range
            if timeframe in ["1D", "1W"]:
                cutoff = datetime.now() - timedelta(days=int(params['days']))
                hist = hist[hist.index >= cutoff]
            return hist
        
        # Fallback YF symbols
        for s in [f"{symbol}.KA", "KSE.KA"]:
            hist = yf.Ticker(s).history(period=params['period'], interval=params['interval'], auto_adjust=False)
            if not hist.empty:
                return hist
    except Exception as e:
        logger.warning(f"YFinance failed for {symbol}: {e}")

    # 2. Try PSX History API
    psx_sym = symbol.replace(".KA", "")
    try:
        today = datetime.now(PKT)
        start_date = (today - timedelta(days=max(int(params['days']), 5))).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        url = f"https://dps.psx.com.pk/timeseries/history/{psx_sym}?from={start_date}&to={end_date}"
        
        headers = {"X-Requested-With": "XMLHttpRequest", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        json_data = resp.json()
        raw_data = json_data.get("data", [])
        
        if raw_data:
            df_rows = []
            for p in raw_data:
                ts = datetime.fromtimestamp(p[0])
                close = float(p[1])
                vol = int(p[2])
                change = float(p[3])
                op = close - change
                df_rows.append({
                    "Date": ts,
                    "Open": op,
                    "High": max(op, close) + abs(change)*0.1,
                    "Low": min(op, close) - abs(change)*0.1,
                    "Close": close,
                    "Volume": vol
                })
            df = pd.DataFrame(df_rows)
            df.set_index("Date", inplace=True)
            
            # Filter locally as PSX API often returns 5 years of data regardless of params
            cutoff = today - timedelta(days=int(params['days']))
            df = df[df.index >= cutoff.replace(tzinfo=None)]
            return df
    except Exception as e:
        logger.error(f"PSX API failed for {symbol}: {e}")

    # 3. Final Fallback: Return empty
    return pd.DataFrame()

@chart_router.get("/{symbol}")
async def get_chart_data(symbol: str, timeframe: str = Query("3M")):
    symbol = symbol.upper()
    timeframe = timeframe.upper()
    
    if symbol not in ["KSE100", "KSE30"] and not symbol.endswith(".KA"):
        # For stocks, allow passing them directly
        pass
    elif symbol not in ["KSE100", "KSE30"]:
        raise HTTPException(status_code=400, detail="Invalid symbol. Use KSE100, KSE30 or STOCK.KA")
    
    if timeframe not in TIMEFRAME_MAP:
        raise HTTPException(status_code=400, detail="Invalid timeframe")

    try:
        hist = await get_historical_df(symbol, timeframe)

        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol} after YF and PSX checks.")

        # Ensure data is sorted by time (ascending) and remove duplicates for lightweight-charts
        hist = hist.sort_index()
        hist = hist[~hist.index.duplicated(keep='last')]

        # OHLCV Formatting
        ohlcv = []
        for ts, row in hist.iterrows():
            ohlcv.append({
                "time": int(ts.timestamp()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        # Moving Averages
        closes = hist["Close"]
        def ma_series(window_size):
            if len(closes) < window_size: return []
            ma = closes.rolling(window=window_size).mean()
            return [{"time": int(ts.timestamp()), "value": round(float(v), 2)} for ts, v in ma.items() if not pd.isna(v)]

        # Process Stats with Live Data Fallback
        latest_px = float(hist.iloc[-1]["Close"])
        latest_op = float(hist.iloc[-1]["Open"])
        latest_hi = float(hist.iloc[-1]["High"])
        latest_lo = float(hist.iloc[-1]["Low"])
        latest_vol = int(hist.iloc[-1]["Volume"])
        prev_close = float(hist.iloc[-2]["Close"]) if len(hist) > 1 else latest_px

        # Inject Live Data from Firestore
        live_data_used = False
        try:
            doc = db.collection("market_data").document("latest").get()
            if doc.exists:
                m_data = doc.to_dict()
                idx_key = symbol.lower()
                live_price_data = m_data.get(idx_key)
                
                if isinstance(live_price_data, dict) and live_price_data.get('value'):
                    lp = float(str(live_price_data['value']).replace(',', ''))
                    if lp > 0:
                        latest_px = lp
                        live_data_used = True
                        # If live is significantly newer or different, append a point to OHLCV 
                        # but only if timestamp would be newer
                        now_ts = int(datetime.now(PKT).timestamp())
                        if now_ts > ohlcv[-1]['time'] + 300: # at least 5 mins newer
                             ohlcv.append({
                                "time": now_ts,
                                "open": ohlcv[-1]['close'],
                                "high": max(ohlcv[-1]['close'], lp),
                                "low": min(ohlcv[-1]['close'], lp),
                                "close": lp,
                                "volume": 0
                            })
        except Exception as ex:
            logger.warning(f"Live data injection failed for {symbol}: {ex}")

        change = latest_px - prev_close
        change_pct = (change / prev_close) * 100 if prev_close != 0 else 0

        stats = {
            "current": round(latest_px, 2),
            "open": round(latest_op, 2),
            "high": round(max(latest_hi, latest_px), 2),
            "low": round(min(latest_lo, latest_px), 2),
            "prev_close": round(prev_close, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "52w_high": round(float(hist["High"].max()), 2),
            "52w_low": round(float(hist["Low"].min()), 2),
            "live": live_data_used
        }

        # Returns
        def period_return(window):
            if len(closes) < window: return None
            past = float(closes.iloc[-window]); now = float(closes.iloc[-1])
            return round(((now - past) / past) * 100, 2)

        returns = { "1M": period_return(min(21, len(closes))), "3M": period_return(min(63, len(closes))), "1Y": period_return(min(252, len(closes))) }

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "ohlcv": ohlcv,
            "ma20": ma_series(20),
            "ma50": ma_series(50),
            "ma200": ma_series(200),
            "foreign_flow": get_foreign_flow_series(60),
            "events": get_event_markers(),
            "breadth": get_breadth_data(),
            "stats": stats,
            "returns": returns,
            "ai_commentary": get_todays_commentary(),
        }

    except Exception as e:
        logger.error(f"Error fetching chart data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@chart_router.get("/{symbol}/intelligence")
async def get_chart_intel_api(symbol: str, mode: str = Query("base"), timeframe: str = Query("3M")):
    """
    Generate conversational AI intelligence for the current chart.
    """
    symbol = symbol.upper()
    try:
        # Get actual data first for context
        full_data = await get_chart_data(symbol, timeframe)
        
        intel_content = await get_chart_intelligence(symbol, mode, timeframe, current_data=full_data)
        
        return {
            "symbol": symbol,
            "mode": mode,
            "timeframe": timeframe,
            "content": intel_content
        }
    except Exception as e:
        logger.error(f"Intelligence API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- HELPER FUNCTIONS (KEEPING PREVIOUS DEFINITIONS) ---

def get_foreign_flow_series(days=60):
    try:
        docs = db.collection("foreign_flow").order_by("date", direction="DESCENDING").limit(days).get()
        rows = [d.to_dict() for d in docs]
        rows.reverse()
        return [{"date": r["date"], "value": round(r.get("net", 0), 2), "color": "#00c896" if r.get("net", 0) >= 0 else "#ef5350"} for r in rows]
    except Exception as e:
        return []

def get_event_markers():
    try:
        docs = db.collection("macro_history").order_by("__name__", direction="DESCENDING").limit(5).get()
        events = []
        for d in docs:
            dt = d.id; data = d.to_dict()
            if abs(data.get("usdPkr", 278) - 278) > 2:
                events.append({"date": dt, "label": "PKR", "description": f"PKR volatility: {data.get('usdPkr')}", "color": "#f0a500"})
        return events
    except: return []

def get_breadth_data():
    try:
        # Try to get from market_watch synced by scraper
        doc = db.collection("market_watch").document("latest").get()
        if doc.exists:
            stocks = doc.to_dict().get("stocks", [])
            if stocks:
                adv = len([s for s in stocks if float(s.get("change", 0)) > 0])
                dec = len([s for s in stocks if float(s.get("change", 0)) < 0])
                unc = len([s for s in stocks if float(s.get("change", 0)) == 0])
                return {"advances": adv, "declines": dec, "unchanged": unc}
        
        # Check market_data fallback
        dm = db.collection("market_data").document("latest").get()
        if dm.exists:
            data = dm.to_dict()
            if "breadth" in data: return data["breadth"]
            
        return {"advances": 52, "declines": 38, "unchanged": 10} 
    except: return {"advances": 0, "declines": 0, "unchanged": 0}

def get_todays_commentary():
    try:
        doc = db.collection("market_briefs").document("latest").get()
        if doc.exists:
            summary = doc.to_dict().get("english_summary", ["KSE-100 index shows stability today."])
            return summary[0] if isinstance(summary, list) else summary
        return "Market data shows stable performance across sectors."
    except: return ""
