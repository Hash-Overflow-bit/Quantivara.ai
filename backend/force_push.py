import os
import sys

# Add current directory to path so we can import scraper
sys.path.append(os.getcwd())

from backend.scraper import push_to_firebase

if __name__ == "__main__":
    print("Manually triggering Firebase update...")
    push_to_firebase()
    print("Update triggered.")
