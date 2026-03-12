from scraper import warmup
import firebase_admin

# Note: scraper already initializes firebase if not initialized
print("Manually triggering Warmup/Bootstrap to Firestore...")
warmup()
print("Firestore baseline seeded from yfinance.")
