try:
    from apscheduler.schedulers.background import BackgroundScheduler
    print("APScheduler OK")
except ImportError as e:
    print(f"APScheduler FAILED: {e}")

import scraper
print("Scraper IMPORTED OK")
