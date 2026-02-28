def compare_staff_lists(attendance_df, staff_list_df):
    """Compare attendance data with master staff list to identify non-attending staff"""
    if attendance_df.empty or staff_list_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 0
    
    # Clean names for comparison (uppercase and strip)
    attendance_df['name_clean'] = attendance_df['name'].astype(str).str.strip().str.upper()
    staff_list_df['name_clean'] = staff_list_df['name'].astype(str).str.strip().str.upper()
    
    # Find staff who have signed in on weekdays
    weekday_df = attendance_df[attendance_df['is_weekday']]
    attending_staff = weekday_df['name_clean'].unique()
    
    # Find all staff in master list
    all_staff = staff_list_df['name_clean'].unique()
    
    # Identify non-attending staff
    non_attending_mask = ~staff_list_df['name_clean'].isin(attending_staff)
    non_attending_staff = staff_list_df[non_attending_mask].copy()
    
    # Get attending staff details from master list
    attending_mask = staff_list_df['name_clean'].isin(attending_staff)
    attending_from_master = staff_list_df[attending_mask].copy()
    
    # Get staff who signed in but not in master list (potential new staff)
    all_attendance_names = set(attendance_df['name_clean'].unique())
    all_staff_set = set(staff_list_df['name_clean'].unique())
    attendance_only_names = all_attendance_names - all_staff_set
    attendance_only_staff = attendance_df[attendance_df['name_clean'].isin(attendance_only_names)][['name', 'department']].drop_duplicates()
    
    # Get period length in weekdays for attendance rate calculation
    min_date = attendance_df['date'].min().date()
    max_date = attendance_df['date'].max().date()
    expected_days = count_weekdays(min_date, max_date)
    
    # Merge attendance data (weekday only) with master list for analysis
    weekday_stats = weekday_df.groupby('name_clean').agg({
        'sign_in_time': 'count',
        'on_time': 'sum',
        'late': 'sum'
    }).reset_index()
    
    merged_df = pd.merge(
        staff_list_df,
        weekday_stats,
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
    
    # Calculate attendance rate (based on weekdays)
    merged_df['attendance_rate'] = round((merged_df['total_days'] / expected_days) * 100, 1) if expected_days > 0 else 0
    
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
