import requests
import json

url = "https://dps.psx.com.pk/timeseries/intraday/KSE100"
headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

try:
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Content Type: {response.headers.get('Content-Type')}")
    print(f"Raw Snippet: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
