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
        
        if 'export_on_peak' in rate and 'export_off_peak' in rate:
            df.loc[peak_mask, 'export_rate'] = rate['export_on_peak']
            df.loc[off_peak_mask, 'export_rate'] = rate['export_off_peak']
        else:
            # Fallback 1:1 net metering
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
    
    # Actual Imports & Exports
    df['cost_actual_import'] = df['Imported_kWh'] * df['import_rate']
    df['credit_actual_export'] = df['Exported_kWh'] * df['export_rate']
    df['cost_actual_net'] = df['cost_actual_import'] - df['credit_actual_export']
    
    return df

def summarize_actual_vs_baseline(df):
    """Summarizes financial baseline vs actual net bill metrics by Peak and Off-Peak."""
    if df.empty:
        return {}
    
    peak_mask = df['is_peak'] == True
    offpeak_mask = df['is_peak'] == False

    baseline_cost = df['cost_baseline'].sum(skipna=True)
    actual_import_cost = df['cost_actual_import'].sum(skipna=True)
    actual_export_credit = df['credit_actual_export'].sum(skipna=True)
    actual_net_cost = df['cost_actual_net'].sum(skipna=True)

    # Detailed Peak Breakdown
    peak_import_kwh = df.loc[peak_mask, 'Imported_kWh'].sum()
    peak_import_cost = df.loc[peak_mask, 'cost_actual_import'].sum(skipna=True)
    peak_export_kwh = df.loc[peak_mask, 'Exported_kWh'].sum()
    peak_export_credit = df.loc[peak_mask, 'credit_actual_export'].sum(skipna=True)

    # Detailed Off-Peak Breakdown
    offpeak_import_kwh = df.loc[offpeak_mask, 'Imported_kWh'].sum()
    offpeak_import_cost = df.loc[offpeak_mask, 'cost_actual_import'].sum(skipna=True)
    offpeak_export_kwh = df.loc[offpeak_mask, 'Exported_kWh'].sum()
    offpeak_export_credit = df.loc[offpeak_mask, 'credit_actual_export'].sum(skipna=True)

    # Rates Arrays
    import_peak_rates = [float(r) for r in sorted(df.loc[peak_mask, 'import_rate'].dropna().unique())]
    import_offpeak_rates = [float(r) for r in sorted(df.loc[offpeak_mask, 'import_rate'].dropna().unique())]
    export_peak_rates = [float(r) for r in sorted(df.loc[peak_mask, 'export_rate'].dropna().unique())]
    export_offpeak_rates = [float(r) for r in sorted(df.loc[offpeak_mask, 'export_rate'].dropna().unique())]

    return {
        "consumed_kwh": df['Consumed_kWh'].sum(),
        "imported_kwh": df['Imported_kWh'].sum(),
        "exported_kwh": df['Exported_kWh'].sum(),
        "baseline_cost": baseline_cost,
        "actual_import_cost": actual_import_cost,
        "actual_export_credit": actual_export_credit,
        "actual_net_cost": actual_net_cost,
        "total_savings": baseline_cost - actual_net_cost,
        "savings_pct": ((baseline_cost - actual_net_cost) / baseline_cost * 100) if baseline_cost > 0 else 0,
        # Peak Details
        "peak_import_kwh": peak_import_kwh,
        "peak_import_cost": peak_import_cost,
        "peak_export_kwh": peak_export_kwh,
        "peak_export_credit": peak_export_credit,
        "import_peak_rates": import_peak_rates,
        "export_peak_rates": export_peak_rates,
        # Off-Peak Details
        "offpeak_import_kwh": offpeak_import_kwh,
        "offpeak_import_cost": offpeak_import_cost,
        "offpeak_export_kwh": offpeak_export_kwh,
        "offpeak_export_credit": offpeak_export_credit,
        "import_offpeak_rates": import_offpeak_rates,
        "export_offpeak_rates": export_offpeak_rates,
    }

if __name__ == "__main__":
    df = load_energy_data()
    if not df.empty:
        df = apply_tariffs(df)
        df = calculate_actual_bill(df)
        summary = summarize_actual_vs_baseline(df)
        
        print(f"Processed {len(df)} rows.")
        print(f"Baseline Cost:         ${summary['baseline_cost']:,.2f}")
        print(f"Actual Net Bill:       ${summary['actual_net_cost']:,.2f} (Savings: ${summary['total_savings']:,.2f})")
        print("-" * 50)
        print("ON-PEAK BREAKDOWN:")
        print(f"  Imports: {summary['peak_import_kwh']:,.1f} kWh | Cost: ${summary['peak_import_cost']:,.2f} | Rates: {summary['import_peak_rates']}")
        print(f"  Exports: {summary['peak_export_kwh']:,.1f} kWh | Credit: ${summary['peak_export_credit']:,.2f} | Rates: {summary['export_peak_rates']}")
        print("OFF-PEAK BREAKDOWN:")
        print(f"  Imports: {summary['offpeak_import_kwh']:,.1f} kWh | Cost: ${summary['offpeak_cost']:,.2f} | Rates: {summary['import_offpeak_rates']}")
        print(f"  Exports: {summary['offpeak_export_kwh']:,.1f} kWh | Credit: ${summary['offpeak_export_credit']:,.2f} | Rates: {summary['export_offpeak_rates']}")
    else:
        print("No data found in database. Run db.py first.")
