import streamlit as st
import pandas as pd
import datetime
from io import BytesIO

# ================== CONFIG ==================
st.set_page_config(
    page_title="Staff Attendance Dashboard",
    layout="wide"
)

# Define late time (8:00 AM)
LATE_TIME = datetime.time(8, 0)

# ================== HEADER ==================
st.title("Staff Attendance Dashboard")
st.markdown("Upload your attendance Excel file to view staff statistics and weekly reports.")

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
        
        # Convert time columns to datetime
        df["sign_in"] = pd.to_datetime(df["sign_in"], format='%H:%M', errors="coerce").dt.time
        df["sign_out"] = pd.to_datetime(df["sign_out"], format='%H:%M', errors="coerce").dt.time
        
        # Filter out rows where both sign_in and sign_out are null
        df = df.dropna(subset=["sign_in", "sign_out"], how="all")
        
        # Add day of week
        df["day"] = df["date"].dt.day_name()
        
        # Add week number
        df["week"] = df["date"].dt.isocalendar().week
        
        # Mark late arrivals (after 8:00 AM)
        df["late"] = df["sign_in"].apply(lambda x: False if pd.isna(x) else x > LATE_TIME)
        df["on_time"] = ~df["late"]
        
        return df
    
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

def calculate_kpis(df):
    """Calculate KPI metrics from the data"""
    # Get unique staff count
    total_staff = df["name"].nunique()
    
    # Get today's date
    today = datetime.date.today()
    
    # Filter for today's data
    today_data = df[df["date"].dt.date == today]
    
    # Count present today (those who signed in)
    present_today = today_data["name"].nunique()
    
    # Calculate absent today
    absent_today = total_staff - present_today
    
    # Calculate average sign-ins this week
    current_week = datetime.date.today().isocalendar()[1]
    this_week_data = df[df["week"] == current_week]
    if this_week_data.empty:
        avg_signins = 0
    else:
        signins_by_staff = this_week_data.groupby("name")["sign_in"].count()
        avg_signins = round(signins_by_staff.mean(), 1)
    
    return {
        "total_staff": total_staff,
        "present_today": present_today,
        "absent_today": absent_today,
        "avg_signins": avg_signins,
        "today": today
    }

def get_weekly_report(df, week_num=None):
    """Generate weekly sign-in report"""
    if week_num is None:
        week_num = datetime.date.today().isocalendar()[1]
    
    # Filter for the specific week
    weekly_data = df[df["week"] == week_num].copy()
    
    if weekly_data.empty:
        return pd.DataFrame()
    
    # Aggregate data for the report
    # Get the sign-in time for each day per employee
    weekly_data["sign_in_str"] = weekly_data["sign_in"].apply(
        lambda x: x.strftime("%I:%M %p") if not pd.isna(x) else "No Sign-in"
    )
    
    # Count total sign-ins per employee for the week
    signin_counts = weekly_data.groupby("name")["sign_in"].count().reset_index()
    signin_counts.columns = ["name", "total_signins"]
    
    # Get daily sign-in times
    daily_signins = weekly_data[["name", "day", "sign_in_str"]].copy()
    
    # Merge with total counts
    report = pd.merge(daily_signins, signin_counts, on="name", how="left")
    
    # Add checkmark for sign-ins
    report["total_signins_display"] = report["total_signins"].apply(lambda x: f"✅ {int(x)}" if pd.notna(x) else "✅ 0")
    
    # Select and rename columns for display
    report = report[["name", "day", "sign_in_str", "total_signins_display"]]
    report.columns = ["Employee Name", "Day", "Sign-In Time", "Total Sign-Ins (This Week)"]
    
    # Sort by day order
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    report["Day"] = pd.Categorical(report["Day"], categories=day_order, ordered=True)
    report = report.sort_values(["Employee Name", "Day"])
    
    return report

