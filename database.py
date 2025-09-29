import pymysql
import datetime
from datetime import date

# --- DB Connection ---
conn = pymysql.connect(
    host="localhost",
    user="root",
    password="1234",
    database="habit_tracker",
    autocommit=True,
    cursorclass=pymysql.cursors.DictCursor
)
cursor = conn.cursor()

def create_or_get_user(username, email=None):
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    if user:
        return user
    cursor.execute("INSERT INTO users (username, email) VALUES (%s, %s)", (username, email))
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    return cursor.fetchone()

def add_habit(user_id, name, frequency="daily", target=1, target_time=None):
    cursor.execute(
        "INSERT INTO habits (user_id, name, frequency, target, target_time) VALUES (%s,%s,%s,%s,%s)",
        (user_id, name, frequency, target, target_time)
    )

def get_habit(habit_id):
    """Fetch a single habit by its ID"""
    cursor.execute("SELECT * FROM habits WHERE id=%s", (habit_id,))
    return cursor.fetchone()

def mark_habit_done(habit_id):
    cursor.execute("SELECT * FROM habits WHERE id=%s", (habit_id,))
    habit = cursor.fetchone()
    if not habit:
        return {"ok": False, "msg": "Habit not found"}

    user_id = habit["user_id"]
    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")  # convert to string

    # Prevent duplicate progress entry for today
    cursor.execute("""
        SELECT * FROM progress
        WHERE user_id=%s AND habit_id=%s AND log_date=%s
    """, (user_id, habit_id, today_str))
    if cursor.fetchone():
        return {"ok": False, "msg": "Already marked done today"}

    # Get current streak and longest streak
    streak = habit.get("streak") or 0
    longest = habit.get("longest_streak") or 0
    last_done = habit.get("last_done_date")

    # Convert last_done to date
    if last_done:
        if isinstance(last_done, str):
            last_done = datetime.datetime.strptime(last_done, "%Y-%m-%d").date()

    # Calculate streak
    if last_done is None:
        streak = 1
    elif last_done == today - datetime.timedelta(days=1):
        streak += 1
    else:
        streak = 1

    longest = max(longest, streak)

    cursor.execute("""
        UPDATE habits
        SET streak=%s, longest_streak=%s, last_done_date=%s
        WHERE id=%s
    """, (streak, longest, today_str, habit_id))

    # Insert progress for today
    cursor.execute("""
        INSERT INTO progress (user_id, habit_id, status, completed_at, log_date)
        VALUES (%s, %s, 'done', NOW(), %s)
    """, (user_id, habit_id, today_str))

    # Add XP to user
    xp_gain = 10
    cursor.execute("UPDATE users SET xp=xp+%s WHERE id=%s", (xp_gain, user_id))

    return {"ok": True, "streak": streak, "xp_gain": xp_gain}

def mark_habit_skipped(habit_id):
    cursor.execute("SELECT user_id FROM habits WHERE id=%s", (habit_id,))
    h = cursor.fetchone()
    if not h: return {"ok": False}
    user_id = h["user_id"]
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    cursor.execute(
        "INSERT INTO progress (user_id, habit_id, status, completed_at, log_date) VALUES (%s,%s,'skipped', NOW(), %s)",
        (user_id, habit_id, today_str)
    )
    return {"ok": True}

def get_progress(habit_id, days=30):
    """
    Return recent progress for a habit.
    Dates are returned as strings for easier plotting.
    """
    cursor.execute("""
        SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d') AS date, status, completed_at
        FROM progress
        WHERE habit_id=%s
          AND log_date >= CURDATE() - INTERVAL %s DAY
        ORDER BY log_date DESC
    """, (habit_id, days))
    return cursor.fetchall()

def get_user_dashboard(user_id):
    cursor.execute("SELECT COUNT(*) AS habit_count FROM habits WHERE user_id=%s", (user_id,))
    hc = cursor.fetchone()["habit_count"]
    cursor.execute("SELECT xp FROM users WHERE id=%s", (user_id,))
    xp = cursor.fetchone()["xp"]
    return {"habit_count": hc, "xp": xp}

def get_leaderboard():
    cursor.execute("SELECT username, xp FROM users ORDER BY xp DESC LIMIT 10")
    return cursor.fetchall()

