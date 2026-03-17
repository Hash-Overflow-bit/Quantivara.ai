# Prediction Engine v2.0: Four Critical Fixes + Signal Feedback Loop

## Overview

Your prediction engine was bunching scores, firing single-timeframe signals without confluence, not analyzing volume direction, and ignoring trend regime. This update implements all four fixes plus a continuous learning feedback loop.

---

## Problem 1: Score Bunching (19–25 WEAK) ✅ FIXED

### The Issue

Raw scores like 22.5 were meaningless without historical context. All WEAK predictions looked similar even though some were top 5% and others were bottom 10%.

### The Fix: Percentile Ranking

Each stock now receives a **percentile label** calculated across the entire universe scored that day.

**Before:**

```
ABOT: Score 22.5 [WEAK]
AKBL: Score 22.3 [WEAK]
GLAXO: Score 23.1 [WEAK]
```

User: "All WEAK? Are these different?"

**After:**

```
ABOT: Score 22.5 [Top 15% of 103 stocks] [WEAK]
AKBL: Score 22.3 [Top 45% of 103 stocks] [WEAK]
GLAXO: Score 23.1 [Top 8% of 103 stocks] [WEAK]
```

User: "Ah, GLAXO's WEAK signal is stronger than AKBL's."

### Implementation

```python
# In run_prediction_engine()
ranked = sorted(results, key=lambda x: x['score'], reverse=True)
for idx, r in enumerate(ranked):
    percentile = round((idx / len(ranked)) * 100, 1)
    r['percentile_label'] = f"Top {round(100 - percentile)}% of today's {len(ranked)} stocks"
```

**Firestore document now includes:**

```json
{
  "score": 22.5,
  "percentile": 15,
  "percentile_label": "Top 15% of today's 103 stocks",
  "bias": "WEAK"
}
```

---

## Problem 2: Single-Timeframe Signals (No Confluence) ✅ FIXED

### The Issue

Your engine fired signals independently:

- "Closed top 0% of range" (price action)
- "Above MA20" (moving average)
- "Vol 6.1x avg" (volume)

Each could be noise. A stock with ALL THREE is much more reliable than one with only one signal.

### The Fix: Confluence Scoring

Signals are now **weighted by how many other signals agree**.

**Confluence Multiplier Logic:**

```python
1 signal fired = 1.0x multiplier (baseline)
2 signals fired = 1.4x multiplier
3+ signals fired = 1.8x multiplier (very high confidence)

final_score = base_score * confluence_multiplier
```

### Example

```
ABOT:
  - D1_close_strength: 15 pts
  - D3_rsi_momentum: 12 pts
  - D5_above_ma20: 8 pts
  ─────────────────────
  Base Score: 35 points
  Signals Fired: 3 → Confluence Multiplier: 1.8x
  FINAL: 35 × 1.8 = 63 [STRONG_BULLISH instead of WATCH]
```

### Firestore Document

```json
{
  "score": 63.0,
  "base_score": 35.0,
  "confluence_count": 3,
  "confluence_multiplier": 1.8,
  "bias": "STRONG_BULLISH"
}
```

---

## Problem 3: Volume Without Direction Context ✅ FIXED

### The Issue

"Vol 6.1x avg" could mean:

- **Bullish:** Price +3% on 6x volume → Institutional accumulation
- **Bearish:** Price -2% on 6x volume → Institutional distribution

Your engine treated both the same.

### The Fix: Directional Volume Analysis

Volume scores now change based on **whether price is up or down**:

```python
def get_directional_volume(hist, volume_multiple):
    last_close = hist['Close'].iloc[-1]
    prev_close = hist['Close'].iloc[-2]

    if last_close > prev_close:
        return {
            "direction": "BULLISH_VOLUME",
            "score_mult": 1.3,  # Boost score
            "msg": f"Vol {volume_multiple}x avg on UP day"
        }
    elif last_close < prev_close:
        return {
            "direction": "BEARISH_VOLUME",
            "score_mult": 0.5,  # Reduce score
            "msg": f"Vol {volume_multiple}x avg on DOWN day (distribution)"
        }
```

### Example

