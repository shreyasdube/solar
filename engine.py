import os
import sqlite3
import pandas as pd
import numpy as np

DB_PATH = "data/enphase.db"
RATES_PATH = "rates_schedule.csv"

def load_energy_data(db_path=DB_PATH):
    """Loads full interval data from SQLite enphase_energy_data table."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    
    # Select all production, consumption, battery, and grid interval columns
    query = """
    SELECT timestamp, consumed_wh, imported_wh, produced_wh, exported_wh, battery_charge_wh, battery_discharge_wh 
    FROM enphase_energy_data
    """
    try:
        df = pd.read_sql(query, conn)
    except Exception:
        # Fallback if battery/export columns are optional or named slightly differently
        df = pd.read_sql("SELECT * FROM enphase_energy_data", conn)
        
    conn.close()
    if not df.empty:
        df['Date/Time'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
        df = df.sort_values('Date/Time').drop_duplicates(subset=['Date/Time'])
    return df

def apply_tariffs(df, rates_path=RATES_PATH):
    """Maps seasonal TOU import/export tariffs to each interval."""
    df['import_rate'] = np.nan
    df['export_rate'] = 0.0  # Default export credit rate (can be adjusted in rates_schedule.csv)
    df['is_peak'] = False
    
    if not os.path.exists(rates_path) or df.empty:
        return df
    
    rates = pd.read_csv(rates_path)
    rates['effective_start'] = pd.to_datetime(rates['effective_start'])
    rates['effective_end'] = pd.to_datetime(rates['effective_end']) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    
    for _, rate in rates.iterrows():
        date_mask = (df['Date/Time'] >= rate['effective_start']) & (df['Date/Time'] <= rate['effective_end'])
        
        m = df['Date/Time'].dt.month
        if rate['start_month'] <= rate['end_month']:
            season_mask = (m >= rate['start_month']) & (m <= rate['end_month'])
        else:
            season_mask = (m >= rate['start_month']) | (m <= rate['end_month'])
            
        combined_mask = date_mask & season_mask
        h = df['Date/Time'].dt.hour
        peak_mask = combined_mask & (h >= rate['peak_start_hour']) & (h < rate['peak_end_hour'])
        off_peak_mask = combined_mask & ~peak_mask
        
        df.loc[peak_mask, 'is_peak'] = True
        df.loc[peak_mask, 'import_rate'] = rate['import_on_peak']
        df.loc[off_peak_mask, 'import_rate'] = rate['import_off_peak']
        
        # Export rate mapping (1:1 net metering or specific feed-in tariff)
        if 'export_on_peak' in rate and 'export_off_peak' in rate:
            df.loc[peak_mask, 'export_rate'] = rate['export_on_peak']
            df.loc[off_peak_mask, 'export_rate'] = rate['export_off_peak']
        
    return df

def calculate_actual_bill(df):
    """Calculates both baseline (no solar/battery) and actual net bill (with solar/battery)."""
    if df.empty:
        return df
    
    # Conversion from Wh to kWh
    df['Consumed_kWh'] = df.get('consumed_wh', 0) / 1000.0
    df['Imported_kWh'] = df.get('imported_wh', 0) / 1000.0
    df['Produced_kWh'] = df.get('produced_wh', 0) / 1000.0
    df['Exported_kWh'] = df.get('exported_wh', 0) / 1000.0
    df['Battery_Discharge_kWh'] = df.get('battery_discharge_wh', 0) / 1000.0
    df['Battery_Charge_kWh'] = df.get('battery_charge_wh', 0) / 1000.0

    # Baseline Cost (What you would pay without solar/battery)
    df['cost_baseline'] = df['Consumed_kWh'] * df['import_rate']
    
    # Actual Import Cost & Export Credit
    df['cost_actual_import'] = df['Imported_kWh'] * df['import_rate']
    df['credit_actual_export'] = df['Exported_kWh'] * df['export_rate']
    
    # Net Actual Cost
    df['cost_actual_net'] = df['cost_actual_import'] - df['credit_actual_export']
    
    return df

def summarize_actual_vs_baseline(df):
    """Summarizes baseline vs actual bill metrics and total savings."""
    if df.empty:
        return {}
    
    total_consumed_kwh = df['Consumed_kWh'].sum()
    total_imported_kwh = df['Imported_kWh'].sum()
    total_produced_kwh = df['Produced_kWh'].sum()
    total_exported_kwh = df['Exported_kWh'].sum()
    total_battery_discharged_kwh = df['Battery_Discharge_kWh'].sum()

    baseline_cost = df['cost_baseline'].sum(skipna=True)
    actual_import_cost = df['cost_actual_import'].sum(skipna=True)
    actual_export_credit = df['credit_actual_export'].sum(skipna=True)
    actual_net_cost = df['cost_actual_net'].sum(skipna=True)
    
    total_savings = baseline_cost - actual_net_cost

    return {
        "consumed_kwh": total_consumed_kwh,
        "imported_kwh": total_imported_kwh,
        "produced_kwh": total_produced_kwh,
        "exported_kwh": total_exported_kwh,
        "battery_discharged_kwh": total_battery_discharged_kwh,
        "baseline_cost": baseline_cost,
        "actual_import_cost": actual_import_cost,
        "actual_export_credit": actual_export_credit,
        "actual_net_cost": actual_net_cost,
        "total_savings": total_savings,
        "savings_pct": (total_savings / baseline_cost * 100) if baseline_cost > 0 else 0
    }
