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
