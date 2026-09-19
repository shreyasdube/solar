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
    analysis_df['export_rate'] = df['export_rate']

    analysis_df = calculate_baseline(df, analysis_df)
    analysis_df = calculate_solar_battery(df, analysis_df)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    analysis_df.to_csv(OUTPUT_FILE, index=False)

    print(f"Analysis successfully written to: {OUTPUT_FILE}")


def calculate_baseline(df, analysis_df):
    """
    Calculates baseline metrics as if the home had no solar or battery systems.
    Formula: baseline_import = consumed_wh - stored_wh
    """
    analysis_df['baseline_import_kwh'] = ((df['consumed_wh'] - df['stored_wh']).clip(lower=0) / 1000.0).round(4)
    analysis_df['baseline_cost'] = (analysis_df['baseline_import_kwh'] * df['import_rate']).round(4)

    cols_to_sum = ['baseline_import_kwh', 'baseline_cost']
    months = pd.to_datetime(analysis_df['timestamp']).dt.strftime('%b %Y')
    summary = analysis_df.groupby([months, 'is_peak'])[cols_to_sum].sum()

    print(f"\n==============================================")
    print(f"       BASELINE PERFORMANCE METRICS           ")
    print(f"==============================================")
    for month in summary.index.get_level_values(0).unique():
        print(f"{month}:")
        print(f"   Total Cost   : {summary.loc[month, 'baseline_import_kwh'].sum():10.2f} kWh  |  Cost: ${summary.loc[month, 'baseline_cost'].sum():8.2f}")
        print(f"     └─ Peak    : {summary.loc[(month, True), 'baseline_import_kwh']:10.2f} kWh  |  Cost: ${summary.loc[(month, True), 'baseline_cost']:7.2f}")
        print(f"     └─ Off-Peak: {summary.loc[(month, False), 'baseline_import_kwh']:10.2f} kWh  |  Cost: ${summary.loc[(month, False), 'baseline_cost']:7.2f}")
        print(f"-------------------------------------------------------")

    return analysis_df


def calculate_solar_battery(df, analysis_df):
    """
    Calculates the real-world financial performance of your combined Solar + Battery setup.
    """
    analysis_df['solar_battery_import_kwh'] = (df['imported_wh'] / 1000.0).round(4)
    analysis_df['solar_battery_export_kwh'] = (df['exported_wh'] / 1000.0).round(4)
    analysis_df['solar_battery_net_kwh'] = (analysis_df['solar_battery_import_kwh'] - analysis_df['solar_battery_export_kwh']).round(4)
    
    analysis_df['solar_battery_import_cost'] = (analysis_df['solar_battery_import_kwh'] * df['import_rate']).round(4)
    analysis_df['solar_battery_export_cost'] = (analysis_df['solar_battery_export_kwh'] * df['export_rate']).round(4)
    analysis_df['solar_battery_net_cost'] = (analysis_df['solar_battery_import_cost'] - analysis_df['solar_battery_export_cost']).round(4)

    cols_to_sum = [
        'solar_battery_import_kwh', 'solar_battery_export_kwh', 'solar_battery_net_kwh',
        'solar_battery_import_cost', 'solar_battery_export_cost', 'solar_battery_net_cost'
    ]
    months = pd.to_datetime(analysis_df['timestamp']).dt.strftime('%b %Y')
    summary = analysis_df.groupby([months, 'is_peak'])[cols_to_sum].sum()

    print(f"\n=======================================================")
    print(f"       SOLAR+BATTERY PERFORMANCE METRICS  ")
    print(f"=======================================================")
    for month in summary.index.get_level_values(0).unique():
        p_row = summary.loc[(month, True)]
        op_row = summary.loc[(month, False)]
        
        total_net_kwh = summary.loc[month, 'solar_battery_net_kwh'].sum()
        total_net_cost = summary.loc[month, 'solar_battery_net_cost'].sum()

        print(f"{month}:")
        print(f"   Total Net Summary : {total_net_kwh:10.2f} kWh  |  Net Bill: ${total_net_cost:7.2f}")
        print(f"     ├─ [PEAK WINDOW]")
        print(f"     │    ├── Import : {p_row['solar_battery_import_kwh']:10.2f} kWh  |  Cost  : ${p_row['solar_battery_import_cost']:7.2f}")
        print(f"     │    ├── Export : {p_row['solar_battery_export_kwh']:10.2f} kWh  |  Credit: ${p_row['solar_battery_export_cost']:7.2f}")
        print(f"     │    └── Net    : {p_row['solar_battery_net_kwh']:10.2f} kWh  |  Net   : ${p_row['solar_battery_net_cost']:7.2f}")
        print(f"     └─ [OFF-PEAK WINDOW]")
        print(f"     │    ├── Import : {op_row['solar_battery_import_kwh']:10.2f} kWh  |  Cost  : ${op_row['solar_battery_import_cost']:7.2f}")
        print(f"     │    ├── Export : {op_row['solar_battery_export_kwh']:10.2f} kWh  |  Credit: ${op_row['solar_battery_export_cost']:7.2f}")
        print(f"     │    └── Net    : {op_row['solar_battery_net_kwh']:10.2f} kWh  |  Net   : ${op_row['solar_battery_net_cost']:7.2f}")
        print(f"-------------------------------------------------------")

    return analysis_df

if __name__ == "__main__":
    run_financial_analysis()
