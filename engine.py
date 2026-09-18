import os
import sqlite3
import pandas as pd
import numpy as np

DB_PATH = "data/enphase.db"
RATES_PATH = "rates_schedule.csv"

def load_energy_data(db_path=DB_PATH):
    """Loads interval data from SQLite enphase_energy_data table."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT timestamp, consumed_wh, imported_wh, exported_wh 
    FROM enphase_energy_data
    """
    try:
        df = pd.read_sql(query, conn)
    except Exception:
        df = pd.read_sql("SELECT * FROM enphase_energy_data", conn)
        
    conn.close()
    if not df.empty:
        df['Date/Time'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
        df = df.sort_values('Date/Time').drop_duplicates(subset=['Date/Time'])
    return df

def apply_tariffs(df, rates_path=RATES_PATH):
    """Maps seasonal TOU import and export tariffs to each 15-minute interval."""
    df['import_rate'] = np.nan
    df['export_rate'] = 0.0
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
        
        # Solar export rates (use export columns if defined in CSV, else default to 1:1 net metering)
        if 'export_on_peak' in rate and 'export_off_peak' in rate:
            df.loc[peak_mask, 'export_rate'] = rate['export_on_peak']
            df.loc[off_peak_mask, 'export_rate'] = rate['export_off_peak']
        else:
            # 1:1 Net Metering fallback
            df.loc[peak_mask, 'export_rate'] = rate['import_on_peak']
            df.loc[off_peak_mask, 'export_rate'] = rate['import_off_peak']
        
    return df

def calculate_actual_bill(df):
    """Calculates baseline vs actual net bill based strictly on grid import and export."""
    if df.empty:
        return df
    
    # Wh to kWh
    df['Consumed_kWh'] = df.get('consumed_wh', 0) / 1000.0
    df['Imported_kWh'] = df.get('imported_wh', 0) / 1000.0
    df['Exported_kWh'] = df.get('exported_wh', 0) / 1000.0

    # Baseline Cost (No solar/battery)
    df['cost_baseline'] = df['Consumed_kWh'] * df['import_rate']
    
    # Actual Bill = (Grid Import * Import Rate) - (Grid Export * Export Rate)
    df['cost_actual_import'] = df['Imported_kWh'] * df['import_rate']
    df['credit_actual_export'] = df['Exported_kWh'] * df['export_rate']
    df['cost_actual_net'] = df['cost_actual_import'] - df['credit_actual_export']
    
    return df

def summarize_actual_vs_baseline(df):
    """Summarizes financial baseline vs actual net bill metrics."""
    if df.empty:
        return {}
    
    baseline_cost = df['cost_baseline'].sum(skipna=True)
    actual_import_cost = df['cost_actual_import'].sum(skipna=True)
    actual_export_credit = df['credit_actual_export'].sum(skipna=True)
    actual_net_cost = df['cost_actual_net'].sum(skipna=True)
    total_savings = baseline_cost - actual_net_cost

    return {
        "consumed_kwh": df['Consumed_kWh'].sum(),
        "imported_kwh": df['Imported_kWh'].sum(),
        "exported_kwh": df['Exported_kWh'].sum(),
        "baseline_cost": baseline_cost,
        "actual_import_cost": actual_import_cost,
        "actual_export_credit": actual_export_credit,
        "actual_net_cost": actual_net_cost,
        "total_savings": total_savings,
        "savings_pct": (total_savings / baseline_cost * 100) if baseline_cost > 0 else 0
    }

if __name__ == "__main__":
    df = load_energy_data()
    if not df.empty:
        df = apply_tariffs(df)
        df = calculate_actual_bill(df)
        summary = summarize_actual_vs_baseline(df)
        
        print(f"Processed {len(df)} rows.")
        print(f"Baseline Cost:         ${summary['baseline_cost']:,.2f}")
        print(f"Actual Grid Import:    ${summary['actual_import_cost']:,.2f} ({summary['imported_kwh']:,.1f} kWh)")
        print(f"Actual Export Credit: -${summary['actual_export_credit']:,.2f} ({summary['exported_kwh']:,.1f} kWh)")
        print(f"Actual Net Bill:       ${summary['actual_net_cost']:,.2f}")
        print(f"Total Net Savings:     ${summary['total_savings']:,.2f} ({summary['savings_pct']:.1f}%)")
    else:
        print("No data found in database. Run db.py first.")
