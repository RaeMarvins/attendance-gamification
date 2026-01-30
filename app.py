import streamlit as st
import pandas as pd
import numpy as np
import datetime
from io import BytesIO
from datetime import time

# ================== CONFIG ==================
st.set_page_config(
    page_title="Staff Attendance Dashboard",
    layout="wide"
)

# Configuration
LATE_TIME = time(8, 0)  # 8:00 AM

# ================== HEADER ==================
st.title("Staff Attendance Dashboard")
st.markdown("Upload attendance Excel file to view comprehensive staff statistics and weekly reports.")

# ================== FILE UPLOAD ==================
uploaded_file = st.file_uploader(
    "📤 Upload Attendance Excel File",
    type=["xlsx", "xls"],
    help="Upload an Excel file with columns: Person ID, Name, Department, Date, SIGN-IN, SIGN-OUT"
)

# ================== FUNCTIONS ==================
def process_excel_file(file):
    """Process the uploaded Excel file with the specific format"""
    try:
        # Read Excel file, skip the first row (title row)
        df = pd.read_excel(file, header=1)
        
        # Clean column names
        df.columns = ["person_id", "name", "department", "date", "sign_in", "sign_out"]
        
        # Convert date column to datetime
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
        # Convert time columns to datetime.time
        def convert_time(x):
            if pd.isna(x):
                return None
            try:
                # Handle Excel time format
                if isinstance(x, (datetime.time, datetime.datetime)):
                    return x.time() if isinstance(x, datetime.datetime) else x
                # Handle string time
                if isinstance(x, str) and x.strip() != '-':
                    return datetime.datetime.strptime(x.strip(), "%H:%M").time()
                return None
            except:
                return None
        
        df["sign_in_time"] = df["sign_in"].apply(convert_time)
        df["sign_out_time"] = df["sign_out"].apply(convert_time)
        
        # Filter out rows where sign_in_time is null
        df = df[df["sign_in_time"].notna()].copy()
        
        if df.empty:
            return df
        
        # Add day of week
        df["day"] = df["date"].dt.day_name()
        
        # Add week number
        df["week"] = df["date"].dt.isocalendar().week
        
        # Mark late arrivals (after 8:00 AM)
        df["late"] = df["sign_in_time"].apply(lambda x: x > LATE_TIME if x else False)
        df["on_time"] = ~df["late"]
        
        return df
    
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return pd.DataFrame()

def calculate_kpis(df):
    """Calculate KPI metrics from the data"""
    if df.empty:
        return {
            "total_staff": 0,
            "present_today": 0,
            "absent_today": 0,
            "avg_signins": 0.0,
            "today": datetime.date.today(),
            "total_on_time": 0,
            "total_late": 0,
            "on_time_rate": 0.0,
            "avg_daily_attendance": 0.0
        }
    
    # Get unique staff count
    total_staff = df["name"].nunique()
    
    # Get today's date
    today = datetime.date.today()
    
    # Filter for today's data
    today_data = df[df["date"].dt.date == today]
    
    # Count present today (those who signed in)
    present_today = today_data["name"].nunique() if not today_data.empty else 0
    
    # Calculate absent today
    absent_today = max(0, total_staff - present_today)
    
    # Calculate average sign-ins this week
    current_week = today.isocalendar()[1]
    this_week_data = df[df["week"] == current_week]
    if not this_week_data.empty:
        signins_by_staff = this_week_data.groupby("name")["sign_in_time"].count()
        avg_signins = round(signins_by_staff.mean(), 1)
    else:
        avg_signins = 0.0
    
    # Calculate punctuality stats
    total_on_time = df[df["on_time"]]["name"].count()
    total_late = df[df["late"]]["name"].count()
    total_signins = total_on_time + total_late
    on_time_rate = round((total_on_time / total_signins * 100), 1) if total_signins > 0 else 0.0
    
    # Calculate average daily attendance rate
    unique_dates = df["date"].dt.date.nunique()
    if unique_dates > 0:
        daily_attendance = df.groupby("date")["name"].nunique().mean()
        avg_daily_attendance = round(daily_attendance / total_staff * 100, 1)
    else:
        avg_daily_attendance = 0.0
    
    return {
        "total_staff": total_staff,
        "present_today": present_today,
        "absent_today": absent_today,
        "avg_signins": avg_signins,
        "today": today,
        "total_on_time": total_on_time,
        "total_late": total_late,
        "on_time_rate": on_time_rate,
        "avg_daily_attendance": avg_daily_attendance
    }

