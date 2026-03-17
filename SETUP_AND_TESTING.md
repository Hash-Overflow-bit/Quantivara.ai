# PSX Dashboard Data Update - Setup & Testing Guide

## What Was Fixed

### 1. **Scheduler Not Running (Root Cause)**

- **Issue**: The scheduler was defined in `scraper.py` but never started by the main API server
- **Fix**: Integrated APScheduler into FastAPI's lifespan management in `main.py`
- **Result**: Data now updates automatically every 10 minutes during market hours

### 2. **Better Data Parsing**

- Improved `get_all_stocks()` function with robust error handling
- Better logging to identify parsing failures
- Proper rounding of prices to 2 decimals
- Volume format standardization (M/K/B suffix handling)

### 3. **Enhanced Logging**

- Added detailed logging at each step of data collection
- Error messages show exactly where failures occur
- Helps debug PSX website structure changes

## How to Run

### Backend Setup

```bash
cd backend

# Install dependencies (if not already installed)
pip install requests beautifulsoup4 firebase-admin apscheduler yfinance pandas pytz

# Start the backend server
python main.py
# or for production: uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will:

1. Start on `http://localhost:8000`
2. Initialize Firebase connection
3. Start the APScheduler
4. Push data immediately (first update)
5. Schedule updates every 10 minutes (9:00 AM - 4:00 PM PKT)

### Frontend Setup

```bash
# In root directory
npm install
npm run dev
# Opens on http://localhost:5173
```

## Expected Behavior

### Market Hours (9:30 AM - 3:30 PM PKT)

- Data updates every 10 minutes automatically
- Dashboard shows latest prices, volumes, changes
- All prices should match PSX website (exact 2 decimals)
- Volume shows actual trading volume

### After Market Closes (3:30 PM PKT)

- Dashboard shows final day data
- Next update at market open (9:30 AM next day)
- Data persists in Firebase for overnight review

## Data Mapping

The following data should now update automatically:

| Component            | Source                     | Updates      |
| -------------------- | -------------------------- | ------------ |
| KSE-100/KSE-30 Index | PSX Homepage               | Every 10 min |
| Stock Prices         | Market Watch               | Every 10 min |
| Volume               | Market Watch               | Every 10 min |
| Top Gainers/Losers   | Calculated from all stocks | Every 10 min |
| Volume Spikes        | Screener calculation       | Every 10 min |
| Intraday Charts      | PSX API                    | Every 10 min |

## Troubleshooting

### If data isn't updating:

1. **Check backend logs** when running `python main.py`:
   - Look for "✓ Scheduler initialized" message
   - Check for errors in data fetching

2. **Verify Firebase connection**:

   ```bash
   curl http://localhost:8000/api/health
   ```

   Should show current active spikes and tickers tracked

3. **Check market hours**:
   - Scheduler only runs Monday-Friday 9:00 AM - 4:00 PM PKT
   - Outside these hours, no automatic updates

4. **Verify data on PSX** (browser inspection):
   - Visit https://dps.psx.com.pk/market-watch
   - Check if prices match your dashboard
   - If PSX website structure changed, selectors may need updating

5. **Debug script**:
   ```bash
   python backend/debug_psx_structure.py
   ```
   Inspects actual PSX website structure and shows what's being scraped

## Key API Endpoints

- `GET /api/market/status` - Current market indices
- `GET /api/health` - System health & active tracking
- `GET /api/predictions?timeframe=day` - AI predictions by timeframe
- `GET /api/foreign-flow` - Foreign investment flows

All data comes from Firebase Realtime Updates (via onSnapshot in frontend).

## Next Steps

1. **Verify data accuracy**: Compare dashboard numbers with PSX website
2. **Monitor logs**: Keep backend logs open during market hours
3. **Test across timeframes**: Verify daily/weekly/monthly predictions update
4. **Check volume accuracy**: Ensure volume numbers match PSX exactly

---

**Last Updated**: 2026-03-13 | **Status**: Scheduler integrated and logging enhanced
