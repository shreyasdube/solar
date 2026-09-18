import streamlit as st
import plotly.express as px
import pandas as pd
from engine import (
    load_energy_data,
    calculate_scenarios,
    summarize_actual_vs_baseline,
    load_srec_data,
)

st.set_page_config(page_title="Belmont Energy Monitor", layout="wide")

st.title("Belmont Energy: Baseline vs. Solar vs. Battery Simulation")

@st.cache_data
def get_processed_data():
    df = load_energy_data()
    if not df.empty:
        df = calculate_scenarios(df)
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
    st.sidebar.header("Filter View")
    available_months = list(full_summary.get('monthly', {}).keys())
    
    selected_month = st.sidebar.selectbox(
        "Select Timeframe:",
        options=["All Months"] + available_months,
        index=0
    )

    # Filter data and select target summary dictionary based on selection
    if selected_month != "All Months":
        df_filtered = df[df['Date/Time'].dt.to_period('M').astype(str) == selected_month].copy()
        summary = full_summary['monthly'][selected_month]
        timeframe_label = f"({selected_month})"
    else:
        df_filtered = df.copy()
        summary = full_summary
        timeframe_label = "(All Months)"

    # 1. High Level Bill Summary Comparison
    st.markdown(f"### 💰 Financial Summary Comparison {timeframe_label}")
    c1, c2, c3, c4 = st.columns(4)
    
    c1.metric(
        "Baseline Cost (No Solar)", 
        f"${summary['baseline_cost']:,.2f}",
        help="Estimated cost if 100% of consumption was imported from the grid with no solar or battery."
    )
    c2.metric(
        "Solar Only Net Cost", 
        f"${summary['solar_only_net_cost']:,.2f}",
        delta=f"-${summary['solar_only_savings']:,.2f} vs Base",
        delta_color="inverse",
        help="Simulated cost with solar panels only and no home battery storage."
    )
    c3.metric(
        "Solar + Battery Net Cost", 
        f"${summary['actual_net_cost']:,.2f}",
        delta=f"-${summary['total_savings']:,.2f} vs Base",
        delta_color="inverse",
        help="Actual cost with both solar generation and your Enphase battery system."
    )
    c4.metric(
        "Battery Added Value", 
        f"${summary['battery_added_savings']:,.2f}",
        delta="Additional savings from battery",
        help="Extra savings achieved by the battery above the solar-only setup."
    )

    # 2. Detailed Scenario Breakdown Tabs
    st.markdown("---")
    tab_actual, tab_solar_only, tab_roi, tab_srec = st.tabs([
        "🔋 Solar + Battery (Actual)", 
        "☀️ Solar Only (Simulation)", 
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

    with tab_roi:
        st.subheader("Financial Return on Investment (ROI) & Simple Payback")
        st.caption("✨ Note: ROI and Payback calculations include both utility bill savings and SREC renewable certificate earnings.")
        r1, r2 = st.columns(2)
        
        with r1:
            st.markdown("### ☀️ Solar Array Only")
            st.metric("Estimated ROI", f"{summary['solar_roi_pct']:.2f}% / year")
            st.metric("Simple Payback Period", f"{summary['solar_payback_yrs']:.1f} Years")
            st.caption("Based on standard solar array capital investment defaults + SRECs.")

        with r2:
            st.markdown("### 🔋 Solar + Battery Combined")
            st.metric("Estimated ROI", f"{summary['combined_roi_pct']:.2f}% / year")
            st.metric("Simple Payback Period", f"{summary['combined_payback_yrs']:.1f} Years")
            st.caption("Based on combined system capital investment defaults + SRECs.")

    with tab_srec:
        st.subheader("Solar Renewable Energy Certificate (SREC) Tracking")
        
        s1, s2, s3 = st.columns(3)
        s1.metric("Total SREC Revenue Earned", f"${total_srec_earned:,.2f}")
        s2.metric("Total RECs Sold", f"{srec_df['quantity'].sum() if not srec_df.empty else 0:,.1f}")
        avg_price = srec_df['price'].mean() if not srec_df.empty else 0.0
        s3.metric("Average Sale Price / REC", f"${avg_price:,.2f}")

        st.markdown("---")
        st.markdown("### 📋 SREC Transaction History (`srec_history.csv`)")
        if not srec_df.empty:
            st.dataframe(srec_df, use_container_width=True)
        else:
            st.info("No `srec_history.csv` found in the project directory.")

    # 3. Daily Activity Visualization
    st.markdown("---")
    st.subheader("Daily Grid Activity Comparison")
    
    view_mode = st.radio(
        "Select Daily View Mode:",
        options=["Solar + Battery (Actual)", "Solar Only (Simulation)"],
        horizontal=True
    )

    df_filtered['Date'] = df_filtered['Date/Time'].dt.date
    df_filtered['Rate_Window'] = df_filtered['is_peak'].map({True: 'On-Peak', False: 'Off-Peak'})

    if view_mode == "Solar + Battery (Actual)":
        daily_df = (
            df_filtered.groupby(['Date', 'Rate_Window'])[['Imported_kWh', 'Exported_kWh']]
            .sum()
            .reset_index()
        )
        import_col, export_col = 'Imported_kWh', 'Exported_kWh'
        chart_title = f"Daily Actual Grid Activity Breakdown (kWh) {timeframe_label}"
    else:
        daily_df = (
            df_filtered.groupby(['Date', 'Rate_Window'])[['Solar_Only_Import_kWh', 'Solar_Only_Export_kWh']]
            .sum()
            .reset_index()
        )
        import_col, export_col = 'Solar_Only_Import_kWh', 'Solar_Only_Export_kWh'
        chart_title = f"Daily Simulated Solar-Only Grid Activity Breakdown (kWh) {timeframe_label}"

    daily_melted = pd.melt(
        daily_df,
        id_vars=['Date', 'Rate_Window'],
        value_vars=[import_col, export_col],
        var_name='Type',
        value_name='kWh'
    )

    daily_melted['Category'] = daily_melted['Rate_Window'] + " " + daily_melted['Type'].map({
        import_col: 'Import',
        export_col: 'Solar Export'
    })

    fig = px.bar(
        daily_melted,
        x="Date",
        y="kWh",
        color="Category",
        color_discrete_map={
            "On-Peak Import": "#EF553B",     # Red
            "Off-Peak Import": "#636efa",    # Blue
            "On-Peak Solar Export": "#FFA15A", # Orange
            "Off-Peak Solar Export": "#00CC96" # Green
        },
        title=chart_title,
        labels={"kWh": "Energy (kWh)", "Date": "Date"},
        barmode="stack"
    )

    st.plotly_chart(fig, use_container_width=True)