def create_attendance_leaderboard(df):
    """Create a leaderboard of staff ranked by attendance and punctuality"""
    if df.empty:
        return pd.DataFrame()
    
    # Calculate total days, on-time days, and late days for each staff member
    attendance_stats = df.groupby(["name", "department"]).agg({
        "sign_in_time": "count",
        "on_time": "sum",
        "late": "sum"
    }).reset_index()
    
    attendance_stats.columns = ["name", "department", "total_days", "on_time_days", "late_days"]
    
    # Calculate average sign-in time for each staff member
    def time_to_minutes(t):
        if pd.isna(t):
            return np.nan
        return t.hour * 60 + t.minute
    
    df["sign_in_minutes"] = df["sign_in_time"].apply(time_to_minutes)
    
    avg_times = df.groupby("name")["sign_in_minutes"].mean().reset_index()
    avg_times.columns = ["name", "avg_minutes"]
    
    # Merge average times with attendance stats
    leaderboard = pd.merge(attendance_stats, avg_times, on="name", how="left")
    
    # Convert average minutes back to time string
    leaderboard["avg_signin_time"] = leaderboard["avg_minutes"].apply(
        lambda x: f"{int(x//60):02d}:{int(x%60):02d}" if not np.isnan(x) else "N/A"
    )
    
    # Calculate on-time percentage
    leaderboard["on_time_percentage"] = round(
        (leaderboard["on_time_days"] / leaderboard["total_days"]) * 100, 1
    )
    
    # Sort by total days descending, then by average sign-in time ascending (earlier is better)
    leaderboard = leaderboard.sort_values(
        by=["total_days", "avg_minutes"], 
        ascending=[False, True]
    ).reset_index(drop=True)
    
    # Add rank
    leaderboard.insert(0, "rank", range(1, len(leaderboard) + 1))
    
    # Select and order columns
    display_cols = [
        "rank", "name", "department", "total_days", 
        "avg_signin_time", "on_time_percentage", 
        "on_time_days", "late_days"
    ]
    
    return leaderboard[display_cols]

def create_weekly_report(df, week_num=None):
    """Create a clean weekly report with days as columns"""
    if df.empty:
        return pd.DataFrame()
    
    if week_num is None:
        week_num = datetime.date.today().isocalendar()[1]
    
    # Filter for the specific week
    weekly_data = df[df["week"] == week_num].copy()
    
    if weekly_data.empty:
        return pd.DataFrame()
    
    # Convert sign-in time to display format
    weekly_data["sign_in_display"] = weekly_data["sign_in_time"].apply(
        lambda x: x.strftime("%I:%M %p") if pd.notna(x) else "Absent"
    )
    
    # Create pivot table with days as columns
    pivot_df = weekly_data.pivot_table(
        index="name",
        columns="day",
        values="sign_in_display",
        aggfunc=lambda x: x.iloc[0] if len(x) > 0 else "Absent",
        fill_value="Absent"
    )
    
    # Calculate weekly statistics
    weekly_stats = weekly_data.groupby("name").agg({
        "sign_in_time": "count",
        "on_time": "sum",
        "late": "sum"
    }).reset_index()
    weekly_stats.columns = ["name", "total_days", "on_time_days", "late_days"]
    
    # Calculate average sign-in time for the week
    def avg_time_func(times):
        valid_times = [t for t in times if pd.notna(t)]
        if not valid_times:
            return None
        
        # Convert to minutes
        minutes = [t.hour * 60 + t.minute for t in valid_times]
        avg_minutes = sum(minutes) / len(minutes)
        return f"{int(avg_minutes//60):02d}:{int(avg_minutes%60):02d}"
    
    avg_times = weekly_data.groupby("name")["sign_in_time"].apply(avg_time_func).reset_index()
    avg_times.columns = ["name", "avg_time"]
    
    # Merge all data
    report_df = pd.merge(pivot_df, weekly_stats, on="name", how="left")
    report_df = pd.merge(report_df, avg_times, on="name", how="left")
    
    # Reorder columns for better presentation
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    existing_days = [day for day in day_order if day in report_df.columns]
    
    # Create final column order
    final_cols = ["name"] + existing_days + ["avg_time", "total_days", "on_time_days", "late_days"]
    report_df = report_df[final_cols]
    
    # Add emoji indicators for days
    for day in existing_days:
        if day in report_df.columns:
            report_df[f"{day}_icon"] = report_df.apply(
                lambda row: "✅" if row[day] != "Absent" else "❌", axis=1
            )
    
    # Sort by total days descending
    report_df = report_df.sort_values("total_days", ascending=False).reset_index(drop=True)
    
    return report_df

