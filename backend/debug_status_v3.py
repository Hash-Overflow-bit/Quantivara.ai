import requests
from bs4 import BeautifulSoup

def find_status_logic():
    url = "https://dps.psx.com.pk/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Search for 'Regular' and look at its siblings/parents
    regular_el = soup.find(string=lambda t: 'Regular' in t and 'State' in t)
    if regular_el:
        print(f"Found indicator: {regular_el.strip()}")
        print(f"Parent Class: {regular_el.parent.get('class')}")
        print(f"Grandparent Class: {regular_el.parent.parent.get('class')}")
    else:
        # Fallback: search for any 'Open' or 'Closed' near topbar
        topbar = soup.select_one(".topbar")
        if topbar:
            print("Topbar content (first 1000 chars):")
            print(topbar.get_text(separator=' ').strip()[:1000])

    # Check for 'Market Status' text explicitly
    status_search = soup.find_all(string=lambda t: 'Market' in t and ('Open' in t or 'Closed' in t))
    for s in status_search:
        print(f"Market search found: {s.strip()}")

if __name__ == "__main__":
    find_status_logic()