```
ABOT: Price +2%, Vol 6x avg
  Base Vol Score: 20 pts
  Direction: BULLISH → 20 × 1.3 = 26 pts ✓

ENGRO: Price -3%, Vol 6x avg
  Base Vol Score: 20 pts
  Direction: BEARISH → 20 × 0.5 = 10 pts ⚠️ (distribution)
```

---

## Problem 4: No Trend Filter (Dead-Cat Bounces) ✅ FIXED

### The Issue

Your engine could fire "Closed top of range" while stock was in a 3-month downtrend with broken support. This is a dead-cat bounce, not a buy signal.

### The Fix: Trend Regime Filter

Before scoring bullish signals, check: **Is price aligned with MA50 and MA200?**

```python
def get_trend_regime(hist):
    ma50 = calc_ma(hist['Close'], 50)
    ma200 = calc_ma(hist['Close'], 200)
    current = hist['Close'].iloc[-1]

    if current > ma50 > ma200:
        return {"trend": "UPTREND", "multiplier": 1.2}
    elif current < ma50 < ma200:
        return {"trend": "DOWNTREND", "multiplier": 0.6}
    else:
        return {"trend": "NEUTRAL", "multiplier": 1.0}
```

### Signal Adjustment

```python
# In calculate_day_signals()
trend_regime = get_trend_regime(hist)

# D1: Close Strength
base_score = 25
final_score = base_score * trend_regime["multiplier"]

if trend == "UPTREND":   # 1.2x → 30 pts
if trend == "DOWNTREND": # 0.6x → 15 pts (suppressed)
if trend == "NEUTRAL":   # 1.0x → 25 pts
```

### Example

```
ABOT closes at top of range:
  - Base Close Strength Score: 25 pts
  - Trend: UPTREND (price > MA50 > MA200)
  - Multiplier: 1.2x
  - Final: 25 × 1.2 = 30 pts ✓

DGKC closes at top of range:
  - Base Close Strength Score: 25 pts
  - Trend: DOWNTREND (price < MA50 < MA200)
  - Multiplier: 0.6x
  - Final: 25 × 0.6 = 15 pts ⚠️ (suppressed)
```

---

## BONUS: Signal Outcome Tracking (The Secret Sauce)

### What It Does

Every signal your engine fires is logged with the **entry price and timestamp**. After 5 and 10 trading sessions, the system checks: **"Did this signal actually work?"**

After 3–4 weeks, you get a **per-signal accuracy report** showing which signals are real alpha and which are noise.

### How It Works

**1. Log Signal**

```python
# When engine fires signals on 2026-03-13
db.collection("signal_log").document(signal_id).set({
    "symbol": "ABOT",
    "signal_description": "Closed top 5% of range [UPTREND]",
    "entry_price": 487.50,
    "fired_date": "2026-03-13",
    "timeframe": "day",
    "validation_status": "PENDING"  # Check outcome after 5 & 10 sessions
})
```

**2. Check Outcome**

```python
# After 5-7 calendar days, log_signal_outcomes() runs
# Fetches ABOT's current price and calculates return

ABOT price on 2026-03-20: 502.30
Return after 5 sessions: ((502.30 - 487.50) / 487.50) * 100 = +3.1%

Update signal_log with:
{
    "outcome_5_sessions": "WIN",
    "price_5_sessions": 502.30,
    "return_5_sessions": 3.1
}
```

**3. Get Accuracy Report**

```python
# After 3-4 weeks of data
accuracy = get_signal_accuracy_report("day")

Sample output:
{
  "D1_close_strength": {
    "win_rate": 64.2,      # 64.2% of signals returned positive
    "total_signals": 47,
    "wins": 30,
    "losses": 17,
    "recommendation": "KEEP" # >55% = trusted signal
  },
  "D2_vol_spike": {
    "win_rate": 48.1,
    "total_signals": 54,
    "wins": 26,
    "losses": 28,
    "recommendation": "DISABLE" # <45% = unreliable
  }
}
```

### Full Integration

**1. File: `signal_tracker.py` (NEW)**
Handles all outcome logging and accuracy calculations. 3 main functions:

