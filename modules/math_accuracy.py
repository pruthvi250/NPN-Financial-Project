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
    """Actual revenue vs the 'Predicted revenue' guidance figure already in the data.

    The original formula could produce None for missing predictions and very low or
    negative percentages when the forecast was an extreme outlier. This version:
    - treats missing or blank forecasts as missing data, not as a hard failure
    - avoids divide-by-zero for actual revenue of zero
    - caps extraordinarily poor forecasts to a lower-bound floor to prevent
      unrealistic negative/very-low accuracy results from dominating the review
    - preserves the raw forecast and actual values for auditability
    """
    out = df[["Year"]].copy()
    if "Quarters" in df.columns:
        out["Period"] = df["Year"].astype(str) + " " + df["Quarters"].astype(str)
    else:
        out["Period"] = df["Year"].astype(str)
    out["Actual Revenue"] = df["Revenues"]
    raw_predicted = df["Predicted revenue"]
    out["Predicted Revenue"] = raw_predicted

    def _cap_prediction(prediction, actual):
        if pd.isna(prediction) or prediction in (None, ""):
            return None
        try:
            pred = float(prediction)
            act = float(actual)
        except (TypeError, ValueError):
            return None
        if abs(pred) < 1e-9:
            return None
        if pd.isna(act):
            return pred
        cap_ratio = 3.0
        if abs(act) > 0:
            max_allowed = abs(act) * cap_ratio
            pred = min(max(pred, -max_allowed), max_allowed)
        return pred

    out["Predicted Revenue (Capped)"] = out.apply(
        lambda row: _cap_prediction(row["Predicted Revenue"], row["Actual Revenue"]), axis=1
    )

    def _accuracy(row):
        pred = row["Predicted Revenue (Capped)"]
        actual = row["Actual Revenue"]

        if pd.isna(pred) or pred in (None, ""):
            return None

        try:
            pred = float(pred)
            actual = float(actual)
        except (TypeError, ValueError):
            return None

        if abs(pred) < 1e-9:
            return None

        if pd.isna(actual):
            return None

        if abs(actual) < 1e-9:
            if abs(pred) < 1e-9:
                return 100.0
            return 0.0

        error_ratio = abs(actual - pred) / abs(actual)
        if error_ratio > 1:
            error_ratio = 1.0

        accuracy = (1 - error_ratio) * 100
        accuracy = max(0.0, min(100.0, accuracy))
        return round(accuracy, 2)

    out["Accuracy %"] = out.apply(_accuracy, axis=1)
    return out[["Year", "Period", "Actual Revenue", "Predicted Revenue", "Predicted Revenue (Capped)", "Accuracy %"]]


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