# ================== MAIN ==================
if uploaded_file is not None:
    # Process the uploaded file
    df = process_excel_file(uploaded_file)
    
    if not df.empty:
        # Calculate KPIs
        kpis = calculate_kpis(df)
        
        # ================== KPI METRICS ==================
        st.markdown("### 📊 Attendance Overview")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                label="Total Staff",
                value=kpis["total_staff"],
                help="Number of unique staff members in the data"
            )
        
        with col2:
            st.metric(
                label="Daily Attendance",
                value=f"{kpis['avg_daily_attendance']}%",
                help="Average percentage of staff attending daily"
            )
        
        with col3:
            st.metric(
                label="On-Time Rate",
                value=f"{kpis['on_time_rate']}%",
                delta=f"{kpis['total_on_time']} on-time sign-ins",
                help="Percentage of sign-ins before 8:00 AM"
            )
        
        with col4:
            st.metric(
                label="Avg Sign-Ins/Staff",
                value=kpis["avg_signins"],
                help="Average number of sign-ins per staff member"
            )
        
        with col5:
            st.metric(
                label="Total Sign-Ins",
                value=kpis["total_on_time"] + kpis["total_late"],
                delta=f"{kpis['total_late']} late",
                help="Total number of sign-ins recorded"
            )
        
        st.markdown("---")
        
        # ================== ATTENDANCE LEADERBOARD ==================
        st.markdown("### 🏆 Attendance & Punctuality Leaderboard")
        st.markdown("Staff ranked by **total days attended** (primary) and **average sign-in time** (secondary)")
        
        leaderboard = create_attendance_leaderboard(df)
        
        if not leaderboard.empty:
            # Display leaderboard with progress bars for on-time percentage
            st.dataframe(
                leaderboard,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "rank": st.column_config.NumberColumn("Rank", width="small"),
                    "name": st.column_config.TextColumn("Employee Name", width="medium"),
                    "department": st.column_config.TextColumn("Department", width="medium"),
                    "total_days": st.column_config.NumberColumn(
                        "Total Days",
                        width="small",
                        help="Total number of days signed in"
                    ),
                    "avg_signin_time": st.column_config.TextColumn(
                        "Avg Sign-In Time", 
                        width="small",
                        help="Average time of sign-in across all days"
                    ),
                    "on_time_percentage": st.column_config.ProgressColumn(
                        "On-Time %", 
                        format="%.1f%%",
                        min_value=0,
                        max_value=100,
                        width="medium",
                        help="Percentage of days signed in before 8:00 AM"
                    ),
                    "on_time_days": st.column_config.NumberColumn(
                        "On-Time Days", 
                        width="small",
                        help="Number of days signed in before 8:00 AM"
                    ),
                    "late_days": st.column_config.NumberColumn(
                        "Late Days", 
                        width="small",
                        help="Number of days signed in after 8:00 AM"
                    )
                }
            )
            
            # Add leaderboard statistics
            st.markdown("#### 📈 Leaderboard Statistics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                top_performer = leaderboard.iloc[0]
                st.metric(
                    "Top Performer", 
                    top_performer["name"].split()[0],
                    delta=f"{top_performer['total_days']} days",
                    help=f"{top_performer['name']} leads with {top_performer['total_days']} days attended"
                )
            
            with col2:
                avg_days = round(leaderboard["total_days"].mean(), 1)
                st.metric(
                    "Avg Days/Staff", 
                    avg_days,
                    help="Average number of days attended per staff member"
                )
            
            with col3:
                perfect_attendance = len(leaderboard[leaderboard["late_days"] == 0])
                st.metric(
                    "Perfect Attendance", 
                    perfect_attendance,
                    help="Number of staff with zero late days"
                )
            
            with col4:
                best_punctuality = leaderboard["on_time_percentage"].max()
                st.metric(
                    "Best On-Time Rate", 
                    f"{best_punctuality}%",
                    help="Highest on-time percentage achieved"
                )
        
        st.markdown("---")
        
        # ================== WEEKLY REPORT ==================
        st.markdown("### 📅 Weekly Attendance Report")
        
        # Week selector
        weeks = sorted(df["week"].unique())
        current_week = datetime.date.today().isocalendar()[1]
        
        if weeks:
            col1, col2 = st.columns([1, 3])
            with col1:
                selected_week = st.selectbox(
                    "Select Week:",
                    options=weeks,
                    index=weeks.index(current_week) if current_week in weeks else 0,
                    format_func=lambda x: f"Week {x}"
                )
            
            # Generate weekly report
            weekly_report = create_weekly_report(df, selected_week)
            
            if not weekly_report.empty:
                # Get just the display columns (without the icon columns)
                display_cols = [col for col in weekly_report.columns if not col.endswith('_icon')]
                display_df = weekly_report[display_cols].copy()
                
                # Rename columns for better display
                rename_dict = {
                    "name": "Employee Name",
                    "avg_time": "Avg Time",
                    "total_days": "Days",
                    "on_time_days": "On-Time",
                    "late_days": "Late"
                }
                display_df = display_df.rename(columns=rename_dict)
                
                # Display the table
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Show summary
                total_employees = len(weekly_report)
                total_days_present = weekly_report["total_days"].sum()
                avg_days_per_employee = round(weekly_report["total_days"].mean(), 1)
                
                st.caption(f"""
                **Summary for Week {selected_week}:** 
                {total_employees} employees | {total_days_present} total sign-ins | 
                {avg_days_per_employee} average days per employee
                """)
            else:
                st.warning(f"No attendance data available for Week {selected_week}")
        else:
            st.info("No weekly data available in the uploaded file.")
        
        # ================== ADDITIONAL INSIGHTS ==================
        with st.expander("📈 View Detailed Insights"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📊 Top 10 Most Consistent Attendees")
                top_10 = leaderboard.head(10)[["rank", "name", "total_days", "on_time_percentage"]]
                st.dataframe(
                    top_10,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "rank": "Rank",
                        "name": "Name",
                        "total_days": "Days Attended",
                        "on_time_percentage": st.column_config.ProgressColumn(
                            "On-Time %",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100
                        )
                    }
                )
            
            with col2:
                st.markdown("#### 📅 Attendance Distribution")
                # Create attendance distribution bins
                if not leaderboard.empty:
                    bins = [0, 2, 4, 6, 8, 10, float('inf')]
                    labels = ["0-2 days", "3-4 days", "5-6 days", "7-8 days", "9-10 days", "10+ days"]
                    
                    leaderboard["attendance_range"] = pd.cut(
                        leaderboard["total_days"], 
                        bins=bins, 
                        labels=labels, 
                        right=False
                    )
                    
                    distribution = leaderboard["attendance_range"].value_counts().sort_index().reset_index()
                    distribution.columns = ["Days Attended", "Number of Staff"]
                    
                    st.dataframe(
                        distribution,
                        use_container_width=True,
                        hide_index=True
                    )
    
    else:
        st.warning("The uploaded file doesn't contain valid attendance data. Please check the file format.")
        
else:
    # ================== PLACEHOLDER UI ==================
    st.info("👆 Upload an attendance Excel file to view the dashboard")
    
    # Example of the dashboard layout
    with st.expander("📋 What to expect after upload"):
        st.markdown("""
        After uploading your Excel file, you'll see:
        
        1. **📊 Attendance Overview**: Key metrics at a glance
        2. **🏆 Attendance Leaderboard**: Staff ranked by total days attended (most to least)
        3. **📅 Weekly Attendance Report**: Clean table with days as columns
        4. **📈 Detailed Insights**: Top performers and attendance distribution
        
        **Expected Excel Format:**
        - File should have columns: Person ID, Name, Department, Date, SIGN-IN, SIGN-OUT
        - Date format: MM/DD/YYYY
        - Time format: HH:MM (24-hour)
        - Can have sign-in and sign-out on separate rows
        """)
    
    # Placeholder metrics
    st.markdown("### 📊 Attendance Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    for col, value, label in zip([col1, col2, col3, col4, col5], 
                                  ["0", "0%", "0%", "0.0", "0"], 
                                  ["Total Staff", "Daily Attendance", "On-Time Rate", "Avg Sign-Ins/Staff", "Total Sign-Ins"]):
        with col:
            st.metric(label=label, value=value)

# ================== FOOTER ==================
st.markdown("---")
st.caption("Staff Attendance Dashboard | Upload Excel files with attendance data for analysis")
