# app.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date
import database



# --- Page Config ---
st.set_page_config(page_title="Habit Tracker", layout="wide")

# --- Session State ---
if "user" not in st.session_state:
    st.session_state.user = None


def login_or_create(username, email=None):
    user = database.create_or_get_user(username, email)
    st.session_state.user = user


def get_badge(progress_count: int):
    if progress_count >= 50:
        return "🏆 Platinum"
    elif progress_count >= 30:
        return "🥇 Gold"
    elif progress_count >= 15:
        return "🥈 Silver"
    elif progress_count >= 5:
        return "🥉 Bronze"
    else:
        return "🔰 Beginner"


# --- Sidebar Navigation ---
with st.sidebar:
    st.title("Duo Tracker ⚡")
    menu = st.radio("Navigate", ["🏠 Home", "✅ Habit Tracker", "💰 Finance Tracker"])
    st.header("Account")

    if st.session_state.user:
        st.write(f"Logged in as **{st.session_state.user['username']}**")
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()
    else:
        u = st.text_input("Username")
        e = st.text_input("Email (optional)")
        if st.button("Login / Create"):
            if not u.strip():
                st.warning("Enter a username")
            else:
                login_or_create(u.strip(), e.strip() or None)
                st.rerun()


# ===========================
# --- HOME PAGE ---
# ===========================
if menu == "🏠 Home":
    st.title("Duo Tracker ⚡")

    if not st.session_state.user:
        st.subheader("Welcome — create an account on the sidebar to get started.")
        st.markdown("""
       ✅ Build habits → earn XP 🔥  
       💰 Track money → save gold 💎  
       Slack off? Streak breaks & wallet cries 😭  
       Stay consistent, grow rich (in habits + coins)! ⚡
        """)
        st.stop()

    user = st.session_state.user
    st.header(f"Hello, {user['username']} 👋")
    st.success("Use the sidebar to explore Habit Tracker, Finance Tracker.")


# ===========================
# --- HABIT TRACKER ---
# ===========================
elif menu == "✅ Habit Tracker":
    if not st.session_state.user:
        st.warning("Please log in from the sidebar first.")
        st.stop()

    user = st.session_state.user
    st.header("✅ Habit Tracker")

    # Dashboard summary
    dash = database.get_user_dashboard(user["id"])
    daily_streak = database.get_daily_streak(user["id"])
    progress = database.get_user_progress_count(user["id"])
    progress_count = progress["done_count"] or 0
    badge = get_badge(progress_count)

    # --- Top summary panel ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("⭐ XP", dash["xp"])
    col2.metric("📋 Habits", dash["habit_count"])
    col3.metric("🔥 Daily Streak", int(daily_streak))
    col4.metric("🎖 Badge", badge)


    # --- Add new habit ---
    st.subheader("Add a habit")
    with st.form("add_habit_form"):
        name = st.text_input("Habit name (e.g., 'Study', 'Exercise')")
        freq = st.selectbox("Frequency", ["daily", "weekly"])
        time_pref = st.time_input("Preferred time (optional)", value=None)
        submitted = st.form_submit_button("Add habit")
        if submitted:
            tstr = time_pref.strftime("%H:%M") if time_pref else None
            if not name.strip():
                st.warning("Name is required")
            else:
                database.add_habit(user["id"], name.strip(), frequency=freq, target_time=tstr)
                st.success("Habit added. Reloading...")
                st.rerun()

    # --- List habits ---
    st.subheader("Your habits")
    habits = database.get_habits(user["id"])
    if not habits:
        st.info("No habits yet — add one above.")
    else:
        for h in habits:
            with st.container():
                cols = st.columns([3, 1, 1, 1, 1])
                cols[0].markdown(f"**{h['name']}**  \nFrequency: {h['frequency']}")
                cols[1].markdown(f"Streak: **{h['streak']}**")
                cols[2].markdown(f"Longest: **{h['longest_streak']}**")
                cols[3].markdown(f"Last done: {h['last_done_date'] or '-'}")

                if cols[4].button("✅ Done", key=f"done-{h['id']}"):
                    res = database.mark_habit_done(h["id"])
                    if res.get("ok"):
                        st.success(f"Marked done — streak now {res['streak']}, +{res['xp_gain']} XP")
                    else:
                        st.warning(res.get("msg", "Could not mark done"))
                    st.rerun()

                if cols[4].button("⏭ Skip", key=f"skip-{h['id']}"):
                    res = database.mark_habit_skipped(h["id"])
                    if res.get("ok"):
                        st.info("Marked as skipped — streak reset")
                    else:
                        st.warning(res.get("msg", "Could not mark skipped"))
                    st.rerun()

        # --- Habit details + charts ---
        st.subheader("Habit progress")
        habit_choices = {h["name"]: h["id"] for h in habits}
        selected_name = st.selectbox("Select habit to view", list(habit_choices.keys()))
        selected_id = habit_choices[selected_name]

        prog = database.get_progress(selected_id, days=30)
        # Build dataframe of last 30 days
        last_30 = pd.date_range(end=date.today(), periods=30).strftime("%Y-%m-%d").tolist()
        df = pd.DataFrame({"date": last_30})
        status_map = {p["date"]: p["status"] for p in prog}
        df["status"] = df["date"].apply(lambda d: 1 if status_map.get(d) == "done" else 0)

        st.markdown("**Last 30 days (1 = done)**")
        fig, ax = plt.subplots(figsize=(8, 2.5))
        ax.plot(df["date"], df["status"], marker="o")
        ax.set_ylim(-0.1, 1.1)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["miss", "done"])
        ax.set_xlabel("Date")
        ax.set_xticks(df["date"].iloc[::5])  # show fewer x labels
        ax.tick_params(axis='x', rotation=45)
        st.pyplot(fig)


    # --- Leaderboard ---
    st.subheader("Leaderboard")
    lb = database.get_leaderboard()
    if lb:
        st.table(lb)
    else:
        st.write("No users yet.")


    ##streak freeze

    st.markdown("## 🛒 Streak Freeze Shop")
    dashboard = dashboard = database.get_user_dashboard(user["id"])
    col1, col2 = st.columns(2)

    with col1:
        st.metric("⭐ XP", dashboard["xp"])

    with col2:
        st.metric("❄️ Streak Freezes", dashboard["streak_freeze"])

    if st.button("Buy ❄️ Streak Freeze (50 XP)"):
        if dashboard["xp"] >= 50:
            database.buy_streak_freeze(user["id"], cost=50)
            st.success("You bought a ❄️ Streak Freeze!")
            st.rerun()  # 🔥 this reloads and fetches updated values
        else:
            st.error("Not enough XP to buy a streak freeze.")

    # --- Daily Log ---
    st.markdown("### 📅 Daily Activity Log (last 7 days)")

    log = database.get_user_progress_log(user["id"], days=7)
    if not log:
        st.info("No activity recorded yet.")
    else:
        df = pd.DataFrame(log)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["completed_at"] = pd.to_datetime(df["completed_at"]).dt.strftime("%H:%M:%S")

        st.table(df.rename(columns={
            "habit_name": "Habit",
            "date": "Date",
            "status": "Status",
            "completed_at": "Time"
        }))


