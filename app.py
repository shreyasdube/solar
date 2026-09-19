import os
import pandas as pd
import streamlit as st

st.title("⚡ Energy Asset Cost Comparison")

FILE_PATH = os.path.join("data", "analysis.csv")

if not os.path.exists(FILE_PATH):
    st.error(f"File not found at {FILE_PATH}. Run analysis.py first.")
else:
    df = pd.read_csv(FILE_PATH)
    
    months = pd.to_datetime(df['timestamp']).dt.strftime('%b %Y')
    
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

    # Formula: ((Asset Total - Baseline Total) / Baseline Total) * 100
    solar_pct_diff = ((solar_total - base_total) / base_total) * 100 if base_total else 0
    battery_pct_diff = ((battery_total - base_total) / base_total) * 100 if base_total else 0
    solar_battery_pct_diff = ((solar_battery_total - base_total) / base_total) * 100 if base_total else 0

    st.subheader("📊 Total Cumulative Costs")
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
    st.subheader("💰 Investment & Payback Analysis (ROI)")
    st.markdown("Based on net upfront system costs: **$22,000 for Solar** and **$18,000 for Batteries**.")

    savings_solar = base_total - solar_total
    savings_battery = base_total - battery_total
    savings_solar_battery = base_total - solar_battery_total

    payback_solar = 22000.0 / savings_solar
    payback_battery = 18000.0 / savings_battery
    payback_solar_battery = 40000.0 / savings_solar_battery

    st.markdown("### ☀️ Solar Only Track")
    r1_col1, r1_col2, r1_col3 = st.columns(3)
    r1_col1.metric("Net Upfront Investment", "$22,000.00")
    r1_col2.metric("Annual Bill Savings", f"${savings_solar:,.2f}")
    r1_col3.metric("Estimated Payback Window", f"{payback_solar:.1f} Years" if payback_solar else "No Payback")

    st.markdown("### 🔋 Battery Only Track")
    r2_col1, r2_col2, r2_col3 = st.columns(3)
    r2_col1.metric("Net Upfront Investment", "$18,000.00")
    r2_col2.metric("Annual Bill Savings", f"${savings_battery:,.2f}")
    r2_col3.metric("Estimated Payback Window", f"{payback_battery:.1f} Years" if payback_battery else "No Payback")

    st.markdown("### ⚡ Solar + Battery Combination")
    r3_col1, r3_col2, r3_col3 = st.columns(3)
    r3_col1.metric("Net Upfront Investment", "$40,000.00")
    r3_col2.metric("Annual Bill Savings", f"${savings_solar_battery:,.2f}")
    r3_col3.metric("Estimated Payback Window", f"{payback_solar_battery:.1f} Years" if payback_solar_battery else "No Payback")

    st.divider()
    st.subheader("📅 Monthly Cost Breakdown")
    st.dataframe(monthly_costs, use_container_width=True)

    st.divider()
    st.subheader("📈 Monthly Cost Trajectory")
    st.markdown("Track and compare how your utility bills fluctuate over time across each setup.")
    st.line_chart(monthly_costs, height=400)
