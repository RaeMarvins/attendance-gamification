import streamlit as st
import pandas as pd
import numpy as np
import datetime
from io import BytesIO
from datetime import time
import base64

# ================== CONFIG ==================
st.set_page_config(
    page_title="Staff Attendance Dashboard",
    layout="wide"
)

# Configuration
LATE_TIME = time(8, 0)  # 8:00 AM

# ================== HEADER ==================
st.title("Staff Attendance Dashboard")
st.markdown("Upload multiple attendance Excel files to view comprehensive staff statistics across all periods.")

# ================== FILE UPLOAD ==================
uploaded_files = st.file_uploader(
    "📤 Upload Attendance Excel Files",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    help="Upload one or more Excel files with columns: Person ID, Name, Department, Date, SIGN-IN, SIGN-OUT"
)

# ================== FUNCTIONS ==================
def process_excel_file(file, file_name=""):
    """Process a single uploaded Excel file with the specific format"""
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
        
        # Add week number and week identifier
        df["week_num"] = df["date"].dt.isocalendar().week
        df["week_year"] = df["date"].dt.isocalendar().year
        df["week_identifier"] = df["week_year"].astype(str) + "-W" + df["week_num"].astype(str)
        
        # Add month and year for time period tracking
        df["month"] = df["date"].dt.month
        df["year"] = df["date"].dt.year
        df["month_year"] = df["date"].dt.strftime("%b %Y")
        
        # Mark late arrivals (after 8:00 AM)
        df["late"] = df["sign_in_time"].apply(lambda x: x > LATE_TIME if x else False)
        df["on_time"] = ~df["late"]
        
        # Add source file name for tracking
        df["source_file"] = file_name
        
        return df
    
    except Exception as e:
        st.error(f"Error processing file {file_name}: {str(e)}")
        return pd.DataFrame()

def combine_all_files(uploaded_files):
    """Combine data from all uploaded files"""
    all_data = []
    file_names = []
    
    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        file_names.append(file_name)
        df = process_excel_file(uploaded_file, file_name)
        if not df.empty:
            all_data.append(df)
    
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        return combined_df, file_names
    else:
        return pd.DataFrame(), file_names

def calculate_kpis(df):
    """Calculate KPI metrics from the combined data"""
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
            "avg_daily_attendance": 0.0,
            "total_signins": 0,
            "total_days_covered": 0,
            "date_range": "N/A"
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
    
    # Calculate average sign-ins per staff
    signins_by_staff = df.groupby("name")["sign_in_time"].count()
    avg_signins = round(signins_by_staff.mean(), 1)
    
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
    
    # Calculate date range
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    date_range = f"{min_date.strftime('%b %d, %Y')} to {max_date.strftime('%b %d, %Y')}"
    total_days_covered = (max_date - min_date).days + 1
    
    return {
        "total_staff": total_staff,
        "present_today": present_today,
        "absent_today": absent_today,
        "avg_signins": avg_signins,
        "today": today,
        "total_on_time": total_on_time,
        "total_late": total_late,
        "on_time_rate": on_time_rate,
        "avg_daily_attendance": avg_daily_attendance,
        "total_signins": total_signins,
        "total_days_covered": total_days_covered,
        "date_range": date_range
    }

def create_attendance_leaderboard(df):
    """Create a leaderboard of staff ranked by attendance and punctuality from combined data"""
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

