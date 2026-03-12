import yfinance as yf
import json
import os
import sys
from datetime import datetime
import pytz

# Redirect print to a file
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_results.txt")
log = open(log_path, 'w', encoding='utf-8')

def p(msg=""):
    print(msg)
    log.write(msg + "\n")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PKT = pytz.timezone('Asia/Karachi')

# Suppress yfinance warnings
import warnings
warnings.filterwarnings("ignore")
import logging
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ============================================================
p("=" * 80)
p("STEP 1: yFinance PSX Data Verification")
p("=" * 80)

test_tickers = ["OGDC.KA", "LUCK.KA", "HUBC.KA", "HBL.KA", "FFC.KA", "KEL.KA", "PPL.KA", "EFERT.KA", "PSO.KA", "ENGRO.KA"]
working = 0
broken = 0

for t in test_tickers:
    try:
        ticker = yf.Ticker(t)
        hist = ticker.history(period="5d", interval="1d")
        if hist.empty:
            p(f"  FAIL  {t:12} => EMPTY (possibly wrong suffix)")
            broken += 1
        else:
            vol = hist['Volume'].iloc[-1]
            close = hist['Close'].iloc[-1]
            p(f"  OK    {t:12} => Close: {close:10.2f}  Volume: {vol:>14,.0f}  Rows: {len(hist)}")
            working += 1
    except Exception as e:
        p(f"  FAIL  {t:12} => ERROR: {e}")
        broken += 1

p(f"\n  Result: {working}/{len(test_tickers)} tickers returning data")

# ============================================================
p("\n" + "=" * 80)
p("STEP 2: 30-Day Baseline Sanity Check")
p("=" * 80)

baseline_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "volume_baseline.json")
with open(baseline_path, 'r') as f:
    baseline = json.load(f)

p(f"  Total tickers in baseline: {len(baseline)}")

zero_vol = [s for s, d in baseline.items() if d.get('avg_30d_volume', 0) == 0]
huge_vol = [s for s, d in baseline.items() if d.get('avg_30d_volume', 0) > 500_000_000]
tiny_vol = [s for s, d in baseline.items() if 0 < d.get('avg_30d_volume', 0) < 500_000]
liquid = [s for s, d in baseline.items() if d.get('avg_30d_volume', 0) >= 500_000]

p(f"  Liquid stocks (avg >= 500K):  {len(liquid)}")
p(f"  Illiquid stocks (avg < 500K): {len(tiny_vol)}")

if zero_vol:
    p(f"  RED FLAG: {len(zero_vol)} stocks with avg volume = 0: {zero_vol[:5]}")
else:
    p(f"  OK: No stocks with zero volume")
if huge_vol:
    p(f"  WARNING: {len(huge_vol)} stocks with avg volume > 500M: {huge_vol[:5]}")
else:
    p(f"  OK: No stocks with suspiciously large volume")

sorted_baseline = sorted(baseline.items(), key=lambda x: x[1].get('avg_30d_volume', 0), reverse=True)
p("\n  Top 10 by avg 30d volume:")
for sym, data in sorted_baseline[:10]:
    avg = data.get('avg_30d_volume', 0)
    updated = data.get('updated_at', 'unknown')
    p(f"    {sym:10} => avg: {avg:>14,}  | updated: {updated}")

# ============================================================
p("\n" + "=" * 80)
p("STEP 3: Volume Spike Screener Dry Run")
p("=" * 80)

from scraper import get_all_stocks, get_volume_spikes, MARKET_OPEN_H

now = datetime.now(PKT)
current_hour = now.hour + now.minute/60
hours_elapsed = current_hour - MARKET_OPEN_H
hours_capped = min(max(hours_elapsed, 0), 6.0)

p(f"  Current PKT Time: {now.strftime('%H:%M:%S')}")
p(f"  Hours since 9:30 AM: {hours_elapsed:.2f}")
p(f"  Hours capped: {hours_capped:.2f}")

all_stocks = get_all_stocks()
p(f"  Stocks scraped from PSX: {len(all_stocks)}")

stock_map = {s['symbol']: s for s in all_stocks}
spike_count = 0
analyzed = 0

