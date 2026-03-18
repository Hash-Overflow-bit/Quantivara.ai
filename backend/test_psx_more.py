import requests
import json
from datetime import datetime, timedelta

def test_endpoint(url):
    print(f"Testing: {url}")
    headers = {"X-Requested-With": "XMLHttpRequest", "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", [])
            print(f"Points: {len(items)}")
            if items:
                print(f"Sample: {items[0]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_endpoint("https://dps.psx.com.pk/timeseries/intraday/KSE100")
    test_endpoint("https://dps.psx.com.pk/timeseries/history/KSE100")
    # Some other common PSX endpoints
    test_endpoint("https://dps.psx.com.pk/timeseries/intraday/SYS")
    test_endpoint("https://dps.psx.com.pk/indices")
