import requests
from bs4 import BeautifulSoup
import json

def test_nccpl():
    url = "https://www.nccpl.com.pk/en/investor-services/foreign-investors-trading-report"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    print(f"Fetching {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=20)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for any tables
            tables = soup.find_all("table")
            print(f"Found {len(tables)} tables.")
            
            for i, table in enumerate(tables):
                print(f"\n--- Table {i} ---")
                # Look for distinctive headers
                headers = [th.text.strip() for th in table.find_all("th")]
                if not headers:
                    # Try the first row TD as headers
                    first_row = table.find("tr")
                    if first_row:
                        headers = [td.text.strip() for td in first_row.find_all("td")]
                
                print(f"Headers: {headers}")
                
                # Show first row of data
                rows = table.find_all("tr")
                if len(rows) > 1:
                    first_data_row = [td.text.strip() for td in rows[1].find_all("td")]
                    print(f"Row 1: {first_data_row}")
            
            # Save snippet for inspection
            with open("nccpl_snippet.html", "w", encoding="utf-8") as f:
                f.write(response.text[:5000])
        else:
            print("Failed to get 200 status. Is there a Cloudflare check?")
            if "Cloudflare" in response.text or "Just a moment" in response.text:
                print("Confirmed: Cloudflare protection active.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_nccpl()
