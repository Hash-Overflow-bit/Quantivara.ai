import requests
from bs4 import BeautifulSoup
import re

def check_status_v2():
    url = "https://dps.psx.com.pk/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Check all elements with text containing 'Open' or 'Closed'
    potential_elements = soup.find_all(string=re.compile(r'Open|Closed|State', re.I))
    for el in potential_elements:
        parent = el.parent
        print(f"Parent Class: {parent.get('class')}, Text: {el.strip()}")

    # specifically look for the indicators seen in markdown
    indicators = soup.select(".stats__item")
    for ind in indicators:
        print(f"Stats item: {ind.get_text(separator=' ').strip()}")

if __name__ == "__main__":
    check_status_v2()
