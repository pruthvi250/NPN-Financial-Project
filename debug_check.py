import pandas as pd
from modules.universal_validation_engine import BalanceSheetEquationRule, _find_column, _safe_numeric

df = pd.DataFrame([
    {"Year": 2026, "Total Assets": 100, "Total Liabilities": 40, "Total Equity": 60}
])
print(df.columns.tolist())
print(_find_column(df, ["Total Assets"]))
print(_safe_numeric(df.iloc[-1]["Total Assets"]))
rule = BalanceSheetEquationRule(tolerance=1.0)
print(rule.evaluate(df))
