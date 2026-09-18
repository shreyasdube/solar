import os
import sqlite3
import glob
import pandas as pd
import numpy as np

DB_PATH = "data/enphase.db"
DATA_DIR = "raw_reports"
RATES_PATH = "rates_schedule.csv"

def get_rates_df(rates_path=RATES_PATH):
    """Loads and formats the rate schedule."""
    if not os.path.exists(rates_path):
        return pd.DataFrame()
    rates = pd.read_csv(rates_path)
    rates['effective_start'] = pd.to_datetime(rates['effective_start']).dt.tz_localize(None)
    rates['effective_end'] = (pd.to_datetime(rates['effective_end']) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)).dt.tz_localize(None)
    return rates

def apply_tariffs_to_df(df, rates_df):
    """Maps tariffs directly onto the usage dataframe."""
    df['import_rate'] = np.nan
    df['export_rate'] = 0.0
    df['is_peak'] = False

    if rates_df.empty or df.empty:
        return df

    for _, rate in rates_df.iterrows():
        date_mask = (df['timestamp'] >= rate['effective_start']) & (df['timestamp'] <= rate['effective_end'])
        m = df['timestamp'].dt.month
        if rate['start_month'] <= rate['end_month']:
            season_mask = (m >= rate['start_month']) & (m <= rate['end_month'])
        else:
            season_mask = (m >= rate['start_month']) | (m <= rate['end_month'])
        
        combined_mask = date_mask & season_mask
        h = df['timestamp'].dt.hour
        peak_mask = combined_mask & (h >= rate['peak_start_hour']) & (h < rate['peak_end_hour'])
        off_peak_mask = combined_mask & ~peak_mask

        df.loc[peak_mask, 'is_peak'] = True
        df.loc[peak_mask, 'import_rate'] = rate['import_on_peak']
        df.loc[off_peak_mask, 'import_rate'] = rate['import_off_peak']
        
        if 'export_rate' in rate and pd.notna(rate['export_rate']):
            df.loc[combined_mask, 'export_rate'] = rate['export_rate']

    return df

