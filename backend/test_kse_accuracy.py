import yfinance as yf
import requests
from datetime import datetime

def test_kse_accuracy():
    symbol = "^KSE100"
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    ticker = yf.Ticker(symbol, session=session)
    
    print("--- Yahoo Info ---")
    info = ticker.info
    print(f"regularMarketPrice: {info.get('regularMarketPrice')}")
    print(f"previousClose: {info.get('previousClose')}")
    print(f"currentPrice: {info.get('currentPrice')}")
    
    print("\n--- Yahoo History (1d) ---")
    hist = ticker.history(period="1d", interval="1m")
    if not hist.empty:
        print(f"Last History Close: {hist['Close'].iloc[-1]}")
        print(f"Last History Time: {hist.index[-1]}")
    else:
        print("History empty")

    print("\n--- PSX Scraper Fallback (Current) ---")
    url = "https://dps.psx.com.pk/"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".topIndices__item")
        for item in items:
            name_el = item.select_one(".topIndices__item__name")
            val_el = item.select_one(".topIndices__item__val")
            if name_el and val_el and "KSE100" in name_el.text:
                print(f"PSX Homepage KSE100: {val_el.text.strip()}")
    except Exception as e:
        print(f"PSX Scraping error: {e}")

if __name__ == "__main__":
    test_kse_accuracy()
