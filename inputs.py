import os
import glob
import pandas as pd 

RAW_INPUTS_DIR = "raw_inputs"
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "enphase.csv")
RATES_FILE = os.path.join(OUTPUT_DIR, "rates_schedule.csv")

def process_raw_data():
    """
      Reads all raw Enphase CSV reports from raw_inputs/,
      deduplicates 15-min intervals, aggregates energy values hourly,
      and writes to enphase.csv.
    """
    # Ensure output directory exists 
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    # Find all CSV files in input directory
    csv_files = glob.glob(os.path.join(RAW_INPUTS_DIR, "*.csv"))
    if not csv_files:
        print(f"No CSV files found in directory: '{RAW_INPUTS_DIR}'")
        return

    frames = [] 
    for filepath in csv_files:
        try:
            temp_df = pd.read_csv(filepath)

            # Add timestamp column and remove original Date/Time column
            temp_df.insert(0, 'timestamp', pd.to_datetime(temp_df[temp_df.columns[0]]))
            temp_df = temp_df.drop(columns=[temp_df.columns[1]])

            # Clean up metric headers into snake_case format
            col_map = {
                c: f"{keyword}_wh"
                for c in temp_df.columns
                for keyword in ['produced', 'consumed', 'imported', 'exported', 'stored', 'discharged']
                if keyword in c.lower()
            }
            temp_df = temp_df.rename(columns=col_map)

            print(temp_df.columns.tolist())
            print(temp_df[['timestamp', 'produced_wh', 'consumed_wh']].head())
            print(temp_df.info())

            frames.append(temp_df)
        except Exception as e: 
            print(f"Error processing {filepath}: {e}")

    if not frames: 
        print("No valid energy interval data found.")
        return

    # Combine all input reports
    combined_df = pd.concat(frames, ignore_index=True)
    combined_df = combined_df.sort_values('timestamp').drop_duplicates(subset=['timestamp']).reset_index(drop=True)

    # Aggregate by hourly
    combined_df['hourly_timestamp'] = combined_df['timestamp'].dt.floor('h')
    energy_cols = ['produced_wh', 'consumed_wh', 'exported_wh', 'imported_wh', 'stored_wh', 'discharged_wh']
    hourly_df = combined_df.groupby('hourly_timestamp')[energy_cols].sum().reset_index()
    hourly_df = hourly_df.rename(columns={'hourly_timestamp': 'timestamp'})

    # Apply rates schedule mapping
    hourly_df = apply_rate_schedule(hourly_df)
    if hourly_df is None:
        print("Aborting file save because rate schedule mapping failed.")
        return

    hourly_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Processed {len(csv_files)} raw file(s) into {len(hourly_df)} hourly records.")
    print(f"Output saved to: {OUTPUT_FILE}")

    print(hourly_df.head(3).to_string(index=False))
    print(hourly_df.tail(3).to_string(index=False))
    print(f"Total Rows: {hourly_df.shape[0]} | Total Columns: {hourly_df.shape[1]}")

def apply_rate_schedule(df):
    """
    Reads the utility rates schedule and maps is_peak, import_rate, 
    and export_rate columns to the energy dataframe based on the timestamp.
    """
    if not os.path.exists(RATES_FILE):
        print(f"Warning: '{RATES_FILE}' not found. Returning null.")
        return None
    
    # Load rates and parse dates
    rates_df = pd.read_csv(RATES_FILE)
    rates_df['effective_start'] = pd.to_datetime(rates_df['effective_start'])
    rates_df['effective_end'] = pd.to_datetime(rates_df['effective_end'])

    # Initialize destination columns with default values
    df['is_peak'] = False
    df['import_rate'] = 0.0
    df['export_rate'] = 0.0
    months = df['timestamp'].dt.month
    hours = df['timestamp'].dt.hour

    # Iterate over each row in the rate schedule to apply matching rules
    for _, rule in rates_df.iterrows():
        # 1. Match overall date range and season months
        date_mask = df['timestamp'].between(rule['effective_start'], rule['effective_end'])
        month_mask = months.between(rule['start_month'], rule['end_month']) if rule['start_month'] <= rule['end_month'] else (months >= rule['start_month']) | (months <= rule['end_month'])
        rule_mask = date_mask & month_mask
        
        if not rule_mask.any():
            continue

        # 2. Set default Off-Peak values for the matching season window
        df.loc[rule_mask, ['is_peak', 'import_rate', 'export_rate']] = [False, rule['import_off_peak'], rule['export_off_peak']]

        # 3. Overwrite just the Peak hours within that window
        peak_mask = rule_mask & hours.between(rule['peak_start_hour'], rule['peak_end_hour'], inclusive='left')
        df.loc[peak_mask, ['is_peak', 'import_rate', 'export_rate']] = [True, rule['import_on_peak'], rule['export_on_peak']]

    return df

if __name__ == "__main__":
    process_raw_data()

