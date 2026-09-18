import streamlit as st
import plotly.express as px
import pandas as pd
from engine import (
    load_energy_data,
    summarize_actual_vs_baseline,
    load_srec_data,
)

st.set_page_config(page_title="Belmont Energy Monitor", layout="wide")
st.title("Belmont Energy: Baseline vs. Solar vs. Battery Simulation")

@st.cache_data
def get_processed_data():
    df = load_energy_data()
    return df

df = get_processed_data()

if df.empty:
    st.warning("No interval data loaded in SQLite database yet.")
else:
    # Rate coverage check
    unmatched_df = df[df['import_rate'].isna()]
    if not unmatched_df.empty:
        st.error(
            f"⚠️ **{len(unmatched_df)} interval records** have no matching tariff in `rates_schedule.csv`!"
        )

    # Compute overall and monthly summaries
    full_summary = summarize_actual_vs_baseline(df)
    total_srec_earned, annual_srec_earned, srec_df = load_srec_data()

    # Sidebar Month Filter
    st.sidebar.header("Filter Options")
    available_months = list(full_summary.get("monthly", {}).keys())
    
    selected_month = st.sidebar.selectbox(
        "Select Month", 
        ["All Months"] + available_months
    )

    if selected_month != "All Months":
        df_filtered = df[df['Date/Time'].dt.to_period('M').astype(str) == selected_month]
        summary = full_summary["monthly"][selected_month]
        timeframe_label = f"({selected_month})"
    else:
        df_filtered = df.copy()
        summary = full_summary["overall"]
        timeframe_label = "(All Months)"

    # 1. High Level Bill Summary Comparison
    st.markdown(f"### 💰 Financial Summary Comparison {timeframe_label}")
    c1, c2, c3, c4 = st.columns(4)
    
    c1.metric(
        "Baseline Cost (No Solar/Bat)",
        f"${summary['baseline_cost']:,.2f}",
        help="Estimated cost if 100% of consumption was imported from the grid with no solar or battery."
    )
    c2.metric(
        "Solar Only Net Cost",
        f"${summary['solar_only_net_cost']:,.2f}",
        delta=f"-${summary['solar_only_savings']:,.2f} vs Base",
        delta_color="inverse",
        help="Simulated cost with solar generation but no battery storage."
    )
    c3.metric(
        "Battery Only Net Cost",
        f"${summary['battery_only_net_cost']:,.2f}",
        delta=f"-${summary['battery_only_savings']:,.2f} vs Base",
        delta_color="inverse",
        help="Simulated cost with battery arbitrage only and no solar generation."
    )
    c4.metric(
        "Solar + Battery Net Cost",
        f"${summary['actual_net_cost']:,.2f}",
        delta=f"-${summary['total_savings']:,.2f} vs Base",
        delta_color="inverse",
        help="Actual cost with both solar generation and your Enphase battery system."
    )

    # 2. Detailed Scenario Breakdown Tabs
    st.markdown("---")
    tab_actual, tab_solar_only, tab_battery_only, tab_roi, tab_srec = st.tabs([
        "🔋 Solar + Battery (Actual)",
        "☀️ Solar Only (Simulation)",
        "⚡ Battery Only (Simulation)",
        "📈 ROI & Payback Analysis",
        "📜 SREC Credits & Revenue"
    ])

    with tab_actual:
        st.subheader(f"Solar + Battery Performance Breakdown {timeframe_label}")
        col_pa1, col_pa2 = st.columns(2)
        with col_pa1:
            st.markdown("🔴 **On-Peak Summary**")
            st.metric("Grid Import", f"{summary['peak_import_kwh']:,.1f} kWh", f"${summary['peak_import_cost']:,.2f}")
            st.metric("Solar Export", f"{summary['peak_export_kwh']:,.1f} kWh", f"-${summary['peak_export_credit']:,.2f}")
        with col_pa2:
            st.markdown("🔵 **Off-Peak Summary**")
            st.metric("Grid Import", f"{summary['offpeak_import_kwh']:,.1f} kWh", f"${summary['offpeak_import_cost']:,.2f}")
            st.metric("Solar Export", f"{summary['offpeak_export_kwh']:,.1f} kWh", f"-${summary['offpeak_export_credit']:,.2f}")

    with tab_solar_only:
        st.subheader(f"Solar-Only (No Battery) Simulation Breakdown {timeframe_label}")
        col_so1, col_so2 = st.columns(2)
        with col_so1:
            st.markdown("🔴 **On-Peak Summary (Solar Only)**")
            st.metric("Grid Import", f"{summary['peak_so_import_kwh']:,.1f} kWh", f"${summary['peak_so_import_cost']:,.2f}")
            st.metric("Solar Export", f"{summary['peak_so_export_kwh']:,.1f} kWh", f"-${summary['peak_so_export_credit']:,.2f}")
        with col_so2:
            st.markdown("🔵 **Off-Peak Summary (Solar Only)**")
            st.metric("Grid Import", f"{summary['offpeak_so_import_kwh']:,.1f} kWh", f"${summary['offpeak_so_import_cost']:,.2f}")
            st.metric("Solar Export", f"{summary['offpeak_so_export_kwh']:,.1f} kWh", f"-${summary['offpeak_so_export_credit']:,.2f}")

    with tab_battery_only:
        st.subheader(f"Battery-Only (Arbitrage) Simulation Breakdown {timeframe_label}")
        col_bo1, col_bo2 = st.columns(2)
        with col_bo1:
            st.markdown("🔴 **On-Peak Summary (Battery Only)**")
            st.metric("Grid Import", f"{summary['peak_bo_import_kwh']:,.1f} kWh", f"${summary['peak_bo_import_cost']:,.2f}")
        with col_bo2:
            st.markdown("📈 **Standalone Battery Economics**")
            st.metric("Arbitrage Savings vs Base", f"${summary['battery_only_savings']:,.2f}")
            st.metric("Estimated Battery-Only ROI", f"{summary['battery_only_roi_pct']:.2f}% / year")
            st.metric("Simple Payback Period", f"{summary['battery_only_payback_yrs']:.1f} Years")

    with tab_roi:
        st.subheader("Financial Return on Investment (ROI) & Simple Payback")
        st.caption("✨ Note: ROI and Payback calculations include both utility bill savings and SREC renewable certificate earnings.")
        
        r1, r2, r3 = st.columns(3)
        r1.metric("Solar-Only Payback", f"{summary['solar_payback_yrs']:.1f} Years", f"{summary['solar_roi_pct']:.2f}% ROI")
        r2.metric("Battery-Only Payback", f"{summary['battery_only_payback_yrs']:.1f} Years", f"{summary['battery_only_roi_pct']:.2f}% ROI")
        r3.metric("Combined System Payback", f"{summary['combined_payback_yrs']:.1f} Years", f"{summary['combined_roi_pct']:.2f}% ROI")
        
        st.caption("Based on default system capital cost estimates in `engine.py` + SRECs.")

    with tab_srec:
        st.subheader("Solar Renewable Energy Certificate (SREC) Tracking")
        s1, s2, s3 = st.columns(3)
        s1.metric("Total SREC Revenue Earned", f"${total_srec_earned:,.2f}")
        s2.metric("Total RECs Sold", f"{srec_df['quantity'].sum() if not srec_df.empty else 0:,.1f}")
        s3.metric("Annualized SREC Rate", f"${annual_srec_earned:,.2f} / year")

        if not srec_df.empty:
            st.dataframe(srec_df, use_container_width=True)
        else:
            st.info("No `srec_history.csv` data found.")
