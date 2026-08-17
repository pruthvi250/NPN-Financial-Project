"""
wp514.py

Builds a comprehensive WP-514 Audit Work Paper report from the outputs of
all four automated checks (Mathematical Accuracy, Prior Year Tie-Out,
Internal Consistency, Spelling & Grammar).

Supports export to JSON, CSV, and full interactive HTML report formats,
including exact data values for any flagged discrepancies / false verification checks.
"""

from datetime import date
import json
import pandas as pd


def _count_flags(df: pd.DataFrame) -> int:
    if df is None or df.empty or "Flag" not in df.columns:
        return 0
    return int(df["Flag"].sum())


def _extract_df_failures(df: pd.DataFrame) -> list:
    """Extracts rows from a DataFrame where Flag is True, returning formatted dict records."""
    if df is None or df.empty or "Flag" not in df.columns:
        return []
    failed = df[df["Flag"] == True].copy()
    if failed.empty:
        return []

    records = []
    for _, row in failed.iterrows():
        rec = {}
        for col in failed.columns:
            if col == "Flag":
                continue
            val = row[col]
            if pd.isna(val):
                rec[col] = "N/A"
            elif isinstance(val, float):
                rec[col] = f"{val:,.2f}"
            elif isinstance(val, int):
                rec[col] = f"{val:,}"
            else:
                rec[col] = str(val)
        records.append(rec)
    return records


def _extract_tieout_failures(df: pd.DataFrame) -> list:
    """Extracts failing tie-out items comparing Annual vs Quarterly Q4 figures."""
    if df is None or df.empty:
        return []
    flag_cols = [c for c in df.columns if c.endswith("Flag")]
    if not flag_cols:
        return []
    failed = df[df[flag_cols].any(axis=1)].copy()
    if failed.empty:
        return []

    records = []
    for _, row in failed.iterrows():
        year = str(row.get("Year", "N/A"))
        for flag_col in flag_cols:
            if row[flag_col] is True or row[flag_col] == 1:
                metric = flag_col[:-5]  # remove ' Flag'
                annual_val = row.get(f"{metric} (Annual File)", "N/A")
                q4_val = row.get(f"{metric} (Q4, Quarterly File)", "N/A")
                diff = row.get(f"{metric} Diff", "N/A")

                ann_str = f"{annual_val:,.2f}" if isinstance(annual_val, (float, int)) else str(annual_val)
                q4_str = f"{q4_val:,.2f}" if isinstance(q4_val, (float, int)) else str(q4_val)
                diff_str = f"{diff:,.2f}" if isinstance(diff, (float, int)) else str(diff)

                records.append({
                    "Year": year,
                    "Metric": metric,
                    "Annual File Balance": ann_str,
                    "Q4 Quarterly Balance": q4_str,
                    "Difference": diff_str,
                })
    return records


