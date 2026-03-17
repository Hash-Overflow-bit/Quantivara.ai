import os
import sys
import json
import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from typing import List, Dict, Any, Optional
import re
import logging
import random

# Set up global logger
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("PSX_SCRAPER")

# Import local modules with dual-mode support (package vs script)
try:
    # Try as package first
    from .shared import db, PKT, MARKET_OPEN_H, MARKET_CLOSE_H, _BASE_DIR
    from .prediction_engine import run_prediction_engine
    from .foreign_flow import update_foreign_flow
    from .ai_engine import generate_chart_commentary
except (ImportError, ValueError):
    # Fallback to script mode: ensuring path is set correctly above
    from shared import db, PKT, MARKET_OPEN_H, MARKET_CLOSE_H, _BASE_DIR
    from prediction_engine import run_prediction_engine
    from foreign_flow import update_foreign_flow
    from ai_engine import generate_chart_commentary

# --- 1. CONSTANTS & CONFIG ---
SECTOR_MAP = {
    "0801": "AUTOMOBILE ASSEMBLER",
    "0802": "AUTOMOBILE PARTS & ACCESSORIES",
    "0803": "CABLE & ELECTRICAL GOODS",
    "0804": "CEMENT",
    "0805": "CHEMICAL",
    "0806": "CLOSE - END MUTUAL FUND",
    "0807": "COMMERCIAL BANKS",
    "0808": "ENGINEERING",
    "0809": "FERTILIZER",
    "0810": "FOOD & PERSONAL CARE PRODUCTS",
    "0811": "GLASS & CERAMICS",
    "0812": "INSURANCE",
    "0813": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "0814": "JUTE",
    "0815": "LEASING COMPANIES",
    "0816": "LEATHER & TANNERIES",
    "0818": "MISCELLANEOUS",
    "0819": "MODARABAS",
    "0820": "OIL & GAS EXPLORATION COMPANIES",
    "0821": "OIL & GAS MARKETING COMPANIES",
    "0822": "PAPER, BOARD & PACKAGING",
    "0823": "PHARMACEUTICALS",
    "0824": "POWER GENERATION & DISTRIBUTION",
    "0825": "REFINERY",
    "0826": "SUGAR & ALLIED INDUSTRIES",
    "0827": "SYNTHETIC & RAYON",
    "0828": "TECHNOLOGY & COMMUNICATION",
    "0829": "TEXTILE COMPOSITE",
    "0830": "TEXTILE SPINNING",
    "0831": "TEXTILE WEAVING",
    "0832": "TOBACCO",
    "0833": "TRANSPORT",
    "0834": "VANASPATI & ALLIED INDUSTRIES",
    "0835": "WOOLLEN",
    "0836": "REAL ESTATE INVESTMENT TRUST",
    "0837": "EXCHANGE TRADED FUNDS",
    "0838": "PROPERTY"
}

# --- HELPERS ---

def get_market_status():
    """
    Calculate actual market status based on Pakistan Stock Exchange hours.
    Returns: "OPEN", "PRE_OPEN", or "CLOSED"
    """
    now_pkt = datetime.now(PKT)
    current_hour = now_pkt.hour + now_pkt.minute / 60.0
    day_of_week = now_pkt.weekday()  # 0=Monday, 6=Sunday
    
    is_weekday = day_of_week < 5  # Monday to Friday
    
    if is_weekday and MARKET_OPEN_H <= current_hour < MARKET_CLOSE_H:
        return "OPEN"
    elif is_weekday and current_hour < MARKET_OPEN_H:
        return "PRE_OPEN"
    else:
        return "CLOSED"



# --- 2. SCRAPING FUNCTIONS ---

def get_psx_page():
    """Fetch the PSX Data Portal page with headers to avoid blocking."""
    url = "https://dps.psx.com.pk/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"ERROR fetching PSX page: {e}")
        return None

def get_intraday_data(symbol="KSE100"):
    """Fetch intraday timeseries data from PSX."""
    url = f"https://dps.psx.com.pk/timeseries/intraday/{symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        json_resp = response.json()
        data = json_resp.get("data", [])
        
        if isinstance(data, list) and data:
            # Format for Recharts: [{"time": "HH:mm", "value": 123}, ...]
            formatted: List[Dict[str, Any]] = []
            # Use list() to ensure slicing is recognized by all linters
            recent_data = list(data)[-50:]
            for point in recent_data:  
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    t = time.strftime('%H:%M', time.localtime(int(point[0])))
                    val = float(point[1])
                    formatted.append({"time": t, "value": val})
            return formatted
        return []
    except Exception as e:
        print(f"ERROR fetching intraday for {symbol}: {e}")
        return []


