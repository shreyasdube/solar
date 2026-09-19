import os
import pandas as pd
import streamlit as st

# 1. Page Configuration Setup
st.set_page_config(
    page_title="Home Energy Performance Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Energy Asset Cost & ROI Comparison")

# Establish exact data paths
ANALYSIS_FILE = os.path.join("data", "analysis.csv")
SREC_FILE = os.path.join("data", "srec_history.csv")

# Hard-Fail Validation Checks for Source Content Files
if not os.path.exists(ANALYSIS_FILE):
    st.error(f"Missing Critical Core File: '{ANALYSIS_FILE}' was not found. Please run your backend analysis pipeline first.")
    st.stop()

if not os.path.exists(SREC_FILE):
    st.error(f"Missing Critical Core File: '{SREC_FILE}' was not found. Please verify your SREC transaction logs exist.")
    st.stop()

# Load Source Datasets
df = pd.read_csv(ANALYSIS_FILE)
srec_df = pd.read_csv(SREC_FILE)

df['timestamp'] = pd.to_datetime(df['timestamp'])
srec_df['date'] = pd.to_datetime(srec_df['date'])

# 2. Sidebar Interactive Price Tuning Controls
st.sidebar.header("🎛️ System Cost Inputs ($)")
st.sidebar.markdown("Adjust net upfront pricing after incentives to dynamically compute system payback windows.")

solar_cost_input = st.sidebar.number_input(
    label="☀️ Solar Array System Cost ($)",
    min_value=0.0,
    value=22000.00,
    step=500.00,
    format="%.2f"
)

battery_cost_input = st.sidebar.number_input(
    label="🔋 Battery Storage System Cost ($)",
    min_value=0.0,
    value=18000.00,
    step=500.00,
    format="%.2f"
)

# Derived Combined Threshold
solar_battery_cost_input = solar_cost_input + battery_cost_input

# =====================================================================
# FIXED SECTION 3: Process Monthly Cost Streams with True Datetimes
# =====================================================================
# Cleanly truncate timestamps to the start of each month as actual datetime values
df['month_date'] = df['timestamp'].dt.to_period('M').dt.to_timestamp()

cost_columns = {
    'baseline_cost': 'Baseline ($)',
    'solar_only_net_cost': 'Solar Only ($)',
    'battery_only_import_cost': 'Battery Only ($)',
    'solar_battery_net_cost': 'Solar + Battery ($)'
}

# Group data by the true datetime column and sort chronologically
monthly_costs = df.groupby('month_date')[list(cost_columns.keys())].sum().sort_index()

# Calculate Global Lifetime Totals from the datetime-sorted framework
base_total = monthly_costs['baseline_cost'].sum()
solar_total = monthly_costs['solar_only_net_cost'].sum()
battery_total = monthly_costs['battery_only_import_cost'].sum()
solar_battery_total = monthly_costs['solar_battery_net_cost'].sum()

# Rename columns to user-friendly titles
monthly_costs = monthly_costs.rename(columns=cost_columns)

# Compute Comparative Efficiency Delta Percentages vs Baseline Benchmark
solar_pct_diff = ((solar_total - base_total) / base_total) * 100 if base_total else 0
battery_pct_diff = ((battery_total - base_total) / base_total) * 100 if base_total else 0
solar_battery_pct_diff = ((solar_battery_total - base_total) / base_total) * 100 if base_total else 0

# 4. Render Core Total Cumulative Cost Interface Cards
st.subheader("📊 Total Cumulative Utility Bills")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Baseline Total", value=f"${base_total:,.2f}")
with col2:
    st.metric(label="Solar Only Total", value=f"${solar_total:,.2f}", delta=f"{solar_pct_diff:.1f}% vs baseline", delta_color="inverse")
with col3:
    st.metric(label="Battery Only Total", value=f"${battery_total:,.2f}", delta=f"{battery_pct_diff:.1f}% vs baseline", delta_color="inverse")
with col4:
    st.metric(label="Solar + Battery Total", value=f"${solar_battery_total:,.2f}", delta=f"{solar_battery_pct_diff:.1f}% vs baseline", delta_color="inverse")

st.divider()

# 5. Process SREC Payout Fields & Multi-Year Scale
total_lifetime_srec = srec_df['total_sales'].sum()

# Calculate total unique calendar days inside the dataset pool to handle partial or overlapping years
total_days = df['timestamp'].dt.date.nunique()
years_span = total_days / 365.25

# Smooth total raw utility cost savings inside the active file pool
total_savings_solar = base_total - solar_total
total_savings_battery = base_total - battery_total
total_savings_solar_battery = base_total - solar_battery_total

# Annualize utility savings down to a standardized 365.25-day index rate
annualized_savings_solar = (total_savings_solar / total_days) * 365.25
annualized_savings_battery = (total_savings_battery / total_days) * 365.25
annualized_savings_solar_battery = (total_savings_solar_battery / total_days) * 365.25

# Normalize SREC cash income streams to an annualized rate relative to data timeline span
annual_srec_income = total_lifetime_srec / years_span if years_span > 0 else 0.0

# Add the SREC payouts back into your final annualized ROI track returns
roi_return_solar = annualized_savings_solar + annual_srec_income
roi_return_battery = annualized_savings_battery
roi_return_solar_battery = annualized_savings_solar_battery + annual_srec_income