def build_wp514(
    entity_name: str,
    period_current: str,
    period_prior: str,
    preparer_name: str,
    math_results: dict,
    tieout_result: pd.DataFrame,
    consistency_results: dict,
    grammar_results: dict,
) -> dict:
    anomalies = []
    detailed_exceptions = {}

    # 1. Mathematical Accuracy Checks
    math_details = {}
    for name, df in math_results.items():
        failures = _extract_df_failures(df)
        n = len(failures)
        math_details[name] = {
            "verified": n == 0,
            "flag_count": n,
            "failed_data": failures,
        }
        if n > 0:
            anomalies.append(f"{name}: {n} period(s) flagged")
            detailed_exceptions[name] = failures

    # 2. Prior Year Tie-Out Check
    tieout_failures = _extract_tieout_failures(tieout_result)
    tieout_flags = len(tieout_failures)
    if tieout_flags > 0:
        anomalies.append(f"Prior Year Tie-Out: {tieout_flags} discrepancy item(s) flagged")
        detailed_exceptions["Prior Year Tie-Out Discrepancies"] = tieout_failures

    # 3. Internal Consistency Checks
    consistency_details = {}
    for name, df in consistency_results.items():
        failures = _extract_df_failures(df)
        n = len(failures)
        consistency_details[name] = {
            "verified": n == 0,
            "flag_count": n,
            "failed_data": failures,
        }
        if n > 0:
            anomalies.append(f"{name}: {n} period(s) flagged")
            detailed_exceptions[name] = failures

    # 4. Spelling & Grammar Checks
    spelling_issues = grammar_results.get("spelling_issues", []) if grammar_results else []
    grammar_issues = grammar_results.get("grammar_issues", []) if grammar_results else []
    currency_issues = grammar_results.get("currency_format_issues", []) if grammar_results else []

    if spelling_issues:
        anomalies.append(f"Spelling: {len(spelling_issues)} potential issue(s)")
        detailed_exceptions["Spelling Discrepancies"] = spelling_issues
    if grammar_issues:
        anomalies.append(f"Grammar: {len(grammar_issues)} potential issue(s)")
        detailed_exceptions["Grammar Discrepancies"] = grammar_issues
    if currency_issues:
        anomalies.append(f"Currency Format: {len(currency_issues)} non-standard symbol(s)")
        detailed_exceptions["Currency Format Issues"] = currency_issues

    math_clean = all(d["verified"] for d in math_details.values()) if math_details else True
    tieout_clean = (tieout_flags == 0)
    consistency_clean = all(d["verified"] for d in consistency_details.values()) if consistency_details else True
    spelling_grammar_clean = (len(spelling_issues) + len(grammar_issues) + len(currency_issues)) == 0

    wp_temp = {
        "entity_name": entity_name,
        "anomalies": anomalies,
        "detailed_exceptions": detailed_exceptions,
    }
    audit_narrative = generate_audit_narrative(wp_temp)

    wp = {
        "wp_reference": "WP-514",
        "preparer_name": preparer_name or "Audit Analyst",
        "review_date": str(date.today()),
        "entity_name": entity_name,
        "period_current": str(period_current),
        "period_prior": str(period_prior),
        "mathematical_accuracy_verified": math_clean,
        "prior_year_tie_out_verified": tieout_clean,
        "internal_consistency_verified": consistency_clean,
        "spelling_grammar_clean": spelling_grammar_clean,
        "verification_summary": {
            "Mathematical Accuracy": "VERIFIED" if math_clean else "EXCEPTION NOTED",
            "Prior Year Tie-Out": "VERIFIED" if tieout_clean else "EXCEPTION NOTED",
            "Internal Consistency": "VERIFIED" if consistency_clean else "EXCEPTION NOTED",
            "Spelling & Grammar": "VERIFIED" if spelling_grammar_clean else "EXCEPTION NOTED",
        },
        "anomalies_found_count": len(anomalies),
        "anomalies": anomalies,
        "detailed_exceptions": detailed_exceptions,
        "audit_narrative": audit_narrative,
        "overall_status": "Clean" if not anomalies else "Exceptions Noted",
    }
    return wp


def generate_audit_narrative(wp: dict, api_key: str = None) -> str:
    """Generates automated auditor narrative notes for identified exceptions."""
    anomalies = wp.get("anomalies", [])
    entity = wp.get("entity_name", "the Entity")
    detailed_exceptions = wp.get("detailed_exceptions", {})

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are a senior banking auditor reviewing WP-514 for {entity}. "
                f"Anomalies: {json.dumps(anomalies)}. "
                f"Exceptions Data: {json.dumps(detailed_exceptions)}. "
                "Provide a formal 2-paragraph auditor explanation note detailing accounting reasons for discrepancies "
                "(e.g., quarterly vs annual headcount methodology, cash flow line item aggregations) and next audit recommendations."
            )
            res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return res.text.strip()
        except Exception:
            pass

    if not anomalies:
        return (
            f"Based on automated verification of financial statements for {entity}, all balance sheet identities, "
            "cash flow sum checks, prior-year tie-outs, and internal consistency cross-checks were verified clean "
            "with zero flagged material exceptions. The work paper is approved as clean."
        )

    notes = [
        f"Automated audit verification for {entity} identified {len(anomalies)} discrepancy area(s) requiring auditor attention:"
    ]
    for category, details in detailed_exceptions.items():
        if "Headcount" in category:
            notes.append(
                "• Headcount Discrepancy: Annual reported headcount differs from 4-quarter average. "
                "Auditor Note: Annual disclosure likely reflects December 31 year-end spot headcount rather than simple quarterly average."
            )
        elif "Cash Flow" in category:
            notes.append(
                "• Cash Flow Variance: Stated Net Cash Flow differs from sum of Operating, Investing, and Financing activities. "
                "Auditor Note: Review sub-line rounding and non-operating/foreign exchange reconciliation items."
            )
        elif "Prior Year" in category:
            notes.append(
                "• Prior Year Tie-Out: Annual closing balances differ from Q4 quarter-end balances. "
                "Auditor Note: Confirm post-Q4 audit adjustments ledger with client accounting team."
            )
        else:
            notes.append(f"• {category}: Discrepancies flagged in {len(details)} period(s). Requires line-item review.")

    notes.append("Audit Recommendation: Proceed with management inquiry on flagged reconciliation items.")
    return "\n\n".join(notes)


def to_json(wp: dict) -> str:
    return json.dumps(wp, indent=2)


