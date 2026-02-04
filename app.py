import streamlit as st
import pandas as pd
import numpy as np
import datetime
from io import BytesIO
from datetime import time
import zipfile

# ================== CONFIG ==================
st.set_page_config(
    page_title="Staff Attendance Dashboard",
    layout="wide"
)

# Configuration
LATE_TIME = time(8, 0)  # 8:00 AM

# ================== HEADER ==================
st.title("Staff Attendance Dashboard")
st.markdown("Upload attendance files and staff list to compare attendance records.")

# ================== FILE UPLOAD ==================
col1, col2 = st.columns(2)

with col1:
    uploaded_files = st.file_uploader(
        "📤 Upload Attendance Excel Files",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Upload one or more Excel files with columns: Person ID, Name, Department, Date, SIGN-IN, SIGN-OUT"
    )

with col2:
    staff_list_file = st.file_uploader(
        "👥 Upload Staff Master List (Optional)",
        type=["xlsx", "xls", "csv"],
        help="Upload a master list of all staff members. Should have columns: Person ID, Name, Department"
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

def process_staff_list(file):
    """Process the staff master list file"""
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Standardize column names
        df.columns = [col.lower().strip().replace(' ', '_') for col in df.columns]
        
        # Check for required columns
        required_cols = ['name']
        if 'person_id' not in df.columns and 'id' in df.columns:
            df = df.rename(columns={'id': 'person_id'})
        if 'department' not in df.columns and 'dept' in df.columns:
            df = df.rename(columns={'dept': 'department'})
        
        # Keep only relevant columns
        keep_cols = []
        for col in ['person_id', 'name', 'department']:
            if col in df.columns:
                keep_cols.append(col)
        
        if len(keep_cols) == 0:
            st.error("Staff list must contain at least 'name' column")
            return pd.DataFrame()
        
        df = df[keep_cols].copy()
        
        # Clean data
        df['name'] = df['name'].astype(str).str.strip().str.upper()
        if 'department' in df.columns:
            df['department'] = df['department'].astype(str).str.strip()
        
        return df.drop_duplicates()
        
    except Exception as e:
        st.error(f"Error processing staff list: {str(e)}")
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

def compare_staff_lists(attendance_df, staff_list_df):
    """Compare attendance data with master staff list to identify non-attending staff"""
    if attendance_df.empty or staff_list_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # Clean names for comparison (uppercase and strip)
    attendance_df['name_clean'] = attendance_df['name'].astype(str).str.strip().str.upper()
    staff_list_df['name_clean'] = staff_list_df['name'].astype(str).str.strip().str.upper()
    
    # Find staff who have signed in
    attending_staff = attendance_df['name_clean'].unique()
    
    # Find all staff in master list
    all_staff = staff_list_df['name_clean'].unique()
    
    # Identify non-attending staff
    non_attending_mask = ~staff_list_df['name_clean'].isin(attending_staff)
    non_attending_staff = staff_list_df[non_attending_mask].copy()
    
    # Get attending staff details from master list
    attending_mask = staff_list_df['name_clean'].isin(attending_staff)
    attending_from_master = staff_list_df[attending_mask].copy()
    
    # Get staff who signed in but not in master list (potential new staff)
    attendance_only_mask = ~attendance_df['name_clean'].isin(all_staff)
    attendance_only_staff = attendance_df[attendance_only_mask][['name', 'department']].drop_duplicates()
    
    # Merge attendance data with master list for analysis
    merged_df = pd.merge(
        staff_list_df,
        attendance_df.groupby('name_clean').agg({
            'sign_in_time': 'count',
            'on_time': 'sum',
            'late': 'sum'
        }).reset_index(),
        on='name_clean',
        how='left'
    )
    
    # Rename columns
    merged_df = merged_df.rename(columns={
        'sign_in_time': 'total_days',
        'on_time': 'on_time_days',
        'late': 'late_days'
    })
    
    # Fill NaN values for non-attending staff
    merged_df['total_days'] = merged_df['total_days'].fillna(0).astype(int)
    merged_df['on_time_days'] = merged_df['on_time_days'].fillna(0).astype(int)
    merged_df['late_days'] = merged_df['late_days'].fillna(0).astype(int)
    
    # Calculate on-time percentage
    merged_df['on_time_percentage'] = merged_df.apply(
        lambda x: round((x['on_time_days'] / x['total_days'] * 100), 1) if x['total_days'] > 0 else 0,
        axis=1
    )
    
    # Add attendance status
    merged_df['attendance_status'] = merged_df['total_days'].apply(
        lambda x: 'Regular' if x >= 3 else ('Occasional' if x > 0 else 'Non-Attending')
    )
    
    return merged_df, non_attending_staff, attendance_only_staff

def calculate_kpis(df, staff_list_df=None):
    """Calculate KPI metrics from the combined data"""
    if df.empty:
        base_kpis = {
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
        
        if staff_list_df is not None and not staff_list_df.empty:
            base_kpis.update({
                "total_staff_in_list": len(staff_list_df),
                "attending_staff": 0,
                "non_attending_staff": len(staff_list_df),
                "attendance_rate": 0.0
            })
        
        return base_kpis
    
    # Get unique staff count from attendance data
    attending_staff_count = df["name"].nunique()
    
    # Get today's date
    today = datetime.date.today()
    
    # Filter for today's data
    today_data = df[df["date"].dt.date == today]
    
    # Count present today (those who signed in)
    present_today = today_data["name"].nunique() if not today_data.empty else 0
    
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
        avg_daily_attendance = round(daily_attendance / attending_staff_count * 100, 1) if attending_staff_count > 0 else 0.0
    else:
        avg_daily_attendance = 0.0
    
    # Calculate date range
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    date_range = f"{min_date.strftime('%b %d, %Y')} to {max_date.strftime('%b %d, %Y')}"
    total_days_covered = (max_date - min_date).days + 1
    
    kpis = {
        "total_staff": attending_staff_count,
        "present_today": present_today,
        "absent_today": 0,  # Will be calculated below if staff list is provided
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
    
    # Add staff list comparison metrics if staff list is provided
    if staff_list_df is not None and not staff_list_df.empty:
        total_staff_in_list = len(staff_list_df)
        non_attending_count = total_staff_in_list - attending_staff_count
        attendance_rate = round((attending_staff_count / total_staff_in_list) * 100, 1) if total_staff_in_list > 0 else 0
        
        kpis.update({
            "total_staff_in_list": total_staff_in_list,
            "attending_staff": attending_staff_count,
            "non_attending_staff": max(0, non_attending_count),
            "attendance_rate": attendance_rate,
            "absent_today": max(0, total_staff_in_list - present_today)
        })
    
    return kpis

def create_attendance_leaderboard(merged_df):
    """Create a leaderboard of staff ranked by attendance and punctuality"""
    if merged_df.empty:
        return pd.DataFrame()
    
    # Calculate average sign-in time if we have the detailed data
    # This would require access to the detailed attendance data
    # For now, we'll work with the merged dataframe
    
    # Sort by total days descending, then by on-time percentage descending
    leaderboard = merged_df.sort_values(
        by=["total_days", "on_time_percentage"], 
        ascending=[False, False]
    ).reset_index(drop=True)
    
    # Add rank
    leaderboard.insert(0, "rank", range(1, len(leaderboard) + 1))
    
    # Select and order columns
    display_cols = [
        "rank", "name", "department", "total_days", 
        "on_time_percentage", "on_time_days", "late_days",
        "attendance_status"
    ]
    
    # Only include columns that exist
    display_cols = [col for col in display_cols if col in leaderboard.columns]
    
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

# ================== MAIN ==================
if uploaded_files:
    # Process all uploaded files
    with st.spinner("Processing uploaded files..."):
        df, file_names = combine_all_files(uploaded_files)
    
    if not df.empty:
        # File upload summary
        st.success(f"✅ Successfully processed {len(file_names)} attendance file(s)")
        
        # Process staff list if provided
        staff_list_df = pd.DataFrame()
        if staff_list_file is not None:
            with st.spinner("Processing staff list..."):
                staff_list_df = process_staff_list(staff_list_file)
            if not staff_list_df.empty:
                st.success(f"✅ Processed staff list with {len(staff_list_df)} staff members")
        
        # Compare staff lists if staff list is provided
        merged_df = pd.DataFrame()
        non_attending_staff = pd.DataFrame()
        attendance_only_staff = pd.DataFrame()
        
        if not staff_list_df.empty:
            merged_df, non_attending_staff, attendance_only_staff = compare_staff_lists(df, staff_list_df)
        
        # Calculate KPIs
        kpis = calculate_kpis(df, staff_list_df)
        
        # ================== STAFF COMPARISON SECTION ==================
        if not staff_list_df.empty:
            st.markdown("---")
            st.markdown("### 👥 Staff Attendance Comparison")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    label="Total Staff in List",
                    value=kpis.get("total_staff_in_list", 0),
                    help="Total staff members in master list"
                )
            
            with col2:
                st.metric(
                    label="Staff Who Signed In",
                    value=kpis.get("attending_staff", kpis["total_staff"]),
                    delta=f"{kpis.get('attendance_rate', 0)}% attendance rate",
                    help="Staff members who have signed in at least once"
                )
            
            with col3:
                non_attending_count = kpis.get("non_attending_staff", 0)
                st.metric(
                    label="Never Signed In",
                    value=non_attending_count,
                    delta=f"{non_attending_count} staff",
                    help="Staff members who have never signed in"
                )
            
            with col4:
                if not attendance_only_staff.empty:
                    st.metric(
                        label="Not in Master List",
                        value=len(attendance_only_staff),
                        help="Staff who signed in but not in master list"
                    )
                else:
                    st.metric(
                        label="All Staff Accounted",
                        value="✓",
                        help="All signing staff are in master list"
                    )
            
            # Display non-attending staff
            if not non_attending_staff.empty:
                with st.expander("📋 View Staff Who Never Signed In", expanded=True):
                    st.dataframe(
                        non_attending_staff,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "name": "Staff Name",
                            "department": "Department",
                            "person_id": "ID"
                        }
                    )
                    
                    # Add download option for non-attending staff
                    csv_data = non_attending_staff.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Non-Attending Staff List",
                        data=csv_data,
                        file_name="non_attending_staff.csv",
                        mime="text/csv",
                        help="Download list of staff who never signed in"
                    )
            
            # Display staff who signed in but not in master list
            if not attendance_only_staff.empty:
                with st.expander("📝 View Staff Not in Master List", expanded=True):
                    st.info("These staff members signed in but are not in the master list. They may be new hires or need to be added to the master list.")
                    st.dataframe(
                        attendance_only_staff,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "name": "Staff Name",
                            "department": "Department"
                        }
                    )
        
        # ================== KPI METRICS ==================
        st.markdown("---")
        st.markdown("### 📊 Attendance Overview")
        st.caption(f"Data Range: {kpis['date_range']} ({kpis['total_days_covered']} days)")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                label="Total Staff",
                value=kpis["total_staff"],
                help="Number of unique staff members in attendance data"
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
        
        # ================== ATTENDANCE LEADERBOARD ==================
        st.markdown("---")
        st.markdown("### 🏆 Attendance Leaderboard")
        
        # Use merged_df if available, otherwise use attendance data
        if not merged_df.empty:
            leaderboard = create_attendance_leaderboard(merged_df)
        else:
            # Create basic leaderboard from attendance data only
            attendance_stats = df.groupby(["name", "department"]).agg({
                "sign_in_time": "count",
                "on_time": "sum",
                "late": "sum"
            }).reset_index()
            
            attendance_stats.columns = ["name", "department", "total_days", "on_time_days", "late_days"]
            attendance_stats["on_time_percentage"] = round(
                (attendance_stats["on_time_days"] / attendance_stats["total_days"]) * 100, 1
            )
            attendance_stats["attendance_status"] = attendance_stats["total_days"].apply(
                lambda x: 'Regular' if x >= 3 else ('Occasional' if x > 0 else 'Non-Attending')
            )
            
            leaderboard = attendance_stats.sort_values("total_days", ascending=False).reset_index(drop=True)
            leaderboard.insert(0, "rank", range(1, len(leaderboard) + 1))
        
        if not leaderboard.empty:
            # Display leaderboard with progress bars for on-time percentage
            column_config = {
                "rank": st.column_config.NumberColumn("Rank", width="small"),
                "name": st.column_config.TextColumn("Employee Name", width="medium"),
                "department": st.column_config.TextColumn("Department", width="medium"),
                "total_days": st.column_config.NumberColumn(
                    "Total Days",
                    width="small",
                    help="Total number of days signed in"
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
            
            # Add attendance status column if it exists
            if "attendance_status" in leaderboard.columns:
                column_config["attendance_status"] = st.column_config.TextColumn(
                    "Status",
                    width="small",
                    help="Attendance pattern: Regular (3+ days), Occasional (1-2 days), Non-Attending (0 days)"
                )
            
            st.dataframe(
                leaderboard,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            # Add leaderboard statistics
            st.markdown("#### 📈 Leaderboard Statistics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if len(leaderboard) > 0:
                    top_performer = leaderboard.iloc[0]
                    st.metric(
                        "Top Performer", 
                        top_performer["name"].split()[0] if isinstance(top_performer["name"], str) else "N/A",
                        delta=f"{top_performer['total_days']} days",
                        help="Staff with most days attended"
                    )
            
            with col2:
                avg_days = round(leaderboard["total_days"].mean(), 1)
                st.metric(
                    "Avg Days/Staff", 
                    avg_days,
                    help="Average number of days attended per staff member"
                )
            
            with col3:
                if "attendance_status" in leaderboard.columns:
                    regular_count = len(leaderboard[leaderboard["attendance_status"] == "Regular"])
                    st.metric(
                        "Regular Attendees", 
                        regular_count,
                        help="Staff who attended 3+ days"
                    )
            
            with col4:
                best_punctuality = leaderboard["on_time_percentage"].max() if "on_time_percentage" in leaderboard.columns else 0
                st.metric(
                    "Best On-Time Rate", 
                    f"{best_punctuality}%",
                    help="Highest on-time percentage achieved"
                )
        
        # ================== ATTENDANCE DISTRIBUTION ==================
        st.markdown("---")
        st.markdown("### 📊 Attendance Distribution")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Create attendance frequency distribution
            if not leaderboard.empty and "total_days" in leaderboard.columns:
                st.markdown("#### Days Attended Distribution")
                
                # Create bins for attendance days
                max_days = leaderboard["total_days"].max()
                if max_days <= 5:
                    bins = [0, 1, 2, 3, 4, 5]
                    labels = ["0 days", "1 day", "2 days", "3 days", "4 days", "5+ days"]
                else:
                    bin_step = max(1, max_days // 5)
                    bins = list(range(0, max_days + bin_step, bin_step))
                    bins = sorted(set(bins))
                    labels = [f"{bins[i]}-{bins[i+1]-1} days" if i < len(bins)-2 else f"{bins[i]}+ days" 
                             for i in range(len(bins)-1)]
                
                leaderboard_copy = leaderboard.copy()
                leaderboard_copy["attendance_range"] = pd.cut(
                    leaderboard_copy["total_days"], 
                    bins=bins, 
                    labels=labels, 
                    right=False,
                    include_lowest=True
                )
                
                distribution = leaderboard_copy["attendance_range"].value_counts().sort_index().reset_index()
                distribution.columns = ["Days Attended", "Number of Staff"]
                
                st.dataframe(
                    distribution,
                    use_container_width=True,
                    hide_index=True
                )
        
        with col2:
            # Show summary statistics
            st.markdown("#### Attendance Summary")
            
            summary_data = []
            
            if not staff_list_df.empty:
                summary_data.append(["Staff in Master List", kpis.get("total_staff_in_list", "N/A")])
                summary_data.append(["Staff Who Attended", kpis.get("attending_staff", kpis["total_staff"])])
                summary_data.append(["Never Attended", kpis.get("non_attending_staff", 0)])
                summary_data.append(["Attendance Rate", f"{kpis.get('attendance_rate', 0)}%"])
            
            summary_data.append(["Average Days/Staff", f"{kpis['avg_signins']}"])
            summary_data.append(["On-Time Rate", f"{kpis['on_time_rate']}%"])
            summary_data.append(["Data Days Covered", kpis["total_days_covered"]])
            summary_data.append(["Total Sign-Ins", f"{kpis['total_signins']:,}"])
            
            summary_df = pd.DataFrame(summary_data, columns=["Metric", "Value"])
            st.dataframe(
                summary_df,
                use_container_width=True,
                hide_index=True
            )
        
        # ================== EXPORT SECTION ==================
        st.markdown("---")
        st.markdown("## 📤 Export Reports")
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Export combined report
            if not merged_df.empty:
                combined_csv = merged_df.to_csv(index=False)
                st.download_button(
                    label="📊 Download Full Comparison",
                    data=combined_csv,
                    file_name=f"staff_attendance_comparison_{timestamp}.csv",
                    mime="text/csv",
                    help="Download complete staff comparison data"
                )
        
        with col2:
            # Export non-attending staff list
            if not non_attending_staff.empty:
                non_attending_csv = non_attending_staff.to_csv(index=False)
                st.download_button(
                    label="📋 Download Non-Attending List",
                    data=non_attending_csv,
                    file_name=f"non_attending_staff_{timestamp}.csv",
                    mime="text/csv",
                    help="Download list of staff who never signed in"
                )
        
        with col3:
            # Export attendance-only staff
            if not attendance_only_staff.empty:
                attendance_only_csv = attendance_only_staff.to_csv(index=False)
                st.download_button(
                    label="👤 Download New Staff List",
                    data=attendance_only_csv,
                    file_name=f"new_staff_list_{timestamp}.csv",
                    mime="text/csv",
                    help="Download staff who signed in but not in master list"
                )
        
        # ================== DATA SUMMARY ==================
        st.markdown("---")
        st.markdown("### 📋 Data Summary")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Files Processed",
                len(file_names),
                help="Number of attendance files processed"
            )
        
        with col2:
            st.metric(
                "Staff Records",
                f"{kpis['total_staff']} / {kpis.get('total_staff_in_list', kpis['total_staff'])}",
                help="Attending staff / Total staff in list"
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
    st.info("👆 Upload attendance Excel files to begin analysis")
    
    # Instructions
    with st.expander("📋 How to use this dashboard"):
        st.markdown("""
        ### **Dashboard Features:**
        
        1. **Staff Comparison**: Upload a master staff list to compare against attendance records
        2. **Identify Non-Attending Staff**: Find staff who are in the master list but never signed in
        3. **Find New Staff**: Identify staff who signed in but aren't in the master list
        4. **Attendance Analysis**: View detailed attendance patterns and punctuality
        
        ### **File Requirements:**
        
        **Attendance Files:**
        - Excel files with columns: Person ID, Name, Department, Date, SIGN-IN, SIGN-OUT
        - Date format: MM/DD/YYYY
        - Time format: HH:MM (24-hour)
        
        **Staff Master List (Optional):**
        - Excel or CSV file with columns: Name (required), Person ID, Department
        - Helps identify staff who never sign in
        
        ### **Expected Outputs:**
        - List of staff who never signed in
        - List of new staff not in master list
        - Attendance leaderboard
        - Detailed attendance statistics
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
st.caption("Staff Attendance Dashboard with Staff Comparison | Upload master list to identify non-attending staff")
