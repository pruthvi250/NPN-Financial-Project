"""
internal_consistency.py
Replaces Internal.py.

Internal.py required two separate CSV uploads named "financial data" and
"annual report" but both were actually treated as the same schema, and it
computed a 'Net Cash Flow' column that duplicated a column already in the
data. This version does what "internal consistency" actually means for
this problem statement: if a fact appears in more than one place (e.g.
average headcount reported annually vs the four quarters that make it up),
those places should agree.
"""

import pandas as pd

TOLERANCE_HEADCOUNT = 1.0     # people (in hundreds, since data is in thousands-ish units)
TOLERANCE_CASHFLOW = 1.0        # $ millions


def check_headcount_consistency(annual_df: pd.DataFrame, quarterly_df: pd.DataFrame, tolerance: float = TOLERANCE_HEADCOUNT) -> pd.DataFrame:
    q_avg = (
        quarterly_df.groupby("Year")["Headcount"].mean()
        .reset_index()
        .rename(columns={"Headcount": "Headcount (Avg of 4 Quarters)"})
    )
    merged = annual_df[["Year", "Headcount"]].rename(
        columns={"Headcount": "Headcount (Annual Reported)"}
    ).merge(q_avg, on="Year", how="inner")
    merged["Difference"] = (
        merged["Headcount (Annual Reported)"] - merged["Headcount (Avg of 4 Quarters)"]
    )
    merged["Flag"] = merged["Difference"].abs() > tolerance
    return merged


def check_cashflow_consistency(annual_df: pd.DataFrame, quarterly_df: pd.DataFrame, tolerance: float = TOLERANCE_CASHFLOW) -> pd.DataFrame:
    q_col = "Net cash flow" if "Net cash flow" in quarterly_df.columns else "Net cash flow "
    a_col = "Net cash flow" if "Net cash flow" in annual_df.columns else "Net cash flow "

    q_sum = (
        quarterly_df.groupby("Year")[q_col].sum()
        .reset_index()
        .rename(columns={q_col: "Net Cash Flow (Sum of 4 Quarters)"})
    )
    merged = annual_df[["Year", a_col]].rename(
        columns={a_col: "Net Cash Flow (Annual Reported)"}
    ).merge(q_sum, on="Year", how="inner")
    merged["Difference"] = (
        merged["Net Cash Flow (Annual Reported)"] - merged["Net Cash Flow (Sum of 4 Quarters)"]
    )
    merged["Flag"] = merged["Difference"].abs() > tolerance
    return merged


def check_revenue_consistency(annual_df: pd.DataFrame, quarterly_df: pd.DataFrame, tolerance: float = TOLERANCE_CASHFLOW) -> pd.DataFrame:
    q_sum = (
        quarterly_df.groupby("Year")["Revenues"].sum()
        .reset_index()
        .rename(columns={"Revenues": "Revenue (Sum of 4 Quarters)"})
    )
    merged = annual_df[["Year", "Revenues"]].rename(
        columns={"Revenues": "Revenue (Annual Reported)"}
    ).merge(q_sum, on="Year", how="inner")
    merged["Difference"] = (
        merged["Revenue (Annual Reported)"] - merged["Revenue (Sum of 4 Quarters)"]
    )
    merged["Flag"] = merged["Difference"].abs() > tolerance
    return merged


def run_all_checks(annual_df: pd.DataFrame, quarterly_df: pd.DataFrame, tolerance: float = TOLERANCE_CASHFLOW) -> dict:
    return {
        "Headcount: Annual vs Avg of Quarters": check_headcount_consistency(annual_df, quarterly_df, tolerance),
        "Net Cash Flow: Annual vs Sum of Quarters": check_cashflow_consistency(annual_df, quarterly_df, tolerance),
        "Revenue: Annual vs Sum of Quarters": check_revenue_consistency(annual_df, quarterly_df, tolerance),
    }
