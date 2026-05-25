import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# Page config
st.set_page_config(
    page_title="Qomplement Dashboard",
    page_icon="📄",
    layout="wide"
)

# Custom CSS for better look
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Title
st.title("📄 Qomplement AI Agent Dashboard")
st.caption("Real-time invoice processing dashboard")

# Connect to database
@st.cache_data(ttl=60)
def load_data():
    conn = sqlite3.connect('qomplement.db')
    
    # Load invoices
    invoices_df = pd.read_sql_query("""
        SELECT id, invoice_number, vendor_name, invoice_date, 
               total_amount, source_file, extracted_at, status
        FROM invoices 
        ORDER BY id DESC
    """, conn)
    
    # Load line items
    items_df = pd.read_sql_query("""
        SELECT li.*, i.invoice_number, i.vendor_name
        FROM line_items li
        JOIN invoices i ON li.invoice_id = i.id
    """, conn)
    
    # Load logs
    logs_df = pd.read_sql_query("""
        SELECT * FROM processing_logs 
        ORDER BY id DESC 
        LIMIT 100
    """, conn)
    
    conn.close()
    return invoices_df, items_df, logs_df

# Load data
invoices_df, items_df, logs_df = load_data()

# ==================== METRICS ROW ====================
st.subheader("📊 Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Invoices", len(invoices_df))

with col2:
    total_value = invoices_df['total_amount'].sum() if not invoices_df.empty else 0
    st.metric("Total Value", f"${total_value:,.2f}")

with col3:
    unique_vendors = invoices_df['vendor_name'].nunique() if not invoices_df.empty else 0
    st.metric("Unique Vendors", unique_vendors)

with col4:
    total_items = len(items_df) if not items_df.empty else 0
    st.metric("Line Items Processed", total_items)

# ==================== CHARTS ROW ====================
col1, col2 = st.columns(2)

with col1:
    st.subheader("💰 Total by Vendor")
    if not invoices_df.empty:
        vendor_total = invoices_df.groupby('vendor_name')['total_amount'].sum().reset_index()
        fig = px.bar(vendor_total, x='vendor_name', y='total_amount', 
                     title="Invoice Value by Vendor",
                     color_discrete_sequence=['#2E86AB'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data yet")

with col2:
    st.subheader("📅 Invoices Over Time")
    if not invoices_df.empty and invoices_df['invoice_date'].notna().any():
        # Convert to datetime and group by month
        invoices_df['invoice_date'] = pd.to_datetime(invoices_df['invoice_date'])
        monthly = invoices_df.groupby(invoices_df['invoice_date'].dt.to_period('M')).size().reset_index()
        monthly.columns = ['Month', 'Count']
        monthly['Month'] = monthly['Month'].astype(str)
        fig = px.line(monthly, x='Month', y='Count', 
                      title="Invoices per Month",
                      markers=True,
                      color_discrete_sequence=['#A23B72'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No date data yet")

# ==================== RECENT INVOICES TABLE ====================
st.subheader("📋 Recent Invoices")

if not invoices_df.empty:
    # Add filter
    col1, col2 = st.columns(2)
    with col1:
        vendor_filter = st.multiselect(
            "Filter by Vendor",
            options=invoices_df['vendor_name'].unique(),
            default=[]
        )
    
    with col2:
        status_filter = st.multiselect(
            "Filter by Status",
            options=invoices_df['status'].unique() if 'status' in invoices_df.columns else ['processed'],
            default=[]
        )
    
    # Apply filters
    filtered_df = invoices_df.copy()
    if vendor_filter:
        filtered_df = filtered_df[filtered_df['vendor_name'].isin(vendor_filter)]
    if status_filter:
        filtered_df = filtered_df[filtered_df['status'].isin(status_filter)]
    
    # Display table
    display_cols = ['invoice_number', 'vendor_name', 'total_amount', 'invoice_date', 'status']
    available_cols = [col for col in display_cols if col in filtered_df.columns]
    
    st.dataframe(
        filtered_df[available_cols].head(20),
        use_container_width=True,
        column_config={
            "total_amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
            "invoice_date": st.column_config.DateColumn("Date"),
        }
    )
else:
    st.info("No invoices in database yet")

# ==================== LINE ITEMS ====================
if not items_df.empty:
    st.subheader("📦 Recent Line Items")
    st.dataframe(
        items_df[['invoice_number', 'vendor_name', 'description', 'quantity', 'unit_price']].head(10),
        use_container_width=True,
        column_config={
            "unit_price": st.column_config.NumberColumn("Unit Price", format="$%.2f"),
            "quantity": st.column_config.NumberColumn("Qty", format="%.0f"),
        }
    )

# ==================== PROCESSING LOGS ====================
st.subheader("📝 Processing Logs")

if not logs_df.empty:
    # Color status badges
    def color_status(status):
        colors = {
            'success': 'green',
            'failed': 'red',
            'skipped': 'orange'
        }
        return colors.get(status, 'gray')
    
    logs_display = logs_df[['created_at', 'source_file', 'action', 'status', 'error_message']].head(20)
    st.dataframe(logs_display, use_container_width=True)
else:
    st.info("No logs yet")

# ==================== SIDEBAR ====================
with st.sidebar:
    st.image("https://placehold.co/200x60?text=Qomplement", use_container_width=False)
    st.markdown("---")
    
    st.subheader("ℹ️ System Status")
    
    # Database size
    import os
    if os.path.exists('qomplement.db'):
        db_size = os.path.getsize('qomplement.db') / 1024
        st.metric("Database Size", f"{db_size:.1f} KB")
    
    st.markdown("---")
    st.caption("AI Agent Processing Pipeline")
    st.caption("✅ Gmail Integration")
    st.caption("✅ PDF Classification")
    st.caption("✅ Data Extraction")
    st.caption("✅ Database Storage")
    
    st.markdown("---")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# Auto-refresh every 30 seconds
st.markdown("""
    <meta http-equiv="refresh" content="30">
""", unsafe_allow_html=True)