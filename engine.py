import os
import sqlite3
import pandas as pd
import numpy as np

DB_PATH = "data/enphase.db"

# Estimated default system costs for ROI/Payback calculation (adjustable)
SOLAR_SYSTEM_COST = 18000.0  # e.g., estimated net cost for solar array
BATTERY_SYSTEM_COST = 10000.0 # e.g., estimated net cost for battery storage

def load_energy_data(db_path=DB_PATH):
    """Loads interval data and pre-calculated rates directly from SQLite."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    query = """
    SELECT timestamp, consumed_wh, produced_wh, imported_wh, exported_wh, stored_wh, discharged_wh, import_rate, export_rate, is_peak 
    FROM enphase_energy_data
    """
    try:
        df = pd.read_sql(query, conn)
    except Exception:
        # Fallback if columns differ
        df = pd.read_sql("SELECT * FROM enphase_energy_data", conn)
        
    conn.close()
    if not df.empty:
        df['Date/Time'] = pd.to_datetime(df['timestamp'])
        if df['Date/Time'].dt.tz is not None:
            df['Date/Time'] = df['Date/Time'].dt.tz_localize(None)
            
        df['is_peak'] = df['is_peak'].astype(bool)
        df = df.sort_values('Date/Time').drop_duplicates(subset=['Date/Time'])
    return df

def calculate_scenarios(df):
    """Calculates Baseline, Solar Only (No Battery), and Solar + Battery (Actual) bills."""
    if df.empty:
        return df
    
    # 1. Base Energy Conversions (kWh)
    df['Consumed_kWh'] = df.get('consumed_wh', 0) / 1000.0
    df['Produced_kWh'] = df.get('produced_wh', 0) / 1000.0
    df['Imported_kWh'] = df.get('imported_wh', 0) / 1000.0
    df['Exported_kWh'] = df.get('exported_wh', 0) / 1000.0
    df['Stored_kWh'] = df.get('stored_wh', 0) / 1000.0
    df['Discharged_kWh'] = df.get('discharged_wh', 0) / 1000.0

    # Baseline Cost (No solar, 100% grid import)
    df['cost_baseline'] = df['Consumed_kWh'] * df['import_rate']
    
    # Actual Net Bill (Solar + Battery)
    df['cost_actual_import'] = df['Imported_kWh'] * df['import_rate']
    df['credit_actual_export'] = df['Exported_kWh'] * df['export_rate']
    df['cost_actual_net'] = df['cost_actual_import'] - df['credit_actual_export']

    # 2. Clean Solar Only (No Battery) Simulation via Instantaneous Physical Balance
    # Without a battery, solar production meets home consumption first in each interval.
    # Deficit = Grid Import; Surplus = Grid Export.
    df['Solar_Only_Import_kWh'] = (df['Consumed_kWh'] - df['Produced_kWh']).clip(lower=0)
    df['Solar_Only_Export_kWh'] = (df['Produced_kWh'] - df['Consumed_kWh']).clip(lower=0)

    df['cost_solar_only_import'] = df['Solar_Only_Import_kWh'] * df['import_rate']
    df['credit_solar_only_export'] = df['Solar_Only_Export_kWh'] * df['export_rate']
    df['cost_solar_only_net'] = df['cost_solar_only_import'] - df['credit_solar_only_export']
    
    return df

def summarize_slice(df):
    """Helper to compute aggregated metrics for Baseline, Solar Only, and Solar + Battery."""
    if df.empty:
        return {}

    peak_mask = df['is_peak'] == True
    offpeak_mask = df['is_peak'] == False

    # Financial Totals
    baseline_cost = df['cost_baseline'].sum(skipna=True)
    
    solar_only_import_cost = df['cost_solar_only_import'].sum(skipna=True)
    solar_only_export_credit = df['credit_solar_only_export'].sum(skipna=True)
    solar_only_net_cost = df['cost_solar_only_net'].sum(skipna=True)

    actual_import_cost = df['cost_actual_import'].sum(skipna=True)
    actual_export_credit = df['credit_actual_export'].sum(skipna=True)
    actual_net_cost = df['cost_actual_net'].sum(skipna=True)

    # Savings & ROI Metrics
    solar_only_savings = baseline_cost - solar_only_net_cost
    battery_added_savings = solar_only_net_cost - actual_net_cost
    total_savings = baseline_cost - actual_net_cost

    # Simple Payback / ROI calculations (Annualized estimation based on dataset span)
    days_covered = (df['Date/Time'].max() - df['Date/Time'].min()).days or 1
    annualizer = 365.25 / max(days_covered, 1)

    annual_solar_savings = solar_only_savings * annualizer
    annual_total_savings = total_savings * annualizer

    solar_roi_pct = (annual_solar_savings / SOLAR_SYSTEM_COST) * 100 if SOLAR_SYSTEM_COST > 0 else 0
    solar_payback_yrs = SOLAR_SYSTEM_COST / annual_solar_savings if annual_solar_savings > 0 else float('inf')

    combined_system_cost = SOLAR_SYSTEM_COST + BATTERY_SYSTEM_COST
    combined_roi_pct = (annual_total_savings / combined_system_cost) * 100 if combined_system_cost > 0 else 0
    combined_payback_yrs = combined_system_cost / annual_total_savings if annual_total_savings > 0 else float('inf')

    # Peak vs Off-Peak Breakdowns for Solar Only
    peak_so_import_kwh = df.loc[peak_mask, 'Solar_Only_Import_kWh'].sum()
    peak_so_import_cost = df.loc[peak_mask, 'cost_solar_only_import'].sum()
    peak_so_export_kwh = df.loc[peak_mask, 'Solar_Only_Export_kWh'].sum()
    peak_so_export_credit = df.loc[peak_mask, 'credit_solar_only_export'].sum()

    offpeak_so_import_kwh = df.loc[offpeak_mask, 'Solar_Only_Import_kWh'].sum()
    offpeak_so_import_cost = df.loc[offpeak_mask, 'cost_solar_only_import'].sum()
    offpeak_so_export_kwh = df.loc[offpeak_mask, 'Solar_Only_Export_kWh'].sum()
    offpeak_so_export_credit = df.loc[offpeak_mask, 'credit_solar_only_export'].sum()

    # Peak vs Off-Peak Breakdowns for Actual (Solar + Battery)
    peak_import_kwh = df.loc[peak_mask, 'Imported_kWh'].sum()
    peak_import_cost = df.loc[peak_mask, 'cost_actual_import'].sum()
    peak_export_kwh = df.loc[peak_mask, 'Exported_kWh'].sum()
    peak_export_credit = df.loc[peak_mask, 'credit_actual_export'].sum()

    offpeak_import_kwh = df.loc[offpeak_mask, 'Imported_kWh'].sum()
    offpeak_import_cost = df.loc[offpeak_mask, 'cost_actual_import'].sum()
    offpeak_export_kwh = df.loc[offpeak_mask, 'Exported_kWh'].sum()
    offpeak_export_credit = df.loc[offpeak_mask, 'credit_actual_export'].sum()

    return {
        "consumed_kwh": df['Consumed_kWh'].sum(),
        "baseline_cost": baseline_cost,
        
        # Solar Only Scenario
        "solar_only_import_cost": solar_only_import_cost,
        "solar_only_export_credit": solar_only_export_credit,
        "solar_only_net_cost": solar_only_net_cost,
        "solar_only_savings": solar_only_savings,
        "solar_roi_pct": solar_roi_pct,
        "solar_payback_yrs": solar_payback_yrs,
        
        # Solar + Battery Scenario
        "actual_import_cost": actual_import_cost,
        "actual_export_credit": actual_export_credit,
        "actual_net_cost": actual_net_cost,
        "total_savings": total_savings,
        "battery_added_savings": battery_added_savings,
        "combined_roi_pct": combined_roi_pct,
        "combined_payback_yrs": combined_payback_yrs,

        # Solar Only Peak / Off-Peak
        "peak_so_import_kwh": peak_so_import_kwh,
        "peak_so_import_cost": peak_so_import_cost,
        "peak_so_export_kwh": peak_so_export_kwh,
        "peak_so_export_credit": peak_so_export_credit,
        "offpeak_so_import_kwh": offpeak_so_import_kwh,
        "offpeak_so_import_cost": offpeak_so_import_cost,
        "offpeak_so_export_kwh": offpeak_so_export_kwh,
        "offpeak_so_export_credit": offpeak_so_export_credit,

        # Solar + Battery Peak / Off-Peak
        "peak_import_kwh": peak_import_kwh,
        "peak_import_cost": peak_import_cost,
        "peak_export_kwh": peak_export_kwh,
        "peak_export_credit": peak_export_credit,
        "offpeak_import_kwh": offpeak_import_kwh,
        "offpeak_import_cost": offpeak_import_cost,
        "offpeak_export_kwh": offpeak_export_kwh,
        "offpeak_export_credit": offpeak_export_credit,

        # Rate lists for UI verification
        "import_peak_rates": [float(r) for r in sorted(df.loc[peak_mask, 'import_rate'].dropna().unique())],
        "import_offpeak_rates": [float(r) for r in sorted(df.loc[offpeak_mask, 'import_rate'].dropna().unique())],
        "export_peak_rates": [float(r) for r in sorted(df.loc[peak_mask, 'export_rate'].dropna().unique())],
        "export_offpeak_rates": [float(r) for r in sorted(df.loc[offpeak_mask, 'export_rate'].dropna().unique())],
    }

def summarize_actual_vs_baseline(df):
    """Summarizes baseline, solar-only, and solar+battery metrics overall and per month."""
    if df.empty:
        return {}

    overall_summary = summarize_slice(df)
    
    df['Month_Period'] = df['Date/Time'].dt.to_period('M')
    monthly_summaries = {}
    
    for month, group in df.groupby('Month_Period'):
        monthly_summaries[str(month)] = summarize_slice(group)

    overall_summary['monthly'] = monthly_summaries
    return overall_summary
