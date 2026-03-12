from scraper import (get_market_indices, get_market_movers, get_market_sectors, 
                     get_macro_data, get_intraday_data, get_all_stocks, generate_expected_movers)
import time

def dry_run():
    print("--- DRY RUN START ---")
    
    print("\n1. Fetching Indices...")
    indices = get_market_indices()
    print(f"Indices: {indices}")
    
    print("\n2. Fetching Movers...")
    movers = get_market_movers()
    print(f"Movers: {movers}")
    
    print("\n3. Fetching Sectors...")
    sectors = get_market_sectors()
    print(f"Sectors: {sectors}")
    
    print("\n4. Fetching Macro Data...")
    macro = get_macro_data()
    print(f"Macro: {macro}")
    
    print("\n5. Fetching Intraday Data (KSE100)...")
    intraday = get_intraday_data("KSE100")
    print(f"Intraday points: {len(intraday)}")
    
    print("\n6. Fetching All Stocks (Market Watch)...")
    all_stocks = get_all_stocks()
    print(f"Total stocks: {len(all_stocks)}")
    
    # print("\n7. Generating Expected Movers (Predictions)...")
    # predictions = generate_expected_movers()
    # print(f"Predictions: {predictions}")
    
    print("\n--- DRY RUN COMPLETE ---")

if __name__ == "__main__":
    dry_run()
