import streamlit as st
import plotly.express as px
import pandas as pd
from engine import (
    load_energy_data,
    calculate_actual_bill,
    summarize_actual_vs_baseline,
)

st.set_page_config(page_title="Belmont Energy Monitor", layout="wide")

st.title("Belmont Energy: Baseline vs. Actual Bill")

@st.cache_data
def get_processed_data():
    df = load_energy_data()
    if not df.empty:
        df = calculate_actual_bill(df)
    return df

df = get_processed_data()

if df.empty:
    st.warning("No interval data loaded in SQLite database yet.")
else:
    # Rate coverage check
    unmatched_df = df[df['import_rate'].isna()]
    if not unmatched_df.empty:
        st.error(
            f"⚠️ **{len(unmatched_df)} interval records** have no matching tariff!"
        )

    # Compute overall and monthly summaries
    full_summary = summarize_actual_vs_baseline(df)
    
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

    # 1. High Level Bill Summary
    st.markdown(f"### 💰 Baseline vs. Actual Bill Summary {timeframe_label}")
    c1, c2, c3, c4, c5 = st.columns(5)
    
    c1.metric(
        "Baseline TOU Cost", 
        f"${summary['baseline_cost']:,.2f}",
        help="Estimated cost if 100% of consumption was imported from the grid with no solar/battery."
    )
    c2.metric(
        "Gross Import Cost", 
        f"${summary['actual_import_cost']:,.2f}",
        help=f"On-Peak: ${summary['peak_import_cost']:,.2f} | Off-Peak: ${summary['offpeak_import_cost']:,.2f}"
    )
    c3.metric(
        "Solar Export Credits", 
        f"-${summary['actual_export_credit']:,.2f}",
        delta=f"-${summary['actual_export_credit']:,.2f}",
        delta_color="normal",
        help=f"On-Peak Export: -${summary['peak_export_credit']:,.2f} | Off-Peak Export: -${summary['offpeak_export_credit']:,.2f}"
    )
    c4.metric(
        "Actual Net Bill", 
        f"${summary['actual_net_cost']:,.2f}",
        help="Gross Import Cost minus Solar Export Credits."
    )
    c5.metric(
        "Total Net Savings", 
        f"${summary['total_savings']:,.2f}", 
        delta=f"{summary['savings_pct']:.1f}% Savings",
        help="Baseline Cost minus Actual Net Bill."
    )

    # 2. TOU Peak & Off-Peak Rate Verification Breakdown
    st.markdown("---")
    st.markdown(f"### 📊 TOU Rate & Financial Verification Breakdown {timeframe_label}")
    
    col_peak, col_offpeak = st.columns(2)
    
    imp_p_rates = ", ".join([f"${r:.5f}" for r in summary['import_peak_rates']])
    exp_p_rates = ", ".join([f"${r:.5f}" for r in summary['export_peak_rates']])
    imp_op_rates = ", ".join([f"${r:.5f}" for r in summary['import_offpeak_rates']])
    exp_op_rates = ", ".join([f"${r:.5f}" for r in summary['export_offpeak_rates']])

    with col_peak:
        st.markdown("🔴 **On-Peak Summary**")
        st.metric("Grid Import", f"{summary['peak_import_kwh']:,.1f} kWh", f"${summary['peak_import_cost']:,.2f}")
        st.caption(f"**Import Rate:** {imp_p_rates}")
        st.metric("Solar Export", f"{summary['peak_export_kwh']:,.1f} kWh", f"-${summary['peak_export_credit']:,.2f}")
        st.caption(f"**Export Rate:** {exp_p_rates}")

    with col_offpeak:
        st.markdown("🔵 **Off-Peak Summary**")
        st.metric("Grid Import", f"{summary['offpeak_import_kwh']:,.1f} kWh", f"${summary['offpeak_import_cost']:,.2f}")
        st.caption(f"**Import Rate:** {imp_op_rates}")
        st.metric("Solar Export", f"{summary['offpeak_export_kwh']:,.1f} kWh", f"-${summary['offpeak_export_credit']:,.2f}")
        st.caption(f"**Export Rate:** {exp_op_rates}")

    # 3. Daily Peak/Off-Peak Import & Export Visualization
    st.markdown("---")
    st.subheader(f"Daily Grid Activity Breakdown {timeframe_label}")

    df_filtered['Date'] = df_filtered['Date/Time'].dt.date
    df_filtered['Rate_Window'] = df_filtered['is_peak'].map({True: 'On-Peak', False: 'Off-Peak'})

    # Daily aggregate
    daily_df = (
        df_filtered.groupby(['Date', 'Rate_Window'])[['Imported_kWh', 'Exported_kWh']]
        .sum()
        .reset_index()
    )

    # Reshape for multi-series Plotly chart
    daily_melted = pd.melt(
        daily_df,
        id_vars=['Date', 'Rate_Window'],
        value_vars=['Imported_kWh', 'Exported_kWh'],
        var_name='Type',
        value_name='kWh'
    )

    # Combine Type and Rate Window into explicit legend categories
    daily_melted['Category'] = daily_melted['Rate_Window'] + " " + daily_melted['Type'].map({
        'Imported_kWh': 'Import',
        'Exported_kWh': 'Solar Export'
    })

    fig = px.bar(
        daily_melted,
        x="Date",
        y="kWh",
        color="Category",
        color_discrete_map={
            "On-Peak Import": "#EF553B",      # Red
            "Off-Peak Import": "#636efa",     # Blue
            "On-Peak Solar Export": "#FFA15A", # Orange
            "Off-Peak Solar Export": "#00CC96" # Green
        },
        title=f"Daily Grid Activity Breakdown (kWh) {timeframe_label}",
        labels={"kWh": "Energy (kWh)", "Date": "Date"},
        barmode="stack"
    )

    st.plotly_chart(fig, use_container_width=True)