def ingest_csv_files(data_dir=DATA_DIR, db_path=DB_PATH):
    """Ingests all CSV files in raw_reports/data, maps rates, pre-calculates scenarios, and updates SQLite."""
    rates_df = get_rates_df()
    search_dirs = [data_dir, "data"]
    csv_files = []
    for d in search_dirs:
        if os.path.exists(d):
            csv_files.extend(glob.glob(os.path.join(d, "*.csv")))
            csv_files.extend(glob.glob(os.path.join(d, "*.CSV")))
    
    csv_files = list(set([f for f in csv_files if not f.endswith("rates_schedule.csv")]))

    if not csv_files:
        print("No energy usage CSV files found to process.")
        return

    frames = []
    for f in csv_files:
        try:
            temp_df = pd.read_csv(f)
            frames.append(temp_df)
        except Exception as e:
            print(f"Error reading {f}: {e}")

    if not frames:
        print("No valid data frames loaded from CSVs.")
        return

    raw_df = pd.concat(frames, ignore_index=True)

    ts_col = [c for c in raw_df.columns if 'date' in c.lower() or 'time' in c.lower()][0]
    raw_df['timestamp'] = pd.to_datetime(raw_df[ts_col], errors='coerce')
    if raw_df['timestamp'].dt.tz is not None:
        raw_df['timestamp'] = raw_df['timestamp'].dt.tz_localize(None)

    col_map = {}
    for c in raw_df.columns:
        clow = c.lower()
        if 'consume' in clow: col_map[c] = 'consumed_wh'
        elif 'produce' in clow: col_map[c] = 'produced_wh'
        elif 'import' in clow: col_map[c] = 'imported_wh'
        elif 'export' in clow: col_map[c] = 'exported_wh'
        elif 'stored' in clow: col_map[c] = 'stored_wh'
        elif 'discharge' in clow or 'disched' in clow: col_map[c] = 'discharged_wh'

    raw_df = raw_df.rename(columns=col_map)
    raw_df = raw_df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])

    processed_df = apply_tariffs_to_df(raw_df, rates_df)

    # 1. Base Unit Conversions (Wh to kWh)
    processed_df['Consumed_kWh'] = processed_df.get('consumed_wh', 0.0) / 1000.0
    processed_df['Produced_kWh'] = processed_df.get('produced_wh', 0.0) / 1000.0
    processed_df['Imported_kWh'] = processed_df.get('imported_wh', 0.0) / 1000.0
    processed_df['Exported_kWh'] = processed_df.get('exported_wh', 0.0) / 1000.0
    processed_df['Stored_kWh'] = processed_df.get('stored_wh', 0.0) / 1000.0
    processed_df['Discharged_kWh'] = processed_df.get('discharged_wh', 0.0) / 1000.0

    # 2. Baseline Cost (No Solar/Battery)
    processed_df['cost_baseline'] = processed_df['Consumed_kWh'] * processed_df['import_rate']

    # 3. Actual Costs (Solar + Battery)
    processed_df['cost_actual_import'] = processed_df['Imported_kWh'] * processed_df['import_rate']
    processed_df['credit_actual_export'] = processed_df['Exported_kWh'] * processed_df['export_rate']
    processed_df['cost_actual_net'] = processed_df['cost_actual_import'] - processed_df['credit_actual_export']

    # 4. Solar Only Simulation (Instantaneous Physical Balance)
    processed_df['Solar_Only_Import_kWh'] = (processed_df['Consumed_kWh'] - processed_df['Produced_kWh']).clip(lower=0)
    processed_df['Solar_Only_Export_kWh'] = (processed_df['Produced_kWh'] - processed_df['Consumed_kWh']).clip(lower=0)
    processed_df['cost_solar_only_import'] = processed_df['Solar_Only_Import_kWh'] * processed_df['import_rate']
    processed_df['credit_solar_only_export'] = processed_df['Solar_Only_Export_kWh'] * processed_df['export_rate']
    processed_df['cost_solar_only_net'] = processed_df['cost_solar_only_import'] - processed_df['credit_solar_only_export']

    # 5. Battery Only Simulation (Arbitrage Only, No Solar)
    ROUND_TRIP_EFFICIENCY = 0.90  # 90% combined efficiency for charge + discharge cycles

    processed_df['Battery_Only_Discharged_kWh'] = np.where(
        processed_df['is_peak'], 
        processed_df['Discharged_kWh'], 
        0.0
    )

    total_discharged_peak = processed_df['Battery_Only_Discharged_kWh'].sum()
    offpeak_mask = processed_df['is_peak'] == False
    num_offpeak_intervals = offpeak_mask.sum()

    processed_df['Battery_Only_Charging_kWh'] = 0.0
    if num_offpeak_intervals > 0 and total_discharged_peak > 0:
        energy_needed_per_offpeak_interval = (total_discharged_peak / ROUND_TRIP_EFFICIENCY) / num_offpeak_intervals
        processed_df.loc[offpeak_mask, 'Battery_Only_Charging_kWh'] = energy_needed_per_offpeak_interval

    processed_df['Battery_Only_Import_kWh'] = np.where(
        processed_df['is_peak'],
        (processed_df['Consumed_kWh'] - processed_df['Battery_Only_Discharged_kWh']).clip(lower=0),
        processed_df['Consumed_kWh'] + processed_df['Battery_Only_Charging_kWh']
    )
    processed_df['cost_battery_only'] = processed_df['Battery_Only_Import_kWh'] * processed_df['import_rate']

    # Build final DataFrame to write into SQLite
    db_df = pd.DataFrame({
        'timestamp': processed_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S'),
        'consumed_wh': processed_df.get('consumed_wh', 0.0),
        'produced_wh': processed_df.get('produced_wh', 0.0),
        'imported_wh': processed_df.get('imported_wh', 0.0),
        'exported_wh': processed_df.get('exported_wh', 0.0),
        'stored_wh': processed_df.get('stored_wh', 0.0),
        'discharged_wh': processed_df.get('discharged_wh', 0.0),
        'Consumed_kWh': processed_df['Consumed_kWh'],
        'Produced_kWh': processed_df['Produced_kWh'],
        'Imported_kWh': processed_df['Imported_kWh'],
        'Exported_kWh': processed_df['Exported_kWh'],
        'Stored_kWh': processed_df['Stored_kWh'],
        'Discharged_kWh': processed_df['Discharged_kWh'],
        'import_rate': processed_df['import_rate'],
        'export_rate': processed_df['export_rate'],
        'is_peak': processed_df['is_peak'].astype(int),
        'cost_baseline': processed_df['cost_baseline'],
        'cost_actual_import': processed_df['cost_actual_import'],
        'credit_actual_export': processed_df['credit_actual_export'],
        'cost_actual_net': processed_df['cost_actual_net'],
        'Solar_Only_Import_kWh': processed_df['Solar_Only_Import_kWh'],
        'Solar_Only_Export_kWh': processed_df['Solar_Only_Export_kWh'],
        'cost_solar_only_net': processed_df['cost_solar_only_net'],
        'Battery_Only_Import_kWh': processed_df['Battery_Only_Import_kWh'],
        'cost_battery_only': processed_df['cost_battery_only']
    })

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    db_df.to_sql("enphase_energy_data", conn, if_exists="replace", index=False)
    conn.close()

    print(f"Successfully re-indexed and updated {db_path}. Total records: {len(db_df)}")

if __name__ == "__main__":
    ingest_csv_files()