def to_dataframe(wp: dict) -> pd.DataFrame:
    """Flat view for CSV export, including full detailed failure data formatted."""
    flat = wp.copy()
    flat["anomalies"] = "; ".join(flat["anomalies"]) if flat["anomalies"] else "None"
    
    # Format detailed exceptions as JSON string for CSV row inclusion
    if "detailed_exceptions" in flat:
        flat["detailed_exceptions_data"] = json.dumps(flat["detailed_exceptions"])
        del flat["detailed_exceptions"]
    if "verification_summary" in flat:
        flat["verification_summary"] = json.dumps(flat["verification_summary"])
        
    return pd.DataFrame([flat])


def to_html(wp: dict) -> str:
    """Generates a professional HTML report for the WP-514 work paper, displaying
    executive summary and detailed data tables for all unverified (False) checks.
    """
    entity = wp.get("entity_name", "N/A")
    wp_ref = wp.get("wp_reference", "WP-514")
    preparer = wp.get("preparer_name", "Audit Analyst")
    rev_date = wp.get("review_date", str(date.today()))
    curr_per = wp.get("period_current", "N/A")
    prior_per = wp.get("period_prior", "N/A")
    status = wp.get("overall_status", "Clean")
    status_class = "badge-clean" if status == "Clean" else "badge-exception"

    math_verified = wp.get("mathematical_accuracy_verified", True)
    tieout_verified = wp.get("prior_year_tie_out_verified", True)
    consistency_verified = wp.get("internal_consistency_verified", True)
    grammar_clean = wp.get("spelling_grammar_clean", True)

    summary_rows = [
        ("Mathematical Accuracy", math_verified),
        ("Prior Year Tie-Out", tieout_verified),
        ("Internal Consistency", consistency_verified),
        ("Spelling & Grammar Scan", grammar_clean),
    ]

    summary_table_html = ""
    for title, verified in summary_rows:
        v_badge = '<span class="status-pass">VERIFIED</span>' if verified else '<span class="status-fail">EXCEPTION NOTED</span>'
        summary_table_html += f"""
        <tr>
            <td style="font-weight: 600;">{title}</td>
            <td>{v_badge}</td>
            <td>{"No discrepancy detected" if verified else "Discrepancy data flagged below"}</td>
        </tr>
        """

    detailed_exceptions = wp.get("detailed_exceptions", {})
    exceptions_sections_html = ""

    if not detailed_exceptions:
        exceptions_sections_html = """
        <div class="clean-box">
            <h4 style="margin: 0; color: #065f46;">✔ All Financial Statement Checks Verified Clean</h4>
            <p style="margin: 6px 0 0 0; color: #047857; font-size: 14px;">No mathematical, tie-out, internal consistency, or spelling exceptions were identified in the reported data.</p>
        </div>
        """
    else:
        for check_name, records in detailed_exceptions.items():
            records_html = ""
            if isinstance(records, list) and len(records) > 0:
                if isinstance(records[0], dict):
                    headers = list(records[0].keys())
                    header_th = "".join([f"<th>{h}</th>" for h in headers])
                    rows_td = ""
                    for rec in records:
                        row_cells = "".join([f"<td>{rec.get(h, '')}</td>" for h in headers])
                        rows_td += f"<tr>{row_cells}</tr>"
                    
                    records_html = f"""
                    <div class="table-container">
                        <table class="data-table">
                            <thead><tr>{header_th}</tr></thead>
                            <tbody>{rows_td}</tbody>
                        </table>
                    </div>
                    """
                else:
                    items_li = "".join([f"<li><code>{item}</code></li>" for item in records])
                    records_html = f"<ul class='issue-list'>{items_li}</ul>"

            exceptions_sections_html += f"""
            <div class="exception-card">
                <div class="exception-card-header">
                    <h3>⚠️ Discrepancy Details: {check_name}</h3>
                    <span class="status-fail">FAIL / EXCEPTION</span>
                </div>
                <p class="exception-desc">The following exact data rows failed verification thresholds and require auditor adjustment or explanation:</p>
                {records_html}
            </div>
            """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{wp_ref} Work Paper Report - {entity}</title>
    <style>
        :root {{
            --primary: #0f172a;
            --primary-light: #1e293b;
            --accent: #2563eb;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --pass-bg: #dcfce7;
            --pass-text: #15803d;
            --fail-bg: #fee2e2;
            --fail-text: #b91c1c;
            --border: #e2e8f0;
        }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            margin: 0;
            padding: 30px 20px;
        }}
        .container {{
            max-width: 960px;
            margin: 0 auto;
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05), 0 8px 10px -6px rgba(0,0,0,0.01);
            overflow: hidden;
            border: 1px solid var(--border);
        }}
        .header {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #ffffff;
            padding: 32px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-title h1 {{
            margin: 0;
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        .header-title p {{
            margin: 6px 0 0 0;
            color: #94a3b8;
            font-size: 14px;
        }}
        .badge-clean {{
            background: #064e3b;
            color: #34d399;
            border: 1px solid #059669;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 14px;
            letter-spacing: 0.5px;
        }}
        .badge-exception {{
            background: #7f1d1d;
            color: #fca5a5;
            border: 1px solid #dc2626;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 14px;
            letter-spacing: 0.5px;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            background: #f1f5f9;
            padding: 24px 40px;
            border-bottom: 1px solid var(--border);
        }}
        .meta-item label {{
            display: block;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-muted);
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .meta-item span {{
            font-size: 15px;
            font-weight: 600;
            color: var(--text-main);
        }}
        .content {{
            padding: 40px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 700;
            margin: 0 0 16px 0;
            color: var(--primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-title::before {{
            content: '';
            display: inline-block;
            width: 4px;
            height: 18px;
            background: var(--accent);
            border-radius: 2px;
        }}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 36px;
        }}
        .summary-table th, .summary-table td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }}
        .summary-table th {{
            background: #f8fafc;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
        }}
        .status-pass {{
            background: var(--pass-bg);
            color: var(--pass-text);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
        }}
        .status-fail {{
            background: var(--fail-bg);
            color: var(--fail-text);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
        }}
        .clean-box {{
            background: #ecfdf5;
            border: 1px solid #a7f3d0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .exception-card {{
            background: #fff;
            border: 1px solid #fca5a5;
            border-left: 5px solid #ef4444;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px rgba(239, 68, 68, 0.05);
        }}
        .exception-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .exception-card-header h3 {{
            margin: 0;
            font-size: 16px;
            color: #991b1b;
        }}
        .exception-desc {{
            margin: 0 0 16px 0;
            font-size: 13px;
            color: #7f1d1d;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            background: #fff;
            border: 1px solid var(--border);
            border-radius: 6px;
            overflow: hidden;
        }}
        .data-table th, .data-table td {{
            padding: 10px 14px;
            text-align: left;
            font-size: 13px;
            border-bottom: 1px solid var(--border);
        }}
        .data-table th {{
            background: #f1f5f9;
            color: var(--text-main);
            font-weight: 600;
        }}
        .data-table tr:nth-child(even) {{
            background: #f8fafc;
        }}
        .issue-list {{
            margin: 0;
            padding-left: 20px;
            color: #991b1b;
        }}
        .issue-list li {{
            margin-bottom: 6px;
        }}
        .footer {{
            padding: 24px 40px;
            background: #f8fafc;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-muted);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-title">
                <h1>{wp_ref} Audit Work Paper Report</h1>
                <p>Automated Financial Statement Review & Anomalies Log</p>
            </div>
            <div>
                <span class="{status_class}">{status.upper()}</span>
            </div>
        </div>

        <div class="meta-grid">
            <div class="meta-item">
                <label>Entity Name</label>
                <span>{entity}</span>
            </div>
            <div class="meta-item">
                <label>Preparer Name</label>
                <span>{preparer}</span>
            </div>
            <div class="meta-item">
                <label>Review Date</label>
                <span>{rev_date}</span>
            </div>
            <div class="meta-item">
                <label>Current Period</label>
                <span>{curr_per}</span>
            </div>
            <div class="meta-item">
                <label>Prior Period</label>
                <span>{prior_per}</span>
            </div>
            <div class="meta-item">
                <label>Work Paper Reference</label>
                <span>{wp_ref}</span>
            </div>
        </div>

        <div class="content">
            <h2 class="section-title">1. Executive Summary & Verification Checklist</h2>
            <table class="summary-table">
                <thead>
                    <tr>
                        <th>Audit Procedure / Check Category</th>
                        <th>Verification Status</th>
                        <th>Auditor Notes</th>
                    </tr>
                </thead>
                <tbody>
                    {summary_table_html}
                </tbody>
            </table>

            <h2 class="section-title">2. Discrepancy & Exception Logs (Failed Checks Data)</h2>
            {exceptions_sections_html}

            <h2 class="section-title">3. Auditor Executive Summary & Discrepancy Commentary</h2>
            <div style="background: #f8fafc; border: 1px solid var(--border); border-left: 4px solid var(--accent); border-radius: 8px; padding: 20px; font-size: 14px; line-height: 1.6; white-space: pre-line;">
                {wp.get("audit_narrative", "No audit notes generated.")}
            </div>
        </div>

        <div class="footer">
            <span>Generated by Financial Statement Analysis & Review Tool</span>
            <span>WP-514 Standard Work Paper • Confidential Audit Documentation</span>
        </div>
    </div>
</body>
</html>
"""
    return html_content
