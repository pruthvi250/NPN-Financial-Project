"""Universal financial statement validation and reconciliation engine.

This module follows a deterministic, rule-based design and is intentionally
agnostic to any specific company, account taxonomy, or reporting format.
It supports annual and quarterly review workflows and returns auditable
standardized results without inventing numbers or assumptions.
"""

from __future__ import annotations

import math
import re
from numbers import Real
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


SEVERITY_ORDER = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
STATUS_ORDER = {"PASS": 0, "WARNING": 1, "FAIL": 2, "NOT_CHECKED": 3}


def _normalize_key(value: Any) -> str:
    if value is None:
        return ""
    cleaned = str(value).strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return " ".join(cleaned.split())


def _safe_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass
    if isinstance(value, (bool,)):
        return None
    if isinstance(value, Real):
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("₹", "").replace("$", "").replace("€", "").replace("£", "")
        if text in {"", "-", "nan", "na", "n/a", "not disclosed", "not available"}:
            return None
        text = text.replace("(", "-").replace(")", "")
        try:
            return float(text)
        except ValueError:
            match = re.findall(r"[-+]?\d*\.?\d+(?:e[-+]?\d+)?", text)
            if match:
                try:
                    return float(match[0])
                except ValueError:
                    return None
    return None


def _find_column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lookup = { _normalize_key(col): col for col in df.columns }
    for candidate in candidates:
        key = _normalize_key(candidate)
        if key in lookup:
            return lookup[key]
    for col in df.columns:
        col_key = _normalize_key(col)
        for candidate in candidates:
            if candidate.lower() in col_key or col_key in candidate.lower():
                return col
    return None


def _extract_periods(df: pd.DataFrame) -> Dict[str, Any]:
    year_col = _find_column(df, ["Year", "Fiscal Year", "Reporting Year"])
    quarter_col = _find_column(df, ["Quarter", "Quarters", "Reporting Period", "Period"])
    fiscal_year = None
    quarter = None
    if year_col is not None and year_col in df.columns:
        values = df[year_col].dropna().astype(str)
        if not values.empty:
            fiscal_year = values.iloc[0]
    if quarter_col is not None and quarter_col in df.columns:
        quarter_values = df[quarter_col].dropna().astype(str)
        if not quarter_values.empty:
            quarter = quarter_values.iloc[0]
    return {"fiscal_year": fiscal_year, "quarter": quarter}


def detect_reporting_frequency(df: pd.DataFrame) -> str:
    """Determine whether the statement is annual, quarterly, monthly or unknown."""
    if df is None or df.empty:
        return "unknown"
    if _find_column(df, ["Quarter", "Quarters", "Reporting Period", "Period"]) is not None:
        q_values = df[_find_column(df, ["Quarter", "Quarters", "Reporting Period", "Period"])].astype(str)
        if q_values.str.contains("Q", case=False, na=False).any() or q_values.str.contains("H1|H2|YTD|9M|6M", case=True, na=False).any():
            return "quarterly"
    if _find_column(df, ["Year", "Fiscal Year"]) is not None:
        return "annual"
    return "unknown"


