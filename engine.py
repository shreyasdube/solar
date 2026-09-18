import os
import sqlite3
import pandas as pd

DB_PATH = "data/enphase.db"

def load_energy_data(db_path=DB_PATH):
    """Loads interval data and pre-calculated rates directly from SQLite."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    query = """
    SELECT timestamp, consumed_wh, imported_wh, exported_wh, import_rate, export_rate, is_peak 
    FROM enphase_energy_data
    """
    try:
        df = pd.read_sql(query, conn)
    except Exception:
        df = pd.read_sql("SELECT * FROM enphase_energy_data", conn)
        
    conn.close()
    if not df.empty:
        df['Date/Time'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None)
        df['is_peak'] = df['is_peak'].astype(bool)
        df = df.sort_values('Date/Time').drop_duplicates(subset=['Date/Time'])
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

def summarize_slice(df):
    """Helper to compute aggregated metrics for a given subset (single month or overall)."""
    if df.empty:
        return {}

    peak_mask = df['is_peak'] == True
    offpeak_mask = df['is_peak'] == False

    baseline_cost = df['cost_baseline'].sum(skipna=True)
    actual_import_cost = df['cost_actual_import'].sum(skipna=True)
    actual_export_credit = df['credit_actual_export'].sum(skipna=True)
    actual_net_cost = df['cost_actual_net'].sum(skipna=True)

    peak_import_kwh = df.loc[peak_mask, 'Imported_kWh'].sum()
    peak_import_cost = df.loc[peak_mask, 'cost_actual_import'].sum(skipna=True)
    peak_export_kwh = df.loc[peak_mask, 'Exported_kWh'].sum()
    peak_export_credit = df.loc[peak_mask, 'credit_actual_export'].sum(skipna=True)

    offpeak_import_kwh = df.loc[offpeak_mask, 'Imported_kWh'].sum()
    offpeak_import_cost = df.loc[offpeak_mask, 'cost_actual_import'].sum(skipna=True)
    offpeak_export_kwh = df.loc[offpeak_mask, 'Exported_kWh'].sum()
    offpeak_export_credit = df.loc[offpeak_mask, 'credit_actual_export'].sum(skipna=True)

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
        "peak_import_kwh": peak_import_kwh,
        "peak_import_cost": peak_import_cost,
        "peak_export_kwh": peak_export_kwh,
        "peak_export_credit": peak_export_credit,
        "import_peak_rates": import_peak_rates,
        "export_peak_rates": export_peak_rates,
        "offpeak_import_kwh": offpeak_import_kwh,
        "offpeak_import_cost": offpeak_import_cost,
        "offpeak_export_kwh": offpeak_export_kwh,
        "offpeak_export_credit": offpeak_export_credit,
        "import_offpeak_rates": import_offpeak_rates,
        "export_offpeak_rates": export_offpeak_rates,
    }

def summarize_actual_vs_baseline(df):
    """Summarizes financial baseline vs actual net bill metrics overall and per month."""
    if df.empty:
        return {}

    overall_summary = summarize_slice(df)
    
    # Monthly Breakdown
    df['Month_Period'] = df['Date/Time'].dt.to_period('M')
    monthly_summaries = {}
    
    for month, group in df.groupby('Month_Period'):
        monthly_summaries[str(month)] = summarize_slice(group)

    overall_summary['monthly'] = monthly_summaries
    return overall_summary

if __name__ == "__main__":
    df = load_energy_data()
    if not df.empty:
        df = calculate_actual_bill(df)
        summary = summarize_actual_vs_baseline(df)
        
        print(f"Processed {len(df)} rows across {len(summary['monthly'])} month(s).\n")
        
        # Print Monthly Summaries
        for month, m_summary in summary['monthly'].items():
            print(f"==================== MONTH: {month} ====================")
            print(f"Baseline Cost:         ${m_summary['baseline_cost']:,.2f}")
            print(f"Actual Net Bill:       ${m_summary['actual_net_cost']:,.2f} (Savings: ${m_summary['total_savings']:,.2f})")
            print("ON-PEAK:")
            print(f"  Imports: {m_summary['peak_import_kwh']:,.1f} kWh | Cost: ${m_summary['peak_import_cost']:,.2f}")
            print(f"  Exports: {m_summary['peak_export_kwh']:,.1f} kWh | Credit: ${m_summary['peak_export_credit']:,.2f}")
            print("OFF-PEAK:")
            print(f"  Imports: {m_summary['offpeak_import_kwh']:,.1f} kWh | Cost: ${m_summary['offpeak_import_cost']:,.2f}")
            print(f"  Exports: {m_summary['offpeak_export_kwh']:,.1f} kWh | Credit: ${m_summary['offpeak_export_credit']:,.2f}\n")
        
        print("==================== OVERALL TOTAL ====================")
        print(f"Baseline Cost:         ${summary['baseline_cost']:,.2f}")
        print(f"Actual Net Bill:       ${summary['actual_net_cost']:,.2f} (Savings: ${summary['total_savings']:,.2f})")
    else:
        print("No data found in database. Run db.py first.")
