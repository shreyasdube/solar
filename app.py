import streamlit as st
import plotly.express as px
import pandas as pd
from engine import load_energy_data, apply_tariffs, calculate_actual_bill, summarize_actual_vs_baseline

st.set_page_config(page_title="Belmont Energy Monitor", layout="wide")

st.title("Belmont Energy: Baseline vs. Actual Bill Monitor")

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
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Baseline TOU Cost", f"${summary['baseline_cost']:,.2f}")
    c2.metric("Actual Net Grid Bill", f"${summary['actual_net_cost']:,.2f}")
    c3.metric("Total Solar + Battery Savings", f"${summary['total_savings']:,.2f}", delta=f"{summary['savings_pct']:.1f}% Savings")
    c4.metric("Grid Import Reduction", f"{summary['consumed_kwh'] - summary['imported_kwh']:,.1f} kWh")

    # Generation & Storage Overview
    st.markdown("---")
    st.markdown("### ⚡ Solar & Battery Performance Summary")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Solar Produced", f"{summary['produced_kwh']:,.1f} kWh")
    col2.metric("Battery Discharged", f"{summary['battery_discharged_kwh']:,.1f} kWh")
    col3.metric("Exported to Grid", f"{summary['exported_kwh']:,.1f} kWh")

    # Daily Stacked Bar Chart - Net Grid Import vs Solar/Battery Contribution
    st.markdown("---")
    st.subheader("Daily Energy Source Breakdown")

    df['Date'] = df['Date/Time'].dt.date
    daily_df = df.groupby('Date')[['Imported_kWh', 'Produced_kWh', 'Battery_Discharge_kWh']].sum().reset_index()

    daily_melted = pd.melt(
        daily_df, 
        id_vars=['Date'], 
        value_vars=['Imported_kWh', 'Produced_kWh', 'Battery_Discharge_kWh'],
        var_name='Source', 
        value_name='kWh'
    )
    daily_melted['Source'] = daily_melted['Source'].map({
        'Imported_kWh': 'Grid Import',
        'Produced_kWh': 'Solar Production',
        'Battery_Discharge_kWh': 'Battery Discharge'
    })

    fig = px.bar(
        daily_melted,
        x="Date",
        y="kWh",
        color="Source",
        color_discrete_map={"Grid Import": "#EF553B", "Solar Production": "#FECB52", "Battery Discharge": "#00CC96"},
        title="Daily Consumption Supply Sources (kWh)",
        barmode="stack"
    )

    st.plotly_chart(fig, use_container_width=True)
