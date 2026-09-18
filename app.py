import streamlit as st
import plotly.express as px
from engine import load_energy_data, apply_tariffs, calculate_baseline

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

    # Summary Metrics
    col1, col2, col3 = st.columns(3)
    total_kwh = df['Consumed_kWh'].sum()
    total_cost = df['cost_baseline'].sum(skipna=True)
    avg_rate = total_cost / total_kwh if total_kwh > 0 else 0

    col1.metric("Total Consumption", f"{total_kwh:,.1f} kWh")
    col2.metric("Total Baseline Cost", f"${total_cost:,.2f}")
    col3.metric("Effective Rate", f"${avg_rate:.3f} / kWh")

    st.markdown("---")

    # Time-Series Chart
    st.subheader("15-Minute Electricity Consumption & Peak Hours")
    fig = px.line(
        df, 
        x="Date/Time", 
        y="Consumed_kWh", 
        color="is_peak",
        color_discrete_map={True: "red", False: "blue"},
        title="Interval Usage (Red = Peak Rate Hours)",
        labels={"Consumed_kWh": "Consumption (kWh)", "is_peak": "Peak Hours"}
    )
    st.plotly_chart(fig, use_container_width=True)
