import yfinance as yf
import json
import os
import time
from datetime import datetime, timedelta

def build_baseline():
    print("Building 30-day volume baseline...")
    with open('backend/kse100.json', 'r') as f:
        tickers = json.load(f)
    
    baseline = {}
    
    # We can batch download for efficiency
    batch_size = 20
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        yf_tickers = " ".join([f"{t}.KA" for t in batch])
        print(f"Fetching batch: {yf_tickers}")
        
        try:
            data = yf.download(yf_tickers, period="40d", interval="1d", group_by='ticker', progress=False)
            
            for t in batch:
                symbol = f"{t}.KA"
                if symbol not in data:
                    print(f"  Warning: No data for {t}")
                    continue
                
                ticker_df = data[symbol]
                # Filter out rows with 0 volume (non-trading days)
                ticker_df = ticker_df[ticker_df['Volume'] > 0]
                
                if len(ticker_df) < 5:
                    print(f"  Warning: Not enough history for {t}")
                    continue
                
                # Take last 30 trading days EXCLUDING today if possible
                # If market is open, the last row is today.
                # For baseline, we want historical average.
                hist = ticker_df.iloc[:-1].tail(30)
                if hist.empty:
                    # If it only has 1 record, take it
                    hist = ticker_df
                
                avg_vol = int(hist['Volume'].mean())
                baseline[t] = {
                    "avg_30d_volume": avg_vol,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
        except Exception as e:
            print(f"  Error fetching batch starting with {batch[0]}: {e}")
        
        time.sleep(1) # Rate limiting friendly

    with open('backend/volume_baseline.json', 'w') as f:
        json.dump(baseline, f, indent=2)
    
    print(f"Successfully built baseline for {len(baseline)} symbols.")

if __name__ == "__main__":
    build_baseline()
