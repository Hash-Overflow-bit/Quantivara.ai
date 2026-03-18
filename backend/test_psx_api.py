import requests
import json
from datetime import datetime, timedelta

def test_psx_api(symbol, timeframe_days):
    today = datetime.now()
    start_date = (today - timedelta(days=timeframe_days)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    
    # Test History
    url_history = f"https://dps.psx.com.pk/timeseries/history/{symbol}?from={start_date}&to={end_date}"
    print(f"Testing History: {url_history}")
    try:
        r = requests.get(url_history, timeout=10)
        print(f"History Status: {r.status_code}")
        data = r.json()
        points = data.get("data", [])
        print(f"History Points: {len(points)}")
        if points:
            print(f"First point: {points[0]}")
            print(f"Last point: {points[-1]}")
    except Exception as e:
        print(f"History Failed: {e}")

    # Test Intraday
    url_intraday = f"https://dps.psx.com.pk/timeseries/intraday/{symbol}"
    print(f"\nTesting Intraday: {url_intraday}")
    try:
        r = requests.get(url_intraday, timeout=10)
        print(f"Intraday Status: {r.status_code}")
        data = r.json()
        points = data.get("data", [])
        print(f"Intraday Points: {len(points)}")
        if points:
            print(f"First point: {points[0]}")
            print(f"Last point: {points[-1]}")
    except Exception as e:
        print(f"Intraday Failed: {e}")

if __name__ == "__main__":
    print("--- KSE100 1D ---")
    test_psx_api("KSE100", 1)
    print("\n--- KSE100 30D (1M) ---")
    test_psx_api("KSE100", 30)