p(f"\n  {'SYMBOL':<10} {'TODAY_VOL':>12} {'PROJ_VOL':>12} {'AVG_VOL':>12} {'SPIKE':>8} {'PRICE':>8} {'CHG':>8}")
p("  " + "-" * 75)

for symbol, base_data in sorted(baseline.items()):
    if symbol not in stock_map:
        continue
    s = stock_map[symbol]
    avg_vol = base_data.get('avg_30d_volume', 1)
    if avg_vol < 500_000:
        continue
    try:
        vol_str = s['volume'].replace(',', '')
        if 'M' in vol_str: today_vol = float(vol_str.replace('M', '')) * 1_000_000
        elif 'K' in vol_str: today_vol = float(vol_str.replace('K', '')) * 1_000
        else: today_vol = float(vol_str)
    except: continue
    
    analyzed += 1
    adj_hours = max(hours_capped, 0.1)
    projected_vol = (today_vol / adj_hours) * 6.0
    spike_ratio = round(projected_vol / avg_vol, 2)
    
    flag = "RED" if spike_ratio >= 3 else "YLW" if spike_ratio >= 2 else "GRN" if spike_ratio >= 1.5 else ""
    if spike_ratio >= 1.5: spike_count += 1
    if spike_ratio >= 1.0 or analyzed <= 5:
        p(f"  {symbol:<10} {today_vol:>12,.0f} {projected_vol:>12,.0f} {avg_vol:>12,.0f} {spike_ratio:>7.2f}x {s['price']:>8.2f} {s['change']:>+7.2f}% {flag}")

p(f"\n  Analyzed: {analyzed} liquid stocks | Spikes >= 1.5x: {spike_count}")

spikes = get_volume_spikes()
p(f"\n  get_volume_spikes() returned: {len(spikes)} spikes")
for sp in spikes[:10]:
    p(f"    {sp['symbol']:10} => {sp['spike_ratio']}x  (today: {sp['today_vol']:,.0f} vs avg: {sp['avg_vol']:,.0f})")

# ============================================================
p("\n" + "=" * 80)
p("STEP 4: Cross-Verify Top Spike (PSX vs yFinance)")
p("=" * 80)

if spikes:
    top = spikes[0]
    sym = top['symbol']
    p(f"  Testing top spike: {sym}")
    p(f"  PSX Scrape => Price:{top['price']:.2f}, Vol:{top['today_vol']:,.0f}, Spike:{top['spike_ratio']}x")
    try:
        yf_t = yf.Ticker(f"{sym}.KA")
        yf_h = yf_t.history(period="1d", interval="1d")
        if not yf_h.empty:
            yf_vol = yf_h['Volume'].iloc[-1]
            yf_close = yf_h['Close'].iloc[-1]
            p(f"  yFinance   => Close:{yf_close:.2f}, Volume:{yf_vol:,.0f}")
            vol_diff = abs(top['today_vol'] - yf_vol) / max(yf_vol, 1) * 100
            price_diff = abs(top['price'] - yf_close) / max(yf_close, 1) * 100
            p(f"  Volume diff: {vol_diff:.1f}% {'PASS' if vol_diff < 15 else 'FAIL'}")
            p(f"  Price diff:  {price_diff:.1f}% {'PASS' if price_diff < 5 else 'FAIL'}")
        else:
            p(f"  yFinance returned empty for {sym}.KA")
    except Exception as e:
        p(f"  yFinance error: {e}")
else:
    p("  No spikes to cross-verify.")

p("\n" + "=" * 80)
p("CHECKLIST SUMMARY")
p("=" * 80)
p(f"  [{'PASS' if working >= 8 else 'FAIL'}] Step 1: yFinance returns PSX data ({working}/{len(test_tickers)})")
p(f"  [{'PASS' if not zero_vol and not huge_vol else 'FAIL'}] Step 2: Baseline volumes sensible")
p(f"  [{'PASS' if spike_count > 0 else 'WARN'}] Step 3: Screener finds spikes ({spike_count} found)")
p(f"  [INFO] Step 4: See cross-verification above")
p(f"  [INFO] Step 5: Scheduler running (check terminal)")
p(f"  [TODO] Step 6: Add /api/health endpoint")
p("=" * 80)

log.close()
print(f"\nFull results saved to: {log_path}")
