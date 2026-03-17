
import sys
import os
import json

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from shared import db

def check_fix_application():
    doc = db.collection("market_data").document("latest").get()
    if doc.exists:
        data = doc.to_dict()
        print(f"Update time: {data.get('timestamp')}")
        print(f"KSE-100 Val (Flat): {data.get('kse100_val')}")
        print(f"KSE-100 Val (Nested): {data.get('kse100', {}).get('value')}")
    else:
        print("Market data doc not found")

if __name__ == "__main__":
    check_fix_application()
