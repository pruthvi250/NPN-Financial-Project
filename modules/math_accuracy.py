"""
math_accuracy.py
Replaces Accuracy.py.

The original Accuracy.py trained a Ridge regression on 5 annual data points
to "predict" revenue/net income/margin and called the model's own fit
error "accuracy" - that measures how well a regression line fits 5 dots,
not whether the financial statement's math is internally correct, and 5
points is too few to fit any model reliably.

The actual "Mathematical Accuracy" check the problem statement asks for is
much simpler and more defensible:
  1. Does Total Assets = Total Liabilities + Total Equity? (balance sheet identity)
  2. Does the stated Net Cash Flow equal the sum of operating + investing +
     financing cash flows?
  3. How accurate was prior guidance? -> use the 'Predicted revenue' column
     that is already in the data (this is literally what
     display_revenue_accuracy() in Accuracy.py was trying to do, just
     rewritten without the regression detour).
"""

import pandas as pd

TOLERANCE = 1.0  # default in $ millions


def check_balance_sheet_identity(df: pd.DataFrame, tolerance: float = TOLERANCE) -> pd.DataFrame:
    out = df[["Year"]].copy()
    out["Total Assets"] = df["Total Assets"]
    out["Liabilities + Equity"] = df["Total Liabilities"] + df["Total Equity"]
    out["Difference"] = out["Total Assets"] - out["Liabilities + Equity"]
    out["Flag"] = out["Difference"].abs() > tolerance
    return out


def check_cash_flow_sum(df: pd.DataFrame, tolerance: float = TOLERANCE) -> pd.DataFrame:
    stated_col = "Net cash flow" if "Net cash flow" in df.columns else "Net cash flow "
    out = df[["Year"]].copy()
    out["Stated Net Cash Flow"] = df[stated_col]
    out["Computed (Op + Inv + Fin)"] = (
        df["Net cash flow by operating activity"]
        + df["Net cash flow by investing activity"]
        + df["Net cash flow by financial activity"]
    )
    out["Difference"] = out["Stated Net Cash Flow"] - out["Computed (Op + Inv + Fin)"]
    out["Flag"] = out["Difference"].abs() > tolerance
    return out


def check_guidance_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    """Actual revenue vs the 'Predicted revenue' guidance figure already in the data."""
    out = df[["Year"]].copy()
    if "Quarters" in df.columns:
        out["Period"] = df["Year"].astype(str) + " " + df["Quarters"].astype(str)
    else:
        out["Period"] = df["Year"].astype(str)
    out["Actual Revenue"] = df["Revenues"]
    out["Predicted Revenue"] = df["Predicted revenue"]

    def _accuracy(row):
        pred = row["Predicted Revenue"]
        actual = row["Actual Revenue"]
        if pd.isna(pred) or pred == 0:
            return None
        return round((1 - abs(actual - pred) / actual) * 100, 2)

    out["Accuracy %"] = out.apply(_accuracy, axis=1)
    return out[["Period", "Actual Revenue", "Predicted Revenue", "Accuracy %"]]


def check_net_income_consistency(df: pd.DataFrame, tolerance: float = TOLERANCE) -> pd.DataFrame:
    """Annual.csv has both 'Net income' and 'Income after tax' - these should match
    (or be explained) since they describe the same bottom-line figure."""
    if "Net income" not in df.columns or "Income after tax" not in df.columns:
        return pd.DataFrame()
    out = df[["Year"]].copy()
    out["Net Income"] = df["Net income"]
    out["Income After Tax"] = df["Income after tax"]
    out["Difference"] = out["Net Income"] - out["Income After Tax"]
    out["Flag"] = out["Difference"].abs() > tolerance
    return out


def run_all_checks(df: pd.DataFrame, tolerance: float = TOLERANCE) -> dict:
    results = {
        "Balance Sheet Identity (Assets = Liabilities + Equity)": check_balance_sheet_identity(df, tolerance),
        "Cash Flow Sum Check": check_cash_flow_sum(df, tolerance),
        "Revenue Guidance Accuracy": check_guidance_accuracy(df),
    }
    ni_check = check_net_income_consistency(df, tolerance)
    if not ni_check.empty:
        results["Net Income vs Income After Tax"] = ni_check
    return results