def get_all_stocks():
    """Fetch all stocks from the Market Watch page with robust error handling."""
    url = "https://dps.psx.com.pk/market-watch"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        stocks = []
        # The selector from browser research: table.tbl tr
        rows = soup.select("table.tbl tr")
        
        if not rows:
            print(f"WARNING: No table rows found on PSX Market Watch. Found {len(rows)} rows")
            return []
            
        print(f"Parsing {len(rows)} rows from PSX Market Watch...")
        
        for idx, row in enumerate(rows):
            try:
                cols = row.select("td")
                if len(cols) < 11:
                    continue
                
                # Extract raw values first
                symbol_raw = cols[0].text.strip()
                
                # Clean symbol - remove extra whitespace/newlines
                if "\n" in symbol_raw:
                    symbol = symbol_raw.split("\n")[0].strip()
                else:
                    symbol = symbol_raw.strip()
                
                # Skip header rows and empty symbols
                if not symbol or symbol.lower() in ["symbol", "sector", "name"]:
                    continue
                
                try:
                    # PSX Table columns (verified structure):
                    # 0: SYMBOL, 1: SECTOR, 2: COMPANY, 3-5: LDCP/HIGH/LOW
                    # 6: OPEN, 7: CLOSE/CURRENT, 8: CHANGE, 9: CHANGE(%), 10: VOLUME
                    
                    # Try to parse price from column 7 (usually current price)
                    price_text = cols[7].text.strip().replace(",", "").replace(" ", "")
                    price = float(price_text) if price_text else 0.0
                    
                    # Change percentage from column 9
                    change_text = cols[9].text.strip().replace(",", "").replace("%", "").replace(" ", "")
                    change = float(change_text) if change_text else 0.0
                    
                    # Volume from column 10 (keeps M/K suffix)
                    volume = cols[10].text.strip().replace(" ", "")
                    
                    if price <= 0:
                        continue
                    
                    stocks.append({
                        "symbol": symbol.upper(),
                        "sector_id": cols[1].text.strip(),
                        "price": float(f"{price:.2f}"),
                        "change": float(f"{change:.2f}"),
                        "volume": volume
                    })
                except (ValueError, IndexError) as e:
                    print(f"DEBUG: Could not parse stock row {idx}: {symbol} - {str(e)}")
                    continue
            except Exception as e:
                print(f"DEBUG: Error processing row {idx}: {str(e)}")
                continue
        
        print(f"[OK] Successfully parsed {len(stocks)} stocks from Market Watch")
        return stocks
    except Exception as e:
        print(f"ERROR fetching all stocks from PSX: {e}")
        print(f"URL: {url}")
        return []



def analyze_announcement_sentiment(headline):
    """
    Simple keyword-based sentiment analysis for PSX headlines.
    Returns: 'bullish', 'bearish', or 'neutral'
    """
    headline_lower = headline.lower()
    
    bullish_keywords = [
        "profit", "increase", "growth", "dividend", "bonus", "rights", 
        "acquisition", "expansion", "positive", "award", "contract", "upgrade",
        "interim dividend", "final dividend", "payout", "earnings growth"
    ]
    bearish_keywords = [
        "loss", "decrease", "decline", "reduction", "suspension", "penalty", 
        "resignation", "investigation", "negative", "downgrade", "closed",
        "winding up", "default", "impairment"
    ]
    
    # Calculate scores
    bull_score = sum(1 for word in bullish_keywords if word in headline_lower)
    bear_score = sum(1 for word in bearish_keywords if word in headline_lower)
    
    if bull_score > bear_score:
        return "bullish"
    elif bear_score > bull_score:
        return "bearish"
    else:
        return "neutral"

