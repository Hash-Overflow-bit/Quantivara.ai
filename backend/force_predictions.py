from prediction_engine import run_prediction_engine
import firebase_admin

print("🚀 Manually triggering Multi-Timeframe Scoring Engine...")
print("Scoring DAY timeframe...")
run_prediction_engine("day")
print("Scoring WEEK timeframe...")
run_prediction_engine("week")
print("Scoring MONTH timeframe...")
run_prediction_engine("month")
print("✅ All timeframes scored and synced to Firestore.")
