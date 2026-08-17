"""
data_loader.py
Loads and lightly cleans the Annual / Quarterly financial CSVs.

Why this exists: the original scripts (Accuracy.py, Internal.py, prior.py)
each read CSVs independently with slightly different column-name
assumptions (e.g. 'Net cash flow' vs 'Net cash flow '). Centralizing the
load + column-normalization here means every module sees the same clean
column names, so a fix here fixes it everywhere.
"""

import pandas as pd


# Common labels used by exports from accounting systems and public filings.
# They are converted to the names the analysis modules use internally.
COLUMN_ALIASES = {
    "year": "Year",
    "fiscal year": "Year",
    "quarter": "Quarters",
    "quarters": "Quarters",
    "fiscal quarter": "Quarters",
    "revenue": "Revenues",
    "revenues": "Revenues",
    "total revenue": "Revenues",
    "sales": "Revenues",
    "total assets": "Total Assets",
    "assets": "Total Assets",
    "total liabilities": "Total Liabilities",
    "liabilities": "Total Liabilities",
    "total equity": "Total Equity",
    "shareholders equity": "Total Equity",
    "shareholder equity": "Total Equity",
    "stockholders equity": "Total Equity",
    "operating income": "Operating income",
    "operating profit": "Operating income",
    "ebit": "Operating income",
    "net income": "Net income",
    "net profit": "Net income",
    "income after tax": "Income after tax",
    "headcount": "Headcount",
    "employee count": "Headcount",
    "employees": "Headcount",
    "cash flow from operating activities": "Net cash flow by operating activity",
    "net cash flow from operating activities": "Net cash flow by operating activity",
    "net cash flow by operating activity": "Net cash flow by operating activity",
    "cash flow from investing activities": "Net cash flow by investing activity",
    "net cash flow from investing activities": "Net cash flow by investing activity",
    "net cash flow by investing activity": "Net cash flow by investing activity",
    "cash flow from financing activities": "Net cash flow by financial activity",
    "net cash flow from financing activities": "Net cash flow by financial activity",
    "net cash flow by financial activity": "Net cash flow by financial activity",
    "net cash flow": "Net cash flow",
    "cash and cash equivalents net change": "Net cash flow",
    "predicted revenue": "Predicted revenue",
    "revenue forecast": "Predicted revenue",
}


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common CSV headers and financial number formats."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={c: COLUMN_ALIASES.get(c.casefold(), c) for c in df.columns})

    # Accounting exports often contain commas, currency marks, or parentheses
    # for negatives. Convert values where possible while leaving text intact.
    for column in df.columns:
        if column in {"Year", "Quarters"}:
            continue
        if df[column].dtype == object:
            cleaned = (df[column].astype(str).str.strip()
                       .str.replace(",", "", regex=False)
                       .str.replace("$", "", regex=False)
                       .str.replace("(", "-", regex=False)
                       .str.replace(")", "", regex=False)
                       .replace({"": None, "nan": None, "N/A": None, "-": None}))
            numeric = pd.to_numeric(cleaned, errors="coerce")
            # Keep narrative columns intact; convert only columns that contain numbers.
            if numeric.notna().any():
                df[column] = numeric

    if "Year" in df.columns:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        df = df.dropna(subset=["Year"])
        df["Year"] = df["Year"].astype(int)
    if "Quarters" in df.columns:
        df["Quarters"] = (df["Quarters"].astype(str).str.strip().str.upper()
                          .str.replace("QUARTER", "Q", regex=False)
                          .str.replace(" ", "", regex=False))
    return df


def load_annual(file_or_path) -> pd.DataFrame:
    """Load the Annual financials CSV. Accepts a path or an uploaded file object."""
    df = pd.read_csv(file_or_path)
    df = _clean_columns(df)
    # Drop forecast-only rows when an assets column is available.
    if "Total Assets" in df.columns:
        df = df.dropna(subset=["Total Assets"])
    return df.reset_index(drop=True)


def load_quarterly(file_or_path) -> pd.DataFrame:
    """Load the Quarterly financials CSV. Accepts a path or an uploaded file object."""
    df = pd.read_csv(file_or_path)
    df = _clean_columns(df)
    if "Total Assets" in df.columns:
        df = df.dropna(subset=["Total Assets"])
    return df.reset_index(drop=True)


ANNUAL_REQUIRED_COLS = [
    "Year", "Total Assets", "Revenues", "Operating income",
    "Net cash flow by operating activity", "Net cash flow by investing activity",
    "Net cash flow by financial activity", "Headcount", "Net cash flow",
    "Total Liabilities", "Total Equity",
]

QUARTERLY_REQUIRED_COLS = [
    "Year", "Quarters", "Total Assets", "Revenues",
    "Net cash flow by operating activity", "Net cash flow by investing activity",
    "Net cash flow by financial activity", "Headcount", "Net cash flow",
    "Total Liabilities", "Total Equity",
]


def validate_schema(df: pd.DataFrame, required_cols: list) -> list:
    """Returns a list of missing required columns (empty list = schema OK)."""
    return [c for c in required_cols if c not in df.columns]
