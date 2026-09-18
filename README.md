# Solar & Battery ROI Calculator

A Streamlit application designed to model electricity savings, battery arbitrage, and payback timelines using 15-minute interval data from Enphase solar systems.

## Prerequisites

- Docker & Docker Compose
- Git
- Python 3.11+ (for local development)

## Project Structure

```text
.
├── .gitignore
├── README.md
├── requirements.txt
├── raw_reports/       # Directory for monthly Enphase CSV exports
└── data/              # SQLite database storage (git-ignored)
```

## Installation

Add .gitignore
```bash
cat << 'EOF' > .gitignore
__pycache__/
*.py[cod]
.venv/
venv/
data/*.db
data/*.db-journal
.DS_Store
.idea/
.vscode/
EOF
```

Add requirements.txt
```bash
cat << 'EOF' > requirements.txt
streamlit>=1.30.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
EOF
```

Create a virtual environment & test dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Dev Notes

Verify DB has the right number of records

```python
python3 -c "import sqlite3; conn = sqlite3.connect('data/enphase.db'); count = conn.execute('SELECT count(*) FROM enphase_energy_data').fetchone()[0]; print(f'Total 15-min rows in database: {count}')"
```
