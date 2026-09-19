import os
import pandas as pd
import streamlit as st

st.title("⚡ Energy Asset Cost Comparison")

FILE_PATH = os.path.join("data", "analysis.csv")

if not os.path.exists(FILE_PATH):
    st.error(f"File not found at {FILE_PATH}. Run analysis.py first.")
else:
    # 1. Load data
    df = pd.read_csv(FILE_PATH)
    
    # 2. Group by month name (e.g., 'Jan 2025')
    months = pd.to_datetime(df['timestamp']).dt.strftime('%b %Y')
    
    cost_columns = {
        'baseline_cost': 'Baseline ($)',
        'solar_only_net_cost': 'Solar Only ($)',
        'battery_only_import_cost': 'Battery Only ($)',
        'solar_battery_net_cost': 'Solar + Battery ($)'
    }
    
    # 3. Sum up the costs chronologically
    monthly_costs = df.groupby(months)[list(cost_columns.keys())].sum()
    monthly_costs = monthly_costs.reindex(months.unique())
    monthly_costs = monthly_costs.rename(columns=cost_columns)
    
    # 4. Show the table in the UI
    st.dataframe(monthly_costs)
