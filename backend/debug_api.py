import sys
import os
import json
from datetime import datetime

# Import shared and foreign_flow if possible
sys.path.append(os.path.abspath('.'))
try:
    from shared import db, PKT
    print("Firebase initialized successfully.")
except Exception as e:
    print(f"Failed to initialize Firebase: {e}")
    sys.exit(1)

def test_foreign_flow_logic(days=90):
    print(f"Testing foreign-flow logic for {days} days...")
    try:
        # 1. Test Firestore Query
        print("Querying Firestore 'foreign_flow' collection...")
        docs = db.collection("foreign_flow").order_by("date", direction="DESCENDING").limit(days).get()
        data = [d.to_dict() for d in docs]
        print(f"Found {len(data)} documents in Firestore.")
        
        data.reverse()
        
        # 2. Test Summary Calculation
        last_5 = data[-5:] if len(data) >= 5 else data
        last_30 = data[-30:] if len(data) >= 30 else data
        
        sum_5 = round(sum(d.get('net', 0) for d in last_5), 2)
        sum_30 = round(sum(d.get('net', 0) for d in last_30), 2)
        print(f"Summary: last_5d_net={sum_5}, last_30d_net={sum_30}")
        
        # 3. Test yfinance part
        index_points = []
        print("Testing yfinance data fetching...")
        try:
            import yfinance as yf
            # Try multiple options as in main.py
            found = False
            for ticker_sym in ["^KSE100", "KSE100.KA", "KSE.KA"]:
                print(f"  Trying ticker: {ticker_sym}")
                index_ticker = yf.Ticker(ticker_sym)
                index_hist = index_ticker.history(period="6mo", interval="1d")
                if not index_hist.empty:
                    print(f"  Successfully fetched data for {ticker_sym}. Points: {len(index_hist)}")
                    for dt, row in index_hist.iterrows():
                        index_points.append({"time": dt.strftime("%Y-%m-%d"), "value": round(float(row['Close']), 2)})
                    found = True
                    break
                else:
                    print(f"  No data for {ticker_sym}")
            
            if not found:
                print("  No yfinance data found for any ticker.")
                if data:
                    print("  Fallback: Generating pseudo-index data based on last market val...")
                    current_val = 115842.20
                    latest_market = db.collection("market_data").document("latest").get()
                    if latest_market.exists:
                        current_val = latest_market.to_dict().get("kse100_val", current_val)
                    
                    import random
                    for d in data:
                        index_points.append({"time": d.get('date'), "value": round(current_val * (1 + random.uniform(-0.02, 0.02)), 2)})
        except Exception as ey:
            print(f"  yfinance test encountered error: {ey}")

        result = {
            "flow_data_count": len(data),
            "index_data_count": len(index_points),
            "summary": {
                "last_5d_net": sum_5,
                "last_30d_net": sum_30,
                "total_points": len(data)
            }
        }
        print("Test Result JSON:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"Critical error in test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_foreign_flow_logic()
