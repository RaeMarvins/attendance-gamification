import streamlit as st
import pandas as pd
import datetime
from io import BytesIO

# ================== CONFIG ==================
st.set_page_config(
    page_title="Staff Attendance Dashboard",
    layout="wide"
)

# ================== HEADER ==================
st.title("Staff Attendance Dashboard")

# ================== KPI METRICS ==================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Total Staff",
        value="25",
    )

with col2:
    st.metric(
        label="Present Today",
        value="18",
    )

with col3:
    st.metric(
        label="Absent Today",
        value="7",
    )

with col4:
    st.metric(
        label="Avg Sign-Ins This Week",
        value="4.2",
    )

st.markdown("---")

# ================== WEEKLY SIGN-IN REPORT ==================
st.subheader("Weekly Sign-In Report")

# Create the table data
data = {
    "Employee Name": ["Sarah Johnson", "Michael Smith", "Emily Davis", 
                     "James Wilson", "Laura Brown", "Daniel Miller"],
    "Day": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Monday"],
    "Sign-In Time": ["8:45 AM", "9:00 AM", "8:35 AM", "9:15 AM", "8:50 AM", "8:40 AM"],
    "Total Sign-Ins (This Week)": ["✅ 5", "✅ 4", "✅ 6", "✅ 5", "✅ 4", "✅ 3"]
}

# Create DataFrame
df = pd.DataFrame(data)

# Display the table
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Employee Name": st.column_config.TextColumn("Employee Name"),
        "Day": st.column_config.TextColumn("Day"),
        "Sign-In Time": st.column_config.TextColumn("Sign-In Time"),
        "Total Sign-Ins (This Week)": st.column_config.TextColumn("Total Sign-Ins (This Week)")
    }
)

# Show pagination info
st.caption("Showing 1 to 6 of 6 entries")
