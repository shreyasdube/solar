import os
import glob
import sqlite3
import pandas as pd

DB_PATH = "data/enphase.db"
RAW_REPORTS_DIR = "raw_reports"

def init_db():
    """Initializes the SQLite database and enphase_energy_data table if not present."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS enphase_energy_data (
            timestamp TEXT PRIMARY KEY,
            produced_wh INTEGER,
            consumed_wh INTEGER,
            exported_wh INTEGER,
            imported_wh INTEGER,
            stored_battery_wh INTEGER,
            discharged_battery_wh INTEGER
        )
    """)
    conn.commit()
    conn.close()

def ingest_enphase_df(df):
    """Parses an Enphase DataFrame and upserts rows into SQLite."""
    df.columns = df.columns.str.strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    rows = []
    for _, r in df.iterrows():
        rows.append((
            str(r['Date/Time']),
            int(r['Energy Produced (Wh)']),
            int(r['Energy Consumed (Wh)']),
            int(r['Exported to Grid (Wh)']),
            int(r['Imported from Grid (Wh)']),
            int(r['Stored in batteries (Wh)']),
            int(r['Discharged from batteries (Wh)'])
        ))
    cursor.executemany("""
        INSERT OR IGNORE INTO enphase_energy_data VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()

def sync_raw_reports_folder():
    """Scans raw_reports/ directory for CSVs and ingests them into SQLite."""
    if os.path.exists(RAW_REPORTS_DIR):
        csv_files = glob.glob(os.path.join(RAW_REPORTS_DIR, "*.csv"))
        for f in csv_files:
            try:
                df = pd.read_csv(f)
                ingest_enphase_df(df)
            except Exception as e:
                print(f"Skipping {f}: {e}")

if __name__ == "__main__":
    init_db()
    sync_raw_reports_folder()
    print("Database synced successfully.")
