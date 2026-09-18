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
        
        if 'export_on_peak' in rate and 'export_off_peak' in rate:
            df.loc[peak_mask, 'export_rate'] = rate['export_on_peak']
            df.loc[off_peak_mask, 'export_rate'] = rate['export_off_peak']
        else:
            df.loc[peak_mask, 'export_rate'] = rate['import_on_peak']
            df.loc[off_peak_mask, 'export_rate'] = rate['import_off_peak']
            
    return df

def ingest_csv_files(data_dir=DATA_DIR, db_path=DB_PATH):
    """Ingests all CSV files in raw_reports/data, maps rates, and updates SQLite."""
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
            ts_col = [c for c in temp_df.columns if 'date' in c.lower() or 'time' in c.lower()][0]
            # Convert to standard pandas datetime and strip timezone info
            temp_df['timestamp'] = pd.to_datetime(temp_df[ts_col], format='ISO8601', errors='coerce')
            if temp_df['timestamp'].dt.tz is not None:
                temp_df['timestamp'] = temp_df['timestamp'].dt.tz_localize(None)
                
            temp_df = temp_df.dropna(subset=['timestamp'])
            frames.append(temp_df)
        except Exception as e:
            print(f"Skipping {f}: {e}")

    if not frames:
        return

    raw_df = pd.concat(frames, ignore_index=True)
    
    col_map = {}
    for c in raw_df.columns:
        clow = c.lower()
        if 'consumed' in clow: col_map[c] = 'consumed_wh'
        elif 'imported' in clow: col_map[c] = 'imported_wh'
        elif 'exported' in clow: col_map[c] = 'exported_wh'
    
    raw_df = raw_df.rename(columns=col_map)
    raw_df = raw_df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])

    processed_df = apply_tariffs_to_df(raw_df, rates_df)
    
    # Store timestamp in SQLite as standard ISO format string (YYYY-MM-DD HH:MM:SS)
    db_df = pd.DataFrame({
        'timestamp': processed_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S'),
        'consumed_wh': processed_df.get('consumed_wh', 0.0),
        'imported_wh': processed_df.get('imported_wh', 0.0),
        'exported_wh': processed_df.get('exported_wh', 0.0),
        'import_rate': processed_df['import_rate'],
        'export_rate': processed_df['export_rate'],
        'is_peak': processed_df['is_peak'].astype(int)
    })

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    
    # Overwrite DB with the clean schema and formatted strings
    db_df.to_sql("enphase_energy_data", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Successfully re-indexed and updated {db_path}. Total records: {len(db_df)}")

if __name__ == "__main__":
    ingest_csv_files()
