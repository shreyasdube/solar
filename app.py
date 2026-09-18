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
    st.markdown("### Time-of-Use (TOU) Rate Verification")
    
    col_peak, col_offpeak = st.columns(2)
    
    peak_rates_str = ", ".join([f"${r:.5f}" for r in summary['peak_rates']]) if summary['peak_rates'] else "None"
    offpeak_rates_str = ", ".join([f"${r:.5f}" for r in summary['offpeak_rates']]) if summary['offpeak_rates'] else "None"

    with col_peak:
        st.markdown("🔴 **On-Peak**")
        st.metric("Peak Usage", f"{summary['peak_kwh']:,.1f} kWh")
        st.metric("Peak Cost", f"${summary['peak_cost']:,.2f}")
        st.caption(f"**Applied Tariff Rates:** {peak_rates_str}")

    with col_offpeak:
        st.markdown("🔵 **Off-Peak**")
        st.metric("Off-Peak Usage", f"{summary['offpeak_kwh']:,.1f} kWh")
        st.metric("Off-Peak Cost", f"${summary['offpeak_cost']:,.2f}")
        st.caption(f"**Applied Tariff Rates:** {offpeak_rates_str}")

    # Stacked Hourly Bar Chart
    st.markdown("---")
    st.subheader("Hourly Electricity Consumption (Peak vs. Off-Peak)")

    # Floor timestamps to hourly buckets while preserving rate window status
    df['Hourly_Timestamp'] = df['Date/Time'].dt.floor('h')
    df['Rate Window'] = df['is_peak'].map({True: 'On-Peak', False: 'Off-Peak'})

    # Aggregate 15-minute intervals into hourly sums per rate window
    hourly_df = (
        df.groupby(['Hourly_Timestamp', 'Rate Window'])['Consumed_kWh']
        .sum()
        .reset_index()
    )

    fig = px.bar(
        hourly_df,
        x="Hourly_Timestamp",
        y="Consumed_kWh",
        color="Rate Window",
        color_discrete_map={"On-Peak": "#EF553B", "Off-Peak": "#636efa"},
        title="Hourly Consumption Breakdown (kWh)",
        labels={"Consumed_kWh": "Consumption (kWh)", "Hourly_Timestamp": "Date & Time"},
        barmode="stack"
    )

    # Remove gaps between bars for clean rendering over multi-week spans
    fig.update_layout(bargap=0)

    st.plotly_chart(fig, use_container_width=True)