# ================== MAIN ==================
if uploaded_file is not None:
    # Process the uploaded file
    df = process_excel_file(uploaded_file)
    
    if df is not None and not df.empty:
        # Calculate KPIs
        kpis = calculate_kpis(df)
        
        # ================== KPI METRICS ==================
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Total Staff",
                value=kpis["total_staff"],
            )
        
        with col2:
            st.metric(
                label="Present Today",
                value=kpis["present_today"],
                delta=f"{kpis['today'].strftime('%b %d, %Y')}"
            )
        
        with col3:
            st.metric(
                label="Absent Today",
                value=kpis["absent_today"],
            )
        
        with col4:
            st.metric(
                label="Avg Sign-Ins This Week",
                value=kpis["avg_signins"],
            )
        
        st.markdown("---")
        
        # ================== WEEK SELECTOR ==================
        # Get unique weeks from data
        weeks = sorted(df["week"].unique())
        current_week = datetime.date.today().isocalendar()[1]
        
        if weeks:
            selected_week = st.selectbox(
                "Select Week for Report:",
                options=weeks,
                index=weeks.index(current_week) if current_week in weeks else 0,
                format_func=lambda x: f"Week {x}"
            )
        else:
            selected_week = current_week
        
        # ================== WEEKLY SIGN-IN REPORT ==================
        st.subheader(f"Weekly Sign-In Report - Week {selected_week}")
        
        # Generate weekly report
        weekly_report = get_weekly_report(df, selected_week)
        
        if not weekly_report.empty:
            # Display the table
            st.dataframe(
                weekly_report,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Employee Name": st.column_config.TextColumn("Employee Name", width="medium"),
                    "Day": st.column_config.TextColumn("Day", width="small"),
                    "Sign-In Time": st.column_config.TextColumn("Sign-In Time", width="small"),
                    "Total Sign-Ins (This Week)": st.column_config.TextColumn("Total Sign-Ins", width="small")
                }
            )
            
            # Show pagination info
            total_entries = len(weekly_report)
            st.caption(f"Showing 1 to {total_entries} of {total_entries} entries")
            
            # ================== ADDITIONAL STATS ==================
            with st.expander("📊 View Additional Statistics"):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Punctuality statistics
                    st.markdown("#### 🕐 Punctuality Overview")
                    on_time_count = df[df["on_time"] == True]["sign_in"].count()
                    late_count = df[df["late"] == True]["sign_in"].count()
                    total_signins = on_time_count + late_count
                    
                    if total_signins > 0:
                        on_time_percentage = (on_time_count / total_signins) * 100
                        st.metric("On-Time Rate", f"{on_time_percentage:.1f}%")
                    else:
                        st.metric("On-Time Rate", "0%")
                    
                    st.metric("Total On-Time Sign-Ins", on_time_count)
                    st.metric("Total Late Sign-Ins", late_count)
                
                with col2:
                    # Department breakdown
                    st.markdown("#### 👥 Department Breakdown")
                    dept_counts = df.groupby("department")["name"].nunique().reset_index()
                    dept_counts.columns = ["Department", "Staff Count"]
                    st.dataframe(dept_counts, hide_index=True, use_container_width=True)
        
        else:
            st.warning(f"No data available for Week {selected_week}")
    
    else:
        st.error("The uploaded file doesn't contain valid attendance data. Please check the file format.")
        
else:
    # Display placeholder metrics when no file is uploaded
    st.info("👆 Upload an attendance Excel file to view the dashboard")
    
    # Show example of expected format
    with st.expander("📋 Expected File Format"):
        st.markdown("""
        Your Excel file should have the following structure:
        
        | Person ID | Name | Department | Date | SIGN-IN | SIGN-OUT |
        |-----------|------|------------|------|---------|----------|
        | '00000001 | John Doe | Department | 11/10/2025 | 07:47 | 18:36 |
        | '00000002 | Jane Smith | Department | 11/10/2025 | 08:15 | 17:30 |
        
        **Note:**
        - The file should start with the data headers on row 2 (skip the title row)
        - Date format: MM/DD/YYYY
        - Time format: HH:MM (24-hour format)
        - SIGN-IN and SIGN-OUT can be on separate rows as shown in your example file
        """)
    
    # Placeholder metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(label="Total Staff", value="0")
    
    with col2:
        st.metric(label="Present Today", value="0")
    
    with col3:
        st.metric(label="Absent Today", value="0")
    
    with col4:
        st.metric(label="Avg Sign-Ins This Week", value="0.0")
    
    st.markdown("---")
    
    # Placeholder table
    st.subheader("Weekly Sign-In Report")
    placeholder_data = {
        "Employee Name": ["Upload file to see data"],
        "Day": [""],
        "Sign-In Time": [""],
        "Total Sign-Ins (This Week)": [""]
    }
    
    st.dataframe(
        pd.DataFrame(placeholder_data),
        use_container_width=True,
        hide_index=True
    )
    st.caption("Upload a file to view attendance data")
