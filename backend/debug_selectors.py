from bs4 import BeautifulSoup
import re

with open('psx_home_pretty.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

print("--- Indices ---")
for item in soup.select('.topIndices__item'):
    name = item.select_one('.topIndices__item__name').text.strip() if item.select_one('.topIndices__item__name') else "N/A"
    val = item.select_one('.topIndices__item__val').text.strip() if item.select_one('.topIndices__item__val') else "N/A"
    change = item.select_one('.topIndices__item__percentage').text.strip() if item.select_one('.topIndices__item__percentage') else "N/A"
    print(f"{name}: {val} ({change})")

print("\n--- Market Status & Volume ---")
# Search for elements containing "Market" or "Volume" or "Status"
for tag in soup.find_all(['span', 'div', 'p', 'i']):
    text = tag.get_text().strip()
    if any(k in text for k in ['Market Status', 'Market Volume', 'OPEN', 'CLOSED']):
        classes = tag.get('class', [])
        print(f"[{tag.name}] {classes}: {text[:100]}")

print("\n--- Summary Stats Search ---")
stats = soup.select('.stats__item')
for s in stats:
    print(f"Stats Item: {s.get_text().strip()}")
