
import sys
import os
import json

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from shared import db

def check_firestore_freshness():
    print("Checking Firestore data freshness...")
    
    collections = ["market_data", "market_movers", "market_sectors", "volume_spikes"]
    
    for col in collections:
        doc = db.collection(col).document("latest").get()
        if doc.exists:
            data = doc.to_dict()
            timestamp = data.get("timestamp") or data.get("updated_at") or data.get("generated_at") or "No timestamp"
            print(f"Collection '{col}': Latest update at {timestamp}")
            if col == "market_data":
                print(f"  KSE-100: {data.get('kse100', {}).get('value')}")
        else:
            print(f"Collection '{col}': Document 'latest' NOT FOUND")

if __name__ == "__main__":
    check_firestore_freshness()
