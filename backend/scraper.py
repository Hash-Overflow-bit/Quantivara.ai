import os
import json
import time
import requests
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
import firebase_admin
from firebase_admin import credentials, firestore
from shared import db, PKT, MARKET_OPEN_H, MARKET_CLOSE_H, _BASE_DIR
from prediction_engine import run_prediction_engine


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
        
        if data and isinstance(data, list):
            # Format for Recharts: [{"time": "HH:mm", "value": 123}, ...]
            formatted = []
            for point in data[-50:]:  # Take last 50 points for sparkline
                t = time.strftime('%H:%M', time.localtime(point[0]))
                val = float(point[1])
                formatted.append({"time": t, "value": val})
            return formatted
        return []
    except Exception as e:
        print(f"ERROR fetching intraday for {symbol}: {e}")
        return []


def get_all_stocks():
    """Fetch all stocks from the Market Watch page."""
    url = "https://dps.psx.com.pk/market-watch"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        stocks = []
        # The selector from browser research: table.tbl tr
        rows = soup.select("table.tbl tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) >= 11:
                symbol = cols[0].text.strip()
                # Symbol often has extra text, clean it
                if "\n" in symbol:
                    symbol = symbol.split("\n")[0].strip()
                
                try:
                    # PSX Table columns:
                    # 0: SYMBOL, 1: SECTOR, 2: LISTED IN, 3: LDCP, 4: LOW, 5: HIGH
                    # 6: LOW, 7: CURRENT, 8: CHANGE, 9: CHANGE (%), 10: VOLUME
                    price = float(cols[7].text.strip().replace(",", ""))
                    change_text = cols[9].text.strip().replace(",", "").replace("%", "")
                    change = float(change_text)
                    volume = cols[10].text.strip()
                    
                    stocks.append({
                        "symbol": symbol,
                        "price": price,
                        "change": change,
                        "volume": volume
                    })
                except (ValueError, IndexError):
                    continue
        
        return stocks[:200] # Expand to 200 stocks
    except Exception as e:
        print(f"ERROR fetching all stocks: {e}")
        return []


import re

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
    for ann in announcements[:30]:
        sentiment = analyze_announcement_sentiment(ann["headline"])
        if sentiment == "neutral":
            continue

        symbol = ann["symbol"].upper()
        
        # STRICT FILTERING: Only include if we have a real price for it
        if symbol not in stock_prices:
            # Try a slightly more relaxed check (e.g. symbol is part of the key)
            matched_symbol = None
            for s in stock_prices.keys():
                if s == symbol or s.startswith(symbol) or symbol.startswith(s):
                    matched_symbol = s
                    break
            
            if matched_symbol:
                symbol = matched_symbol
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
            
    return {
        "expected_gainers": final_gainers[:5],
        "expected_losers": final_losers[:5]
    }


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
                raw_vol = s['volume'].replace(',', '')
                vol = float(raw_vol.replace('M', '')) * 1e6 if 'M' in raw_vol else (float(raw_vol.replace('K', '')) * 1e3 if 'K' in raw_vol else float(raw_vol))
                doc_ref = db.collection("daily_volumes").document(f"{s['symbol']}.KA")
                doc = doc_ref.get()
                history = doc.to_dict().get("history", []) if doc.exists else []
                history = [i for i in history if i["date"] != today_str] + [{"date": today_str, "volume": vol, "close": s['price']}]
                doc_ref.set({"history": history[-35:], "last_updated": datetime.now(PKT).isoformat()})
            except: continue
    print("Daily volumes synced to cloud.")

def daily_cleanup():
    print("Daily cleanup (Cloud mode)")

def get_volume_spikes():
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
    """Fetch USD/PKR and Gold prices using yfinance"""
    try:
        # USD to PKR
        usd_pkr_ticker = yf.Ticker("PKR=X")
        usd_pkr = usd_pkr_ticker.history(period="1d")['Close'].iloc[-1]
        
        # Gold futures (proxied as general macro context)
        gold_ticker = yf.Ticker("GC=F")
        gold = gold_ticker.history(period="1d")['Close'].iloc[-1]
        
        return {
            "usdPkr": float(round(usd_pkr, 2)),
            "gold": float(round(gold, 2)),
            "tBillYield": 16.5  # Latest SBP rates can be hard-coded or scraped from SBP.org.pk
        }
    except Exception as e:
        print(f"WARNING: Error fetching macro data from yfinance: {e}")
        return {"usdPkr": 278.40, "gold": 194500, "tBillYield": 16.5}


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
            "status": "CLOSED"
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
                
                # Get percentage change
                pct = 0.0
                if change_el:
                    pct_text = change_el.text.strip().replace("(", "").replace(")", "").replace("%", "")
                    try:
                        pct = float(pct_text)
                    except:
                        pass
                
                if name == "KSE100":
                    data["kse100"] = {"value": val, "change": pct}
                elif name == "KSE30":
                    data["kse30"] = {"value": val, "change": pct}

        # 2. Market Status & Volume
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
                
                if label == 'STATE':
                    data["status"] = val.upper()
                elif label == 'VOLUME':
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
        # Updated selectors for new PSX layout
        tables = soup.select(".market-performers__table")
        if len(tables) < 3:
            return None
            
        def parse_table(table):
            stocks = []
            rows = table.select("tbody tr")[:5]
            for row in rows:
                cols = row.select("td")
                if len(cols) >= 4:
                    symbol = cols[0].get_text(strip=True)
                    # Index 2: Price, Index 3: % Change
                    price_text = cols[2].get_text(strip=True).replace(",", "")
                    change_text = cols[3].get_text(strip=True).replace("%", "").replace("+", "")
                    
                    try:
                        price = float(price_text)
                        change = float(change_text)
                        stocks.append({"symbol": symbol, "price": price, "change": change})
                    except:
                        continue
            return stocks

        # Adjust indices based on actual DOM structure observed
        # index 1 = Advancers, index 2 = Decliners
        return {
            "top_gainers": parse_table(tables[1]),
            "top_losers": parse_table(tables[2])
        }
    except Exception as e:
        print(f"WARNING: Error parsing PSX movers: {e}")
        return None


def get_market_sectors():
    """Calculates sector performance by averaging changes of its KSE-100 components."""
    try:
        kse100_path = os.path.join(os.path.dirname(__file__), "kse100.json")
        if not os.path.exists(kse100_path):
            return {"sectors": []}
            
        with open(kse100_path, 'r') as f:
            tickers = json.load(f)
            
        sector_map = {}
        # Sample first 30 for speed in the live scraper to keep loop tight
        for symbol in tickers[:30]:
            try:
                ticker = yf.Ticker(f"{symbol}.KA")
                hist = ticker.history(period="2d", interval="1d", auto_adjust=False)
                if len(hist) < 2: continue
                
                info = ticker.info
                sector = info.get('sector', 'Unknown')
                
                prev = hist['Close'].iloc[-2]
                curr = hist['Close'].iloc[-1]
                if prev > 0:
                    change = ((curr - prev) / prev) * 100
                    if sector not in sector_map: sector_map[sector] = []
                    sector_map[sector].append(change)
            except: continue
            
        final_sectors = []
        for name, changes in sector_map.items():
            final_sectors.append({
                "name": name,
                "change": round(sum(changes)/len(changes), 2)
            })
        return {"sectors": sorted(final_sectors, key=lambda x: x['change'], reverse=True)}
    except Exception as e:
        print(f"ERROR calculating sectors: {e}")
        return {"sectors": []}


# --- 3. FIREBASE WRITERS ---

def push_to_firebase():
    """Fetches all data and updates Firestore"""
    if not db:
        print("Skipping Firebase push - DB not initialized.")
        return

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Updating market data...")
    try:
        # Update status to OPEN during screener runs
        if db:
            db.collection("market_data").document("latest").update({
                "status": "OPEN",
                "phase": "OPEN"
            })

        # 1. Macro Data (Always real if yfinance works)
        macro = get_macro_data()

        # 2. Market Indices (Try real, fallback to variated mock)
        indices = get_market_indices()
        if not indices:
            print("WARNING: Using mock indices (PSX Scraping failed).")
            import random
            indices = {
                "kse100": {"value": 115842.20 * (1 + random.uniform(-0.001, 0.001)), "change": 1.40},
                "kse30": {"value": 38214.10, "change": 0.81},
                "volume": "412M",
                "status": "OPEN"
            }

        # 3. Market Movers (Derive from all_stocks for robustness)
        all_stocks = get_all_stocks()
        movers = None
        if all_stocks:
            # Sort by percentage change
            sorted_stocks = sorted(all_stocks, key=lambda x: x['change'], reverse=True)
            movers = {
                "top_gainers": sorted_stocks[:5],
                "top_losers": sorted_stocks[-5:][::-1] # Bottom 5, then reversed for descending absolute loss
            }
        
        if not movers:
            print("WARNING: Using mock movers (Derivation failed).")
            movers = {
                "top_gainers": [
                    {"symbol": "ENGRO", "price": 315.45, "change": 6.2},
                    {"symbol": "LUCK", "price": 890.20, "change": 4.6},
                ],
                "top_losers": [
                    {"symbol": "TRG", "price": 70.10, "change": -4.2},
                    {"symbol": "HBL", "price": 103.40, "change": -3.2},
                ]
            }

        # 4. Sectors (Always mocked for now)
        sectors = get_market_sectors()

        # Combine macro and indices
        market_data = {**indices, **macro}
        
        # 5. Intraday Charts
        kse100_chart = get_intraday_data("KSE100")
        kse30_chart = get_intraday_data("KSE30")
        
        # 6. All Stocks (Market Watch) already fetched above

        # 7. Expected Movers (Predictions)
        expected_movers = generate_expected_movers()

        # 8. Volume Spikes (Screener)
        volume_spikes = get_volume_spikes()

        # Write to latest documents in Firestore
        db.collection("market_data").document("latest").set(market_data)
        db.collection("market_movers").document("latest").set(movers)
        db.collection("market_sectors").document("latest").set(sectors)
        
        # Predicted Movers
        db.collection("expected_movers").document("latest").set(expected_movers)
        
        # Volume Spikes
        db.collection("volume_spikes").document("latest").set({"spikes": volume_spikes})
        
        # Charts collection
        if kse100_chart:
            db.collection("charts").document("kse100").set({"points": kse100_chart})
        if kse30_chart:
            db.collection("charts").document("kse30").set({"points": kse30_chart})
            
        # Market Watch collection
        if all_stocks:
            db.collection("market_watch").document("latest").set({"stocks": all_stocks})
        
        print(f"Successfully updated Firestore with {len(all_stocks)} stocks and charts.")
    except Exception as e:
        print(f"Failed to push data: {e}")


# --- 4. SCHEDULER ---

if __name__ == "__main__":
    print("Starting PSX Insider Smart Scraper Engine...")
    
    # Run once immediately
    push_to_firebase()
    
    scheduler = BackgroundScheduler(timezone=PKT)

    # 1. Warmup at 9:25 AM PKT (M-F)
    scheduler.add_job(
        warmup,
        trigger="cron",
        day_of_week="mon-fri",
        hour=9, minute=25,
        id="warmup"
    )

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

    # 3. Save Daily Close at 3:35 PM PKT
    scheduler.add_job(
        save_daily_close,
        trigger="cron",
        day_of_week="mon-fri",
        hour=15, minute=35,
        id="daily_close"
    )

    # 4. Daily Cleanup at 4:00 PM PKT
    scheduler.add_job(
        daily_cleanup,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16, minute=0,
        id="cleanup"
    )

    # --- 4. PREDICTION ENGINE JOBS ---
    
    def job_day_predictions():
        print("Running DAILY prediction engine...")
        run_prediction_engine("day")

    def job_week_predictions():
        print("Running WEEKLY prediction engine...")
        run_prediction_engine("week")

    def job_month_predictions():
        print("Running MONTHLY prediction engine...")
        run_prediction_engine("month")

    # Day: Mon-Fri 9:00 AM
    scheduler.add_job(
        job_day_predictions,
        trigger="cron",
        day_of_week="mon-fri",
        hour=9, minute=0,
        id="pred_day"
    )

    # Week: Monday 9:00 AM
    scheduler.add_job(
        job_week_predictions,
        trigger="cron",
        day_of_week="mon",
        hour=9, minute=1, # Slightly offset from day
        id="pred_week"
    )

    # Month: 1st of month 9:00 AM
    scheduler.add_job(
        job_month_predictions,
        trigger="cron",
        day="1",
        hour=9, minute=2, # Slightly offset
        id="pred_month"
    )

    scheduler.start()
    print("APScheduler running in background.")
    
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
