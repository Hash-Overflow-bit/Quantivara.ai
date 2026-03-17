"""
Signal outcome tracking module.
This system logs every signal and validates accuracy 5 & 10 sessions later.
Building the feedback loop that separates real alpha from noise.
"""

from datetime import datetime, timedelta
import yfinance as yf
from shared import db, PKT


def log_signal_outcomes(ranked_results: list, timeframe: str, run_date: str):
    """
    Log all fired signals with entry price for later outcome tracking.
    After 5 and 10 sessions, we check: did the predicted move happen?
    """
    if not db: return
    
    for result in ranked_results:
        symbol = result['symbol']
        signals = result['signals_fired']
        entry_price = result['price_at_run']
        
        # Each signal gets logged independently for outcome tracking
        for idx, signal_msg in enumerate(signals):
            signal_id = f"{symbol}_{run_date}_{timeframe}_{idx}_{hash(signal_msg)}"
            
            db.collection("signal_log").document(signal_id).set({
                "symbol": symbol,
                "signal_description": signal_msg,
                "entry_price": entry_price,
                "fired_date": run_date,
                "fired_timestamp": datetime.now(PKT).isoformat(),
                "timeframe": timeframe,
                "score": result['score'],
                "bias": result['bias'],
                # Outcome tracking (populated later)
                "outcome_5_sessions": None,
                "outcome_10_sessions": None,
                "price_5_sessions": None,
                "price_10_sessions": None,
                "return_5_sessions": None,
                "return_10_sessions": None,
                "validation_status": "PENDING"
            })


def check_signal_outcomes():
    """
    Run this daily (after market close).
    For signals fired 5 and 10 sessions ago, fetch current price and record outcome.
    This gives you per-signal accuracy which you can use to weight signals better.
    """
    if not db: return
    
    today = datetime.now(PKT)
    
    # Find signals to check
    pending_signals = db.collection("signal_log").where(
        "validation_status", "==", "PENDING"
    ).stream()
    
    checked_count = 0
    for signal_doc in pending_signals:
        signal = signal_doc.to_dict()
        fired_date = datetime.strptime(signal['fired_date'], '%Y-%m-%d').replace(tzinfo=PKT)
        days_elapsed = (today - fired_date).days
        
        symbol = signal['symbol']
        entry_price = signal['entry_price']
        
        try:
            # Fetch current price
            ticker = yf.Ticker(f"{symbol}.KA")
            hist = ticker.history(period="1mo", interval="1d")
            if hist.empty: continue
            
            current_price = float(hist['Close'].iloc[-1])
            
            # Check 5-session outcome (approximately 7 calendar days)
            if 5 <= days_elapsed < 7 and not signal.get('outcome_5_sessions'):
                return_5 = round(((current_price - entry_price) / entry_price) * 100, 2)
                signal_doc.reference.update({
                    "price_5_sessions": current_price,
                    "return_5_sessions": return_5,
                    "outcome_5_sessions": "WIN" if return_5 > 0 else "LOSS" if return_5 < 0 else "FLAT"
                })
                checked_count += 1
            
            # Check 10-session outcome (approximately 14 calendar days)
            if days_elapsed >= 10 and not signal.get('outcome_10_sessions'):
                return_10 = round(((current_price - entry_price) / entry_price) * 100, 2)
                signal_doc.reference.update({
                    "price_10_sessions": current_price,
                    "return_10_sessions": return_10,
                    "outcome_10_sessions": "WIN" if return_10 > 0 else "LOSS" if return_10 < 0 else "FLAT",
                    "validation_status": "COMPLETE"
                })
                checked_count += 1
        except Exception as e:
            print(f"Error checking outcome for {symbol}: {e}")
    
    print(f"✓ Signal outcome tracking: validated {checked_count} signal outcomes")


def get_signal_accuracy_report(timeframe: str = "day") -> dict:
    """
    Query signal_log and compute accuracy by signal type.
    Example: "D1_close_strength" has 65% win rate, "D2_vol_spike" has 48% etc.
    Use this to weight or disable low-accuracy signals.
    """
    if not db: return {}
    
    # Fetch signals that have completed 5-session validation
    completed = db.collection("signal_log").where(
        "outcome_5_sessions", "!=", None
    ).where(
        "timeframe", "==", timeframe
    ).stream()
    
    stats = {}
    for signal_doc in completed:
        signal = signal_doc.to_dict()
        signal_type = signal['signal_description'].split('[')[0].strip()  # Extract signal name
        outcome = signal.get('outcome_5_sessions')
        
        if signal_type not in stats:
            stats[signal_type] = {"wins": 0, "losses": 0, "flats": 0}
        
        if outcome == "WIN":
            stats[signal_type]["wins"] += 1
        elif outcome == "LOSS":
            stats[signal_type]["losses"] += 1
        else:
            stats[signal_type]["flats"] += 1
    
    # Calculate accuracy percentages
    report = {}
    for signal_type, outcomes in stats.items():
        total = outcomes["wins"] + outcomes["losses"] + outcomes["flats"]
        if total > 0:
            win_rate = round((outcomes["wins"] / total) * 100, 1)
            report[signal_type] = {
                "win_rate": win_rate,
                "total_signals": total,
                "wins": outcomes["wins"],
                "losses": outcomes["losses"],
                "flats": outcomes["flats"],
                "recommendation": "KEEP" if win_rate >= 55 else "REVIEW" if win_rate >= 45 else "DISABLE"
            }
    
    return report
