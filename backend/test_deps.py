import yfinance as yf
import pandas as pd
print("Imports successful")
try:
    ticker = yf.Ticker("PKR=X")
    hist = ticker.history(period="1d")
    print("yfinance fetch successful")
    print(hist.tail())
except Exception as e:
    print(f"yfinance fetch failed: {e}")