def create_time_period_report(df, period_type="week"):
    """Create a report grouped by time period (week or month)"""
    if df.empty:
        return pd.DataFrame()
    
    if period_type == "week":
        # Group by week
        period_col = "week_identifier"
        period_name = "Week"
    else:
        # Group by month
        period_col = "month_year"
        period_name = "Month"
    
    # Calculate statistics by time period
    period_stats = df.groupby(period_col).agg({
        "name": "nunique",
        "sign_in_time": "count",
        "on_time": "sum",
        "late": "sum"
    }).reset_index()
    
    period_stats.columns = [period_name, "Unique Staff", "Total Sign-Ins", "On-Time", "Late"]
    
    # Calculate percentages
    period_stats["On-Time %"] = round((period_stats["On-Time"] / period_stats["Total Sign-Ins"]) * 100, 1)
    period_stats["Attendance Rate %"] = round((period_stats["Unique Staff"] / df["name"].nunique()) * 100, 1)
    
    # Sort by period
    if period_type == "week":
        # Sort weeks chronologically
        period_stats[period_name] = pd.Categorical(
            period_stats[period_name], 
            categories=sorted(period_stats[period_name].unique(), key=lambda x: (int(x.split('-')[0]), int(x.split('-W')[1]))),
            ordered=True
        )
    else:
        # Sort months chronologically
        period_stats["sort_date"] = pd.to_datetime(period_stats[period_name], format="%b %Y")
        period_stats = period_stats.sort_values("sort_date")
        period_stats = period_stats.drop("sort_date", axis=1)
    
    period_stats = period_stats.sort_values(period_name).reset_index(drop=True)
    
    return period_stats

