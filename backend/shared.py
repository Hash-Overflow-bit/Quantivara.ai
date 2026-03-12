import os
import firebase_admin
from firebase_admin import credentials, firestore
import pytz

# --- Config ---
PKT = pytz.timezone('Asia/Karachi')
MARKET_OPEN_H = 9.5   # 9:30 AM
MARKET_CLOSE_H = 15.5 # 3:30 PM

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH", os.path.join(_BASE_DIR, "serviceAccountKey.json"))

# --- Singleton for DB ---
db = None

def get_db():
    global db
    if db is None:
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(FIREBASE_KEY_PATH)
                firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("Firebase initialized successfully.")
        except Exception as e:
            print(f"WARNING: Firebase initialization failed: {e}")
    return db

db = get_db()
