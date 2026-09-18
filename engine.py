import os
import sqlite3
import pandas as pd
import numpy as np

DB_PATH = "data/enphase.db"
SREC_CSV_PATH = "srec_history.csv"

# Estimated default system costs for ROI/Payback calculation (adjustable)
SOLAR_SYSTEM_COST = 26000.0
BATTERY_SYSTEM_COST = 20000.0

def load_srec_data(csv_path=SREC_CSV_PATH):
    """Loads historical SREC sales and computes total earnings and annualized revenue."""
    if not os.path.exists(csv_path):
        return 0.0, 0.0, pd.DataFrame()
    try:
        df = pd.read_csv(csv_path)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        total_earned = df['total_value'].sum() if 'total_value' in df.columns else 0.0
        
        if 'date' in df.columns and not df['date'].isna().all():
            days = (df['date'].max() - df['date'].min()).days
            years = max(days / 365.25, 1.0)
            annual_srec = total_earned / years
        else:
            annual_srec = total_earned
            
        return total_earned, annual_srec, df
    except Exception as e:
        print(f"Error loading SREC data: {e}")
        return 0.0, 0.0, pd.DataFrame()

def load_energy_data(db_path=DB_PATH):
    """Loads pre-calculated interval data and scenarios directly from SQLite."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql("SELECT * FROM enphase_energy_data", conn)
    except Exception as e:
        print(f"Error reading from database: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()

    if not df.empty:
        df['Date/Time'] = pd.to_datetime(df['timestamp'])
        if df['Date/Time'].dt.tz is not None:
            df['Date/Time'] = df['Date/Time'].dt.tz_localize(None)
        df['is_peak'] = df['is_peak'].astype(bool)
        df = df.sort_values('Date/Time').drop_duplicates(subset=['Date/Time'])
        
    return df

def summarize_slice(df):
    """Computes aggregated metrics and financial summaries using pre-calculated DB columns."""
    if df.empty:
        return {}

    peak_mask = df['is_peak'] == True
    offpeak_mask = df['is_peak'] == False

    # Load SREC data
    total_srec, annual_srec, srec_df = load_srec_data()

    # Annualization factor
    days_covered = (df['Date/Time'].max() - df['Date/Time'].min()).days or 1
    annualizer = 365.25 / max(days_covered, 1)

    # Baseline & Scenario Costs (Pre-calculated in SQLite)
    baseline_cost = df['cost_baseline'].sum(skipna=True)
    actual_net_cost = df['cost_actual_net'].sum(skipna=True)
    solar_only_net_cost = df['cost_solar_only_net'].sum(skipna=True)
    battery_only_net_cost = df['cost_battery_only'].sum(skipna=True)

    total_savings = baseline_cost - actual_net_cost
    solar_only_savings = baseline_cost - solar_only_net_cost
    battery_only_savings = baseline_cost - battery_only_net_cost
    battery_added_savings = total_savings - solar_only_savings

    # Annual Returns & ROI / Payback Calculations
    annual_solar_savings = (solar_only_savings * annualizer) + annual_srec
    annual_total_savings = (total_savings * annualizer) + annual_srec

    solar_roi_pct = (annual_solar_savings / SOLAR_SYSTEM_COST) * 100 if SOLAR_SYSTEM_COST > 0 else 0
    solar_payback_yrs = SOLAR_SYSTEM_COST / annual_solar_savings if annual_solar_savings > 0 else float('inf')

    combined_system_cost = SOLAR_SYSTEM_COST + BATTERY_SYSTEM_COST
    combined_roi_pct = (annual_total_savings / combined_system_cost) * 100 if combined_system_cost > 0 else 0
    combined_payback_yrs = combined_system_cost / annual_total_savings if annual_total_savings > 0 else float('inf')

    battery_only_annual_savings = battery_only_savings * annualizer
    battery_only_roi_pct = (battery_only_annual_savings / BATTERY_SYSTEM_COST) * 100 if BATTERY_SYSTEM_COST > 0 else 0
    battery_only_payback_yrs = BATTERY_SYSTEM_COST / battery_only_annual_savings if battery_only_annual_savings > 0 else float('inf')

    # Detailed breakdown metrics (Actual)
    peak_import_kwh = df.loc[peak_mask, 'Imported_kWh'].sum()
    peak_import_cost = df.loc[peak_mask, 'cost_actual_import'].sum()
    peak_export_kwh = df.loc[peak_mask, 'Exported_kWh'].sum()
    peak_export_credit = df.loc[peak_mask, 'credit_actual_export'].sum()

    offpeak_import_kwh = df.loc[offpeak_mask, 'Imported_kWh'].sum()
    offpeak_import_cost = df.loc[offpeak_mask, 'cost_actual_import'].sum()
    offpeak_export_kwh = df.loc[offpeak_mask, 'Exported_kWh'].sum()
    offpeak_export_credit = df.loc[offpeak_mask, 'credit_actual_export'].sum()

    # Solar-only peak/off-peak stats
    peak_so_import_kwh = df.loc[peak_mask, 'Solar_Only_Import_kWh'].sum()
    peak_so_import_cost = (df.loc[peak_mask, 'Solar_Only_Import_kWh'] * df.loc[peak_mask, 'import_rate']).sum()
    peak_so_export_kwh = df.loc[peak_mask, 'Solar_Only_Export_kWh'].sum()
    peak_so_export_credit = (df.loc[peak_mask, 'Solar_Only_Export_kWh'] * df.loc[peak_mask, 'export_rate']).sum()

    offpeak_so_import_kwh = df.loc[offpeak_mask, 'Solar_Only_Import_kWh'].sum()
    offpeak_so_import_cost = (df.loc[offpeak_mask, 'Solar_Only_Import_kWh'] * df.loc[offpeak_mask, 'import_rate']).sum()
    offpeak_so_export_kwh = df.loc[offpeak_mask, 'Solar_Only_Export_kWh'].sum()
    offpeak_so_export_credit = (df.loc[offpeak_mask, 'Solar_Only_Export_kWh'] * df.loc[offpeak_mask, 'export_rate']).sum()

    # Battery-only peak stats
    peak_bo_import_kwh = df.loc[peak_mask, 'Battery_Only_Import_kWh'].sum()
    peak_bo_import_cost = (df.loc[peak_mask, 'Battery_Only_Import_kWh'] * df.loc[peak_mask, 'import_rate']).sum()

    return {
        "consumed_kwh": df['Consumed_kWh'].sum(),
        "produced_kwh": df['Produced_kWh'].sum(),
        "baseline_cost": baseline_cost,
        "actual_net_cost": actual_net_cost,
        "total_savings": total_savings,
        "solar_only_net_cost": solar_only_net_cost,
        "solar_only_savings": solar_only_savings,
        "battery_only_net_cost": battery_only_net_cost,
        "battery_only_savings": battery_only_savings,
        "battery_added_savings": battery_added_savings,
        "battery_only_roi_pct": battery_only_roi_pct,
        "battery_only_payback_yrs": battery_only_payback_yrs,
        "solar_roi_pct": solar_roi_pct,
        "solar_payback_yrs": solar_payback_yrs,
        "combined_roi_pct": combined_roi_pct,
        "combined_payback_yrs": combined_payback_yrs,
        "total_srec_earned": total_srec,
        "peak_import_kwh": peak_import_kwh,
        "peak_import_cost": peak_import_cost,
        "peak_export_kwh": peak_export_kwh,
        "peak_export_credit": peak_export_credit,
        "offpeak_import_kwh": offpeak_import_kwh,
        "offpeak_import_cost": offpeak_import_cost,
        "offpeak_export_kwh": offpeak_export_kwh,
        "offpeak_export_credit": offpeak_export_credit,
        "peak_so_import_kwh": peak_so_import_kwh,
        "peak_so_import_cost": peak_so_import_cost,
        "peak_so_export_kwh": peak_so_export_kwh,
        "peak_so_export_credit": peak_so_export_credit,
        "offpeak_so_import_kwh": offpeak_so_import_kwh,
        "offpeak_so_import_cost": offpeak_so_import_cost,
        "offpeak_so_export_kwh": offpeak_so_export_kwh,
        "offpeak_so_export_credit": offpeak_so_export_credit,
        "peak_bo_import_kwh": peak_bo_import_kwh,
        "peak_bo_import_cost": peak_bo_import_cost,
    }

def summarize_actual_vs_baseline(df):
    """Summarizes baseline, solar-only, battery-only, and solar+battery metrics overall and per month."""
    if df.empty:
        return {}

    overall_summary = summarize_slice(df)
    df['Month_Period'] = df['Date/Time'].dt.to_period('M')
    
    monthly_summaries = {}
    for month, group in df.groupby('Month_Period'):
        monthly_summaries[str(month)] = summarize_slice(group)

    return {
        "overall": overall_summary,
        "monthly": monthly_summaries
    }