- `log_signal_outcomes()` - Log each fired signal
- `check_signal_outcomes()` - Check 5 & 10 session outcomes
- `get_signal_accuracy_report()` - Generate accuracy per signal type

**2. File: `prediction_engine.py` (UPDATED)**
Now imports signal_tracker and logs outcomes after every prediction run:

```python
# After calculating all predictions
log_signal_outcomes(ranked, timeframe, run_date)
```

**3. Call from Scheduler**
Add to your daily 6 PM job (after market close):

```python
# In scraper.py scheduler
from signal_tracker import check_signal_outcomes
scheduler.add_job(check_signal_outcomes, 'cron', hour=18, minute=30)
```

---

## Installation & Setup

### 1. Files Modified/Created

```
backend/prediction_engine.py    (UPDATED - all 4 fixes + confluence)
backend/signal_tracker.py        (NEW - outcome tracking)
```

### 2. Add to Your Scheduler

Edit `backend/scraper.py`:

```python
def init_scheduler():
    # ... existing jobs ...

    # NEW: Daily signal outcome validation at 6 PM
    scheduler.add_job(
        check_signal_outcomes,  # check_signal_outcomes from signal_tracker
        'cron',
        hour=18,
        minute=30,
        timezone='Asia/Karachi'
    )
```

### 3. Test

```bash
cd backend

# Test prediction engine (should now have confluence + percentiles)
python prediction_engine.py

# Check signal accuracy after collecting data
python -c "from signal_tracker import get_signal_accuracy_report; print(get_signal_accuracy_report('day'))"
```

---

## What You'll See in Firestore

### predictions/latest_day

```json
{
  "data": [
    {
      "symbol": "ABOT",
      "score": 62.5, // Confluence-adjusted
      "base_score": 35.0,
      "confluence_count": 3, // 3 signals = 1.8x multiplier
      "confluence_multiplier": 1.8,
      "percentile": 12.4,
      "percentile_label": "Top 12% of today's 103 stocks",
      "bias": "STRONG BULLISH",
      "signals_fired": [
        "Closed top 5% of range [UPTREND]",
        "RSI 62 momentum zone",
        "Above MA20 (485.30)"
      ]
    }
  ]
}
```

### signal_log/[signal_id]

```json
{
  "symbol": "ABOT",
  "signal_description": "Closed top 5% of range [UPTREND]",
  "entry_price": 487.5,
  "fired_date": "2026-03-13",
  "outcome_5_sessions": "WIN",
  "return_5_sessions": 3.1,
  "outcome_10_sessions": "WIN",
  "return_10_sessions": 5.7,
  "validation_status": "COMPLETE"
}
```

---

## Timeline to Real Validation

- **Day 1-5:** Engine runs, logs signals → No outcome data yet
- **Day 5-7:** First batch of 5-session outcomes recorded
- **Day 10-14:** Second batch of 10-session outcomes recorded
- **Day 21+:** Sufficient data to see signal patterns (50+ signals each type)
- **Day 28:** **First accuracy report tells you which signals actually work on PSX**

This is what separates a dashboard that _looks smart_ from an engine that _actually makes money_.

---

## Key Metrics to Monitor

After 3-4 weeks:

1. **Win Rate by Signal Type** - Which signals have >55% accuracy?
2. **Average Return per Signal** - Do winning signals return 2%? 5%?
3. **False Positive Rate** - How often does STRONG_BULLISH lead to losses?
4. **Confluence Effect** - Compare 1-signal vs 3-signal accuracy

You'll quickly learn:

- "D3_rsi_momentum" is 72% accurate → keep it
- "D6_sector_green" is 38% accurate → disable it
- "Price above MA20 + RSI > 55" returns 4.2% avg → your edge

This feedback loop is what takes your engine from prototype to production.

---

## Questions to Test After 4 Weeks

- Do STRONG_BULLISH predictions actually outperform BULLISH?
- Which signals should be weighted more?
- Should you disable low-accuracy signals?
- What's the average holding period before signals revert?
- Which sectors respond better to your signals?

**The answers come from your signal_log. No guessing. Pure data.**
