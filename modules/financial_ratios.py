"""
financial_ratios.py

Computes key audit financial ratios and Altman Z-Score risk profiling
from loaded annual financial data.
"""

import pandas as pd
import numpy as np


def compute_financial_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Computes operating, liquidity, and leverage ratios per year."""
    if df is None or df.empty:
        return pd.DataFrame()

    out = df[["Year"]].copy()

    # Operating & Profitability Ratios
    if "Revenues" in df.columns and "Operating income" in df.columns:
        out["Operating Margin %"] = (df["Operating income"] / df["Revenues"] * 100).round(2)
    
    if "Revenues" in df.columns and "Net income" in df.columns:
        out["Net Profit Margin %"] = (df["Net income"] / df["Revenues"] * 100).round(2)

    if "Net income" in df.columns and "Total Assets" in df.columns:
        out["ROA (Return on Assets) %"] = (df["Net income"] / df["Total Assets"] * 100).round(2)

    if "Net income" in df.columns and "Total Equity" in df.columns:
        out["ROE (Return on Equity) %"] = (df["Net income"] / df["Total Equity"] * 100).round(2)

    # Leverage & Liquidity Ratios
    if "Total Liabilities" in df.columns and "Total Equity" in df.columns:
        out["Debt-to-Equity"] = (df["Total Liabilities"] / df["Total Equity"]).round(2)

    if "Total Assets" in df.columns and "Total Liabilities" in df.columns:
        out["Debt-to-Assets"] = (df["Total Liabilities"] / df["Total Assets"]).round(2)

    if "Revenues" in df.columns and "Total Assets" in df.columns:
        out["Asset Turnover"] = (df["Revenues"] / df["Total Assets"]).round(2)

    return out


def compute_altman_z_score(df: pd.DataFrame) -> pd.DataFrame:
    """Computes the Altman Z-Score bankruptcy risk model for each annual period:
    Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 0.999*X5

    where:
    X1 = Working Capital / Total Assets  (approx using Assets - Liabilities)
    X2 = Retained Earnings / Total Assets (approx using cumulative Net Income if missing)
    X3 = EBIT / Total Assets (Operating Income / Total Assets)
    X4 = Equity / Total Liabilities
    X5 = Revenues / Total Assets
    """
    if df is None or df.empty:
        return pd.DataFrame()

    out = df[["Year"]].copy()
    assets = df["Total Assets"]
    liab = df["Total Liabilities"]
    equity = df["Total Equity"]
    rev = df["Revenues"]
    op_inc = df["Operating income"] if "Operating income" in df.columns else df["Revenues"] * 0.15

    # Retained earnings approximation
    if "Retained earnings" in df.columns:
        retained = df["Retained earnings"]
    elif "Net income" in df.columns:
        retained = df["Net income"].cumsum()
    else:
        retained = equity * 0.5

    working_cap = assets - liab

    x1 = working_cap / assets
    x2 = retained / assets
    x3 = op_inc / assets
    x4 = equity / liab
    x5 = rev / assets

    z_score = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 0.999 * x5
    out["Altman Z-Score"] = z_score.round(2)

    def _risk_zone(z):
        if z > 2.99:
            return "Safe Zone (Low Risk)"
        elif z >= 1.81:
            return "Grey Zone (Moderate Risk)"
        else:
            return "Distress Zone (High Risk)"

    out["Risk Zone"] = out["Altman Z-Score"].apply(_risk_zone)
    return out
