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
    print("Hello")

if __name__ == "__main__":
    process_raw_data()

