import os
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Home Energy Performance Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Energy Asset Cost & ROI Comparison")

ANALYSIS_FILE = os.path.join("data", "analysis.csv")
SREC_FILE = os.path.join("data", "srec_history.csv")

if not os.path.exists(ANALYSIS_FILE):
    st.error(f"Missing Critical Core File: '{ANALYSIS_FILE}' was not found. Please run your backend analysis pipeline first.")
    st.stop()

if not os.path.exists(SREC_FILE):
    st.error(f"Missing Critical Core File: '{SREC_FILE}' was not found. Please verify your SREC transaction logs exist.")
    st.stop()

df = pd.read_csv(ANALYSIS_FILE)
srec_df = pd.read_csv(SREC_FILE)

df['timestamp'] = pd.to_datetime(df['timestamp'])
srec_df['date'] = pd.to_datetime(srec_df['date'])

months = df['timestamp'].dt.strftime('%b %Y')

cost_columns = {
    'baseline_cost': 'Baseline ($)',
    'solar_only_net_cost': 'Solar Only ($)',
    'battery_only_import_cost': 'Battery Only ($)',
    'solar_battery_net_cost': 'Solar + Battery ($)'
}

monthly_costs = df.groupby(months)[list(cost_columns.keys())].sum()
monthly_costs = monthly_costs.reindex(months.unique())
monthly_costs = monthly_costs.rename(columns=cost_columns)

base_total = monthly_costs['Baseline ($)'].sum()
solar_total = monthly_costs['Solar Only ($)'].sum()
battery_total = monthly_costs['Battery Only ($)'].sum()
solar_battery_total = monthly_costs['Solar + Battery ($)'].sum()

solar_pct_diff = ((solar_total - base_total) / base_total) * 100 if base_total else 0
battery_pct_diff = ((battery_total - base_total) / base_total) * 100 if base_total else 0
solar_battery_pct_diff = ((solar_battery_total - base_total) / base_total) * 100 if base_total else 0

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
annual_srec_income = srec_df[srec_df['date'].dt.year == 2025]['total_sales'].sum()
total_lifetime_srec = srec_df['total_sales'].sum()
st.subheader("💰 Investment & Payback Analysis (ROI)")
st.markdown(f"Based on net upfront system costs: **$22,000 for Solar** and **$18,000 for Batteries**. *(Includes **${annual_srec_income:.2f}** in 2025 SREC Cash Revenue)*")

savings_solar = (base_total - solar_total) + annual_srec_income
savings_battery = base_total - battery_total
savings_solar_battery = (base_total - solar_battery_total) + annual_srec_income
payback_solar = 22000.0 / savings_solar if savings_solar > 0 else 0.0
payback_battery = 18000.0 / savings_battery if savings_battery > 0 else 0.0
payback_solar_battery = 40000.0 / savings_solar_battery if savings_solar_battery > 0 else 0.0

st.markdown("#### ☀️ Solar Only Track")
r1_c1, r1_col2, r1_col3 = st.columns(3)
r1_c1.metric("Net Upfront Investment", "$22,000.00")
r1_col2.metric("Annualized Financial Return", f"${savings_solar:,.2f}")
r1_col3.metric("Estimated Payback Window", f"{payback_solar:.1f} Years" if payback_solar else "No Payback")

st.markdown("#### 🔋 Battery Only Track")
r2_c1, r2_col2, r2_col3 = st.columns(3)
r2_c1.metric("Net Upfront Investment", "$18,000.00")
r2_col2.metric("Annualized Financial Return", f"${savings_battery:,.2f}")
r2_col3.metric("Estimated Payback Window", f"{payback_battery:.1f} Years" if payback_battery else "No Payback")

st.markdown("#### ⚡ Solar + Battery Combination")
r3_c1, r3_col2, r3_col3 = st.columns(3)
r3_c1.metric("Net Upfront Investment", "$40,000.00")
r3_col2.metric("Annualized Financial Return", f"${savings_solar_battery:,.2f}")
r3_col3.metric("Estimated Payback Window", f"{payback_solar_battery:.1f} Years" if payback_solar_battery else "No Payback")

st.divider()
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
st.subheader("📅 Monthly Cost Breakdown")
st.dataframe(monthly_costs.style.format("${:.2f}"), use_container_width=True)

st.divider()
st.subheader("📈 Monthly Cost Trajectory")
st.markdown("Track and compare how your utility bills fluctuate over time across each setup.")
st.line_chart(monthly_costs, height=400)