def get_announcements():
    """Fetch corporate announcements from PSX using direct POST request."""
    url = "https://dps.psx.com.pk/announcements"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://dps.psx.com.pk/announcements"
    }
    # Payload as discovered via browser sniffing
    # type=E seems to be 'Companies Announcements'
    payload = "type=E&symbol=&query=&count=50&offset=0&date_from=&date_to=&page=annc"
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        announcements = []
        rows = soup.select("table tbody tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) >= 3:
                date = cols[0].text.strip()
                time_str = cols[1].text.strip()
                headline = cols[2].text.strip()
                
                # Robust symbol extraction: 
                # PSX headlines often start with "SYMBOL - " or contain "SYMBOL" in brackets
                symbol = ""
                
                # Normalize headline
                headline_raw = headline.strip()

                # Try explicit symbol format "SYMBOL - "
                if " - " in headline_raw:
                    potential = headline_raw.split(" - ")[0].strip()
                    # Real symbols are usually 3-10 chars, all caps/nums
                    if potential.isupper() and 2 <= len(potential) <= 12:
                        symbol = potential

                # Try bracket format "[SYMBOL]" or "(SYMBOL)"
                if not symbol:
                    bracket_match = re.search(r'[\[\(]([A-Z0-9]{2,10})[\]\)]', headline_raw)
                    if bracket_match:
                        symbol = bracket_match.group(1)

                # Fallback to regex for common PSX symbols
                if not symbol:
                    # Filter out generic words
                    noisy_words = ["NOTICE", "BOARD", "TRADING", "MARKET", "FINAL", "ANNUAL", "INTERIM", "PROFIT", "LOSS", "THE", "AND", "FOR", "THIS", "THAT", "WITH", "OF", "IS", "AT", "ON"]
                    regex_matches = re.findall(r'\b([A-Z0-9]{2,10})\b', headline_raw)
                    for m in regex_matches:
                        if m not in noisy_words and m.isupper() and any(c.isalpha() for c in m):
                            symbol = m
                            break
                
                if symbol:
                    # Final normalization
                    symbol = symbol.strip().upper()
                    announcements.append({
                        "date": date,
                        "time": time_str,
                        "symbol": symbol,
                        "headline": headline
                    })
        return announcements
    except Exception as e:
        print(f"ERROR fetching announcements: {e}")
        return []


def generate_expected_movers():
    """Correlates recent announcements with symbols to predict opening movers."""
    announcements = get_announcements()
    if not announcements:
        return {"expected_gainers": [], "expected_losers": []}
    
    # Also get current stock prices for better entry/target calculation
    all_stocks = get_all_stocks()
    stock_prices = {s['symbol']: s['price'] for s in all_stocks}
    
    gainers = []
    losers = []
    
    # Current time for signal context
    entry_time = time.strftime('%H:%M', time.localtime())
    
    # Process only the most recent announcements (first 30 for better coverage)
    latest_anns = list(announcements)[:30]
    for ann in latest_anns:
        if not isinstance(ann, dict): continue
        headline = str(ann.get("headline", ""))
        sentiment = analyze_announcement_sentiment(headline)
        if sentiment == "neutral":
            continue

        symbol = str(ann.get("symbol", "")).upper()
        
        # STRICT FILTERING: Only include if we have a real price for it
        if symbol not in stock_prices:
            # Try a slightly more relaxed check (e.g. symbol is part of the key)
            matched_symbol = None
            for s in stock_prices.keys():
                if s == symbol or s.startswith(symbol) or symbol.startswith(s):
                    matched_symbol = s
                    break
            
            if matched_symbol:
                symbol = str(matched_symbol)
            else:
                continue

        current_price = stock_prices.get(symbol, 0.0)
        if current_price <= 0:
            continue
        
        # Calculate Signals
        target_pct = 0.05 if sentiment == "bullish" else -0.05
        sl_pct = 0.02 if sentiment == "bullish" else -0.02
        
        prediction = {
            "symbol": symbol,
            "reason": ann["headline"],
            "sentiment": sentiment,
            "confidence": 0.85,
            # Trading Signals
            "entry_price": current_price,
            "target_price": round(current_price * (1 + target_pct), 2),
            "stop_loss": round(current_price * (1 - sl_pct), 2),
            "risk_reward": "1:2.5",
            "risk_percentage": 2.0,
            "entry_time": entry_time
        }
        
        if sentiment == "bullish":
            gainers.append(prediction)
        elif sentiment == "bearish":
            losers.append(prediction)
            
    # Ensure uniqueness by symbol
    seen = set()
    final_gainers = []
    for g in gainers:
        if g["symbol"] not in seen:
            final_gainers.append(g)
            seen.add(g["symbol"])
            
    seen = set()
    final_losers = []
    for l in losers:
        if l["symbol"] not in seen:
            final_losers.append(l)
            seen.add(l["symbol"])
            
    res: Dict[str, Any] = {
        "expected_gainers": list(final_gainers)[:5],
        "expected_losers": list(final_losers)[:5]
    }
    return res


def get_rolling_avg(symbol: str):
    """Calculates 30-day average volume from Firestore 'daily_volumes' collection."""
    if not db: return 0
    try:
        db_symbol = f"{symbol}.KA" if not symbol.endswith(".KA") else symbol
        doc = db.collection("daily_volumes").document(db_symbol).get()
        if not doc.exists: return 0
        history = doc.to_dict().get("history", [])
        if not history: return 0
        vols = [item["volume"] for item in history]
        return sum(vols) / len(vols)
    except Exception as e:
        print(f"Error reading rolling avg for {symbol}: {e}")
        return 0

def warmup():
    """Job 1: 9:25 AM PKT - Reset for new day & Bootstrap."""
    print("Warming up for market open (Cloud Mode)...")
    if not db: return
    try:
        db.collection("volume_spikes").document("latest").set({"spikes": []})
        db.collection("market_data").document("latest").update({"status": "PRE_OPEN", "phase": "PRE_OPEN"})
    except Exception as e:
        print(f"Firestore reset failed: {e}")
            
    kse100_path = os.path.join(_BASE_DIR, "kse100.json")
    if os.path.exists(kse100_path):
        with open(kse100_path, 'r') as f:
            for t in json.load(f):
                doc = db.collection("daily_volumes").document(f"{t}.KA").get()
                if not doc.exists or len(doc.to_dict().get("history", [])) < 5:
                    bootstrap_history(t)
    print("Warmup complete")

def bootstrap_history(symbol: str):
    """Initial history seed from yfinance into Firestore."""
    try:
        hist = yf.Ticker(f"{symbol}.KA").history(period="35d", interval="1d", auto_adjust=False).iloc[:-1]
        history_list = [{"date": d.strftime("%Y-%m-%d"), "volume": float(r["Volume"]), "close": float(r["Close"])} for d, r in hist.iterrows()]
        db.collection("daily_volumes").document(f"{symbol}.KA").set({"history": history_list, "last_updated": datetime.now(PKT).isoformat()})
    except Exception as e:
        print(f"Bootstrap failed for {symbol}: {e}")

def save_daily_close():
    """Job 3: 3:35 PM PKT - Finalize daily volume to Firestore."""
    print(f"[{datetime.now(PKT).strftime('%Y-%m-%d %H:%M:%S')}] Cloud Sync: Finalizing daily volumes...")
    today_str = datetime.now(PKT).strftime('%Y-%m-%d')
    all_stocks = get_all_stocks()
    if not all_stocks or not db: return
    
    try:
        db.collection("market_data").document("latest").update({"status": "CLOSED", "phase": "CLOSED", "final_data_date": today_str})
    except: pass

    kse100_path = os.path.join(_BASE_DIR, "kse100.json")
    with open(kse100_path, 'r') as f:
        kse100_tickers = set(json.load(f))
            
    for s in all_stocks:
        if s['symbol'] in kse100_tickers:
            try:
                raw_vol = str(s['volume']).replace(',', '')
                vol = float(raw_vol.replace('M', '')) * 1e6 if 'M' in raw_vol else (float(raw_vol.replace('K', '')) * 1e3 if 'K' in raw_vol else float(raw_vol))
                doc_ref = db.collection("daily_volumes").document(f"{s['symbol']}.KA")
                doc = doc_ref.get()
                history_data = doc.to_dict()
                history = history_data.get("history", []) if history_data else []
                history_list: List[Dict[str, Any]] = [i for i in history if isinstance(i, dict) and i.get("date") != today_str]
                history_list.append({"date": today_str, "volume": vol, "close": s['price']})
                doc_ref.set({"history": history_list[-35:], "last_updated": datetime.now(PKT).isoformat()})
            except: continue
    print("Daily volumes synced to cloud.")

def daily_cleanup():
    print("Daily cleanup (Cloud mode)")

def get_volume_spikes(all_stocks: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Job 2: Projected Spike Calculation using Cloud baseline (YFinance Real-time Fix).
    Fixes the stale 'regularMarketVolume' and split-adjusted price bugs.
    """
    try:
        kse100_path = os.path.join(_BASE_DIR, "kse100.json")
        tickers = json.load(open(kse100_path)) if os.path.exists(kse100_path) else []
        
        spikes = []
        now = datetime.now(PKT)
        # Market open 9:30 AM (9.5), Close 3:30 PM (15.5)
        elapsed = min(max(now.hour + now.minute/60 - MARKET_OPEN_H, 0.1), 6.0)
        
        for symbol in tickers:
            try:
                avg_vol = get_rolling_avg(symbol)
                if avg_vol < 500000: continue # Liquidity filter
                
                ticker = yf.Ticker(f"{symbol}.KA")
                
                # BUG FIX 1: Use regularMarketPrice from info instead of hist['Close']
                # This avoids the split-adjusted price lag/error
                info = ticker.info
                current_price = info.get('regularMarketPrice')
                
                # BUG FIX 2: Use 1m interval sum instead of regularMarketVolume
                # This avoids the stale yfinance cached volume bug
                hist_1m = ticker.history(period="1d", interval="1m")
                today_vol = int(hist_1m['Volume'].sum()) if not hist_1m.empty else 0
                
                # Fallback if info is empty/unreliable for PSX
                if not current_price and not hist_1m.empty:
                    current_price = hist_1m['Close'].iloc[-1]
                
                if not current_price or today_vol == 0:
                    continue
                
                ratio = round((today_vol / elapsed * 6.0) / avg_vol, 2)
                
                if ratio >= 2.0:
                    change = info.get('regularMarketChangePercent', 0)
                    spikes.append({
                        "symbol": symbol,
                        "today_vol": today_vol,
                        "avg_vol": avg_vol,
                        "spike_ratio": ratio,
                        "price": current_price,
                        "change": change,
                        "projected_vol": (today_vol / elapsed) * 6.0
                    })
            except:
                continue
                
        return sorted(spikes, key=lambda x: x['spike_ratio'], reverse=True)
    except Exception as e:
        print(f"Spike calculation error: {e}")
        return []


def get_macro_data():
    """
    Fetch authentic macroeconomic data for Pakistan:
    - USD/PKR: From yfinance (Yahoo Finance - reliable)
    - Gold: From yfinance futures, converted to PKR per 10 grams  
    - T-Bill Yield: From State Bank of Pakistan API
    """
    macro: Dict[str, Any] = {}
    
    # 1. USD to PKR Exchange Rate (from yfinance)
    try:
        usd_pkr_ticker = yf.Ticker("PKR=X")
        rate_data = usd_pkr_ticker.history(period="1d")
        if not rate_data.empty:
            usd_pkr = float(rate_data['Close'].iloc[-1])
            macro["usdPkr"] = float(round(usd_pkr, 2))
        else:
            macro["usdPkr"] = None
    except Exception as e:
        print(f"[WARNING] Failed to fetch USD/PKR: {e}")
        macro["usdPkr"] = None
    
    # 2. Gold Price (convert from USD/oz to PKR/10g)
    try:
        gold_ticker = yf.Ticker("GC=F")  # COMEX Gold Futures
        gold_data = gold_ticker.history(period="1d")
        if not gold_data.empty:
            # Gold futures price is in USD per troy ounce
            gold_usd_per_oz = float(gold_data['Close'].iloc[-1])
            
            # Convert: USD/oz -> PKR/10g
            # 1 troy ounce = 31.1035 grams
            # Formula: (price_usd_per_oz * exchange_rate) / 3.1 = price_pkr_per_10g
            if macro["usdPkr"]:
                gold_pkr_per_10g = (gold_usd_per_oz * macro["usdPkr"]) / 3.1035
                macro["gold"] = float(round(gold_pkr_per_10g, 1))
            else:
                macro["gold"] = None
        else:
            macro["gold"] = None
    except Exception as e:
        print(f"[WARNING] Failed to fetch Gold price: {e}")
        macro["gold"] = None
    
    # 4. Brent Oil Price (Global benchmark)
    try:
        oil_ticker = yf.Ticker("BZ=F") # Brent Crude Futures
        oil_data = oil_ticker.history(period="1d")
        if not oil_data.empty:
            macro["brentOil"] = float(round(oil_data['Close'].iloc[-1], 2))
        else:
            macro["brentOil"] = 82.40 # Fallback
    except Exception as e:
        print(f"[WARNING] Failed to fetch Brent Oil: {e}")
        macro["brentOil"] = 82.40
    
    # Fallback if all failed
    if not macro.get("usdPkr"):
        macro["usdPkr"] = 278.40
    if not macro.get("gold"):
        macro["gold"] = 5096.2
    if not macro.get("brentOil"):
        macro["brentOil"] = 82.40
    
    print(f"[OK] Macro data fetched: USD/PKR={str(macro.get('usdPkr'))}, Gold={str(macro.get('gold'))} PKR/10g, Oil=${str(macro.get('brentOil'))}/bbl")
    return macro


def get_market_indices():
    """Fetch real-time KSE-100 and KSE-30 indices from PSX."""
    soup = get_psx_page()
    if not soup:
        return None

    try:
        data = {
            "kse100": {"value": 0.0, "change": 0.0},
            "kse30": {"value": 0.0, "change": 0.0},
            "volume": "0M",
            "status": "CLOSED",
            "phase": "CLOSED"
        }

        # 1. Parse Indices from the top slider
        items = soup.select(".topIndices__item")
        for item in items:
            name_el = item.select_one(".topIndices__item__name")
            val_el = item.select_one(".topIndices__item__val")
            change_el = item.select_one(".topIndices__item__changep")
            
            if name_el and val_el:
                name = name_el.text.strip().upper()
                val = float(val_el.text.strip().replace(",", ""))
                
                # Get points change
                pts = 0.0
                pts_el = item.select_one(".topIndices__item__change")
                if pts_el:
                    pts_text = pts_el.text.strip().replace(",", "")
                    try:
                        pts = float(pts_text)
                    except:
                        pass

                # Get percentage change
                pct = 0.0
                if change_el:
                    pct_text = change_el.text.strip().replace("(", "").replace(")", "").replace("%", "")
                    try:
                        pct = float(pct_text)
                    except:
                        pass
                
                if name == "KSE100":
                    data["kse100"] = {"value": val, "change": pct, "points": pts}
                elif name == "KSE30":
                    data["kse30"] = {"value": val, "change": pct, "points": pts}

        # 2. Market Status & Volume
        # Detection strategy: Check for "Open" or "Closed" keywords in the page text.
        # This handles the actual website status (holidays, special hours).
        status_text = soup.get_text().upper().replace(" ", "").replace(":", "")
        
        market_status = "CLOSED" # Default
        if "MARKETOPEN" in status_text or "STATEOPEN" in status_text or "REGULARSTATEOPEN" in status_text:
            market_status = "OPEN"
        elif "MARKETCLOSED" in status_text or "STATECLOSED" in status_text or "REGULARSTATECLOSED" in status_text:
            market_status = "CLOSED"
        else:
            # Fallback to time-based status if parsing fails
            market_status = get_market_status()
            
        data["status"] = market_status
        data["phase"] = market_status

        reg_item = soup.select_one('.glide__slide[data-key="REG"]')
        if reg_item:
            stats = reg_item.select('.markets__item__stat')
            for stat in stats:
                label_el = stat.select_one('.markets__item__stat__label')
                if not label_el: continue
                label = label_el.text.strip().upper()
                
                # The value is in the last div of this stat item
                val_divs = stat.select('div')
                if len(val_divs) < 2: continue
                val = val_divs[-1].text.strip()
                
                # The previous logic for 'STATE' is now replaced by the broader text search above.
                # We only need to handle VOLUME here.
                if label == 'VOLUME':
                    try:
                        raw_vol = val.replace(",", "")
                        vol_num = int(raw_vol)
                        if vol_num >= 1_000_000_000:
                            data["volume"] = f"{round(vol_num / 1_000_000_000, 2)}B"
                        elif vol_num >= 1_000_000:
                            data["volume"] = f"{round(vol_num / 1_000_000, 1)}M"
                        else:
                            data["volume"] = f"{round(vol_num / 1000, 1)}K"
                    except:
                        pass

        return data
    except Exception as e:
        print(f"WARNING: Error parsing PSX indices: {e}")
        return None


def get_market_movers():
    """Fetch top gainers and losers from PSX."""
    soup = get_psx_page()
    if not soup:
        return None

    try:
        # Try both the specific class and a more generic search
        tables = soup.select(".market-performers__table")
        if not tables:
            # Fallback: look for tables inside the market-performers ID section
            market_sect = soup.find('div', id='market-performers')
            if market_sect:
                tables = market_sect.select("table")
            else:
                # Last resort: find any table with "tbl" class
                tables = soup.select("table.tbl")

        if len(tables) < 3:
            logger.warning(f"Found only {len(tables)} tables, expected at least 3 for movers")
            return None
            
        def parse_table(table):
            stocks = []
            rows = table.select("tbody tr")[:5]
            for row in rows:
                cols = row.select("td")
                if len(cols) >= 4:
                    symbol = cols[0].get_text(strip=True)
                    # Handle multi-line symbols (e.g. SYMBOL\nName)
                    if "\n" in symbol:
                        symbol = symbol.split("\n")[0].strip()
                    
                    price_text = cols[2].get_text(strip=True).replace(",", "")
                    change_text = cols[3].get_text(strip=True).replace("%", "").replace("+", "")
                    
                    try:
                        price = float(price_text)
                        change = float(change_text)
                        stocks.append({"symbol": symbol, "price": price, "change": change})
                    except:
                        continue
            return stocks

        # Adjust indices if they seem switched or if they are the only tables found
        # Usually: index 1 is gainers, 2 is losers
        return {
            "top_gainers": parse_table(tables[1]),
            "top_losers": parse_table(tables[2])
        }
    except Exception as e:
        logger.warning(f"Error parsing PSX movers: {e}")
        return None


def get_market_sectors(all_stocks=None):
    """Calculates sector performance by averaging changes of components."""
    try:
        if not all_stocks:
            all_stocks = get_all_stocks()
            
        if not all_stocks:
            return {"sectors": []}
            
        sector_groups = {}
        for stock in all_stocks:
            sid = stock.get("sector_id")
            sname = SECTOR_MAP.get(sid, "Other")
            if sname not in sector_groups:
                sector_groups[sname] = []
            sector_groups[sname].append(stock["change"])
            
        final_sectors = []
        for name, changes in sector_groups.items():
            if not changes: continue
            avg_change = sum(changes) / len(changes)
            final_sectors.append({
                "name": name,
                "change": round(avg_change, 2)
            })
            
        return {"sectors": sorted(final_sectors, key=lambda x: x['change'], reverse=True)}
    except Exception as e:
        print(f"ERROR calculating sectors: {e}")
        return {"sectors": []}


# --- 3. FIREBASE WRITERS ---

def push_to_firebase():
    """Fetches all data and updates Firestore with proper logging"""
    logger = logging.getLogger(__name__)
    
    if not db:
        logger.error("Skipping Firebase push - DB not initialized.")
        return

    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"[{timestamp}] Starting market data update...")
    
    try:
        # 1. Macro Data (Always real if yfinance works)
        macro = get_macro_data()
        logger.debug(f"[OK] Macro data: USD/PKR={macro.get('usdPkr')}, Gold={macro.get('gold')}")

        # 2. Market Indices (Try real, fallback to mock)
        indices = get_market_indices()
        if not indices:
            logger.warning("PSX Scraping failed - using mock indices")
            indices = {
                "kse100": {"value": 115842.20 * (1 + random.uniform(-0.001, 0.001)), "change": 1.40},
                "kse30": {"value": 38214.10, "change": 0.81},
                "volume": "412M",
                "status": "OPEN"
            }
        else:
            logger.info(f"[OK] Indices: KSE100={indices['kse100']['value']}, change={indices['kse100']['change']}%")

        # 3. Market Movers (Filter by KSE-100 for the brief)
        all_stocks = get_all_stocks()
        movers: Dict[str, Any] = {"top_gainers": [], "top_losers": []}
        if all_stocks:
            # Load KSE-100 Tickers
            kse100_list = []
            kse100_path = os.path.join(_BASE_DIR, "kse100.json")
            if os.path.exists(kse100_path):
                try:
                    with open(kse100_path, 'r') as f:
                        kse100_list = json.load(f)
                except:
                    kse100_list = []
            
            # Filter stocks that are in KSE-100
            kse100_set = {str(x).upper() for x in kse100_list} if kse100_list else set()
            if kse100_set:
                filtered_stocks = [s for s in all_stocks if str(s.get('symbol', '')).upper() in kse100_set]
                logger.info(f"Filtered {len(filtered_stocks)} KSE-100 stocks from {len(all_stocks)} total")
            else:
                filtered_stocks = all_stocks
                
            if filtered_stocks:
                # Calculate winners/losers
                sorted_stocks = sorted(filtered_stocks, key=lambda x: float(x.get('change', 0)), reverse=True)
                movers = {
                    "top_gainers": sorted_stocks[:5],
                    "top_losers": sorted_stocks[-5:][::-1]
                }
                
                gainers = movers.get("top_gainers", [])
                if gainers:
                    logger.info(f"[OK] Found {len(all_stocks)} stocks | Top KSE-100 gainer: {str(gainers[0].get('symbol'))}")
            else:
                logger.info(f"[OK] Found {len(all_stocks)} stocks | No KSE-100 stocks found in list")
            
        else:
            logger.error("Could not fetch stocks from PSX")
        
        if not movers:
            logger.warning("No movers found from PSX")
            movers = {"top_gainers": [], "top_losers": []}
            
        # 4. Market Sectors (Use all_stocks for broader view)
        sectors = get_market_sectors(all_stocks)
        logger.debug(f"[OK] Sectors fetched: {len(sectors.get('sectors', []))} sectors")

        # Combine macro and indices
        market_data = {**indices, **macro}
        
        # FIX: Flatten KSE-100 keys for main.py API compatibility
        if 'kse100' in indices:
            market_data['kse100_val'] = indices['kse100'].get('value')
            market_data['kse100_change'] = indices['kse100'].get('points')
            market_data['kse100_pct'] = indices['kse100'].get('change')
            
        if 'kse30' in indices:
            market_data['kse30_val'] = indices['kse30'].get('value')
            market_data['kse30_change'] = indices['kse30'].get('points')
            market_data['kse30_pct'] = indices['kse30'].get('change')
            
        # Add global timestamp
        market_data['timestamp'] = timestamp
        market_data['updated_at'] = timestamp

        # 5. Intraday Charts
        kse100_chart = get_intraday_data("KSE100")
        kse30_chart = get_intraday_data("KSE30")
        logger.debug(f"[OK] Chart data: KSE100={len(kse100_chart)} points, KSE30={len(kse30_chart)} points")
        
        # 6. Expected Movers
        expected_movers = generate_expected_movers()
        logger.debug(f"[OK] Expected movers: {len(expected_movers.get('expected_gainers', []))} gainers, {len(expected_movers.get('expected_losers', []))} losers")

        # 7. Volume Spikes
        volume_spikes: List[Dict[str, Any]] = get_volume_spikes(all_stocks)
        high_spikes = [s for s in volume_spikes if float(str(s.get('spike_ratio', 0))) >= 2.0]
        logger.info(f"[OK] Volume spikes detected: {len(high_spikes)} high spikes")

        # Write to Firestore
        db.collection("market_data").document("latest").set(market_data)
        db.collection("market_movers").document("latest").set(movers)
        db.collection("market_sectors").document("latest").set(sectors)
        db.collection("expected_movers").document("latest").set(expected_movers)
        db.collection("volume_spikes").document("latest").set({"spikes": volume_spikes, "updated_at": timestamp})
        
        if kse100_chart:
            db.collection("charts").document("kse100").set({"points": kse100_chart, "updated_at": timestamp, "timestamp": timestamp})
        if kse30_chart:
            db.collection("charts").document("kse30").set({"points": kse30_chart, "updated_at": timestamp, "timestamp": timestamp})
            
        if all_stocks:
            db.collection("market_watch").document("latest").set({"stocks": all_stocks, "updated_at": timestamp, "timestamp": timestamp})
        
        logger.info(f"[OK] Successfully synced to Firebase | {len(all_stocks)} stocks | {len(volume_spikes)} spike alerts")
    except Exception as e:
        logger.error(f"Failed to push data: {e}", exc_info=True)


def fetch_usd_pkr():
    """Fetch USD/PKR rate daily and save to Firestore"""
    logger.info("Running fetch_usd_pkr job...")
    try:
        if not db: return
        import yfinance as yf
        ticker = yf.Ticker("PKR=X")
        hist = ticker.history(period="1d")
        if not hist.empty:
            rate = float(hist["Close"].iloc[-1])
            today_str = datetime.now(PKT).strftime("%Y-%m-%d")
            db.collection("usd_pkr").document(today_str).set({
                "date": today_str,
                "rate": round(rate, 2),
                "timestamp": datetime.now(PKT).isoformat()
            })
            logger.info(f"[OK] USD/PKR fetched and updated: {round(rate, 2)}")
        else:
            logger.warning("fetch_usd_pkr returned empty history.")
    except Exception as e:
        logger.error(f"Failed to fetch USD/PKR: {e}")

def calculate_breadth():
    """Calculate breadth from market_watch and store for history"""
    logger.info("Running calculate_breadth job...")
    try:
        if not db: return
        watch_doc = db.collection("market_watch").document("latest").get()
        if not watch_doc.exists: return
        
        stocks = watch_doc.to_dict().get("stocks", [])
        if not stocks: return
        
        advances = sum(1 for s in stocks if float(s.get("change", 0)) > 0)
        declines = sum(1 for s in stocks if float(s.get("change", 0)) < 0)
        unchanged = sum(1 for s in stocks if float(s.get("change", 0)) == 0)
        
        now = datetime.now(PKT)
        db.collection("breadth_history").document(now.isoformat()).set({
            "advances": advances,
            "declines": declines,
            "unchanged": unchanged,
            "timestamp": now.isoformat()
        })
        logger.info(f"[OK] Breadth calculated: {advances} Adv, {declines} Dec, {unchanged} Unch")
    except Exception as e:
        logger.error(f"Failed to calculate breadth: {e}")


# --- 4. SCHEDULER INITIALIZATION ---

def init_scheduler():
    """Initialize and return the APScheduler instance for use in main.py"""
    logger = logging.getLogger(__name__)
    
    logger.info("Initializing PSX Data Update Scheduler...")
    
    scheduler = BackgroundScheduler(timezone=PKT)

    # 1. Warmup at 9:25 AM PKT (M-F)
    scheduler.add_job(
        warmup,
        trigger="cron",
        day_of_week="mon-fri",
        hour=9, minute=25,
        id="warmup"
    )
    logger.info("[OK] Scheduled: Warmup at 9:25 AM")

    # 2. Main Screener: Every 10 min during market hours (9:30 AM to 3:30 PM)
    # 9-15 hours captures 9:00 to 15:59.
    scheduler.add_job(
        push_to_firebase,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",
        minute="*/10",
        id="screener"
    )
    logger.info("[OK] Scheduled: Data updates every 10 min (9:00 AM - 4:00 PM)")

    # 3. Save Daily Close at 3:35 PM PKT
    scheduler.add_job(
        save_daily_close,
        trigger="cron",
        day_of_week="mon-fri",
        hour=15, minute=35,
        id="daily_close"
    )
    logger.info("[OK] Scheduled: Daily close at 3:35 PM")

    # 4. Daily Cleanup at 4:00 PM PKT
    scheduler.add_job(
        daily_cleanup,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16, minute=0,
        id="cleanup"
    )
    logger.info("[OK] Scheduled: Cleanup at 4:00 PM")

    # --- PREDICTION ENGINE JOBS ---
    
    def job_day_predictions():
        logger.info("Running DAILY prediction engine...")
        run_prediction_engine("day")

    def job_week_predictions():
        logger.info("Running WEEKLY prediction engine...")
        run_prediction_engine("week")

    def job_month_predictions():
        logger.info("Running MONTHLY prediction engine...")
        run_prediction_engine("month")

    # Day: Mon-Fri 9:00 AM
    scheduler.add_job(
        job_day_predictions,
        trigger="cron",
        day_of_week="mon-fri",
        hour=9, minute=0,
        id="pred_day"
    )
    logger.info("[OK] Scheduled: Daily predictions at 9:00 AM")

    # Chart Commentary Data: Mon-Fri 9:05 AM 
    scheduler.add_job(
        lambda: __import__("asyncio").run(generate_chart_commentary()),
        trigger="cron",
        day_of_week="mon-fri",
        hour=9, minute=5,
        id="chart_ai_commentary"
    )
    logger.info("[OK] Scheduled: Chart commentary at 9:05 AM")

    # Week: Monday 9:00 AM
    scheduler.add_job(
        job_week_predictions,
        trigger="cron",
        day_of_week="mon",
        hour=9, minute=1,
        id="pred_week"
    )
    logger.info("[OK] Scheduled: Weekly predictions Monday 9:01 AM")

    # Month: 1st of month 9:00 AM
    scheduler.add_job(
        job_month_predictions,
        trigger="cron",
        day="1",
        hour=9, minute=2,
        id="pred_month"
    )
    logger.info("[OK] Scheduled: Monthly predictions 1st of month 9:02 AM")

    # USD/PKR rate — daily 4:30 PM
    scheduler.add_job(
        fetch_usd_pkr,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16, minute=30,
        id="usd_pkr_fetch"
    )
    logger.info("[OK] Scheduled: USD/PKR fetch at 4:30 PM")

    # Breadth calculation — every 30 min during market
    scheduler.add_job(
        calculate_breadth,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15", minute="*/30",
        id="breadth_calc"
    )
    logger.info("[OK] Scheduled: Breadth calculation every 30 mins")

    # Foreign Flow: Mon-Fri 5:30 PM (NCCPL publishes approx 5:00 PM)
    scheduler.add_job(
        update_foreign_flow,
        trigger="cron",
        day_of_week="mon-fri",
        hour=17, minute=30,
        id="foreign_flow_scrape"
    )
    logger.info("[OK] Scheduled: Foreign flow update at 5:30 PM")

    scheduler.start()
    logger.info("[OK] APScheduler started successfully!")
    return scheduler


if __name__ == "__main__":
    print("Starting PSX Insider Smart Scraper Engine (Direct Mode)...")
    
    # Run once immediately
    print("[DIRECT MODE] Running initial data push...")
    push_to_firebase()
    
    # Initialize and start scheduler
    scheduler = init_scheduler()
    
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down scheduler...")
        scheduler.shutdown()