# 6. Render Investment & Payback Analysis Track Metrics (ROI)
st.subheader("💰 Investment & Payback Analysis (ROI)")
st.markdown(f"Based on custom upfront system costs. Returns annualized dynamically across **{years_span:.2f} Years** of data. *(Includes an annualized rate of **\${annual_srec_income:,.2f}/yr** in SREC cash revenue)*")

# Calculate payback timelines safely using annualized values
payback_solar = solar_cost_input / roi_return_solar if roi_return_solar > 0 else 0.0
payback_battery = battery_cost_input / roi_return_battery if roi_return_battery > 0 else 0.0
payback_solar_battery = solar_battery_cost_input / roi_return_solar_battery if roi_return_solar_battery > 0 else 0.0

# Compact 3-Column horizontal data matrix block layout
track_col1, track_col2, track_col3 = st.columns(3)
with track_col1:
    st.markdown("#### ☀️ Solar Only Track")
    st.metric("Net Upfront Cost", f"${solar_cost_input:,.2f}")
    st.metric("Annualized Return", f"${roi_return_solar:,.2f}")
    st.metric("Payback Window", f"{payback_solar:.1f} Years" if payback_solar else "No Payback")
with track_col2:
    st.markdown("#### 🔋 Battery Only Track")
    st.metric("Net Upfront Cost", f"${battery_cost_input:,.2f}")
    st.metric("Annualized Return", f"${roi_return_battery:,.2f}")
    st.metric("Payback Window", f"{payback_battery:.1f} Years" if payback_battery else "No Payback")
with track_col3:
    st.markdown("#### ⚡ Solar + Battery Combo")
    st.metric("Net Upfront Cost", f"${solar_battery_cost_input:,.2f}")
    st.metric("Annualized Return", f"${roi_return_solar_battery:,.2f}")
    st.metric("Payback Window", f"{payback_solar_battery:.1f} Years" if payback_solar_battery else "No Payback")

st.divider()

# =====================================================================
# FIXED SECTION 6b: Non-Sawtooth ROI Burndown Tracking (Datetime Axis)
# =====================================================================
st.subheader("📉 Investment Payback Burndown")
st.markdown("Track the real-time path to breaking even. This maps monthly utility savings and exact SREC payout dates against your custom setup cost.")

# Build matching dataframe mapped chronologically on true monthly datetime timestamps
burndown_df = pd.DataFrame(index=monthly_costs.index)

# 1. Calculate monthly operational savings
burndown_df['Utility Savings'] = monthly_costs['Baseline ($)'] - monthly_costs['Solar + Battery ($)']

# 2. Match exact SREC ledger entries chronologically using datetime conversion
srec_df['month_date'] = srec_df['date'].dt.to_period('M').dt.to_timestamp()
srec_monthly = srec_df.groupby('month_date')['total_sales'].sum()

burndown_df['SREC Revenue'] = srec_monthly.reindex(burndown_df.index, fill_value=0.0)

# 3. Calculate running recovery trajectory pools
burndown_df['Total Monthly Recovery'] = burndown_df['Utility Savings'] + burndown_df['SREC Revenue']
burndown_df['Unrecovered Balance ($)'] = solar_battery_cost_input - burndown_df['Total Monthly Recovery'].cumsum()

# Plot the clean, strictly chronological balance curve using datetime indices
st.bar_chart(burndown_df[['Unrecovered Balance ($)']], height=300)

st.divider()

# 7. Render SREC Ledger Visualization Row
st.subheader("📜 Solar Renewable Energy Certificates (SREC) Ledger")
srec_left, srec_right = st.columns([1, 2])

with srec_left:
    st.metric(label="Lifetime SREC Revenue Generated", value=f"${total_lifetime_srec:,.2f}")
    st.markdown("""
    **What is an SREC?**  
    For every **1,000 kWh (1 MWh)** of green electricity your solar array produces, you mint 1 certificate. 
    The utility company buys these from you at market auction prices to meet state clean energy mandates.
    """)

with srec_right:
    display_srec = srec_df.copy()
    display_srec['date'] = display_srec['date'].dt.strftime('%m/%d/%Y')
    display_srec = display_srec.rename(columns={
        'date': 'Transaction Date',
        'quantity': 'Certificates (SRECs)',
        'price': 'Auction Price ($)',
        'total_sales': 'Total Payout ($)'
    })
    st.dataframe(display_srec.style.format({
        'Auction Price ($)': '${:.2f}',
        'Total Payout ($)': '${:.2f}'
    }), use_container_width=True, hide_index=True)

st.divider()

# Convert the master table display series index to strings (e.g. "Jan 2025") ONLY for the text elements below
table_costs = monthly_costs.copy()
table_costs.index = table_costs.index.strftime('%b %Y')

# 8. Render Monthly Detailed Breakdown Data Table
st.subheader("📅 Monthly Cost Breakdown")
st.dataframe(table_costs.style.format("${:.2f}"), use_container_width=True)

st.divider()

# 9. Render Interactive Trajectory Graphic Chart Plot (Uses clean continuous datetime index)
st.subheader("📈 Monthly Cost Trajectory")
st.markdown("Track and compare how your utility bills fluctuate over time across each setup.")
st.line_chart(monthly_costs, height=400)
