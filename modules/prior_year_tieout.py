"""
prior_year_tieout.py
Replaces prior.py.

Two things were wrong with prior.py:
  1. Its "Business Insights" section (dividend yield % changes, growth
     rates, correlation commentary) was hardcoded text - correct for one
     specific run of the data, but silently wrong forever after if the
     CSV changes. Everything below is computed live from whatever data
     is loaded.
  2. It never actually performed a "tie-out." A tie-out means: does a
     balance recorded as of a period-end in one document match the same
     balance recorded elsewhere? Here that's Annual.csv's year-end
     figures vs Quarter.csv's Q4 figures for the same year - both should
     describe the same December 31 balance sheet.
"""

import pandas as pd

TOLERANCE = 1.0  # $ millions


def tie_out_annual_vs_q4(annual_df: pd.DataFrame, quarterly_df: pd.DataFrame, tolerance: float = TOLERANCE) -> pd.DataFrame:
    fields = ["Total Assets", "Total Liabilities", "Total Equity"]
    q4 = quarterly_df[quarterly_df["Quarters"] == "Q4"][["Year"] + fields].copy()
    q4 = q4.rename(columns={f: f + " (Q4, Quarterly File)" for f in fields})

    a = annual_df[["Year"] + fields].copy()
    a = a.rename(columns={f: f + " (Annual File)" for f in fields})

    merged = a.merge(q4, on="Year", how="inner")
    for f in fields:
        merged[f + " Diff"] = (
            merged[f + " (Annual File)"] - merged[f + " (Q4, Quarterly File)"]
        )
        merged[f + " Flag"] = merged[f + " Diff"].abs() > tolerance
    return merged


def compute_annual_growth_rates(annual_df: pd.DataFrame) -> pd.DataFrame:
    df = annual_df.sort_values("Year").copy()
    metrics = ["Revenues", "Operating income", "Total Assets", "Net cash flow"]
    metrics = [m for m in metrics if m in df.columns]
    growth = df[["Year"]].copy()
    for m in metrics:
        growth[m + " YoY Growth %"] = df[m].pct_change().round(4) * 100
    return growth


def compute_dividend_yield_changes(annual_df: pd.DataFrame) -> pd.DataFrame:
    col = "Dividend yeild" if "Dividend yeild" in annual_df.columns else "Dividend yield"
    if col not in annual_df.columns:
        return pd.DataFrame()
    df = annual_df.sort_values("Year")[["Year", col]].copy()
    df[col + " Change %"] = df[col].pct_change().round(4) * 100
    return df


def compute_correlations(annual_df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["Revenues", "Operating income", "Total Assets", "Net cash flow"]
            if c in annual_df.columns]
    return annual_df[cols].corr().round(3)
