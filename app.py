import streamlit as st
import plotly.express as px
import pandas as pd
from engine import load_energy_data, apply_tariffs, calculate_actual_bill, summarize_actual_vs_baseline

st.set_page_config(page_title="Belmont Energy Monitor", layout="wide")

st.title("Belmont Energy: Baseline vs. Actual Bill")

@st.cache_data
def get_processed_data():
    df = load_energy_data()
    if not df.empty:
        df = apply_tariffs(df)
        df = calculate_actual_bill(df)
    return df

df = get_processed_data()

if df.empty:
    st.warning("No interval data loaded in SQLite database yet.")
else:
    summary = summarize_actual_vs_baseline(df)

    # Executive Summary Metrics
    st.markdown("### 💰 Baseline vs. Actual Bill Comparison")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Baseline TOU Cost", f"${summary['baseline_cost']:,.2f}")
    c2.metric("Actual Net Bill", f"${summary['actual_net_cost']:,.2f}")
    c3.metric("Total Net Savings", f"${summary['total_savings']:,.2f}", delta=f"{summary['savings_pct']:.1f}% Savings")

    # Financial Breakdown
    st.markdown("---")
    st.markdown("### 📊 Actual Bill Financial Breakdown")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Gross Import Cost", f"${summary['actual_import_cost']:,.2f}", f"{summary['imported_kwh']:,.1f} kWh Imported")
    col2.metric("Export Credits Earned", f"${summary['actual_export_credit']:,.2f}", f"{summary['exported_kwh']:,.1f} kWh Exported")
    col3.metric("Net Grid Bill", f"${summary['actual_net_cost']:,.2f}")

    # Daily Net Import vs Export Chart
    st.markdown("---")
    st.subheader("Daily Grid Activity (Import vs. Export)")

    df['Date'] = df['Date/Time'].dt.date
    daily_df = df.groupby('Date')[['Imported_kWh', 'Exported_kWh']].sum().reset_index()

    daily_melted = pd.melt(
        daily_df, 
        id_vars=['Date'], 
        value_vars=['Imported_kWh', 'Exported_kWh'],
        var_name='Grid Activity', 
        value_name='kWh'
    )
    daily_melted['Grid Activity'] = daily_melted['Grid Activity'].map({
        'Imported_kWh': 'Grid Import',
        'Exported_kWh': 'Grid Export'
    })

    fig = px.bar(
        daily_melted,
        x="Date",
        y="kWh",
        color="Grid Activity",
        color_discrete_map={"Grid Import": "#EF553B", "Grid Export": "#00CC96"},
        title="Daily Grid Imports vs Exports (kWh)",
        barmode="group"
    )

    st.plotly_chart(fig, use_container_width=True)
