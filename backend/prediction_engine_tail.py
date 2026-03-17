

def get_signal_accuracy_report(timeframe: str = "day") -> dict:
    """
    Fetch signal accuracy report from signal_tracker.
    Shows which signals are actually working on PSX.
    """
    try:
        from signal_tracker import get_signal_accuracy_report as fetch_report
        return fetch_report(timeframe)
    except Exception as e:
        print(f"Could not fetch accuracy report: {e}")
        return {}


if __name__ == "__main__":
    # Test runs
    # run_prediction_engine("day")
    # run_prediction_engine("week")
    # run_prediction_engine("month")
    pass
