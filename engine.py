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
    """Loads historical SREC sales to calculate annualized renewable revenue."""
    if not os.path.exists(csv_path):
        return 0.0, 0.0
    
    try:
        df = pd.read_csv(csv_path)
        df['date'] = pd.to_datetime(df['date'])
        total_srec_revenue = df['total_sales'].sum()
        
        # Calculate annual multiplier based on date span of SREC records
        days_span = (df['date'].max() - df['date'].min()).days
        if days_span > 30:
            annual_srec_revenue = total_srec_revenue * (365.25 / days_span)
        else:
            annual_srec_revenue = total_srec_revenue  # Fallback if sparse
            
        return total_srec_revenue, annual_srec_revenue
    except Exception:
        return 0.0, 0.0

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
    
    df['Consumed_kWh'] = df.get('consumed_wh', 0) / 1000.0
    df['Produced_kWh'] = df.get('produced_wh', 0) / 1000.0
    df['Imported_kWh'] = df.get('imported_wh', 0) / 1000.0
    df['Exported_kWh'] = df.get('exported_wh', 0) / 1000.0
    df['Stored_kWh'] = df.get('stored_wh', 0) / 1000.0
    df['Discharged_kWh'] = df.get('discharged_wh', 0) / 1000.0

    # Baseline Cost
    df['cost_baseline'] = df['Consumed_kWh'] * df['import_rate']
    
    # Actual Net Bill (Solar + Battery)
    df['cost_actual_import'] = df['Imported_kWh'] * df['import_rate']
    df['credit_actual_export'] = df['Exported_kWh'] * df['export_rate']
    df['cost_actual_net'] = df['cost_actual_import'] - df['credit_actual_export']

    # Solar Only Simulation (Instantaneous Physical Balance)
    df['Solar_Only_Import_kWh'] = (df['Consumed_kWh'] - df['Produced_kWh']).clip(lower=0)
    df['Solar_Only_Export_kWh'] = (df['Produced_kWh'] - df['Consumed_kWh']).clip(lower=0)

    df['cost_solar_only_import'] = df['Solar_Only_Import_kWh'] * df['import_rate']
    df['credit_solar_only_export'] = df['Solar_Only_Export_kWh'] * df['export_rate']
    df['cost_solar_only_net'] = df['cost_solar_only_import'] - df['credit_solar_only_export']
    
    return df

def summarize_slice(df):
    """Helper to compute aggregated metrics including SREC revenue for ROI/Payback."""
    if df.empty:
        return {}

    peak_mask = df['is_peak'] == True
    offpeak_mask = df['is_peak'] == False

    baseline_cost = df['cost_baseline'].sum(skipna=True)
    solar_only_net_cost = df['cost_solar_only_net'].sum(skipna=True)
    actual_net_cost = df['cost_actual_net'].sum(skipna=True)

    solar_only_savings = baseline_cost - solar_only_net_cost
    battery_added_savings = solar_only_net_cost - actual_net_cost
    total_savings = baseline_cost - actual_net_cost

    # Load SREC data
    total_srec, annual_srec = load_srec_data()

    # Annualization factor based on interval data span
    days_covered = (df['Date/Time'].max() - df['Date/Time'].min()).days or 1
    annualizer = 365.25 / max(days_covered, 1)

    # Total Annual Return = Annual Bill Savings + Annual SREC Revenue
    annual_solar_savings = (solar_only_savings * annualizer) + annual_srec
    annual_total_savings = (total_savings * annualizer) + annual_srec

    solar_roi_pct = (annual_solar_savings / SOLAR_SYSTEM_COST) * 100 if SOLAR_SYSTEM_COST > 0 else 0
    solar_payback_yrs = SOLAR_SYSTEM_COST / annual_solar_savings if annual_solar_savings > 0 else float('inf')

    combined_system_cost = SOLAR_SYSTEM_COST + BATTERY_SYSTEM_COST
    combined_roi_pct = (annual_total_savings / combined_system_cost) * 100 if combined_system_cost > 0 else 0
    combined_payback_yrs = combined_system_cost / annual_total_savings if annual_total_savings > 0 else float('inf')

    # Peak vs Off-Peak Breakdowns (omitted for brevity, keep existing dict fields...)
    return {
        "consumed_kwh": df['Consumed_kWh'].sum(),
        "baseline_cost": baseline_cost,
        "solar_only_net_cost": solar_only_net_cost,
        "solar_only_savings": solar_only_savings,
        "actual_net_cost": actual_net_cost,
        "total_savings": total_savings,
        "battery_added_savings": battery_added_savings,
        "total_srec_earned": total_srec,
        "annual_srec_earned": annual_srec,
        "solar_roi_pct": solar_roi_pct,
        "solar_payback_yrs": solar_payback_yrs,
        "combined_roi_pct": combined_roi_pct,
        "combined_payback_yrs": combined_payback_yrs,
        # ... retain other breakdown metrics as needed ...
    }
