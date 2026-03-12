from scraper import get_intraday_data, get_all_stocks
import json

print("--- TESTING INTRADAY DATA ---")
data_100 = get_intraday_data("KSE100")
print(f"KSE-100 points: {len(data_100)}")
if data_100:
    print(f"Sample point: {data_100[0]}")

print("\n--- TESTING ALL STOCKS DATA ---")
stocks = get_all_stocks()
print(f"Total stocks found: {len(stocks)}")
if stocks:
    print(f"Sample stock: {stocks[0]}")
