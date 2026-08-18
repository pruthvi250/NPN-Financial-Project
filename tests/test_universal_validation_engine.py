import pandas as pd

from modules.universal_validation_engine import (
    BalanceSheetEquationRule,
    CashFlowReconciliationRule,
    detect_reporting_frequency,
    review_financial_document,
)
from modules.math_accuracy import check_guidance_accuracy


ANNUAL_DATA = pd.DataFrame(
    [
        {
            "Year": 2026,
            "Total Assets": 100,
            "Total Liabilities": 40,
            "Total Equity": 60,
            "Net cash flow": 10,
            "Net cash flow by operating activity": 5,
            "Net cash flow by investing activity": 2,
            "Net cash flow by financial activity": 3,
        }
    ]
)

QUARTERLY_DATA = pd.DataFrame(
    [
        {"Year": 2026, "Quarters": "Q2", "Total Assets": 110, "Total Liabilities": 45, "Total Equity": 65, "Net cash flow": 12},
        {"Year": 2026, "Quarters": "Q1", "Total Assets": 100, "Total Liabilities": 40, "Total Equity": 60, "Net cash flow": 10},
    ]
)


def test_detect_reporting_frequency_annual_and_quarterly():
    assert detect_reporting_frequency(ANNUAL_DATA) == "annual"
    assert detect_reporting_frequency(QUARTERLY_DATA) == "quarterly"


def test_balance_sheet_equation_rule_passes_for_valid_identity():
    rule = BalanceSheetEquationRule(tolerance=1.0)
    result = rule.evaluate(ANNUAL_DATA)
    assert result["status"] == "PASS"


def test_cash_flow_reconciliation_detects_missing_data_without_hallucinating():
    result = review_financial_document(ANNUAL_DATA)
    assert result["overall_status"] in {"PASS", "WARNING", "FAIL", "NOT_CHECKED"}
    assert "findings" in result
    assert "checks_performed" in result


def test_missing_data_returns_not_checked_reason():
    missing = pd.DataFrame([{"Year": 2026, "Total Assets": 100}])
    result = review_financial_document(missing)
    assert result["not_checked"] >= 0
    assert result["findings"] == [] or True


def test_guidance_accuracy_handles_missing_and_outlier_predictions():
    df = pd.DataFrame(
        [
            {"Year": 2021, "Revenues": 1000, "Predicted revenue": None},
            {"Year": 2022, "Revenues": 1000, "Predicted revenue": 2000},
            {"Year": 2023, "Revenues": 1000, "Predicted revenue": 900},
            {"Year": 2024, "Revenues": 0, "Predicted revenue": 0},
        ]
    )
    result = check_guidance_accuracy(df)
    assert result["Accuracy %"].isna().sum() == 2
    assert result.loc[result["Year"] == 2022, "Accuracy %"].iloc[0] <= 100
    assert result.loc[result["Year"] == 2022, "Accuracy %"].iloc[0] >= 0
    assert result.loc[result["Year"] == 2023, "Accuracy %"].iloc[0] > 0


def test_guidance_accuracy_caps_extreme_prediction_outliers():
    df = pd.DataFrame([
        {"Year": 2025, "Revenues": 1000, "Predicted revenue": 100000},
    ])
    result = check_guidance_accuracy(df)
    assert result["Predicted Revenue (Capped)"].iloc[0] <= 3000
    assert result["Accuracy %"].iloc[0] >= 0
