
import os
import sys

# Add the current directory to sys.path to simulate running from backend/
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.append(current_dir)

print(f"Current working directory: {current_dir}")
print(f"Python path: {sys.path}")

try:
    import requests
    print("✓ requests imported")
except ImportError as e:
    print(f"✗ requests import failed: {e}")

try:
    import pandas as pd
    print("✓ pandas imported")
except ImportError as e:
    print(f"✗ pandas import failed: {e}")

try:
    import yfinance as yf
    print("✓ yfinance imported")
except ImportError as e:
    print(f"✗ yfinance import failed: {e}")

try:
    import prediction_engine
    print("✓ prediction_engine imported")
except ImportError as e:
    print(f"✗ prediction_engine import failed: {e}")

try:
    import shared
    print("✓ shared imported")
except ImportError as e:
    print(f"✗ shared import failed: {e}")

try:
    from scraper import get_market_status
    print("✓ scraper imported")
except ImportError as e:
    print(f"✗ scraper import failed: {e}")
except Exception as e:
    print(f"✗ scraper import failed with error: {e}")
