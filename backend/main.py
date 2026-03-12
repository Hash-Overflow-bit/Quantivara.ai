from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="PSX Insider API",
    description="Backend AI Engine for Pakistan Stock Exchange Data",
    version="1.0.0"
)

# Allow React frontend to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "message": "PSX Insider AI Engine is running"}

@app.get("/api/market/status")
def get_market_status():
    # Placeholder for live PSX scraping
    return {
        "kse100": {"value": 115842.20, "change": 1.40, "status": "OPEN"},
        "kse30": {"value": 38214.10, "change": 0.81, "status": "OPEN"},
        "volume": "412M",
        "turnover": "18.4B"
    }

@app.get("/api/predictions")
def get_predictions(timeframe: str = "day"):
    """Fetch ranked predictions for Day, Week, or Month."""
    try:
        from scraper import db
        doc = db.collection("predictions").document(f"latest_{timeframe}").get()
        if doc.exists:
            return doc.to_dict()
        return {"data": [], "message": "No predictions found"}
    except Exception as e:
        return {"error": str(e), "data": []}

@app.get("/api/predictions/{symbol}")
def get_stock_predictions(symbol: str):
    """Fetch all timeframe predictions for a specific stock."""
    # This is slightly more complex if we want to search through history, 
    # but for now we'll search the latest snapshots.
    try:
        from scraper import db
        results = {}
        for tf in ["day", "week", "month"]:
            doc = db.collection("predictions").document(f"latest_{tf}").get()
            if doc.exists:
                data = doc.to_dict().get("data", [])
                match = next((item for item in data if item["symbol"] == symbol.upper()), None)
                if match:
                    results[tf] = match
        return results
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/health")
def health():
    import os, json, pytz
    from datetime import datetime
    
    active_spikes = 0
    avg_count = 0
    
    try:
        from scraper import db
        
        # 1. Active Spikes (From Firestore)
        if db:
            spikes_doc = db.collection("volume_spikes").document("latest").get()
            if spikes_doc.exists:
                spikes = spikes_doc.to_dict().get("spikes", [])
                active_spikes = len([s for s in spikes if s.get('spike_ratio', 0) >= 2.0])
                
        # 2. Tracked tickers
        if db:
            avg_count = len(list(db.collection("daily_volumes").list_documents()))
                
    except Exception as e:
        print(f"Health check error: {e}")
        
    PKT = pytz.timezone('Asia/Karachi')
    return {
        'status': 'ok',
        'active_spikes_detected': active_spikes,
        'tickers_tracked_in_baseline': avg_count,
        'checked_at': datetime.now(PKT).strftime('%H:%M PKT')
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

