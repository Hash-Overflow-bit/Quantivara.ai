from bs4 import BeautifulSoup
import sys

try:
    with open('psx_home.html', 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    with open('psx_home_pretty.html', 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print("Prettified HTML saved to psx_home_pretty.html")
    
    # Also find the 154,421 value and its parent
    target = soup.find(string=lambda t: '154,421' in t)
    if target:
        parent = target.parent
        print(f"\nFOUND VALUE: {target.strip()}")
        print(f"PARENT TAG: {parent.name}")
        print(f"PARENT CLASSES: {parent.get('class')}")
        print(f"PARENT HTML SNIPPET:\n{str(parent)[:500]}")
    else:
        print("\nTarget value 154,421 not found in prettified soup.")
except Exception as e:
    print(f"Error: {e}")
