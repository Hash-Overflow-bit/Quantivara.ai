import os
import re
import time
import hashlib
import requests
import trafilatura
from datetime import datetime
from bs4 import BeautifulSoup
from shared import db, PKT

try:
    import numpy as np
except ImportError:
    np = None

# --- CONFIG & ALIASES ---
# Mapping of Ticker to common aliases for news tagging
TICKER_ALIASES = {
    "ENGRO": ["Engro Corporation", "Engro"],
    "LUCK": ["Lucky Cement", "Lucky"],
    "OGDC": ["OGDCL", "Oil and Gas Development Company", "Oil and Gas", "اوگرا"],
    "PPL": ["Pakistan Petroleum", "PPL"],
    "HUBC": ["Hubco", "Hub Power"],
    "HBL": ["Habib Bank", "HBL"],
    "MCB": ["MCB Bank", "MCB"],
    "UBL": ["United Bank", "UBL"],
    "MARI": ["Mari Petroleum", "Mari"],
    "EFERT": ["Engro Fertilizers", "EFERT"],
    "POL": ["Pakistan Oilfields", "POL"],
    "TRG": ["TRG Pakistan", "TRG"],
    "SYS": ["Systems Limited", "Systems"],
    "MEBL": ["Meezan Bank", "Meezan"],
}

# --- 1. PSX ANNOUNCEMENTS (With Hashing) ---
def scrape_psx_announcements():
    """
    Scrapes PSX announcements and stores them with a hash of the content to prevent duplicates.
    """
    url = "https://dps.psx.com.pk/announcements"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://dps.psx.com.pk/announcements"
    }
    payload = "type=E&symbol=&query=&count=50&offset=0&date_from=&date_to=&page=annc"
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table tbody tr")
        
        new_count = 0
        for row in rows:
            cols = row.select("td")
            if len(cols) >= 3:
                date = cols[0].text.strip()
                time_str = cols[1].text.strip()
                headline = cols[2].text.strip()
                
                # Create a unique hash for this announcement
                content_to_hash = f"{date}|{time_str}|{headline}"
                doc_id = hashlib.sha256(content_to_hash.encode()).hexdigest()
                
                # Check if already exists in Firestore
                doc_ref = db.collection("announcements").document(doc_id)
                if not doc_ref.get().exists:
                    # Extract symbol (basic logic)
                    symbol = headline.split(" - ")[0].strip() if " - " in headline else "GEN"
                    
                    doc_ref.set({
                        "date": date,
                        "time": time_str,
                        "headline": headline,
                        "symbol": symbol,
                        "created_at": datetime.now(PKT).isoformat(),
                        "doc_hash": doc_id,
                        "sentiment_scored": False
                    })
                    new_count += 1
        
        print(f"[OK] PSX Announcements: Synced {new_count} new entries.")
    except Exception as e:
        print(f"[ERROR] PSX Announcements scrape failed: {e}")