# ===========================
# --- FINANCE TRACKER ---
# ===========================
elif menu == "💰 Finance Tracker":
    if not st.session_state.user:
        st.warning("Please log in from the sidebar first.")
        st.stop()

    user = st.session_state.user
    st.header("💰 Finance Tracker")

    # --- Add / Update Salary & Debt ---
    st.subheader("💵 Salary & Debt Information")
    with st.form("finance_form"):
        salary = st.number_input("Monthly Salary", min_value=0.0, value=0.0, step=1000.0)
        emi = st.number_input("Monthly EMI / Loan Payment", min_value=0.0, value=0.0, step=500.0)
        debt = st.number_input("Total Debt", min_value=0.0, value=0.0, step=1000.0)
        submitted = st.form_submit_button("Save / Update")
        if submitted:
            database.save_finance(user["id"], salary, emi, debt)
            st.success("Finance info saved.")
            st.rerun()

    # --- Retrieve finance info ---
    finance = database.get_finance(user["id"])
    if finance:
        salary = float(finance["salary"])
        emi = float(finance["emi"])
        debt = float(finance["debt"])

        # --- Record Payments ---
        st.subheader("💳 Record Payment")
        payment_amt = st.number_input("Payment Amount", min_value=0.0, step=500.0)
        if st.button("Add Payment"):
            database.add_payment(user["id"], payment_amt)
            st.success(f"Payment of {payment_amt} recorded!")
            st.rerun()

        # --- Fetch total paid so far ---
        total_paid = float(database.get_total_payments(user["id"]))

        # --- Remaining debt ---
        remaining_debt = max(0, debt - total_paid)

        # --- Calculate remaining months ---
        if emi > 0:
            months_needed = -(-remaining_debt // emi)  # ceiling division
        else:
            months_needed = "N/A"

        # --- Summary Table ---
        st.subheader("📊 Summary")
        st.table({
            "Item": ["Salary", "EMI / Loan Payment", "Total Debt", "Paid So Far", "Remaining Debt", "Months to Clear Debt"],
            "Value": [salary, emi, debt, total_paid, remaining_debt, months_needed]
        })







