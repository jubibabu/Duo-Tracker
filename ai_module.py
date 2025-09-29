# ai_module.py
from datetime import date, timedelta, datetime
import statistics
import database

def suggest_reminder_time(habit_id, window_days=30):
    """
    Suggest reminder time as median hour of completion in the last window_days.
    Falls back to habit.target_time or '08:00'.
    """
    prog = database.get_progress(habit_id, days=window_days)
    hours = []
    for p in prog:
        if p.get("completed_at"):
            try:
                dt = datetime.fromisoformat(p["completed_at"])
                hours.append(dt.hour)
            except Exception:
                pass
    if hours:
        median_hour = int(statistics.median(hours))
        return f"{median_hour:02d}:00"
    # fallback to habit's target_time
    habit = database.get_habit(habit_id)
    if habit and habit.get("target_time"):
        return habit["target_time"]
    return "08:00"

def predict_dropout_risk(habit_id, window_days=14):
    """
    Simple heuristic: let expected_days = window_days (for daily habits).
    risk = 1 - (done_count / expected_days)
    Returns (risk_float, label)
    """
    habit = database.get_habit(habit_id)
    if not habit:
        return (0.0, "unknown")
    frequency = habit.get("frequency", "daily")
    prog = database.get_progress(habit_id, days=window_days)
    done_count = sum(1 for p in prog if p["status"] == "done")
    expected = window_days if frequency == "daily" else max(1, window_days // 7)
    # normalize
    ratio = done_count / expected if expected > 0 else 0
    risk = max(0.0, min(1.0, 1 - ratio))
    if risk >= 0.6:
        label = "HIGH"
    elif risk >= 0.3:
        label = "MEDIUM"
    else:
        label = "LOW"
    return (risk, label)
