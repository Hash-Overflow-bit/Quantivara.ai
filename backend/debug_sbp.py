
import requests
import re
from bs4 import BeautifulSoup

def debug_sbp():
    url = "https://www.sbp.org.pk/ecodata/index2.asp"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        print(f"Status: {r.status_code}")
        # Look for the USD rate link
        links = re.findall(r'href=[\"\']?([^\"\' >]+)', r.text)
        rate_links = [l for l in links if 'Rate' in l or 'rate' in l]
        print(f"Rate Links found: {rate_links}")
        
        # Try to find the weighted average row directly in text
        if "Weighted Average" in r.text:
            print("Found 'Weighted Average' in text!")
            idx = r.text.find("Weighted Average")
            print(f"Content near keyword: {r.text[idx:idx+200]}")
        else:
            print("Keyword 'Weighted Average' NOT found.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_sbp()
