import os
import glob
import pandas as pd 

RAW_INPUTS_DIR = "raw_inputs"
OUTPUT_DIR = "data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "enphase.csv")

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

if __name__ == "__main__":
    process_raw_data()

