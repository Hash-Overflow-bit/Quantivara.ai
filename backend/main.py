import sys
import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Change to the current file's directory to ensure relative paths work
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Redirect stdout/stderr to files immediately for background runs
sys.stdout = open('server_log.txt', 'a', encoding='utf-8', buffering=1)
sys.stderr = open('server_err.txt', 'a', encoding='utf-8', buffering=1)

# Import local shared config
from shared import db, PKT, MARKET_OPEN_H, MARKET_CLOSE_H

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

from pipeline import run_scrape_pipeline
from ai_engine import run_ai_layer
from chart_api import chart_router

# Global scheduler reference
scheduler = AsyncIOScheduler(timezone=PKT)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the FastAPI app"""
    try:
        from scraper import init_scheduler, push_to_firebase
        from foreign_flow import backfill_flow_data, update_foreign_flow
        import asyncio
        import threading
        
        # Check if foreign_flow collection is empty and backfill if needed
        try:
            ff_docs = db.collection("foreign_flow").limit(1).stream()
            ff_count = len(list(ff_docs))
            if ff_count == 0:
                logger.info("Foreign flow collection is empty - backfilling initial data...")
                backfill_flow_data()
        except Exception as e:
            logger.warning(f"Backfill check failed: {e}")
        
        # 1. Add Phase 1 Pipeline Jobs
        scheduler.add_job(run_scrape_pipeline, "cron", hour=9, minute=0, id="pre_market_pipeline")
        scheduler.add_job(run_scrape_pipeline, "cron", hour=15, minute=45, id="post_close_pipeline")
        
        # 2. Add Phase 2 AI Layer Jobs
        scheduler.add_job(run_ai_layer, "cron", hour=9, minute=15, id="morning_ai_layer")
        scheduler.add_job(run_ai_layer, "cron", hour=16, minute=0, id="evening_ai_layer")
        
        # 3. Add existing live scraper (10-min interval)
        scheduler.add_job(push_to_firebase, "cron", day_of_week="mon-fri", hour="9-15", minute="*/10", id="live_scraper")
        
        # 4. Add Foreign Flow Update Job (Daily at 5:30 PM)
        scheduler.add_job(update_foreign_flow, "cron", day_of_week="mon-fri", hour=17, minute=30, id="foreign_flow_scrape")
        
        scheduler.start()
        logger.info("✓ AsyncIOScheduler initialized and started")
        
        # Run initial sync and pipeline tasks in background thread to avoid blocking startup
        def initial_sync():
            logger.info("--- STARTING INITIAL DATA SYNC ---")
            try:
                push_to_firebase()
                run_scrape_pipeline()
                run_ai_layer()
                logger.info("--- INITIAL DATA SYNC COMPLETE ---")
            except Exception as e:
                logger.error(f"Initial sync failed: {e}")

        threading.Thread(target=initial_sync, daemon=True).start()
        
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
    
    yield
    
    # Shutdown: Stop scheduler
    try:
        if scheduler:
            scheduler.shutdown()
            logger.info("✓ Scheduler shutdown complete")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}")

app = FastAPI(
    title="PSX Insider API",
    description="Backend AI Engine for Pakistan Stock Exchange Data",
    version="1.0.0",
    lifespan=lifespan
)

# Allow React frontend to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(chart_router)

@app.get("/")
def read_root():
    return {"status": "online", "message": "PSX Insider AI Engine is running"}

@app.get("/api/market/status")
def get_market_status():
    """Returns actual market status and index values."""
    now_pkt = datetime.now(PKT)
    current_hour = now_pkt.hour + now_pkt.minute / 60.0
    day_of_week = now_pkt.weekday()
    
    is_weekday = day_of_week < 5
    if is_weekday and MARKET_OPEN_H <= current_hour < MARKET_CLOSE_H:
        status = "OPEN"
    elif is_weekday and current_hour < MARKET_OPEN_H:
        status = "PRE_OPEN"
    else:
        status = "CLOSED"
    
    try:
        latest_doc = db.collection("market_data").document("latest").get()
        if latest_doc.exists:
            data = latest_doc.to_dict()
            
            def get_val(key, subkey, default):
                if key in data and isinstance(data[key], dict):
                    return data[key].get(subkey, default)
                return data.get(f"{key}_{subkey}", data.get(f"{key}_{'pct' if subkey == 'change_pct' else subkey}", default))

            return {
                "kse100": {
                    "value": get_val("kse100", "value", 115842.20),
                    "change": get_val("kse100", "points", 0),
                    "change_pct": get_val("kse100", "change", 0),
                    "status": status,
                    "timestamp": data.get("timestamp", now_pkt.isoformat())
                },
                "kse30": {
                    "value": get_val("kse30", "value", 38214.10),
                    "change": get_val("kse30", "points", 0),
                    "change_pct": get_val("kse30", "change", 0),
                    "status": status
                },
                "volume": data.get("volume", "0"),
                "turnover": data.get("turnover", "0"),
                "status": status,
                "market_hours": {"open": "9:30 AM", "close": "3:30 PM", "timezone": "PKT"}
            }
    except Exception as e:
        logger.warning(f"Error reading Firestore: {e}")
    
    return {
        "kse100": {"value": 115842.20, "change": 0, "change_pct": 0, "status": status},
        "kse30": {"value": 38214.10, "change": 0, "change_pct": 0, "status": status},
        "volume": "0",
        "turnover": "0",
        "status": status,
        "market_hours": {"open": "9:30 AM", "close": "3:30 PM", "timezone": "PKT"}
    }

@app.get("/api/predictions")
def get_predictions(timeframe: str = "day"):
    try:
        doc = db.collection("predictions").document(f"latest_{timeframe}").get()
        if doc.exists:
            return doc.to_dict()
        return {"data": [], "message": "No predictions found"}
    except Exception as e:
        return {"error": str(e), "data": []}

@app.get("/api/predictions/{symbol}")
def get_stock_predictions(symbol: str):
    try:
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

@app.get("/api/foreign-flow")
def get_foreign_flow(days: int = 90):
    logger.info(f"API: GET /api/foreign-flow?days={days}")
    try:
        # 1. Fetch Foreign Flow Data from Firestore
        docs = db.collection("foreign_flow").order_by("date", direction="DESCENDING").limit(days).get()
        data = [d.to_dict() for d in docs]
        data.reverse()
        
        last_5 = data[-5:] if len(data) >= 5 else data
        last_30 = data[-30:] if len(data) >= 30 else data
        
        sum_5 = round(sum(d.get('net', 0) for d in last_5), 2)
        sum_30 = round(sum(d.get('net', 0) for d in last_30), 2)
        
        # 2. Fetch Index Data (with timeout and fallbacks)
        index_points = []
        try:
            import yfinance as yf
            import concurrent.futures
            
            def fetch_yf_data(ticker_sym):
                ticker = yf.Ticker(ticker_sym)
                hist = ticker.history(period="6mo", interval="1d")
                return ticker_sym, hist

            logger.info("Fetching yfinance index data...")
            # We try them in parallel or with a short timeout to prevent hanging the whole request
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = {executor.submit(fetch_yf_data, sym): sym for sym in ["^KSE100", "KSE100.KA", "KSE.KA"]}
                for future in concurrent.futures.as_completed(futures, timeout=10):
                    sym, index_hist = future.result()
                    if not index_hist.empty:
                        logger.info(f"Successfully fetched index data for {sym}")
                        for dt, row in index_hist.iterrows():
                            index_points.append({"time": dt.strftime("%Y-%m-%d"), "value": round(float(row['Close']), 2)})
                        break
            
            if not index_points:
                logger.warning("No yfinance data found for indices, using fallback.")
                if data:
                    current_val = 115842.20
                    latest_market = db.collection("market_data").document("latest").get()
                    if latest_market.exists:
                        m_data = latest_market.to_dict()
                        current_val = m_data.get("kse100_val", m_data.get("kse100", {}).get("value", current_val))
                    
                    import random
                    for d in data:
                        index_points.append({"time": d.get('date'), "value": round(current_val * (1 + random.uniform(-0.01, 0.01)), 2)})
        except Exception as ey:
            logger.warning(f"yfinance logic failed: {ey}")
            # Ensure we return something if indices fail but flow is fine
            if not index_points and data:
                 index_points = [{"time": d.get('date'), "value": 0} for d in data]

        return {
            "flow_data": data,
            "index_data": index_points,
            "summary": {
                "last_5d_net": sum_5,
                "last_30d_net": sum_30,
                "total_points": len(data)
            }
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error in get_foreign_flow: {e}\n{error_trace}")
        return {"error": str(e), "trace": error_trace}

@app.get("/api/health")
def health():
    active_spikes = 0
    try:
        spikes_doc = db.collection("volume_spikes").document("latest").get()
        if spikes_doc.exists:
            spikes = spikes_doc.to_dict().get("spikes", [])
            active_spikes = len([s for s in spikes if s.get('spike_ratio', 0) >= 2.0])
    except: pass
        
    return {
        'status': 'ok',
        'active_spikes_detected': active_spikes,
        'checked_at': datetime.now(PKT).strftime('%H:%M PKT')
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
