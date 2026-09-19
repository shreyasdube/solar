import os
import pandas as pd

OUTPUT_DIR = "data"
INPUT_FILE = os.path.join(OUTPUT_DIR, "enphase.csv")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "analysis.csv")

def run_financial_analysis():
    """
    Main orchestration engine. Loads data, passes it through the analysis 
    functions, handles file outputs, and prints summary metrics.
    """
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Base file '{INPUT_FILE}' not found. Please run inputs.py first.")
        return

    df = pd.read_csv(INPUT_FILE)

    analysis_df = pd.DataFrame()
    analysis_df['timestamp'] = df['timestamp']
    analysis_df['is_peak'] = df['is_peak']
    analysis_df['import_rate'] = df['import_rate']

    analysis_df = calculate_baseline(df, analysis_df)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    analysis_df.to_csv(OUTPUT_FILE, index=False)

    total_kwh = analysis_df['baseline_import_wh'].sum() / 1000.0
    total_cost = analysis_df['baseline_cost'].sum()

    print(f"Analysis successfully written to: {OUTPUT_FILE}")
    print(f"--- Baseline Performance Metrics ---")
    print(f"Total Consumption: {total_kwh:.2f} kWh")
    print(f"Total Grid Cost:   ${total_cost:.2f}")
    print(f"\nData Preview:")
    print(analysis_df.head(4).to_string(index=False))

def calculate_baseline(df, analysis_df):
    """
    Calculates baseline metrics as if the home had no solar or battery systems.
    Formula: baseline_import = consumed_wh - stored_wh
    """
    analysis_df['baseline_import_wh'] = (df['consumed_wh'] - df['stored_wh']).clip(lower=0)
    analysis_df['baseline_cost'] = (analysis_df['baseline_import_wh'] / 1000.0) * df['import_rate']
    analysis_df['baseline_cost'] = analysis_df['baseline_cost'].round(4)

    return analysis_df

if __name__ == "__main__":
    run_financial_analysis()