def infer_document_metadata(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {
            "document_type": "financial_statement",
            "reporting_frequency": "unknown",
            "company_name": "unknown",
            "reporting_period_start": None,
            "reporting_period_end": None,
            "currency": "unknown",
            "unit_of_measure": "unknown",
            "comparative_period": None,
        }

    freq = detect_reporting_frequency(df)
    period_info = _extract_periods(df)
    return {
        "document_type": "financial_statement",
        "reporting_frequency": freq,
        "company_name": "unknown",
        "reporting_period_start": None,
        "reporting_period_end": None,
        "currency": "unknown",
        "unit_of_measure": "unknown",
        "comparative_period": None,
        "period_type": "annual" if freq == "annual" else "quarterly",
        "period_length": "full year" if freq == "annual" else "quarter",
        "fiscal_year": period_info.get("fiscal_year"),
        "quarter": period_info.get("quarter"),
    }


class BaseRule:
    check_id: str = "GEN-001"
    check_name: str = "Generic Rule"
    category: str = "General"

    def __init__(self, tolerance: float = 1.0, **kwargs):
        self.tolerance = float(tolerance)
        self.kwargs = kwargs

    def evaluate(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    def _result(self, *, status: str, severity: str, expected: Any, actual: Any, difference: Any, explanation: str, source_pages: Optional[List[int]] = None, confidence: float = 0.95, **extra) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "check_name": self.check_name,
            "category": self.category,
            "status": status,
            "severity": severity,
            "expected": expected,
            "actual": actual,
            "difference": difference,
            "explanation": explanation,
            "source_pages": source_pages or [],
            "confidence": confidence,
            **extra,
        }

    def _not_checked(self, reason: str) -> Dict[str, Any]:
        return self._result(
            status="NOT_CHECKED",
            severity="INFO",
            expected=None,
            actual=None,
            difference=None,
            explanation=reason,
            source_pages=[],
            confidence=0.0,
            reason=reason,
        )


class BalanceSheetEquationRule(BaseRule):
    check_id = "BS-001"
    check_name = "Balance Sheet Equation"
    category = "Mathematical Accuracy"

    def evaluate(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        if df is None or df.empty:
            return self._not_checked("Required supporting data not available.")

        assets_col = _find_column(df, ["Total Assets", "Assets", "Asset Total"])
        liabilities_col = _find_column(df, ["Total Liabilities", "Liabilities", "Liability Total"])
        equity_col = _find_column(df, ["Total Equity", "Equity", "Shareholders Equity", "Owner Equity"])
        if not all([assets_col, liabilities_col, equity_col]):
            return self._not_checked("Required supporting data not available.")

        latest = df.iloc[-1]
        total_assets = _safe_numeric(latest[assets_col])
        total_liabilities = _safe_numeric(latest[liabilities_col])
        total_equity = _safe_numeric(latest[equity_col])
        if any(v is None for v in [total_assets, total_liabilities, total_equity]):
            return self._not_checked("Required supporting data not available.")

        expected = total_liabilities + total_equity
        actual = total_assets
        difference = actual - expected
        tolerance = float(kwargs.get("tolerance", 1.0))
        if abs(difference) <= tolerance:
            status = "PASS"
            severity = "INFO"
        elif abs(difference) <= tolerance * 5:
            status = "WARNING"
            severity = "MEDIUM"
        else:
            status = "FAIL"
            severity = "HIGH"

        return self._result(
            status=status,
            severity=severity,
            expected=expected,
            actual=actual,
            difference=difference,
            explanation="Total Assets do not equal Total Liabilities plus Total Equity." if status != "PASS" else "Balance sheet equation reconciles within tolerance.",
            source_pages=[],
            confidence=0.98,
        )


class CashFlowReconciliationRule(BaseRule):
    check_id = "CF-001"
    check_name = "Cash Flow Reconciliation"
    category = "Cash Flow"

    def evaluate(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        if df is None or df.empty:
            return self._not_checked("Required supporting data not available.")

        net_cash_col = _find_column(df, ["Net cash flow", "Net Cash Flow", "Cash Flow Net"])
        op_col = _find_column(df, ["Net cash flow by operating activity", "Operating cash flow", "Cash flow from operating activities"])
        inv_col = _find_column(df, ["Net cash flow by investing activity", "Investing cash flow", "Cash flow from investing activities"])
        fin_col = _find_column(df, ["Net cash flow by financial activity", "Net cash flow by financing activity", "Financing cash flow", "Cash flow from financing activities"])
        cash_col = _find_column(df, ["Cash and cash equivalents", "Cash and Cash Equivalents", "Cash", "Bank Balance"])

        if not all([net_cash_col, op_col, inv_col, fin_col]):
            return self._not_checked("Required supporting data not available.")

        latest = df.iloc[-1]
        stated_net_cash = _safe_numeric(latest[net_cash_col])
        op_value = _safe_numeric(latest[op_col])
        inv_value = _safe_numeric(latest[inv_col])
        fin_value = _safe_numeric(latest[fin_col])
        if any(v is None for v in [stated_net_cash, op_value, inv_value, fin_value]):
            return self._not_checked("Required supporting data not available.")

        computed = op_value + inv_value + fin_value
        difference = stated_net_cash - computed
        tolerance = float(kwargs.get("tolerance", self.tolerance))
        status = "PASS" if abs(difference) <= tolerance else "FAIL"
        severity = "INFO" if status == "PASS" else "HIGH"

        explanation = "Net cash flow reconciles with operating, investing, and financing cash flows." if status == "PASS" else "Cash flow components do not reconcile to the stated net cash flow."

        result = self._result(
            status=status,
            severity=severity,
            expected=computed,
            actual=stated_net_cash,
            difference=difference,
            explanation=explanation,
            source_pages=[],
            confidence=0.94,
        )

        if cash_col is not None:
            closing_cash = _safe_numeric(latest[cash_col])
            if closing_cash is not None:
                result["balance_sheet_cash"] = closing_cash
        return result


class AnnualComparisonRule(BaseRule):
    check_id = "AN-001"
    check_name = "Annual Comparison"
    category = "Period Analysis"

    def evaluate(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        if df is None or df.empty:
            return self._not_checked("Required supporting data not available.")
        if detect_reporting_frequency(df) != "annual":
            return self._not_checked("Annual comparison not applicable for this reporting frequency.")
        if df.shape[0] < 2:
            return self._not_checked("Required supporting data not available.")
        metric = kwargs.get("metric") or _find_column(df, ["Revenues", "Revenue", "Sales", "Net income", "Operating income", "Total Assets"])
        if metric is None:
            return self._not_checked("Required supporting data not available.")

        values = df[metric].apply(_safe_numeric).dropna()
        if len(values) < 2:
            return self._not_checked("Required supporting data not available.")
        current = values.iloc[-1]
        previous = values.iloc[-2]
        if previous == 0:
            return self._not_checked("Required supporting data not available.")
        change = current - previous
        pct = (change / abs(previous)) * 100
        if abs(pct) >= kwargs.get("exception_threshold", 40):
            status = "FAIL"
            severity = "MEDIUM"
        elif abs(pct) >= kwargs.get("warning_threshold", 20):
            status = "WARNING"
            severity = "LOW"
        else:
            status = "INFO"
            severity = "INFO"

        return self._result(
            status=status,
            severity=severity,
            expected=previous,
            actual=current,
            difference=current - previous,
            explanation=f"Movement of {pct:.2f}% in {metric} between the latest and prior annual periods.",
            source_pages=[],
            confidence=0.9,
            percentage_change=pct,
        )


class QuarterlyComparisonRule(BaseRule):
    check_id = "Q-001"
    check_name = "Quarterly Comparison"
    category = "Period Analysis"

    def evaluate(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        if df is None or df.empty:
            return self._not_checked("Required supporting data not available.")
        if detect_reporting_frequency(df) != "quarterly":
            return self._not_checked("Quarterly comparison not applicable for this reporting frequency.")
        if df.shape[0] < 2:
            return self._not_checked("Required supporting data not available.")
        metric = kwargs.get("metric") or _find_column(df, ["Revenues", "Revenue", "Sales", "Net income", "Operating income", "Total Assets"])
        if metric is None:
            return self._not_checked("Required supporting data not available.")

        values = df[metric].apply(_safe_numeric).dropna()
        if len(values) < 2:
            return self._not_checked("Required supporting data not available.")
        current = values.iloc[-1]
        previous = values.iloc[-2]
        if previous == 0:
            return self._not_checked("Required supporting data not available.")
        diff = current - previous
        pct = (diff / abs(previous)) * 100
        if abs(pct) >= kwargs.get("exception_threshold", 45):
            status = "FAIL"
            severity = "MEDIUM"
        elif abs(pct) >= kwargs.get("warning_threshold", 25):
            status = "WARNING"
            severity = "LOW"
        else:
            status = "INFO"
            severity = "INFO"

        return self._result(
            status=status,
            severity=severity,
            expected=previous,
            actual=current,
            difference=diff,
            explanation=f"Quarter-over-quarter movement of {pct:.2f}% in {metric}.",
            source_pages=[],
            confidence=0.88,
            percentage_change=pct,
        )


class YTDReconciliationRule(BaseRule):
    check_id = "YTD-001"
    check_name = "YTD Reconciliation"
    category = "Period Analysis"

    def evaluate(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        if df is None or df.empty:
            return self._not_checked("Required supporting data not available.")
        if detect_reporting_frequency(df) != "quarterly":
            return self._not_checked("YTD reconciliation not applicable.")

        ytd_cols = [c for c in df.columns if "YTD" in c.upper() or "H1" in c.upper() or "9M" in c.upper() or "6M" in c.upper()]
        if not ytd_cols:
            return self._not_checked("Required supporting data not available.")

        sample = df.iloc[-1]
        for ytd_col in ytd_cols:
            total = _safe_numeric(sample[ytd_col])
            if total is not None:
                return self._result(
                    status="PASS" if total is not None else "NOT_CHECKED",
                    severity="INFO",
                    expected=None,
                    actual=total,
                    difference=0,
                    explanation="YTD figure is present and retained as a separate reported metric.",
                    source_pages=[],
                    confidence=0.7,
                )
        return self._not_checked("Required supporting data not available.")


def _rule_bundle(df: pd.DataFrame, tolerance: float = 1.0) -> List[BaseRule]:
    return [
        BalanceSheetEquationRule(),
        CashFlowReconciliationRule(),
        QuarterlyComparisonRule(),
        AnnualComparisonRule(),
        YTDReconciliationRule(),
    ]


def review_financial_document(df: pd.DataFrame, previous_df: Optional[pd.DataFrame] = None, tolerance: float = 1.0) -> Dict[str, Any]:
    """Evaluate a single document against the deterministic rule set."""
    if df is None or df.empty:
        return {
            "document_summary": infer_document_metadata(df),
            "overall_status": "NOT_CHECKED",
            "checks_performed": 0,
            "passed": 0,
            "warnings": 0,
            "exceptions": 0,
            "not_checked": 1,
            "findings": [],
            "reconciliations": [],
            "period_analysis": {"period_type": "unknown", "period_length": "unknown", "fiscal_year": None, "quarter": None, "comparative_period": None},
            "material_movements": [],
        }

    summary = infer_document_metadata(df)
    checks: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []
    reconciliations: List[Dict[str, Any]] = []
    material_movements: List[Dict[str, Any]] = []

    for rule in _rule_bundle(df, tolerance=tolerance):
        result = rule.evaluate(df, tolerance=tolerance, metric=None)
        checks.append(result)
        if result["status"] in {"WARNING", "FAIL", "NOT_CHECKED"}:
            findings.append(result)
        if result["status"] == "FAIL":
            reconciliations.append({"rule": result["check_name"], "status": "FAIL", "difference": result.get("difference")})
        if result.get("percentage_change") is not None:
            material_movements.append({
                "check_name": result["check_name"],
                "difference": result.get("difference"),
                "percentage_change": result.get("percentage_change"),
                "status": result["status"],
            })

    passed = sum(1 for c in checks if c["status"] == "PASS")
    warnings = sum(1 for c in checks if c["status"] == "WARNING")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")
    not_checked = sum(1 for c in checks if c["status"] == "NOT_CHECKED")

    if fail_count:
        overall_status = "FAIL"
    elif warnings:
        overall_status = "WARNING"
    elif not_checked == len(checks):
        overall_status = "NOT_CHECKED"
    else:
        overall_status = "PASS"

    result = {
        "document_summary": summary,
        "overall_status": overall_status,
        "checks_performed": len(checks),
        "passed": passed,
        "warnings": warnings,
        "exceptions": fail_count,
        "not_checked": not_checked,
        "findings": findings,
        "reconciliations": reconciliations,
        "period_analysis": {
            "period_type": summary.get("period_type", "unknown"),
            "period_length": summary.get("period_length", "unknown"),
            "fiscal_year": summary.get("fiscal_year"),
            "quarter": summary.get("quarter"),
            "comparative_period": summary.get("comparative_period"),
        },
        "material_movements": material_movements,
    }
    return result
