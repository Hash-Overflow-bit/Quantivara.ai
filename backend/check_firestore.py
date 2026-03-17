import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# Path to your Firebase Admin SDK service account key JSON file.
FIREBASE_KEY_PATH = r"c:\Users\Hashir Mehboob\Desktop\Quantivara.ai\backend\serviceAccountKey.json"

try:
    cred = credentials.Certificate(FIREBASE_KEY_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized.")
    
    doc = db.collection("market_data").document("latest").get()
    if doc.exists:
        data = doc.to_dict()
        print("Market Data in Firestore:")
        print(json.dumps(data, indent=2))
    else:
        print("No document found at market_data/latest")

    print("-" * 30)
    doc_brief = db.collection("market_briefs").document("latest").get()
    if doc_brief.exists:
        print("Latest AI Market Brief found:")
        print(json.dumps(doc_brief.to_dict(), indent=2, ensure_ascii=False))
    else:
        print("No AI Market Brief found.")
except Exception as e:
    print(f"Error: {e}")
