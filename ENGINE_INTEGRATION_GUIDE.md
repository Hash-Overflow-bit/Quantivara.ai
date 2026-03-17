# Quick Start: Integrating the Improved Prediction Engine

## 1. Deploy Files

```bash
# These files are already in place:
# - backend/prediction_engine.py (updated with all 4 fixes)
# - backend/signal_tracker.py (new, handles outcome tracking)
```

## 2. Update Your Scheduler

Edit **backend/scraper.py**, add this import:

```python
from signal_tracker import check_signal_outcomes
```

In your `init_scheduler()` function, add this job:

```python
# Run outcome validation daily at 6:30 PM (after market close)
scheduler.add_job(
    check_signal_outcomes,
    'cron',
    hour=18,
    minute=30,
    timezone='Asia/Karachi',
    id='signal_outcome_check'
)
```

## 3. Test It Works

```bash
cd backend

# Test that prediction engine runs without errors
python -c "from prediction_engine import run_prediction_engine; print('OK')"

# Test signal tracker
python -c "from signal_tracker import get_signal_accuracy_report; print(get_signal_accuracy_report('day'))"
```

## 4. Monitor Signals

After you have 2 weeks of data, run:

```python
from signal_tracker import get_signal_accuracy_report

# Get day-trading signal accuracy
day_accuracy = get_signal_accuracy_report("day")

for signal_name, stats in day_accuracy.items():
    print(f"{signal_name}: {stats['win_rate']}% win rate ({stats['recommendation']})")
```

Example output:

```
D1_close_strength: 64.2% win rate (KEEP)
D2_vol_spike: 48.1% win rate (DISABLE)
D3_rsi_momentum: 71.3% win rate (KEEP)
D4_trend_aligned: 68.9% win rate (KEEP)
```

## 5. Firestore Queries

### View top predictions (with percentiles):

```javascript
// In Firebase Console
db.collection("predictions")
  .doc("latest_day")
  .get()
  .then((doc) => {
    doc
      .data()
      .data.slice(0, 5)
      .forEach((stock) => {
        console.log(
          `${stock.symbol}: ${stock.bias} (Top ${stock.percentile}%)`,
        );
      });
  });
```

### View all fired signals:

```javascript
db.collection("signal_log")
  .where("fired_date", "==", "2026-03-13")
  .get()
  .then((snapshot) => {
    console.log(`Total signals fired: ${snapshot.size}`);
  });
```

### View completed signal outcomes:

```javascript
db.collection("signal_log")
  .where("validation_status", "==", "COMPLETE")
  .where("outcome_5_sessions", "==", "WIN")
  .get()
  .then((snapshot) => {
    console.log(`Winning signals: ${snapshot.size}`);
  });
```

## 6. Frontend Display

### Show percentile context

```tsx
// In your predictions list
<div>
  <strong>{stock.symbol}</strong>
  <span>{stock.bias}</span>
  <span className="text-xs text-gray-500">{stock.percentile_label}</span>
</div>
```

### Show confluence confidence

```tsx
<div>
  <span>{stock.bias}</span>
  <span className="text-xs">
    Confidence: {stock.confluence_count} signals
    {stock.confluence_count >= 3 && "  ⭐ High"}
  </span>
</div>
```

## 7. Python Helper Script

Save as **backend/check_engine_health.py**:

```python
def health_check():
    from prediction_engine import get_signal_accuracy_report
    from shared import db

    # Check signal accuracy
    accuracy = get_signal_accuracy_report("day")
    print("Signal Accuracy (5-day outcomes):")
    for signal, stats in accuracy.items():
        status = "✓" if stats['recommendation'] == "KEEP" else "✗"
        print(f"  {status} {signal}: {stats['win_rate']}%")

    # Check recent predictions
    doc = db.collection("predictions").document("latest_day").get()
    if doc.exists:
        data = doc.to_dict()
        print(f"\nLatest predictions: {len(data['data'])} stocks")
        print(f"Top pick: {data['data'][0]['symbol']} ({data['data'][0]['bias']})")

    # Check signal log volume
    signals = db.collection("signal_log").where(
        "validation_status", "==", "PENDING"
    ).stream()
    count = sum(1 for _ in signals)
    print(f"\nPending signal validations: {count}")

if __name__ == "__main__":
    health_check()
```

Run with:

```bash
python backend/check_engine_health.py
```

## 8. What Changes You'll See

**Before:**

```
ABOT: Score 22 [WEAK]
AKBL: Score 20 [WEAK]
GLAXO: Score 24 [WEAK]
```

→ All look the same

**After:**

```
ABOT: Score 31 [Top 8% of 103] [STRONG BULLISH]
  3 confirming signals (close + RSI + MA20)

AKBL: Score 18 [Top 62%] [WEAK]
  1 signal only

GLAXO: Score 25 [Top 25%] [WATCH]
  2 confirming signals but DOWNTREND suppressed price signal
```

→ Clear difference in confidence & context

## 9. Validation Timeline

- **Week 1:** Engine logs initial signals, no outcomes yet
- **Week 2:** 5-session outcomes start appearing
- **Week 3:** 10-session outcomes + pattern emerging
- **Week 4:** First actionable accuracy report ready

## 10. Next Steps (Optional)

Once you have 4 weeks of signal accuracy data:

1. **Weight signals by accuracy** - Higher accuracy signals get higher point values
2. **Dynamic signal selection** - Disable signals with <45% win rate
3. **Macro filter** - Reduce all scores on SBP decision days
4. **Sector rotation** - Add sector momentum as a macro filter

This transforms your engine from rules-based to **data-driven**.

---

**Questions?** Check [PREDICTION_ENGINE_V2_FIXES.md](PREDICTION_ENGINE_V2_FIXES.md) for detailed explanations of each fix.
