
import requests
import json

def find_endpoints():
    base = "https://dps.psx.com.pk"
    endpoints = [
        "/summary/index",
        "/summary/get_summary",
        "/summary/get_indices",
        "/market-summary",
        "/timeseries/intraday/KSE100",
        "/timeseries/history/KSE100"
    ]
    for e in endpoints:
        try:
            r = requests.get(base + e, headers={"X-Requested-With": "XMLHttpRequest", "User-Agent": "Mozilla/5.0"}, timeout=5)
            print(f"Endpoint: {e} -> Status: {r.status_code}, Content-Type: {r.headers.get('Content-Type')}")
            if r.status_code == 200 and 'json' in r.headers.get('Content-Type', '').lower():
                print(f"JSON Found at {e}!")
        except:
            pass

if __name__ == "__main__":
    find_endpoints()