def create_detailed_insights(df, leaderboard):
    """Create detailed insights data"""
    if df.empty:
        return pd.DataFrame()
    
    # Top 10 most consistent attendees
    top_10 = leaderboard.head(10)[["rank", "name", "total_days", "on_time_percentage"]].copy()
    top_10.columns = ["Rank", "Name", "Days Attended", "On-Time %"]
    
    # Attendance distribution
    max_days = leaderboard["total_days"].max()
    if max_days <= 10:
        bins = [0, 2, 4, 6, 8, 10, float('inf')]
        labels = ["0-2 days", "3-4 days", "5-6 days", "7-8 days", "9-10 days", "10+ days"]
    else:
        bin_step = max(1, max_days // 5)
        bins = list(range(0, max_days + bin_step, bin_step))
        if max_days not in bins:
            bins.append(max_days + 1)
        labels = [f"{bins[i]}-{bins[i+1]-1} days" for i in range(len(bins)-1)]
    
    leaderboard_copy = leaderboard.copy()
    leaderboard_copy["attendance_range"] = pd.cut(
        leaderboard_copy["total_days"], 
        bins=bins, 
        labels=labels, 
        right=False
    )
    
    distribution = leaderboard_copy["attendance_range"].value_counts().sort_index().reset_index()
    distribution.columns = ["Days Attended Range", "Number of Staff"]
    
    # Department summary
    dept_summary = df.groupby("department").agg({
        "name": "nunique",
        "sign_in_time": "count",
        "on_time": "sum",
        "late": "sum"
    }).reset_index()
    
    dept_summary.columns = ["Department", "Staff Count", "Total Sign-Ins", "On-Time", "Late"]
    dept_summary["On-Time %"] = round((dept_summary["On-Time"] / dept_summary["Total Sign-Ins"]) * 100, 1)
    
    return {
        "top_10_attendees": top_10,
        "attendance_distribution": distribution,
        "department_summary": dept_summary
    }

def generate_export_package(df, leaderboard, weekly_report, monthly_report, kpis, file_names, insights):
    """Generate a comprehensive Excel export with multiple sheets"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Write KPIs summary sheet
        kpis_df = pd.DataFrame.from_dict(kpis, orient='index').reset_index()
        kpis_df.columns = ["Metric", "Value"]
        kpis_df.to_excel(writer, sheet_name="KPIs Summary", index=False)
        
        # Write leaderboard
        leaderboard.to_excel(writer, sheet_name="Attendance Leaderboard", index=False)
        
        # Write raw data
        df[["date", "name", "department", "sign_in_time", "day", "source_file"]].to_excel(
            writer, sheet_name="Raw Attendance Data", index=False
        )
        
        # Write weekly report
        weekly_report.to_excel(writer, sheet_name="Weekly Analysis", index=False)
        
        # Write monthly report
        monthly_report.to_excel(writer, sheet_name="Monthly Analysis", index=False)
        
        # Write insights
        insights["top_10_attendees"].to_excel(writer, sheet_name="Top 10 Attendees", index=False)
        insights["attendance_distribution"].to_excel(writer, sheet_name="Attendance Distribution", index=False)
        insights["department_summary"].to_excel(writer, sheet_name="Department Summary", index=False)
        
        # Write file list
        files_df = pd.DataFrame(file_names, columns=["Uploaded Files"])
        files_df.to_excel(writer, sheet_name="Files Processed", index=False)
        
        # Get workbook and worksheets for formatting
        workbook = writer.book
        
        # Format KPIs sheet
        kpis_sheet = writer.sheets["KPIs Summary"]
        kpis_format = workbook.add_format({'bold': True})
        kpis_sheet.set_column('A:A', 30)
        kpis_sheet.set_column('B:B', 20)
        
        # Format leaderboard
        leaderboard_sheet = writer.sheets["Attendance Leaderboard"]
        leaderboard_sheet.set_column('A:A', 8)   # Rank
        leaderboard_sheet.set_column('B:B', 25)  # Name
        leaderboard_sheet.set_column('C:C', 20)  # Department
        leaderboard_sheet.set_column('D:D', 10)  # Total Days
        leaderboard_sheet.set_column('E:E', 15)  # Avg Sign-In Time
        leaderboard_sheet.set_column('F:F', 12)  # On-Time %
        leaderboard_sheet.set_column('G:G', 12)  # On-Time Days
        leaderboard_sheet.set_column('H:H', 10)  # Late Days
        
        # Format raw data sheet
        raw_sheet = writer.sheets["Raw Attendance Data"]
        raw_sheet.set_column('A:A', 12)  # Date
        raw_sheet.set_column('B:B', 25)  # Name
        raw_sheet.set_column('C:C', 20)  # Department
        raw_sheet.set_column('D:D', 15)  # Sign-In Time
        raw_sheet.set_column('E:E', 15)  # Day
        raw_sheet.set_column('F:F', 30)  # Source File
    
    return output.getvalue()

def generate_dashboard_summary(df, leaderboard, kpis, file_names):
    """Generate a text summary of the dashboard"""
    summary = f"""
    STAFF ATTENDANCE DASHBOARD REPORT
    =================================
    
    Report Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    Data Period: {kpis['date_range']} ({kpis['total_days_covered']} days)
    Files Processed: {len(file_names)}
    
    KEY PERFORMANCE INDICATORS
    --------------------------
    • Total Staff: {kpis['total_staff']}
    • Daily Attendance Rate: {kpis['avg_daily_attendance']}%
    • On-Time Rate: {kpis['on_time_rate']}%
    • Average Sign-Ins per Staff: {kpis['avg_signins']}
    • Total Sign-Ins: {kpis['total_signins']:,}
    
    TOP 5 PERFORMERS
    -----------------
    """
    
    for i in range(min(5, len(leaderboard))):
        staff = leaderboard.iloc[i]
        summary += f"{i+1}. {staff['name']} - {staff['total_days']} days ({staff['on_time_percentage']}% on-time)\n"
    
    summary += f"""
    
    ATTENDANCE DISTRIBUTION
    ------------------------
    • Perfect Attendance (No Late Days): {len(leaderboard[leaderboard['late_days'] == 0])} staff
    • Average Days per Staff: {round(leaderboard['total_days'].mean(), 1)} days
    • Median Days per Staff: {leaderboard['total_days'].median()} days
    
    PUNCTUALITY OVERVIEW
    --------------------
    • Average Sign-In Time: {leaderboard['avg_signin_time'].iloc[0]} (earliest)
    • Best On-Time Rate: {leaderboard['on_time_percentage'].max()}%
    • Average On-Time Rate: {round(leaderboard['on_time_percentage'].mean(), 1)}%
    
    DATA QUALITY
    ------------
    • Total Records: {len(df):,}
    • Unique Dates: {df['date'].dt.date.nunique()}
    • Files Processed: {len(file_names)}
    """
    
    return summary

# ================== MAIN ==================
if uploaded_files:
    # Process all uploaded files
    with st.spinner("Processing uploaded files..."):
        df, file_names = combine_all_files(uploaded_files)
    
    if not df.empty:
        # File upload summary
        st.success(f"✅ Successfully processed {len(file_names)} file(s)")
        
        with st.expander("📁 View Uploaded Files"):
            for i, file_name in enumerate(file_names, 1):
                st.write(f"{i}. {file_name}")
        
        # Calculate KPIs from combined data
        kpis = calculate_kpis(df)
        
        # Generate reports
        leaderboard = create_attendance_leaderboard(df)
        weekly_report = create_time_period_report(df, period_type="week")
        monthly_report = create_time_period_report(df, period_type="month")
        insights = create_detailed_insights(df, leaderboard)
        
        # ================== KPI METRICS ==================
        st.markdown("### 📊 Combined Attendance Overview")
        st.caption(f"Data Range: {kpis['date_range']} ({kpis['total_days_covered']} days)")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                label="Total Staff",
                value=kpis["total_staff"],
                help="Number of unique staff members across all files"
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
                delta=f"{kpis['total_on_time']:,} on-time",
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
                value=f"{kpis['total_signins']:,}",
                delta=f"{kpis['total_late']:,} late",
                help="Total number of sign-ins across all periods"
            )
        
        st.markdown("---")
        
        # ================== ATTENDANCE LEADERBOARD ==================
        st.markdown("### 🏆 Combined Attendance & Punctuality Leaderboard")
        st.markdown(f"**Based on {kpis['total_days_covered']} days of data across all uploaded files**")
        
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
                        help="Total number of days signed in across all files"
                    ),
                    "avg_signin_time": st.column_config.TextColumn(
                        "Avg Sign-In Time", 
                        width="small",
                        help="Average time of sign-in across all days and files"
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
            st.markdown("#### 📈 Combined Leaderboard Statistics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                top_performer = leaderboard.iloc[0]
                st.metric(
                    "Top Performer", 
                    top_performer["name"].split()[0],
                    delta=f"{top_performer['total_days']} days",
                    help=f"{top_performer['name']} leads with {top_performer['total_days']} total days attended"
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
        
        # ================== TIME PERIOD ANALYSIS ==================
        st.markdown("### 📅 Time Period Analysis")
        
        tab1, tab2 = st.tabs(["Weekly Analysis", "Monthly Analysis"])
        
        with tab1:
            st.markdown("#### 📊 Weekly Attendance Trends")
            if not weekly_report.empty:
                st.dataframe(
                    weekly_report,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Week": st.column_config.TextColumn("Week", width="small"),
                        "Unique Staff": st.column_config.NumberColumn("Staff Count", width="small"),
                        "Total Sign-Ins": st.column_config.NumberColumn("Total Sign-Ins", width="small"),
                        "On-Time": st.column_config.NumberColumn("On-Time", width="small"),
                        "Late": st.column_config.NumberColumn("Late", width="small"),
                        "On-Time %": st.column_config.ProgressColumn(
                            "On-Time %",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100,
                            width="medium"
                        ),
                        "Attendance Rate %": st.column_config.ProgressColumn(
                            "Attendance %",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100,
                            width="medium"
                        )
                    }
                )
        
        with tab2:
            st.markdown("#### 📊 Monthly Attendance Trends")
            if not monthly_report.empty:
                st.dataframe(
                    monthly_report,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Month": st.column_config.TextColumn("Month", width="small"),
                        "Unique Staff": st.column_config.NumberColumn("Staff Count", width="small"),
                        "Total Sign-Ins": st.column_config.NumberColumn("Total Sign-Ins", width="small"),
                        "On-Time": st.column_config.NumberColumn("On-Time", width="small"),
                        "Late": st.column_config.NumberColumn("Late", width="small"),
                        "On-Time %": st.column_config.ProgressColumn(
                            "On-Time %",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100,
                            width="medium"
                        ),
                        "Attendance Rate %": st.column_config.ProgressColumn(
                            "Attendance %",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100,
                            width="medium"
                        )
                    }
                )
        
        # ================== ADDITIONAL INSIGHTS ==================
        with st.expander("📈 View Detailed Insights"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🏆 Top 10 Most Consistent Attendees")
                st.dataframe(
                    insights["top_10_attendees"],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Rank": "Rank",
                        "Name": "Name",
                        "Days Attended": "Days Attended",
                        "On-Time %": st.column_config.ProgressColumn(
                            "On-Time %",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100
                        )
                    }
                )
            
            with col2:
                st.markdown("#### 📅 Attendance Distribution")
                st.dataframe(
                    insights["attendance_distribution"],
                    use_container_width=True,
                    hide_index=True
                )
        
        # ================== EXPORT SECTION ==================
        st.markdown("---")
        st.markdown("## 📤 Export Dashboard Report")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Generate comprehensive Excel report
            excel_data = generate_export_package(df, leaderboard, weekly_report, monthly_report, kpis, file_names, insights)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            st.download_button(
                label="📊 Download Full Excel Report",
                data=excel_data,
                file_name=f"attendance_dashboard_report_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Download complete dashboard data in Excel format with multiple sheets"
            )
        
        with col2:
            # Download leaderboard only
            leaderboard_csv = leaderboard.to_csv(index=False)
            st.download_button(
                label="📋 Download Leaderboard (CSV)",
                data=leaderboard_csv,
                file_name=f"attendance_leaderboard_{timestamp}.csv",
                mime="text/csv",
                help="Download only the attendance leaderboard in CSV format"
            )
        
        with col3:
            # Download summary report
            summary_text = generate_dashboard_summary(df, leaderboard, kpis, file_names)
            st.download_button(
                label="📄 Download Summary Report (TXT)",
                data=summary_text,
                file_name=f"attendance_summary_{timestamp}.txt",
                mime="text/plain",
                help="Download a text summary of the dashboard findings"
            )
        
        # ================== DATA PREVIEW ==================
        with st.expander("🔍 Preview Export Data"):
            tab1, tab2, tab3 = st.tabs(["Raw Data Sample", "Leaderboard", "KPIs"])
            
            with tab1:
                st.dataframe(
                    df[["date", "name", "department", "sign_in_time"]].head(10),
                    use_container_width=True,
                    hide_index=True
                )
            
            with tab2:
                st.dataframe(
                    leaderboard.head(10),
                    use_container_width=True,
                    hide_index=True
                )
            
            with tab3:
                kpis_df = pd.DataFrame.from_dict(kpis, orient='index').reset_index()
                kpis_df.columns = ["Metric", "Value"]
                st.dataframe(
                    kpis_df,
                    use_container_width=True,
                    hide_index=True
                )
        
        # ================== DATA SUMMARY ==================
        st.markdown("---")
        st.markdown("### 📋 Data Summary")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Files Processed",
                len(file_names),
                help="Number of Excel files successfully processed"
            )
        
        with col2:
            st.metric(
                "Data Period",
                f"{kpis['total_days_covered']} days",
                help="Total days covered in the data"
            )
        
        with col3:
            st.metric(
                "Total Records",
                f"{len(df):,}",
                help="Total number of attendance records processed"
            )
    
    else:
        st.warning("The uploaded files don't contain valid attendance data. Please check the file formats.")
        
else:
    # ================== PLACEHOLDER UI ==================
    st.info("👆 Upload one or more attendance Excel files to view the dashboard")
    
    # Example of the dashboard layout
    with st.expander("📋 What to expect after upload"):
        st.markdown("""
        After uploading your Excel files, you'll see:
        
        1. **📊 Combined Overview**: Key metrics from all uploaded files
        2. **🏆 Combined Leaderboard**: Staff ranked across all periods
        3. **📅 Time Period Analysis**: Weekly and monthly trends
        4. **📈 Detailed Insights**: Top performers and distribution analysis
        5. **📤 Export Options**: Download complete reports in multiple formats
        
        **Expected Excel Format:**
        - Each file should have columns: Person ID, Name, Department, Date, SIGN-IN, SIGN-OUT
        - Date format: MM/DD/YYYY
        - Time format: HH:MM (24-hour)
        - Can have sign-in and sign-out on separate rows
        - Files can be from different time periods
        """)
    
    # Placeholder metrics
    st.markdown("### 📊 Combined Attendance Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    for col, value, label in zip([col1, col2, col3, col4, col5], 
                                  ["0", "0%", "0%", "0.0", "0"], 
                                  ["Total Staff", "Daily Attendance", "On-Time Rate", "Avg Sign-Ins/Staff", "Total Sign-Ins"]):
        with col:
            st.metric(label=label, value=value)

# ================== FOOTER ==================
st.markdown("---")
st.caption("Staff Attendance Dashboard | Upload multiple Excel files for comprehensive attendance analysis and export")
