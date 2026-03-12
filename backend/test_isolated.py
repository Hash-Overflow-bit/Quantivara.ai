import requests
from bs4 import BeautifulSoup
import json

def get_announcements():
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
        soup = BeautifulSoup(response.text, "html.parser")
        
        announcements = []
        rows = soup.select("table tbody tr")
        print(f"Found {len(rows)} rows")
        for row in rows:
            cols = row.select("td")
            if len(cols) >= 3:
                date = cols[0].text.strip()
                time_str = cols[1].text.strip()
                headline = cols[2].text.strip()
                
                symbol = ""
                if " - " in headline:
                    potential_symbol = headline.split(" - ")[0].strip()
                    if potential_symbol.isupper() and len(potential_symbol) <= 10:
                        symbol = potential_symbol
                
                announcements.append({
                    "date": date,
                    "time": time_str,
                    "symbol": symbol,
                    "headline": headline
                })
        return announcements
    except Exception as e:
        print(f"ERROR: {e}")
        return []

print("--- TESTING RE-IMPLEMENTED ANNOUNCEMENT SCRAPER ---")
data = get_announcements()
print(f"Scraped {len(data)} announcements")
if data:
    print(json.dumps(data[:5], indent=2))
