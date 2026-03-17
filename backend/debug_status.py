import requests
from bs4 import BeautifulSoup
import re

def check_status():
    url = "https://dps.psx.com.pk/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Current logic
    status_text = soup.get_text().upper()
    print(f"Contains 'MARKET OPEN': {'MARKET OPEN' in status_text}")
    print(f"Contains 'MARKET CLOSED': {'MARKET CLOSED' in status_text}")
    
    # Try to find specific status element
    status_el = soup.select_one(".market-status")
    if status_el:
        print(f"Found .market-status: {status_el.text.strip()}")
    
    topbar_status = soup.select_one(".topbar__status")
    if topbar_status:
        print(f"Found .topbar__status: {topbar_status.text.strip()}")
        
    # Print a snippet of the topbar area
    topbar = soup.select_one(".topbar")
    if topbar:
        print(f"Topbar HTML: {topbar.prettify()[:500]}")

if __name__ == "__main__":
    check_status()
