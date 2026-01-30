import streamlit as st
import pandas as pd
import datetime

st.set_page_config(
    page_title="Attendance Gamification",
    layout="wide"
)

st.title("🎮 Multi-Week Attendance Gamification Dashboard")

st.markdown(
    """
    Upload **multiple weekly attendance Excel files**.
    The system will merge them and generate insights, leaderboards, and badges.
    """
)

uploaded_files = st.file_uploader(
    "📤 Upload Excel files (multiple weeks)",
    type=["xlsx"],
    accept_multiple_files=True
)

LATE_TIME = datetime.time(8, 0)

def process_file(file):
    df = pd.read_excel(file, header=1)
    df.columns = ["person_id", "name", "department", "date", "sign_in", "sign_out"]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["sign_in"] = pd.to_datetime(df["sign_in"], errors="coerce")

    df["late"] = df["sign_in"].dt.time.apply(
        lambda x: False if pd.isna(x) else x > LATE_TIME
    )

    df["on_time"] = ~df["late"]
    df["day"] = df["date"].dt.day_name()
    df["week"] = file.name.replace(".xlsx", "")

    return df

if uploaded_files:
    all_data = pd.concat([process_file(f) for f in uploaded_files], ignore_index=True)

    # ---------------- DAILY OVERVIEW ----------------
    st.subheader("📊 Attendance by Day (All Weeks Combined)")

    daily = (
        all_data.groupby("day")
        .agg(
            on_time=("on_time", "sum"),
            late=("late", "sum")
        )
        .reindex(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"])
        .dropna(how="all")
    )

    st.bar_chart(daily)

    # ---------------- WEEK FILTER ----------------
    st.subheader("🗓️ Week Filter")
    selected_week = st.selectbox(
        "Select week",
        options=["All Weeks"] + sorted(all_data["week"].unique())
    )

    filtered = (
        all_data if selected_week == "All Weeks"
        else all_data[all_data["week"] == selected_week]
    )

    # ---------------- LEADERBOARD ----------------
    # ---------------- LEADERBOARD ----------------
st.subheader("🏆 Leaderboard")

leaderboard = (
    filtered.groupby("name")
    .agg(
        sign_ins=("sign_in", "count"),
        on_time=("on_time", "sum"),
        late=("late", "sum"),
    )
    .reset_index()
)

# Remove rows with zero sign-ins (prevents math errors)
leaderboard = leaderboard[leaderboard["sign_ins"] > 0]

leaderboard["points"] = leaderboard["on_time"] * 10 + leaderboard["late"] * 2
leaderboard = leaderboard.sort_values("points", ascending=False)
leaderboard["rank"] = range(1, len(leaderboard) + 1)

st.dataframe(
    leaderboard[["rank", "name", "points", "on_time", "late"]],
    use_container_width=True
)

# ---------------- BADGES ----------------
st.subheader("🏅 Badges")

def assign_badges(row):
    badges = []

    if row["late"] == 0:
        badges.append("⭐ Perfect Attendance")

    if (row["on_time"] / row["sign_ins"]) >= 0.9:
        badges.append("👑 Punctuality Champ")

    if row["points"] >= 300:
        badges.append("🔥 Consistency King")

    return ", ".join(badges) if badges else "—"

leaderboard["badges"] = leaderboard.apply(assign_badges, axis=1)

st.dataframe(
    leaderboard[["name", "badges"]],
    use_container_width=True
)



    # ---------------- RAW DATA (OPTIONAL) ----------------
    with st.expander("🔍 View merged raw data"):
        st.dataframe(filtered, use_container_width=True)



