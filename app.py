import os
import pandas as pd
import streamlit as str

str.set_page_config(
    page_title="Energy Performance Dashboard",
    page_icon="⚡",
    layout="wide"
)

ANALYSIS_FILE = os.path.join("data", "analysis.csv")

str.title("⚡ Energy System Financial Analysis")
str.markdown("Compare monthly utility costs across different solar and storage configurations.")
