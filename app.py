import streamlit as st
import plotly.express as px
import pandas as pd
from engine import load_energy_data, apply_tariffs, calculate_baseline, summarize_baseline

st.set_page_config(page_title="Belmont Energy Monitor", layout="wide")

st.title("Belmont Energy & TOU Baseline Monitor")

@st.cache_data
def get_processed_data():
    df = load_energy_data()
    if not df.empty:
        df = apply_tariffs(df)
        df = calculate_baseline(df)
    return df

df = get_processed_data()

if df.empty:
    st.warning("No interval data loaded in SQLite database yet.")
else:
    # Check for missing rate coverage
    unmatched_df = df[df['import_rate'].isna()]
    if not unmatched_df.empty:
        st.error(
            f"⚠️ **{len(unmatched_df)} interval records** have no matching tariff in `rates_schedule.csv`! "
            f"Missing dates from **{unmatched_df['Date/Time'].min().strftime('%Y-%m-%d')}** "
            f"to **{unmatched_df['Date/Time'].max().strftime('%Y-%m-%d')}**."
        )

    summary = summarize_baseline(df)

    # Executive Summary Metrics
    st.markdown("### Cost & Consumption Summary")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Consumption", f"{summary['total_kwh']:,.1f} kWh")
    c2.metric("Total Baseline Cost", f"${summary['total_cost']:,.2f}")
    c3.metric("Effective Avg Rate", f"${summary['effective_rate']:.3f} / kWh")

    # Peak vs Off-Peak Detailed Breakdown
    st.markdown("---")
    st.markdown("### Time-of-Use (TOU) Breakdown")
    
    col_peak, col_offpeak = st.columns(2)
    
    with col_peak:
        st.markdown("🔴 **On-Peak**")
        st.metric("Peak Usage", f"{summary['peak_kwh']:,.1f} kWh")
        st.metric("Peak Cost", f"${summary['peak_cost']:,.2f}")
        st.metric("Avg Peak Rate", f"${summary['peak_effective_rate']:.3f} / kWh")

    with col_offpeak:
        st.markdown("🔵 **Off-Peak**")
        st.metric("Off-Peak Usage", f"{summary['offpeak_kwh']:,.1f} kWh")
        st.metric("Off-Peak Cost", f"${summary['offpeak_cost']:,.2f}")
        st.metric("Avg Off-Peak Rate", f"${summary['offpeak_effective_rate']:.3f} / kWh")

    # Interactive Chart
    st.markdown("---")
    st.subheader("15-Minute Interval Usage")
    fig = px.line(
        df, 
        x="Date/Time", 
        y="Consumed_kWh", 
        color="is_peak",
        color_discrete_map={True: "red", False: "blue"},
        title="Consumption (Red = On-Peak Hours, Blue = Off-Peak Hours)",
        labels={"Consumed_kWh": "Consumption (kWh)", "is_peak": "Peak Window"}
    )
    st.plotly_chart(fig, use_container_width=True)