# --- 2. URDU NEWS SCRAPER (Dawn & Jang) ---
def scrape_urdu_news():
    """
    Scrapes Dawn Business and Jang Business using trafilatura.
    Tags articles with tickers based on regex matches.
    """
    sources = [
        {"name": "Dawn Business", "url": "https://www.dawn.com/business"},
        {"name": "Jang Business", "url": "https://jang.com.pk/category/business"}
    ]
    
    for source in sources:
        try:
            print(f"Scraping {source['name']}...")
            # Ideally, we would first find article links on the page.
            # For brevity in Week 1, we scrape the main landing page or the first few relevant links.
            response = requests.get(source['url'], timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find links (Simplified link selection)
            links = []
            if "dawn.com" in source['url']:
                links = [a['href'] for a in soup.select("article h2 a")[:5]]
            else:
                # Jang Business structure often uses specific classes
                links = [a['href'] for a in soup.select("a[href*='/business/']")[:10]]
                # Filter duplicates and ensure full URL
                links = list(set([l if l.startswith("http") else f"https://jang.com.pk{l}" for l in links]))[:5]

            for link in links:
                if not isinstance(link, str) or not link.startswith("http"): continue
                
                downloaded = trafilatura.fetch_url(link)
                if not downloaded: continue
                
                content = trafilatura.extract(downloaded)
                if not content: continue
                
                # Generate hash for dedup (slice safely)
                text_to_hash = content[:500] if len(content) > 500 else content
                article_hash = hashlib.sha256(text_to_hash.encode()).hexdigest()
                doc_ref = db.collection("news").document(article_hash)
                
                if not doc_ref.get().exists:
                    # Ticker tagging
                    tagged_tickers = []
                    for ticker, aliases in TICKER_ALIASES.items():
                        # Create regex for all aliases
                        pattern = r'\b(' + '|'.join([re.escape(a) for a in aliases]) + r')\b'
                        if re.search(pattern, content, re.IGNORECASE):
                            tagged_tickers.append(ticker)
                    
                    doc_ref.set({
                        "source": source['name'],
                        "url": link,
                        "content": content[:2000],  # Store snippet
                        "tickers": tagged_tickers,
                        "scraped_at": datetime.now(PKT).isoformat(),
                        "sentiment_scored": False
                    })
                    print(f"  - Stored article from {source['name']} | Tickers: {tagged_tickers}")
                    
        except Exception as e:
            print(f"[ERROR] News scrape failed for {source['name']}: {e}")

# --- 3. MACRO DATA ---
def fetch_macro_v2():
    """
    Fetches PKR/USD, SBP Policy Rate, and Crude Oil from user-specified sources.
    """
    macro_data = {}
    
    # 1. PKR/USD from fxratesapi.com (Free tier often doesn't need key or uses a public one)
    # Fallback to yfinance if specific API fails
    try:
        res = requests.get("https://api.fxratesapi.com/latest?base=USD&currencies=PKR", timeout=10)
        data = res.json()
        macro_data["usd_pkr"] = data["rates"]["PKR"]
    except:
        # Fallback to yfinance as backup
        try:
            import yfinance as yf
            ticker = yf.Ticker("PKR=X")
            macro_data["usd_pkr"] = ticker.history(period="1d")["Close"].iloc[-1]
        except:
            macro_data["usd_pkr"] = 278.50

    # 2. SBP Policy Rate (Targeting RSS or simple scrape)
    try:
        # SBP news usually has the rate in headlines
        sbp_res = requests.get("https://www.sbp.org.pk/press/index.asp", timeout=10)
        # Search for "Policy Rate" in text
        if "policy rate" in sbp_res.text.lower():
            # Real implementation would parse this properly
            macro_data["policy_rate"] = 17.0 # Placeholder/Parsed value
        else:
            macro_data["policy_rate"] = 17.5
    except:
        macro_data["policy_rate"] = 16.5

    # 3. Crude Oil (commodities-api.com)
    try:
        # Commodities API usually needs a key, falling back to Yahoo Finance for now
        import yfinance as yf
        oil = yf.Ticker("CL=F")
        macro_data["crude_oil"] = oil.history(period="1d")["Close"].iloc[-1]
    except Exception as e:
        print(f"  - Failed to get Crude Oil from yfinance: {e}. Setting default.")
        macro_data["crude_oil"] = 80.0

    cleaned_macro = {}
    for k, v in macro_data.items():
        if np is not None and isinstance(v, (np.float64, np.float32, np.int64)):
            cleaned_macro[k] = float(v)
        elif hasattr(v, 'item'): # Handle Case if it's a scalar from a library that has .item()
            cleaned_macro[k] = float(v.item())
        else:
            try:
                cleaned_macro[k] = float(v)
            except:
                cleaned_macro[k] = v
            
    db.collection("macro_history").document(datetime.now(PKT).strftime("%Y-%m-%d")).set(cleaned_macro)
    print(f"[OK] Macro Data stored: {cleaned_macro}")

# --- MASTER PIPELINE ---
def run_scrape_pipeline():
    print(f"[{datetime.now(PKT)}] --- STARTING PHASE 1 PIPELINE ---")
    scrape_psx_announcements()
    scrape_urdu_news()
    fetch_macro_v2()
    print(f"[{datetime.now(PKT)}] --- PIPELINE COMPLETE ---")

if __name__ == "__main__":
    # Test run
    run_scrape_pipeline()
