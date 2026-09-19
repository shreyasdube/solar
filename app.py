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

    st.subheader("📅 Monthly Cost Breakdown")
    st.dataframe(monthly_costs, use_container_width=True)

    st.divider()

    st.subheader("📊 Configuration Savings Comparison")
    st.bar_chart(monthly_costs, height=350)

