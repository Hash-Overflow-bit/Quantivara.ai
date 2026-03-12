import sqlite3
import yfinance as yf
import os
import json
from datetime import datetime
import time

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(_BASE_DIR, "psx.db")
kse100_path = os.path.join(_BASE_DIR, "kse100.json")

def seed_db():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Seeding psx.db with 30-day history...")
    
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_volumes (
            symbol      TEXT,
            date        TEXT,
            volume      REAL,
            close_price REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spike_cache (
            symbol      TEXT PRIMARY KEY,
            today_vol   REAL,
            avg_vol     REAL,
            spike_ratio REAL,
            price       REAL,
            change      REAL,
            projected_vol REAL,
            updated_at  TEXT
        )
    """)
    
    with open(kse100_path, 'r') as f:
        tickers = json.load(f)
        
    print(f"Fetching history for {len(tickers)} tickers...")
    
    batch_size = 20
    inserted = 0
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        yf_tickers = " ".join([f"{t}.KA" for t in batch])
        try:
            data = yf.download(yf_tickers, period="30d", interval="1d", group_by='ticker', progress=False)
            
            records = []
            for t in batch:
                symbol = f"{t}.KA"
                if symbol not in data: continue
                # if there is no MultiIndex, data is directly accessible if 1 ticker, else data[symbol]
                ticker_df = data[symbol] if len(batch) > 1 else data
                ticker_df = ticker_df[ticker_df['Volume'] > 0].dropna(subset=['Volume'])
                
                for date, row in ticker_df.iterrows():
                    # Check if date is not naive
                    if not pd.isna(row['Volume']):
                        records.append((
                            t,
                            date.strftime('%Y-%m-%d'),
                            float(row['Volume']),
                            float(row['Close'])
                        ))
            
            if records:
                conn.executemany("INSERT OR IGNORE INTO daily_volumes (symbol, date, volume, close_price) VALUES (?, ?, ?, ?)", records)
                conn.commit()
                inserted += len(records)
                print(f"Inserted {len(records)} records for batch {i//batch_size + 1}")
        except Exception as e:
            print(f"  Error fetching baseline batch: {e}")
        time.sleep(1)
        
    print(f"Success: Seeded {inserted} total historical volume records.")
    
if __name__ == "__main__":
    import pandas as pd
    seed_db()
