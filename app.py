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

# 3. Process Monthly Utility Cost Streams
months = df['timestamp'].dt.strftime('%b %Y')

cost_columns = {
    'baseline_cost': 'Baseline ($)',
    'solar_only_net_cost': 'Solar Only ($)',
    'battery_only_import_cost': 'Battery Only ($)',
    'solar_battery_net_cost': 'Solar + Battery ($)'
}

# Group and aggregate data into unique chronological month rows
monthly_costs = df.groupby(months)[list(cost_columns.keys())].sum()
monthly_costs = monthly_costs.reindex(months.unique())
monthly_costs = monthly_costs.rename(columns=cost_columns)

# Calculate Global Full-Year Cumulative Totals
base_total = monthly_costs['Baseline ($)'].sum()
solar_total = monthly_costs['Solar Only ($)'].sum()
battery_total = monthly_costs['Battery Only ($)'].sum()
solar_battery_total = monthly_costs['Solar + Battery ($)'].sum()

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

# 5. Process SREC Payout Fields
annual_srec_income = srec_df[srec_df['date'].dt.year == 2025]['total_sales'].sum()
total_lifetime_srec = srec_df['total_sales'].sum()

# 6. Render Investment & Payback Analysis Track Metrics (ROI)
st.subheader("💰 Investment & Payback Analysis (ROI)")
st.markdown(f"Based on custom upfront system costs: **\${solar_cost_input:,.2f} for Solar** and **\${battery_cost_input:,.2f} for Batteries**. *(Includes **\${annual_srec_income:.2f}** in 2025 SREC Cash Revenue)*")

# Calculate net asset economics by factoring in bill reductions and SREC earnings splits
savings_solar = (base_total - solar_total) + annual_srec_income
savings_battery = base_total - battery_total
savings_solar_battery = (base_total - solar_battery_total) + annual_srec_income

payback_solar = solar_cost_input / savings_solar if savings_solar > 0 else 0.0
payback_battery = battery_cost_input / savings_battery if savings_battery > 0 else 0.0
payback_solar_battery = solar_battery_cost_input / savings_solar_battery if savings_solar_battery > 0 else 0.0

# Compact 3-Column horizontal data matrix block layout
track_col1, track_col2, track_col3 = st.columns(3)
with track_col1:
    st.markdown("#### ☀️ Solar Only Track")
    st.metric("Net Upfront Cost", f"${solar_cost_input:,.2f}")
    st.metric("Annualized Return", f"${savings_solar:,.2f}")
    st.metric("Payback Window", f"{payback_solar:.1f} Years" if payback_solar else "No Payback")
with track_col2:
    st.markdown("#### 🔋 Battery Only Track")
    st.metric("Net Upfront Cost", f"${battery_cost_input:,.2f}")
    st.metric("Annualized Return", f"${savings_battery:,.2f}")
    st.metric("Payback Window", f"{payback_battery:.1f} Years" if payback_battery else "No Payback")
with track_col3:
    st.markdown("#### ⚡ Solar + Battery Combo")
    st.metric("Net Upfront Cost", f"${solar_battery_cost_input:,.2f}")
    st.metric("Annualized Return", f"${savings_solar_battery:,.2f}")
    st.metric("Payback Window", f"{payback_solar_battery:.1f} Years" if payback_solar_battery else "No Payback")

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

# 8. Render Monthly Detailed Breakdown Data Table
st.subheader("📅 Monthly Cost Breakdown")
st.dataframe(monthly_costs.style.format("${:.2f}"), use_container_width=True)

st.divider()

# 9. Render Interactive Trajectory Graphic Chart Plot
st.subheader("📈 Monthly Cost Trajectory")
st.markdown("Track and compare how your utility bills fluctuate over time across each setup.")
st.line_chart(monthly_costs, height=400)