def get_streak(habit_id):
    cursor.execute("SELECT COUNT(*) AS cnt FROM progress WHERE habit_id=%s AND status='done'", (habit_id,))
    return cursor.fetchone()["cnt"]

def get_daily_streak(user_id):
    cursor.execute("""
        SELECT DISTINCT log_date
        FROM progress
        WHERE user_id = %s AND status = 'done'
        ORDER BY log_date DESC
    """, (user_id,))
    rows = cursor.fetchall()

    if not rows:
        return 0

    streak = 0
    today = datetime.date.today()

    for i, row in enumerate(rows):
        log_date = row["log_date"]
        if isinstance(log_date, datetime.datetime):
            log_date = log_date.date()

        expected_date = today - datetime.timedelta(days=i)

        if log_date == expected_date:
            streak += 1
        else:
            # 🔥 Auto-use freeze
            if use_streak_freeze(user_id):
                streak += 1
                continue
            break

    return streak



def get_user_progress_count(user_id):
    """
    Returns the number of completed and skipped progress entries for a user.
    """
    cursor.execute("""
        SELECT 
            SUM(status = 'done')   AS done_count,
            SUM(status = 'skipped') AS skipped_count,
            COUNT(*) AS total_count
        FROM progress
        WHERE user_id = %s
    """, (user_id,))
    return cursor.fetchone()

def get_user_progress_log(user_id, days=7):
    """
    Returns a detailed log of habits (done/skipped) with time for the last N days.
    """
    cursor.execute("""
        SELECT 
            h.name AS habit_name,
            p.log_date AS date,
            p.status,
            p.completed_at
        FROM progress p
        JOIN habits h ON p.habit_id = h.id
        WHERE p.user_id = %s
          AND p.log_date >= CURDATE() - INTERVAL %s DAY
        ORDER BY p.log_date DESC, p.completed_at DESC
    """, (user_id, days))
    return cursor.fetchall()

def get_user_dashboard(user_id):
    cursor.execute("""
        SELECT 
            (SELECT COUNT(*) FROM habits WHERE user_id=%s) AS habit_count,
            xp,
            streak_freeze
        FROM users 
        WHERE id=%s
    """, (user_id, user_id))
    return cursor.fetchone()

def buy_streak_freeze(user_id, cost=50):
    cursor.execute("""
        UPDATE users 
        SET xp = xp - %s, streak_freeze = streak_freeze + 1
        WHERE id=%s AND xp >= %s
    """, (cost, user_id, cost))
    conn.commit()   # 🔥 make sure changes are saved


def use_streak_freeze(user_id):
    """Consume one streak freeze if available"""
    cursor.execute("SELECT streak_freeze FROM users WHERE id=%s", (user_id,))
    sf = cursor.fetchone()["streak_freeze"]

    if sf > 0:
        cursor.execute("""
            UPDATE users
            SET streak_freeze = streak_freeze - 1
            WHERE id = %s
        """, (user_id,))
        return True
    return False

def get_habits(user_id):
    cursor.execute("""
        SELECT id, name, frequency, streak, longest_streak, last_done_date
        FROM habits
        WHERE user_id = %s
    """, (user_id,))
    return cursor.fetchall()


### FINANCE-TRACKER

def save_finance(user_id, salary, emi, debt):
    cursor.execute("SELECT id FROM finance WHERE user_id=%s", (user_id,))
    if cursor.fetchone():
        cursor.execute(
            "UPDATE finance SET salary=%s, emi=%s, debt=%s WHERE user_id=%s",
            (salary, emi, debt, user_id)
        )
    else:
        cursor.execute(
            "INSERT INTO finance (user_id, salary, emi, debt) VALUES (%s, %s, %s, %s)",
            (user_id, salary, emi, debt)
        )
    conn.commit()


def get_finance(user_id):
    cursor.execute("SELECT salary, emi, debt FROM finance WHERE user_id=%s", (user_id,))
    row = cursor.fetchone()
    if row:
        return row
    return None

def add_payment(user_id, amount):
    cursor.execute(
        "INSERT INTO finance_payments (user_id, amount, payment_date) VALUES (%s, %s, %s)",
        (user_id, amount, date.today().isoformat())
    )
    conn.commit()

def get_total_payments(user_id):
    # Use a dict cursor for safety
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT SUM(amount) AS total FROM finance_payments WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    if result is None or result["total"] is None:
        return 0.0
    return float(result["total"])





