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
    df = pd.read_sql("SELECT timestamp, consumed_wh, imported_wh FROM enphase_energy_data", conn)
    conn.close()
    if not df.empty:
        # Parse datetime and convert to timezone-naive to match rates_schedule.csv
        df['Date/Time'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
        df = df.sort_values('Date/Time').drop_duplicates(subset=['Date/Time'])
    return df

def apply_tariffs(df, rates_path=RATES_PATH):
    """Maps seasonal TOU import tariffs to each 15-minute interval."""
    df['import_rate'] = np.nan
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
        
    return df

def calculate_baseline(df):
    """Calculates baseline consumption and cost."""
    if df.empty:
        return df
    
    # Wh to kWh
    df['Consumed_kWh'] = df['consumed_wh'] / 1000.0
    # Baseline Cost = Total Energy Consumed * Import Rate
    df['cost_baseline'] = df['Consumed_kWh'] * df['import_rate']
    return df

def summarize_baseline(df):
    """Calculates summary metrics and explicit rates applied for Peak and Off-Peak windows."""
    if df.empty:
        return {}
    
    peak_mask = df['is_peak'] == True
    offpeak_mask = df['is_peak'] == False

    peak_kwh = df.loc[peak_mask, 'Consumed_kWh'].sum()
    offpeak_kwh = df.loc[offpeak_mask, 'Consumed_kWh'].sum()
    total_kwh = df['Consumed_kWh'].sum()

    peak_cost = df.loc[peak_mask, 'cost_baseline'].sum(skipna=True)
    offpeak_cost = df.loc[offpeak_mask, 'cost_baseline'].sum(skipna=True)
    total_cost = df['cost_baseline'].sum(skipna=True)

    # Distinct rates used in mapped dataset
    peak_rates = sorted(df.loc[peak_mask, 'import_rate'].dropna().unique())
    offpeak_rates = sorted(df.loc[offpeak_mask, 'import_rate'].dropna().unique())

    return {
        "total_kwh": total_kwh,
        "peak_kwh": peak_kwh,
        "offpeak_kwh": offpeak_kwh,
        "total_cost": total_cost,
        "peak_cost": peak_cost,
        "offpeak_cost": offpeak_cost,
        "effective_rate": total_cost / total_kwh if total_kwh > 0 else 0,
        "peak_rates": peak_rates,
        "offpeak_rates": offpeak_rates,
    }

if __name__ == "__main__":
    df = load_energy_data()
    if not df.empty:
        df = apply_tariffs(df)
        df = calculate_baseline(df)
        summary = summarize_baseline(df)
        
        print(f"Processed {len(df)} rows.")
        print(f"Total Usage:    {summary['total_kwh']:,.1f} kWh | Cost: ${summary['total_cost']:,.2f}")
        print(f"Peak Usage:     {summary['peak_kwh']:,.1f} kWh | Cost: ${summary['peak_cost']:,.2f} | Rates Used: {summary['peak_rates']}")
        print(f"Off-Peak Usage: {summary['offpeak_kwh']:,.1f} kWh | Cost: ${summary['offpeak_cost']:,.2f} | Rates Used: {summary['offpeak_rates']}")
    else:
        print("No data found in database. Run db.py first.")
