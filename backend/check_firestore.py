import firebase_admin
from firebase_admin import credentials, firestore
import os

# Path to your Firebase Admin SDK service account key JSON file.
FIREBASE_KEY_PATH = r"c:\Users\Hashir Mehboob\Desktop\Quantivara.ai\backend\serviceAccountKey.json"

try:
    cred = credentials.Certificate(FIREBASE_KEY_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized.")
    
    doc = db.collection("expected_movers").document("latest").get()
    if doc.exists:
        import json
        data = doc.to_dict()
        print("Data found in Firestore:")
        print(json.dumps(data, indent=2))
    else:
        print("No document found at expected_movers/latest")
except Exception as e:
    print(f"Error: {e}")
