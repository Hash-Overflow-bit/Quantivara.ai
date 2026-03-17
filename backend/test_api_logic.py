
import sys
import os
from datetime import datetime

# Add current dir to path
sys.path.append(os.getcwd())

from shared import db, PKT

def test_foreign_flow_logic():
    print("Starting foreign flow test...")
    try:
        from shared import db
        if not db: 
            print("ERROR: DB not initialized")
            return
        
        days = 90
        print(f"Fetching docs from foreign_flow (limit {days})...")
        docs = list(db.collection("foreign_flow").order_by("date", direction="DESCENDING").limit(days).stream())
        data = [d.to_dict() for d in docs]
        print(f"Found {len(data)} documents")
        
        # Reverse to get chronological order for the chart
        data.reverse()
        
        # Calculate Summary
        last_5 = data[-5:] if len(data) >= 5 else data
        last_30 = data[-30:] if len(data) >= 30 else data
        
        sum_5 = round(sum(d.get('net', 0) or d.get('net_foreign_flow', 0) for d in last_5), 2)
        sum_30 = round(sum(d.get('net', 0) or d.get('net_foreign_flow', 0) for d in last_30), 2)
        
        print(f"Summary: 5d Net = {sum_5}, 30d Net = {sum_30}")

        # yfinance correlation (The suspect part)
        print("Importing yfinance...")
        import yfinance as yf
        print("Fetching ^KSE100 history...")
        index_ticker = yf.Ticker("^KSE100")
        index_hist = index_ticker.history(period="6mo", interval="1d")
        print(f"Found {len(index_hist)} historical points for KSE100")
        
        print("Logic test SUCCEEDED")
    except Exception as e:
        print(f"Logic test FAILED with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_foreign_flow_logic()
