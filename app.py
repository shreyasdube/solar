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
    
    st.subheader("📊 Total Cumulative Costs")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(label="Baseline Total", value=f"${monthly_costs['Baseline ($)'].sum():,.2f}")
    with col2:
        st.metric(label="Solar Only Total", value=f"${monthly_costs['Solar Only ($)'].sum():,.2f}")
    with col3:
        st.metric(label="Battery Only Total", value=f"${monthly_costs['Battery Only ($)'].sum():,.2f}")
    with col4:
        st.metric(label="Solar + Battery Total", value=f"${monthly_costs['Solar + Battery ($)'].sum():,.2f}")
        
    st.divider()

    st.subheader("📅 Monthly Cost Breakdown")
    st.dataframe(monthly_costs, use_container_width=True)
