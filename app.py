import streamlit as st
import pandas as pd
import datetime
from io import BytesIO
from fpdf import FPDF

# ================== CONFIG ==================
st.set_page_config(
    page_title="Attendance Gamification",
    layout="wide"
)

LATE_TIME = datetime.time(8, 0)
POINTS_ON_TIME = 10
POINTS_LATE = 2
WEEKDAY_ORDER = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday"
]

LEVELS = {
    "Bronze": (0, 99),
    "Silver": (100, 299),
    "Gold": (300, float("inf"))
}

# ================== UI HEADER ==================
st.title("🎮 Multi-Week Attendance Gamification Dashboard")
st.markdown(
    """
    Upload **multiple weekly attendance Excel files**.  
    The system merges them and generates insights, leaderboards, and badges.
    """
)

# ================== FILE UPLOAD ==================
uploaded_files = st.file_uploader(
    "📤 Upload Excel files (multiple weeks)",
    type=["xlsx"],
    accept_multiple_files=True
)

# ================== DATA PROCESSING ==================
def process_file(file):
    df = pd.read_excel(file, header=1)
    df.columns = [
        "person_id", "name", "department",
        "date", "sign_in", "sign_out"
    ]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["sign_in"] = pd.to_datetime(df["sign_in"], errors="coerce")

    df["late"] = df["sign_in"].dt.time.apply(
        lambda x: False if pd.isna(x) else x > LATE_TIME
    )
    df["on_time"] = ~df["late"]
    df["day"] = df["date"].dt.day_name()
    df["week"] = file.name.replace(".xlsx", "")

    return df

def build_leaderboard(df):
    lb = (
        df.groupby("name")
        .agg(
            sign_ins=("sign_in", "count"),
            on_time=("on_time", "sum"),
            late=("late", "sum"),
        )
        .reset_index()
    )

    lb = lb[lb["sign_ins"] > 0]
    lb["points"] = lb["on_time"] * POINTS_ON_TIME + lb["late"] * POINTS_LATE
    lb = lb.sort_values("points", ascending=False)
    lb["rank"] = range(1, len(lb) + 1)
    
    lb["level"] = lb["points"].apply(assign_level)
    lb["badges"] = lb.apply(assign_badges, axis=1)
    
    return lb

def assign_level(points):
    for lvl, (low, high) in LEVELS.items():
        if low <= points <= high:
            return lvl
    return "—"

def assign_badges(row):
    badges = []

    if row["late"] == 0:
        badges.append("⭐ Perfect Attendance")

    if (row["on_time"] / row["sign_ins"]) >= 0.9:
        badges.append("👑 Punctuality Champ")

    if row["points"] >= 300:
        badges.append("🔥 Consistency King")

    # Add streak badges
    streak = calculate_streak(row["name"], filtered)
    if streak >= 5:
        badges.append(f"🧠 {streak}-Day On-Time Streak")
    
    return ", ".join(badges) if badges else "—"

def calculate_streak(name, df):
    user_data = df[df["name"] == name].sort_values("date")
    streak = max_streak = 0
    for on_time in user_data["on_time"]:
        if on_time:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak

def get_weekly_winners(df):
    winners = df.groupby("week").apply(lambda w: build_leaderboard(w).iloc[0])
    winners = winners.reset_index(drop=True)
    return winners[["week", "name", "points"]]

def download_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Leaderboard")
    return output.getvalue()

def download_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Leaderboard", ln=True, align="C")
    pdf.ln(5)
    # Add table header
    for col in df.columns:
        pdf.cell(40, 10, col, 1)
    pdf.ln()
    # Add table rows
    for _, row in df.iterrows():
        for col in df.columns:
            pdf.cell(40, 10, str(row[col]), 1)
        pdf.ln()
    output = BytesIO()
    pdf.output(output)
    return output.getvalue()


# ================== MAIN APP ==================
if uploaded_files:
    all_data = pd.concat(
        [process_file(f) for f in uploaded_files],
        ignore_index=True
    )

    # -------- DAILY OVERVIEW --------
    st.subheader("📊 Attendance by Day (All Weeks Combined)")
    daily = (
        all_data.groupby("day")
        .agg(on_time=("on_time", "sum"), late=("late", "sum"))
        .reindex(WEEKDAY_ORDER)
        .dropna(how="all")
    )
    st.bar_chart(daily)

    # -------- WEEK FILTER --------
    st.subheader("🗓️ Week Filter")
    selected_week = st.selectbox(
        "Select week",
        options=["All Weeks"] + sorted(all_data["week"].unique())
    )
    filtered = all_data if selected_week == "All Weeks" else all_data[all_data["week"] == selected_week]

    # -------- LEADERBOARD --------
    st.subheader("🏆 Leaderboard")
    leaderboard = build_leaderboard(filtered)
    st.dataframe(
        leaderboard[["rank", "name", "points", "on_time", "late", "level", "badges"]],
        use_container_width=True
    )

    # -------- WEEKLY WINNERS --------
    st.subheader("🥇 Weekly Winners")
    weekly_winners = get_weekly_winners(all_data)
    st.table(weekly_winners)

    # -------- EXPORT OPTIONS --------
    st.subheader("📤 Export Leaderboard")
    excel_data = download_excel(leaderboard)
    pdf_data = download_pdf(leaderboard)

    st.download_button(
        label="Download Excel",
        data=excel_data,
        file_name="leaderboard.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.download_button(
        label="Download PDF",
        data=pdf_data,
        file_name="leaderboard.pdf",
        mime="application/pdf"
    )

    # -------- RAW DATA --------
    with st.expander("🔍 View merged raw data"):
        st.dataframe(filtered, use_container_width=True)

else:
    st.info("👆 Upload one or more attendance Excel files to begin.")
