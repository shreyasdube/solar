import os
import sqlite3
import pandas as pd

DB_PATH = "data/enphase.db"


def load_energy_data(db_path=DB_PATH):
    """Loads interval data and pre-calculated rates directly from SQLite."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    query = """
    SELECT timestamp, consumed_wh, imported_wh, exported_wh, import_rate, export_rate, is_peak
    FROM enphase_energy_data
    """
    try:
        df = pd.read_sql(query, conn)
    except Exception:
        df = pd.read_sql("SELECT * FROM enphase_energy_data", conn)
    conn.close()

    if not df.empty:
        df['Date/Time'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
        df['is_peak'] = df['is_peak'].astype(bool)
        df = df.sort_values('Date/Time').drop_duplicates(subset=['Date/Time'])
    return df


def calculate_actual_bill(df):
    """
    Calculates 3 energy scenarios across all interval records:
    1. Baseline Scenario (No Solar, No Battery): 100% of consumption imported from grid.
    2. Solar Only Scenario (Solar Panels, No Battery): Solar generation offsets home demand in real time; 
       excess exported to grid, deficit imported from grid.
    3. Solar + Battery Scenario (Actual System): Net import and export after battery charge/discharge operations.
    """
    if df.empty:
        return df

    # Wh to kWh conversions
    df['Consumed_kWh'] = df.get('consumed_wh', 0) / 1000.0
    df['Imported_kWh'] = df.get('imported_wh', 0) / 1000.0  # Actual grid import (Solar + Battery)
    df['Exported_kWh'] = df.get('exported_wh', 0) / 1000.0  # Actual grid export (Solar + Battery)

    # Calculate or extract solar production (kWh) per interval
    if 'produced_wh' in df.columns:
        df['Produced_kWh'] = df['produced_wh'] / 1000.0
    else:
        # P = max(0, Consumed + Exported - Imported)
        df['Produced_kWh'] = (
            df.get('consumed_wh', 0) + df.get('exported_wh', 0) - df.get('imported_wh', 0)
        ).clip(lower=0) / 1000.0

    # -------------------------------------------------------------
    # 1. Baseline Scenario (No Solar, No Battery)
    # -------------------------------------------------------------
    df['cost_baseline'] = df['Consumed_kWh'] * df['import_rate']

    # -------------------------------------------------------------
    # 2. Solar Only Scenario (Solar Panels, No Battery Storage)
    # Net demand per 15-min interval = Consumed - Produced
    # -------------------------------------------------------------
    df['solar_only_net_kwh'] = df['Consumed_kWh'] - df['Produced_kWh']
    df['Solar_Only_Import_kWh'] = df['solar_only_net_kwh'].clip(lower=0)
    df['Solar_Only_Export_kWh'] = (-df['solar_only_net_kwh']).clip(lower=0)

    df['cost_solar_only_import'] = df['Solar_Only_Import_kWh'] * df['import_rate']
    df['credit_solar_only_export'] = df['Solar_Only_Export_kWh'] * df['export_rate']
    df['cost_solar_only_net'] = df['cost_solar_only_import'] - df['credit_solar_only_export']

    # -------------------------------------------------------------
    # 3. Solar + Battery Scenario (Actual Recorded System)
    # -------------------------------------------------------------
    df['cost_actual_import'] = df['Imported_kWh'] * df['import_rate']
    df['credit_actual_export'] = df['Exported_kWh'] * df['export_rate']
    df['cost_actual_net'] = df['cost_actual_import'] - df['credit_actual_export']

    return df


def calculate_roi(annual_savings, system_cost):
    """
    Calculates financial ROI percentage and payback period in years given system cost.
    """
    if system_cost is None or system_cost <= 0:
        return {"roi_pct": 0.0, "payback_years": None}
    roi_pct = (annual_savings / system_cost) * 100.0
    payback_years = system_cost / annual_savings if annual_savings > 0 else float('inf')
    return {
        "roi_pct": round(roi_pct, 2),
        "payback_years": round(payback_years, 2) if payback_years != float('inf') else None
    }


def summarize_slice(df, solar_cost=None, battery_cost=None):
    """
    Computes aggregated metrics for a given dataset slice (monthly or overall),
    providing peak/off-peak breakdowns, import/export details, and 3-way comparisons:
    - Base vs Solar Only
    - Base vs Solar + Battery
    - Solar Only vs Solar + Battery
    """
    if df.empty:
        return {}

    peak_mask = df['is_peak'] == True
    offpeak_mask = df['is_peak'] == False

    # 1. Baseline Scenario Totals
    baseline_cost = df['cost_baseline'].sum(skipna=True)
    peak_baseline_cost = df.loc[peak_mask, 'cost_baseline'].sum(skipna=True)
    offpeak_baseline_cost = df.loc[offpeak_mask, 'cost_baseline'].sum(skipna=True)

    # 2. Solar Only Scenario Totals & Breakdowns
    solar_only_import_kwh = df['Solar_Only_Import_kWh'].sum(skipna=True)
    solar_only_export_kwh = df['Solar_Only_Export_kWh'].sum(skipna=True)
    solar_only_import_cost = df['cost_solar_only_import'].sum(skipna=True)
    solar_only_export_credit = df['credit_solar_only_export'].sum(skipna=True)
    solar_only_net_cost = df['cost_solar_only_net'].sum(skipna=True)

    peak_solar_only_import_kwh = df.loc[peak_mask, 'Solar_Only_Import_kWh'].sum(skipna=True)
    peak_solar_only_import_cost = df.loc[peak_mask, 'cost_solar_only_import'].sum(skipna=True)
    peak_solar_only_export_kwh = df.loc[peak_mask, 'Solar_Only_Export_kWh'].sum(skipna=True)
    peak_solar_only_export_credit = df.loc[peak_mask, 'credit_solar_only_export'].sum(skipna=True)

    offpeak_solar_only_import_kwh = df.loc[offpeak_mask, 'Solar_Only_Import_kWh'].sum(skipna=True)
    offpeak_solar_only_import_cost = df.loc[offpeak_mask, 'cost_solar_only_import'].sum(skipna=True)
    offpeak_solar_only_export_kwh = df.loc[offpeak_mask, 'Solar_Only_Export_kWh'].sum(skipna=True)
    offpeak_solar_only_export_credit = df.loc[offpeak_mask, 'credit_solar_only_export'].sum(skipna=True)

    # 3. Solar + Battery (Actual) Totals & Breakdowns
    actual_import_kwh = df['Imported_kWh'].sum(skipna=True)
    actual_export_kwh = df['Exported_kWh'].sum(skipna=True)
    actual_import_cost = df['cost_actual_import'].sum(skipna=True)
    actual_export_credit = df['credit_actual_export'].sum(skipna=True)
    actual_net_cost = df['cost_actual_net'].sum(skipna=True)

    peak_import_kwh = df.loc[peak_mask, 'Imported_kWh'].sum(skipna=True)
    peak_import_cost = df.loc[peak_mask, 'cost_actual_import'].sum(skipna=True)
    peak_export_kwh = df.loc[peak_mask, 'Exported_kWh'].sum(skipna=True)
    peak_export_credit = df.loc[peak_mask, 'credit_actual_export'].sum(skipna=True)

    offpeak_import_kwh = df.loc[offpeak_mask, 'Imported_kWh'].sum(skipna=True)
    offpeak_import_cost = df.loc[offpeak_mask, 'cost_actual_import'].sum(skipna=True)
    offpeak_export_kwh = df.loc[offpeak_mask, 'Exported_kWh'].sum(skipna=True)
    offpeak_export_credit = df.loc[offpeak_mask, 'credit_actual_export'].sum(skipna=True)

    # Tariff Rates
    import_peak_rates = [float(r) for r in sorted(df.loc[peak_mask, 'import_rate'].dropna().unique())]
    import_offpeak_rates = [float(r) for r in sorted(df.loc[offpeak_mask, 'import_rate'].dropna().unique())]
    export_peak_rates = [float(r) for r in sorted(df.loc[peak_mask, 'export_rate'].dropna().unique())]
    export_offpeak_rates = [float(r) for r in sorted(df.loc[offpeak_mask, 'export_rate'].dropna().unique())]

    # -------------------------------------------------------------
    # 3-Way Comparisons & Savings
    # -------------------------------------------------------------
    # 1. Base vs Solar Only
    savings_solar_only = baseline_cost - solar_only_net_cost
    savings_solar_only_pct = ((baseline_cost - solar_only_net_cost) / baseline_cost * 100.0) if baseline_cost > 0 else 0.0

    # 2. Base vs Solar + Battery
    savings_solar_battery = baseline_cost - actual_net_cost
    savings_solar_battery_pct = ((baseline_cost - actual_net_cost) / baseline_cost * 100.0) if baseline_cost > 0 else 0.0

    # 3. Solar Only vs Solar + Battery (Incremental Battery Value)
    savings_battery_addon = solar_only_net_cost - actual_net_cost
    savings_battery_addon_pct = ((solar_only_net_cost - actual_net_cost) / solar_only_net_cost * 100.0) if solar_only_net_cost > 0 else 0.0

    # Optional Capital Financial ROI
    total_system_cost = (solar_cost or 0) + (battery_cost or 0)
    roi_solar_only_fin = calculate_roi(savings_solar_only, solar_cost)
    roi_solar_battery_fin = calculate_roi(savings_solar_battery, total_system_cost if total_system_cost > 0 else None)

    return {
        "consumed_kwh": df['Consumed_kWh'].sum(skipna=True),
        "produced_kwh": df['Produced_kWh'].sum(skipna=True),

        # Scenario Net Bills
        "baseline_cost": baseline_cost,
        "solar_only_net_cost": solar_only_net_cost,
        "actual_net_cost": actual_net_cost,

        # Solar Only Scenario Breakdown
        "solar_only_import_kwh": solar_only_import_kwh,
        "solar_only_export_kwh": solar_only_export_kwh,
        "solar_only_import_cost": solar_only_import_cost,
        "solar_only_export_credit": solar_only_export_credit,
        "peak_solar_only_import_kwh": peak_solar_only_import_kwh,
        "peak_solar_only_import_cost": peak_solar_only_import_cost,
        "peak_solar_only_export_kwh": peak_solar_only_export_kwh,
        "peak_solar_only_export_credit": peak_solar_only_export_credit,
        "offpeak_solar_only_import_kwh": offpeak_solar_only_import_kwh,
        "offpeak_solar_only_import_cost": offpeak_solar_only_import_cost,
        "offpeak_solar_only_export_kwh": offpeak_solar_only_export_kwh,
        "offpeak_solar_only_export_credit": offpeak_solar_only_export_credit,

        # Solar + Battery (Actual) Scenario Breakdown
        "imported_kwh": actual_import_kwh,
        "exported_kwh": actual_export_kwh,
        "actual_import_cost": actual_import_cost,
        "actual_export_credit": actual_export_credit,
        "peak_import_kwh": peak_import_kwh,
        "peak_import_cost": peak_import_cost,
        "peak_export_kwh": peak_export_kwh,
        "peak_export_credit": peak_export_credit,
        "offpeak_import_kwh": offpeak_import_kwh,
        "offpeak_import_cost": offpeak_import_cost,
        "offpeak_export_kwh": offpeak_export_kwh,
        "offpeak_export_credit": offpeak_export_credit,

        # Tariff Rates
        "import_peak_rates": import_peak_rates,
        "export_peak_rates": export_peak_rates,
        "import_offpeak_rates": import_offpeak_rates,
        "export_offpeak_rates": export_offpeak_rates,

        # -------------------------------------------------------------
        # Comparisons Structure
        # -------------------------------------------------------------
        "comparisons": {
            "base_vs_solar_only": {
                "savings_amount": savings_solar_only,
                "savings_pct": savings_solar_only_pct,
                "baseline_cost": baseline_cost,
                "solar_only_cost": solar_only_net_cost,
                "import_reduction_kwh": df['Consumed_kWh'].sum(skipna=True) - solar_only_import_kwh,
            },
            "base_vs_solar_battery": {
                "savings_amount": savings_solar_battery,
                "savings_pct": savings_solar_battery_pct,
                "baseline_cost": baseline_cost,
                "solar_battery_cost": actual_net_cost,
                "import_reduction_kwh": df['Consumed_kWh'].sum(skipna=True) - actual_import_kwh,
            },
            "solar_vs_solar_battery": {
                "incremental_savings_amount": savings_battery_addon,
                "incremental_savings_pct": savings_battery_addon_pct,
                "solar_only_cost": solar_only_net_cost,
                "solar_battery_cost": actual_net_cost,
                "peak_import_avoided_kwh": peak_solar_only_import_kwh - peak_import_kwh,
                "peak_cost_saved": peak_solar_only_import_cost - peak_import_cost,
            }
        },

        # -------------------------------------------------------------
        # Single ROI Fields (Percentage Bill Savings & Formatted String)
        # -------------------------------------------------------------
        "roi_solar_only_pct": savings_solar_only_pct,
        "roi_solar_battery_pct": savings_solar_battery_pct,
        "roi_solar_only_str": f"{savings_solar_only_pct:.1f}% Bill Savings (${savings_solar_only:,.2f})",
        "roi_solar_battery_str": f"{savings_solar_battery_pct:.1f}% Bill Savings (${savings_solar_battery:,.2f})",
        "financial_roi": {
            "solar_only": roi_solar_only_fin,
            "solar_battery": roi_solar_battery_fin
        },

        # Backward compatibility aliases
        "total_savings": savings_solar_battery,
        "savings_pct": savings_solar_battery_pct,
    }


def summarize_actual_vs_baseline(df, solar_cost=None, battery_cost=None):
    """Summarizes baseline, solar-only, and solar+battery net bill metrics overall and per month."""
    if df.empty:
        return {}

    overall_summary = summarize_slice(df, solar_cost=solar_cost, battery_cost=battery_cost)

    # Monthly Breakdown
    df['Month_Period'] = df['Date/Time'].dt.to_period('M')
    monthly_summaries = {}
    for month, group in df.groupby('Month_Period'):
        monthly_summaries[str(month)] = summarize_slice(group, solar_cost=solar_cost, battery_cost=battery_cost)

    overall_summary['monthly'] = monthly_summaries
    return overall_summary


if __name__ == "__main__":
    df = load_energy_data()
    if not df.empty:
        df = calculate_actual_bill(df)
        summary = summarize_actual_vs_baseline(df)
        print(f"Processed {len(df)} rows across {len(summary.get('monthly', {}))} month(s).\n")

        print("==================== OVERALL COMPARISONS ====================")
        print(f"Baseline (No Solar/Battery): ${summary['baseline_cost']:,.2f}")
        print(f"Solar Only Net Bill:        ${summary['solar_only_net_cost']:,.2f}")
        print(f"Solar + Battery Net Bill:   ${summary['actual_net_cost']:,.2f}\n")

        print("--- 1. Base vs Solar Only ---")
        b_s = summary['comparisons']['base_vs_solar_only']
        print(f" Savings: ${b_s['savings_amount']:,.2f} ({b_s['savings_pct']:.1f}%)")

        print("--- 2. Base vs Solar+Battery ---")
        b_sb = summary['comparisons']['base_vs_solar_battery']
        print(f" Savings: ${b_sb['savings_amount']:,.2f} ({b_sb['savings_pct']:.1f}%)")

        print("--- 3. Solar vs Solar+Battery ---")
        s_sb = summary['comparisons']['solar_vs_solar_battery']
        print(f" Incremental Battery Savings: ${s_sb['incremental_savings_amount']:,.2f} ({s_sb['incremental_savings_pct']:.1f}%)\n")

        print("--- ROI METRICS ---")
        print(f"Solar Only ROI:      {summary['roi_solar_only_str']}")
        print(f"Solar + Battery ROI: {summary['roi_solar_battery_str']}")
    else:
        print("No data found in database. Run db.py first.")
