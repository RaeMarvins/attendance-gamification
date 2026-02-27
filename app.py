import streamlit as st
import pandas as pd
import numpy as np
import datetime
from io import BytesIO
from datetime import time
import zipfile
import plotly.graph_objects as go
import plotly.express as px

# ================== CONFIG ==================
st.set_page_config(
    page_title="Staff Attendance Dashboard",
    layout="wide"
)

# Configuration
LATE_TIME = time(8, 0)  # 8:00 AM
WORK_DAYS_PER_WEEK = 5  # Assuming Monday-Friday work week
WORK_DAYS_PER_MONTH = 22  # Average work days per month

# ================== HEADER ==================
st.title("Staff Attendance Dashboard")
st.markdown("Upload attendance files and staff list to compare attendance records.")

# ================== CUSTOM CSS ==================
st.markdown("""
<style>
    /* Status indicators */
    .excellent {
        background-color: #d4edda;
        color: #155724;
        padding: 10px 15px;
        border-radius: 20px;
        font-weight: bold;
        text-align: center;
        border-left: 5px solid #28a745;
        margin: 5px 0;
    }
    .needs-monitoring {
        background-color: #fff3cd;
        color: #856404;
        padding: 10px 15px;
        border-radius: 20px;
        font-weight: bold;
        text-align: center;
        border-left: 5px solid #ffc107;
        margin: 5px 0;
    }
    .intervention {
        background-color: #f8d7da;
        color: #721c24;
        padding: 10px 15px;
        border-radius: 20px;
        font-weight: bold;
        text-align: center;
        border-left: 5px solid #dc3545;
        margin: 5px 0;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .days-lost {
        font-size: 36px;
        font-weight: bold;
        color: #dc3545;
    }
    .financial-impact {
        font-size: 36px;
        font-weight: bold;
        color: #dc3545;
    }
    @media print {
        .excellent, .needs-monitoring, .intervention {
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
    }
    .stButton button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

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

# ================== SIDEBAR CONFIGURATION ==================
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # Daily wage input for financial calculations
    avg_daily_wage = st.number_input(
        "💰 Average Daily Wage ($)",
        min_value=0,
        value=100,
        step=10,
        help="Used to calculate financial impact of absenteeism"
    )
    
    # Work days configuration
    st.markdown("#### 📅 Work Week Configuration")
    work_days_per_week = st.number_input(
        "Work Days per Week",
        min_value=1,
        max_value=7,
        value=5,
        help="Number of working days in a week"
    )
    
    work_days_per_month = st.number_input(
        "Work Days per Month",
        min_value=1,
        max_value=31,
        value=22,
        help="Average number of working days in a month"
    )
    
    st.markdown("---")
    st.markdown("### 📊 Dashboard Info")
    st.markdown("""
    **Features:**
    - 📈 Days Lost Tracking
    - 🟢 Attendance Categories
    - 👥 Staff Comparison
    - 📊 Visual Analytics
    - 📤 Export Reports
    """)

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
        df["week_identifier"] = df["week_year"].astype(str) + "-W" + df["week_num"].astype(str).str.zfill(2)
        
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

def calculate_absenteeism(df, staff_list_df=None, period_days=None, avg_daily_wage=100):
    """Calculate days lost due to absenteeism"""
    if df.empty:
        return {
            "total_days_lost": 0,
            "avg_days_lost_per_staff": 0,
            "absenteeism_rate": 0,
            "financial_impact": 0,
            "productivity_loss": 0,
            "total_possible_days": 0,
            "total_actual_signins": 0,
            "period_days": 0,
            "total_staff": 0
        }
    
    # Get total unique dates in the period
    if period_days is None:
        period_days = df['date'].dt.date.nunique()
    
    # Determine total staff count
    if staff_list_df is not None and not staff_list_df.empty:
        total_staff = len(staff_list_df)
    else:
        total_staff = df['name'].nunique()
    
    # Calculate total possible work days
    total_possible_days = total_staff * period_days
    
    # Calculate total actual sign-ins
    total_actual_signins = len(df)
    
    # Calculate days lost
    total_days_lost = total_possible_days - total_actual_signins
    
    # Calculate average days lost per staff
    avg_days_lost_per_staff = round(total_days_lost / total_staff, 1) if total_staff > 0 else 0
    
    # Calculate absenteeism rate
    absenteeism_rate = round((total_days_lost / total_possible_days) * 100, 1) if total_possible_days > 0 else 0
    
    # Estimate financial impact
    financial_impact = total_days_lost * avg_daily_wage
    
    # Estimate productivity loss (as percentage)
    productivity_loss = round(absenteeism_rate * 0.8, 1)  # Rough estimate: 80% of absenteeism rate
    
    return {
        "total_days_lost": total_days_lost,
        "avg_days_lost_per_staff": avg_days_lost_per_staff,
        "absenteeism_rate": absenteeism_rate,
        "financial_impact": financial_impact,
        "productivity_loss": productivity_loss,
        "total_possible_days": total_possible_days,
        "total_actual_signins": total_actual_signins,
        "period_days": period_days,
        "total_staff": total_staff
    }

def categorize_attendance(attendance_rate):
    """Categorize attendance rate with color coding"""
    if attendance_rate >= 95:
        return "🟢 Excellent", "excellent"
    elif attendance_rate >= 85:
        return "🟡 Needs Monitoring", "needs-monitoring"
    else:
        return "🔴 Intervention Required", "intervention"

def compare_staff_lists(attendance_df, staff_list_df):
    """Compare attendance data with master staff list to identify non-attending staff"""
    if attendance_df.empty or staff_list_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 0
    
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
    
    # Get period length for attendance rate calculation
    period_days = attendance_df['date'].dt.date.nunique()
    expected_days = period_days
    
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
    
    # Calculate attendance rate
    merged_df['attendance_rate'] = round((merged_df['total_days'] / expected_days) * 100, 1)
    
    # Calculate days lost per staff
    merged_df['days_lost'] = expected_days - merged_df['total_days']
    
    # Calculate on-time percentage
    merged_df['on_time_percentage'] = merged_df.apply(
        lambda x: round((x['on_time_days'] / x['total_days'] * 100), 1) if x['total_days'] > 0 else 0,
        axis=1
    )
    
    # Add attendance status and category
    merged_df['attendance_category'] = merged_df['attendance_rate'].apply(
        lambda x: 'Excellent' if x >= 95 else ('Needs Monitoring' if x >= 85 else 'Intervention Required')
    )
    
    # Add attendance status type
    merged_df['attendance_status_type'] = merged_df['total_days'].apply(
        lambda x: 'Regular' if x >= 3 else ('Occasional' if x > 0 else 'Non-Attending')
    )
    
    return merged_df, non_attending_staff, attendance_only_staff, expected_days

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
        "absent_today": 0,
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
    
    # Sort by total days descending, then by on-time percentage descending
    leaderboard = merged_df.sort_values(
        by=["total_days", "on_time_percentage"], 
        ascending=[False, False]
    ).reset_index(drop=True)
    
    # Add rank
    leaderboard.insert(0, "rank", range(1, len(leaderboard) + 1))
    
    # Select and order columns
    display_cols = [
        "rank", "name", "department", "total_days", "days_lost",
        "attendance_rate", "on_time_percentage", "on_time_days", 
        "late_days", "attendance_category", "attendance_status_type"
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
    
    # Calculate attendance rate and days lost for the period
    if len(df['name'].unique()) > 0:
        total_staff = df['name'].nunique()
        period_stats["Attendance Rate %"] = round((period_stats["Unique Staff"] / total_staff) * 100, 1)
        period_stats["Days Lost"] = (total_staff * len(period_stats)) - period_stats["Total Sign-Ins"]
    
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

def create_visual_analytics(df, leaderboard):
    """Create interactive visual analytics"""
    
    fig1, fig2, fig3 = None, None, None
    
    if not df.empty:
        # 1. Attendance Heatmap by Day/Hour
        df['hour'] = df['sign_in_time'].apply(lambda x: x.hour)
        heatmap_data = df.pivot_table(
            index='day', 
            columns='hour', 
            values='sign_in_time', 
            aggfunc='count',
            fill_value=0
        )
        
        # Reorder days
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        heatmap_data = heatmap_data.reindex([d for d in day_order if d in heatmap_data.index])
        
        fig1 = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale='Viridis',
            hoverongaps=False,
            colorbar=dict(title="Sign-Ins")
        ))
        fig1.update_layout(
            title='Attendance Heatmap by Day & Hour',
            xaxis_title='Hour of Day',
            yaxis_title='Day of Week',
            height=400
        )
    
    if not leaderboard.empty and 'attendance_status_type' in leaderboard.columns:
        # 2. Attendance Rate Distribution
        fig2 = go.Figure()
        
        # Add bars for each attendance category
        category_counts = leaderboard['attendance_status_type'].value_counts()
        
        colors = {'Regular': '#28a745', 'Occasional': '#ffc107', 'Non-Attending': '#dc3545'}
        
        fig2.add_trace(go.Bar(
            x=category_counts.index,
            y=category_counts.values,
            marker_color=[colors.get(x, '#6c757d') for x in category_counts.index],
            text=category_counts.values,
            textposition='auto',
        ))
        
        fig2.update_layout(
            title='Staff Attendance Categories',
            xaxis_title='Attendance Status',
            yaxis_title='Number of Staff',
            height=400,
            showlegend=False
        )
        
        # 3. Days Lost Distribution
        if 'days_lost' in leaderboard.columns:
            fig3 = go.Figure()
            
            # Create histogram of days lost
            fig3.add_trace(go.Histogram(
                x=leaderboard['days_lost'],
                nbinsx=20,
                marker_color='#dc3545',
                opacity=0.7,
                name='Days Lost'
            ))
            
            fig3.update_layout(
                title='Distribution of Days Lost per Staff',
                xaxis_title='Days Lost',
                yaxis_title='Number of Staff',
                height=400,
                bargap=0.1
            )
            
            # Add vertical line for average
            avg_days_lost = leaderboard['days_lost'].mean()
            fig3.add_vline(
                x=avg_days_lost, 
                line_dash="dash", 
                line_color="blue",
                annotation_text=f"Avg: {avg_days_lost:.1f}",
                annotation_position="top"
            )
    
    return fig1, fig2, fig3

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
        expected_days = 0
        
        if not staff_list_df.empty:
            merged_df, non_attending_staff, attendance_only_staff, expected_days = compare_staff_lists(df, staff_list_df)
        
        # Calculate KPIs
        kpis = calculate_kpis(df, staff_list_df)
        
        # Calculate absenteeism metrics
        absenteeism = calculate_absenteeism(df, staff_list_df, kpis['total_days_covered'], avg_daily_wage)
        
        # ================== DAYS LOST & ABSENTEEISM SECTION ==================
        st.markdown("---")
        st.markdown("### 📉 Absenteeism Analysis")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h4>Total Days Lost</h4>
                <div class="days-lost">{absenteeism['total_days_lost']:,}</div>
                <small>out of {absenteeism['total_possible_days']:,} possible days</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h4>Absenteeism Rate</h4>
                <div class="days-lost">{absenteeism['absenteeism_rate']:.1f}%</div>
                <small>{absenteeism['avg_days_lost_per_staff']:.1f} days lost per staff</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <h4>Financial Impact</h4>
                <div class="financial-impact">${absenteeism['financial_impact']:,.0f}</div>
                <small>Estimated cost of absenteeism</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <h4>Productivity Loss</h4>
                <div class="days-lost">{absenteeism['productivity_loss']:.1f}%</div>
                <small>Estimated productivity impact</small>
            </div>
            """, unsafe_allow_html=True)
        
        # ================== ATTENDANCE CATEGORIES ==================
        if not merged_df.empty:
            st.markdown("---")
            st.markdown("### 📊 Attendance Categories")
            st.markdown("**🟢 95–100% – Excellent | 🟡 85–94% – Needs Monitoring | 🔴 Below 85% – Intervention Required**")
            
            # Calculate category counts
            category_counts = merged_df['attendance_category'].value_counts()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                excellent_count = category_counts.get('Excellent', 0)
                st.markdown(f"""
                <div class="excellent">
                    🟢 Excellent (≥95%): {excellent_count} staff
                </div>
                """, unsafe_allow_html=True)
                
                if excellent_count > 0:
                    excellent_staff = merged_df[merged_df['attendance_category'] == 'Excellent']
                    st.dataframe(
                        excellent_staff[['name', 'attendance_rate', 'total_days']].head(5),
                        use_container_width=True,
                        hide_index=True
                    )
            
            with col2:
                monitoring_count = category_counts.get('Needs Monitoring', 0)
                st.markdown(f"""
                <div class="needs-monitoring">
                    🟡 Needs Monitoring (85-94%): {monitoring_count} staff
                </div>
                """, unsafe_allow_html=True)
                
                if monitoring_count > 0:
                    monitoring_staff = merged_df[merged_df['attendance_category'] == 'Needs Monitoring']
                    st.dataframe(
                        monitoring_staff[['name', 'attendance_rate', 'total_days']].head(5),
                        use_container_width=True,
                        hide_index=True
                    )
            
            with col3:
                intervention_count = category_counts.get('Intervention Required', 0)
                st.markdown(f"""
                <div class="intervention">
                    🔴 Intervention Required (<85%): {intervention_count} staff
                </div>
                """, unsafe_allow_html=True)
                
                if intervention_count > 0:
                    intervention_staff = merged_df[merged_df['attendance_category'] == 'Intervention Required']
                    st.dataframe(
                        intervention_staff[['name', 'attendance_rate', 'total_days']].head(5),
                        use_container_width=True,
                        hide_index=True
                    )
        
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
                    help="Staff members who have never signed in",
                    delta_color="inverse" if non_attending_count > 0 else "normal"
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
                with st.expander(f"📋 View Staff Who Never Signed In ({len(non_attending_staff)} staff)", expanded=True):
                    st.warning(f"⚠️ {len(non_attending_staff)} staff members have never signed in")
                    st.dataframe(
                        non_attending_staff[['name', 'department', 'person_id']] if 'person_id' in non_attending_staff.columns else non_attending_staff,
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
                        file_name=f"non_attending_staff_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            
            # Display staff who signed in but not in master list
            if not attendance_only_staff.empty:
                with st.expander(f"📝 View Staff Not in Master List ({len(attendance_only_staff)} staff)", expanded=True):
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
            if not staff_list_df.empty:
                total_label = f"{kpis['attending_staff']} / {kpis['total_staff_in_list']}"
                total_help = "Attending staff / Total staff in list"
            else:
                total_label = kpis["total_staff"]
                total_help = "Number of unique staff members in attendance data"
            
            st.metric(
                label="Staff Count",
                value=total_label,
                help=total_help
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
                help="Total number of sign-ins across all periods",
                delta_color="inverse" if kpis['total_late'] > 0 else "normal"
            )
        
        # ================== VISUAL ANALYTICS ==================
        st.markdown("---")
        st.markdown("### 📈 Visual Analytics")
        
        fig1, fig2, fig3 = create_visual_analytics(df, merged_df if not merged_df.empty else pd.DataFrame())
        
        col1, col2 = st.columns(2)
        
        with col1:
            if fig1:
                st.plotly_chart(fig1, use_container_width=True)
            if fig2:
                st.plotly_chart(fig2, use_container_width=True)
        
        with col2:
            if fig3:
                st.plotly_chart(fig3, use_container_width=True)
        
        # ================== ATTENDANCE LEADERBOARD ==================
        st.markdown("---")
        st.markdown("### 🏆 Attendance Leaderboard")
        
        # Use merged_df if available, otherwise create from attendance data
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
            
            # Calculate days lost
            period_days = df['date'].dt.date.nunique()
            attendance_stats["days_lost"] = period_days - attendance_stats["total_days"]
            attendance_stats["attendance_rate"] = round((attendance_stats["total_days"] / period_days) * 100, 1)
            
            attendance_stats["attendance_category"] = attendance_stats["attendance_rate"].apply(
                lambda x: 'Excellent' if x >= 95 else ('Needs Monitoring' if x >= 85 else 'Intervention Required')
            )
            
            attendance_stats["attendance_status_type"] = attendance_stats["total_days"].apply(
                lambda x: 'Regular' if x >= 3 else ('Occasional' if x > 0 else 'Non-Attending')
            )
            
            leaderboard = attendance_stats.sort_values("total_days", ascending=False).reset_index(drop=True)
            leaderboard.insert(0, "rank", range(1, len(leaderboard) + 1))
        
        if not leaderboard.empty:
            # Configure column display
            column_config = {
                "rank": st.column_config.NumberColumn("Rank", width="small"),
                "name": st.column_config.TextColumn("Employee Name", width="medium"),
                "department": st.column_config.TextColumn("Department", width="medium"),
                "total_days": st.column_config.NumberColumn("Days Attended", width="small"),
                "days_lost": st.column_config.NumberColumn("Days Lost", width="small"),
                "attendance_rate": st.column_config.ProgressColumn(
                    "Attendance %",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                    width="medium"
                ),
                "on_time_percentage": st.column_config.ProgressColumn(
                    "On-Time %", 
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                    width="medium"
                ),
                "on_time_days": st.column_config.NumberColumn("On-Time", width="small"),
                "late_days": st.column_config.NumberColumn("Late", width="small"),
                "attendance_category": st.column_config.TextColumn("Category", width="medium"),
                "attendance_status_type": st.column_config.TextColumn("Status", width="small")
            }
            
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
                if "attendance_status_type" in leaderboard.columns:
                    regular_count = len(leaderboard[leaderboard["attendance_status_type"] == "Regular"])
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
        
        # ================== TIME PERIOD ANALYSIS ==================
        st.markdown("---")
        st.markdown("### 📅 Time Period Analysis")
        
        tab1, tab2 = st.tabs(["Weekly Analysis", "Monthly Analysis"])
        
        with tab1:
            st.markdown("#### 📊 Weekly Attendance Trends")
            weekly_report = create_time_period_report(df, period_type="week")
            
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
                        ),
                        "Days Lost": st.column_config.NumberColumn("Days Lost", width="small")
                    }
                )
        
        with tab2:
            st.markdown("#### 📊 Monthly Attendance Trends")
            monthly_report = create_time_period_report(df, period_type="month")
            
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
                        ),
                        "Days Lost": st.column_config.NumberColumn("Days Lost", width="small")
                    }
                )
        
        # ================== EXPORT SECTION ==================
        st.markdown("---")
        st.markdown("## 📤 Export Reports")
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Export full comparison report
            if not merged_df.empty:
                csv_data = merged_df.to_csv(index=False)
                st.download_button(
                    label="📊 Download Full Report",
                    data=csv_data,
                    file_name=f"attendance_full_report_{timestamp}.csv",
                    mime="text/csv",
                    help="Download complete attendance data with categories"
                )
            elif not df.empty:
                # Create summary report from attendance data
                summary_df = df.groupby(['name', 'department']).agg({
                    'sign_in_time': 'count',
                    'on_time': 'sum',
                    'late': 'sum'
                }).reset_index()
                summary_df.columns = ['name', 'department', 'total_days', 'on_time_days', 'late_days']
                summary_df['on_time_percentage'] = round((summary_df['on_time_days'] / summary_df['total_days']) * 100, 1)
                
                csv_data = summary_df.to_csv(index=False)
                st.download_button(
                    label="📊 Download Summary Report",
                    data=csv_data,
                    file_name=f"attendance_summary_{timestamp}.csv",
                    mime="text/csv"
                )
        
        with col2:
            # Export leaderboard
            if not leaderboard.empty:
                csv_data = leaderboard.to_csv(index=False)
                st.download_button(
                    label="🏆 Download Leaderboard",
                    data=csv_data,
                    file_name=f"attendance_leaderboard_{timestamp}.csv",
                    mime="text/csv"
                )
        
        with col3:
            # Export non-attending staff list
            if not non_attending_staff.empty:
                csv_data = non_attending_staff.to_csv(index=False)
                st.download_button(
                    label="📋 Download Non-Attending List",
                    data=csv_data,
                    file_name=f"non_attending_staff_{timestamp}.csv",
                    mime="text/csv"
                )
            elif not staff_list_df.empty and non_attending_staff.empty:
                st.info("✅ All staff in master list have signed in!")
        
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
            if not staff_list_df.empty:
                st.metric(
                    "Staff Coverage",
                    f"{kpis['attending_staff']} / {kpis['total_staff_in_list']}",
                    help="Attending staff / Total staff in list"
                )
            else:
                st.metric(
                    "Unique Staff",
                    kpis['total_staff'],
                    help="Number of unique staff members"
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
        
        1. **📉 Absenteeism Analysis**: Track days lost and financial impact
        2. **🟢 Attendance Categories**: Color-coded staff performance
        3. **👥 Staff Comparison**: Identify non-attending staff
        4. **📊 Visual Analytics**: Interactive charts and heatmaps
        5. **🏆 Leaderboard**: Rank staff by attendance
        6. **📤 Export Reports**: Download data in CSV format
        
        ### **File Requirements:**
        
        **Attendance Files:**
        - Excel files with columns: Person ID, Name, Department, Date, SIGN-IN, SIGN-OUT
        - Date format: MM/DD/YYYY
        - Time format: HH:MM (24-hour)
        
        **Staff Master List (Optional):**
        - Excel or CSV file with columns: Name (required), Person ID, Department
        - Helps identify staff who never sign in
        
        ### **Attendance Categories:**
        - 🟢 **Excellent**: 95-100% attendance rate
        - 🟡 **Needs Monitoring**: 85-94% attendance rate
        - 🔴 **Intervention Required**: Below 85% attendance rate
        """)
    
    # Placeholder metrics
    st.markdown("### 📊 Attendance Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    metrics = [
        ("Total Staff", "0"),
        ("Daily Attendance", "0%"),
        ("On-Time Rate", "0%"),
        ("Avg Sign-Ins", "0.0"),
        ("Total Sign-Ins", "0")
    ]
    
    for col, (label, value) in zip([col1, col2, col3, col4, col5], metrics):
        with col:
            st.metric(label=label, value=value)

# ================== FOOTER ==================
st.markdown("---")
st.caption("Staff Attendance Dashboard | Upload files to analyze attendance patterns and identify improvement areas")
