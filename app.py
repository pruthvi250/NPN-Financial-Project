"""
app.py

Financial Statement Analysis / Review App — Cognizant Hackathon Banking Use Case

Automates audit verification steps: mathematical accuracy, prior-year tie-out,
internal consistency, spelling & grammar check, financial ratio profiling (Altman Z-Score),
WP-514 work paper generation (HTML, JSON, CSV), and LLM Q&A assistant.

Run with:  streamlit run app.py
"""

import os
import importlib

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from modules import data_loader, math_accuracy, prior_year_tieout, internal_consistency, grammar_check, wp514, financial_ratios

# Ensure submodules are reloaded dynamically if changed
importlib.reload(data_loader)
importlib.reload(math_accuracy)
importlib.reload(prior_year_tieout)
importlib.reload(internal_consistency)
importlib.reload(grammar_check)
importlib.reload(wp514)
importlib.reload(financial_ratios)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DEFAULT_ANNUAL = os.path.join(DATA_DIR, "Annual.csv")
DEFAULT_QUARTERLY = os.path.join(DATA_DIR, "Quarter.csv")

st.set_page_config(page_title="Financial Statement Review & Audit Workspace", layout="wide")


def render_variance_chart(df, title, x_column="Year"):
    """Render a feature-scaled variance chart without altering audit data."""
    if df.empty or x_column not in df.columns:
        return
    variance_columns = [c for c in df.columns if c == "Difference" or c.endswith(" Diff")]
    if not variance_columns:
        return
    chart_df = df[[x_column] + variance_columns].melt(
        id_vars=x_column, var_name="Check", value_name="Raw Variance"
    )

    # Scale each check independently by its largest absolute variance.
    # This changes only the chart's display range—not the source data or flags.
    max_abs = chart_df.groupby("Check")["Raw Variance"].transform(lambda values: values.abs().max())
    chart_df["Scaled Variance"] = chart_df["Raw Variance"].div(max_abs.where(max_abs.ne(0), 1))

    if chart_df["Raw Variance"].fillna(0).eq(0).all():
        st.info(f"{title}: all reported variances are zero, so there is no visible variance to plot.")
        return

    fig = px.bar(
        chart_df, x=x_column, y="Scaled Variance", color="Check", barmode="group",
        title=title, template="plotly_white",
        color_discrete_sequence=px.colors.qualitative.Safe,
        custom_data=["Raw Variance"],
    )
    fig.update_traces(
        hovertemplate="Year: %{x}<br>Scaled variance: %{y:.3f}<br>Actual variance: %{customdata[0]:,.2f}<extra>%{fullData.name}</extra>"
    )
    fig.add_hline(y=0, line_color="#64748b", line_width=1)
    fig.update_layout(
        yaxis_title="Scaled variance (each check: -1 to +1)",
        margin=dict(l=20, r=20, t=45, b=20), legend_title_text="",
    )
    st.caption("Chart display uses max-absolute feature scaling per check; hover to see the unmodified actual variance. The audit table and exception flags use original values.")
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Shared data loading (sidebar) - every tab reads from the same session state
# ---------------------------------------------------------------------------
def load_data_sidebar():
    st.sidebar.header("Data Sources")
    st.sidebar.caption("Upload the two CSV files to analyse your own financial data. "
                       "The files are processed in memory and are not saved by the app.")

    use_demo_data = st.sidebar.checkbox("Use bundled demo data", value=False)

    annual_file = st.sidebar.file_uploader("Annual financials CSV", type="csv", key="annual_upload")
    quarterly_file = st.sidebar.file_uploader("Quarterly financials CSV", type="csv", key="quarterly_upload")

    template_col1, template_col2 = st.sidebar.columns(2)
    with template_col1:
        with open(DEFAULT_ANNUAL, "rb") as sample:
            st.download_button("Annual template", sample.read(), "Annual_template.csv", "text/csv")
    with template_col2:
        with open(DEFAULT_QUARTERLY, "rb") as sample:
            st.download_button("Quarterly template", sample.read(), "Quarterly_template.csv", "text/csv")

    if not use_demo_data and (annual_file is None or quarterly_file is None):
        st.sidebar.info("Upload both files to begin, or select bundled demo data.")
        return None, None, 1.0

    try:
        annual_source = DEFAULT_ANNUAL if use_demo_data else annual_file
        quarterly_source = DEFAULT_QUARTERLY if use_demo_data else quarterly_file
        annual_df = data_loader.load_annual(annual_source)
        quarterly_df = data_loader.load_quarterly(quarterly_source)
    except Exception as e:
        st.sidebar.error(f"Could not load data: {e}")
        return None, None, 1.0

    missing_a = data_loader.validate_schema(annual_df, data_loader.ANNUAL_REQUIRED_COLS)
    missing_q = data_loader.validate_schema(quarterly_df, data_loader.QUARTERLY_REQUIRED_COLS)
    if missing_a:
        st.sidebar.error("Annual CSV is not compatible. Missing: " + ", ".join(missing_a))
    if missing_q:
        st.sidebar.error("Quarterly CSV is not compatible. Missing: " + ", ".join(missing_q))
    if missing_a or missing_q:
        st.sidebar.caption("Use the template files, or rename equivalent columns (for example, Revenue, Sales, or Total Revenue are accepted).")
        return None, None, 1.0

    source_key = (("demo",) if use_demo_data else
                  (annual_file.name, annual_file.size, quarterly_file.name, quarterly_file.size))
    if st.session_state.get("data_source_key") != source_key:
        for result_key in ("math_results", "tieout_result", "consistency_results"):
            st.session_state.pop(result_key, None)
        st.session_state["data_source_key"] = source_key

    st.sidebar.success(f"Loaded {len(annual_df)} annual rows and {len(quarterly_df)} quarterly rows.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Audit Parameters")
    tolerance = st.sidebar.slider(
        "Materiality Tolerance ($M)",
        min_value=0.1,
        max_value=10.0,
        value=1.0,
        step=0.1,
        help="Discrepancies exceeding this threshold will be flagged as exceptions.",
    )

    return annual_df, quarterly_df, tolerance


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def tab_overview(annual_df, quarterly_df):
    st.header("Executive Audit Dashboard")
    st.write(
        "Automated audit suite validating financial statement accuracy, prior-year tie-outs, "
        "internal consistency, narrative quality, bankruptcy risk profiling (Altman Z-Score), "
        "and automated WP-514 audit work paper generation."
    )

    # Executive KPI Summary Cards
    latest_row = annual_df.sort_values("Year").iloc[-1]
    latest_year = latest_row["Year"]
    revenue = latest_row.get("Revenues", 0)
    net_income = latest_row.get("Net income", 0)
    op_income = latest_row.get("Operating income", 0)
    margin = (op_income / revenue * 100) if revenue else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(f"Latest Revenue ({latest_year})", f"₹{revenue:,.1f} CR")
    with col2:
        st.metric(f"Net Income ({latest_year})", f"₹{net_income:,.1f} CR")
    with col3:
        st.metric("Operating Margin", f"{margin:.2f}%")
    with col4:
        st.metric("Reporting Currency", "INR (₹CR)")

    st.markdown("---")

    st.subheader("Financial Performance Trends")
    st.caption("Annual performance, growth, and margin trends generated from the uploaded Annual financials CSV.")
    chart_df = annual_df.sort_values("Year").copy()
    trend_col, margin_col = st.columns((3, 2))
    with trend_col:
        selected_metrics = st.multiselect(
            "Metrics to compare ($M)",
            options=[c for c in ["Revenues", "Operating income", "Net income", "Net cash flow", "Total Assets"] if c in chart_df.columns],
            default=[c for c in ["Revenues", "Operating income", "Net income"] if c in chart_df.columns],
            key="annual_trend_metrics",
        )
        fig = go.Figure()
        palette = ["#2563eb", "#059669", "#7c3aed", "#ea580c", "#0891b2"]
        for index, metric in enumerate(selected_metrics):
            fig.add_trace(go.Scatter(
                x=chart_df["Year"], y=chart_df[metric], name=metric,
                mode="lines+markers", line=dict(color=palette[index], width=3),
                hovertemplate="%{x}<br>₹%{y:,.1f}M<extra>" + metric + "</extra>",
            ))
        fig.update_layout(xaxis_title="Year", yaxis_title="Amount (₹ Millions)", template="plotly_white",
                          margin=dict(l=20, r=20, t=30, b=20), hovermode="x unified",
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
    with margin_col:
        margin_df = chart_df[["Year", "Revenues"]].copy()
        margin_df["Revenue Growth %"] = chart_df["Revenues"].pct_change() * 100
        if "Operating income" in chart_df.columns:
            margin_df["Operating Margin %"] = chart_df["Operating income"] / chart_df["Revenues"] * 100
        if "Net income" in chart_df.columns:
            margin_df["Net Margin %"] = chart_df["Net income"] / chart_df["Revenues"] * 100
        margin_fig = px.line(margin_df, x="Year", y=[c for c in margin_df.columns if c.endswith("%")],
                             markers=True, title="Growth & Profitability (%)", template="plotly_white",
                             color_discrete_sequence=["#2563eb", "#059669", "#7c3aed"])
        margin_fig.add_hline(y=0, line_color="#94a3b8", line_width=1)
        margin_fig.update_layout(margin=dict(l=20, r=20, t=45, b=20), legend_title_text="")
        st.plotly_chart(margin_fig, use_container_width=True)

    st.subheader("Quarterly Performance Trends")
    q_chart_df = quarterly_df.sort_values(["Year", "Quarters"]).copy()
    q_chart_df["Period"] = q_chart_df["Year"].astype(str) + " " + q_chart_df["Quarters"]
    quarterly_metric = st.selectbox(
        "Quarterly metric (₹M)",
        [c for c in ["Revenues", "Operating income", "Net income", "Net cash flow", "Total Assets"] if c in q_chart_df.columns],
    )
    quarterly_fig = px.area(q_chart_df, x="Period", y=quarterly_metric, markers=True,
                            title=f"{quarterly_metric} by Quarter", template="plotly_white",
                            color_discrete_sequence=["#2563eb"])
    quarterly_fig.update_layout(xaxis_title="Reporting Period", yaxis_title="Amount (₹ Millions)",
                                margin=dict(l=20, r=20, t=45, b=20))
    st.plotly_chart(quarterly_fig, use_container_width=True)

    st.subheader("Annual Financial Statements")
    st.dataframe(annual_df, use_container_width=True)

    st.subheader("Quarterly Financial Statements")
    st.dataframe(quarterly_df, use_container_width=True)


def tab_math_accuracy(annual_df, tolerance):
    st.header("Mathematical Accuracy")
    st.caption(
        f"Checks balance sheet identity, cash-flow sum, and guidance accuracy using materiality tolerance of **${tolerance:,.1f}M**."
    )
    results = math_accuracy.run_all_checks(annual_df, tolerance=tolerance)
    for name, df in results.items():
        st.subheader(name)
        st.dataframe(df, use_container_width=True)
        render_variance_chart(df, f"{name}: Variance by Year")
        if "Flag" in df.columns and df["Flag"].any():
            st.warning(f"{int(df['Flag'].sum())} period(s) flagged exceeding ${tolerance:,.1f}M tolerance.")
    st.session_state["math_results"] = results


def tab_prior_year_tieout(annual_df, quarterly_df, tolerance):
    st.header("Prior Year Tie-Out")
    st.caption(
        f"Confirms year-end balances in Annual file match Q4 figures in Quarterly file (tolerance: **${tolerance:,.1f}M**)."
    )
    tieout_df = prior_year_tieout.tie_out_annual_vs_q4(annual_df, quarterly_df, tolerance=tolerance)
    st.dataframe(tieout_df, use_container_width=True)
    render_variance_chart(tieout_df, "Annual vs Q4 Tie-Out Variances")
    flag_cols = [c for c in tieout_df.columns if c.endswith("Flag")]
    if flag_cols and tieout_df[flag_cols].any(axis=None):
        st.warning("One or more years show a tie-out break between Annual and Quarterly files.")
    else:
        st.success("All years tie out cleanly between Annual and Quarterly files.")

    st.subheader("Year-over-Year Growth Rates")
    growth_df = prior_year_tieout.compute_annual_growth_rates(annual_df)
    st.dataframe(growth_df, use_container_width=True)
    growth_columns = [column for column in growth_df.columns if column.endswith("YoY Growth %")]
    if growth_columns:
        growth_fig = px.line(
            growth_df, x="Year", y=growth_columns, markers=True,
            title="Year-over-Year Growth Rate Trends", template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        growth_fig.add_hline(y=0, line_color="#64748b", line_width=1)
        growth_fig.update_layout(
            yaxis_title="Growth rate (%)", xaxis_title="Year", hovermode="x unified",
            margin=dict(l=20, r=20, t=45, b=20), legend_title_text="",
        )
        st.plotly_chart(growth_fig, use_container_width=True)

    st.subheader("Correlation Matrix")
    correlation_df = prior_year_tieout.compute_correlations(annual_df)
    st.dataframe(correlation_df, use_container_width=True)
    if not correlation_df.empty:
        correlation_fig = go.Figure(data=go.Heatmap(
            z=correlation_df.values,
            x=correlation_df.columns,
            y=correlation_df.index,
            zmin=-1, zmax=1,
            colorscale="RdBu",
            reversescale=True,
            text=correlation_df.round(2).values,
            texttemplate="%{text}",
            textfont={"size": 12},
            hovertemplate="%{y} × %{x}<br>Correlation: %{z:.3f}<extra></extra>",
            colorbar={"title": "Correlation"},
        ))
        correlation_fig.update_layout(
            title="Correlation Heatmap", template="plotly_white",
            xaxis={"side": "bottom"}, yaxis={"autorange": "reversed"},
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(correlation_fig, use_container_width=True)

    st.session_state["tieout_result"] = tieout_df


def tab_internal_consistency(annual_df, quarterly_df, tolerance):
    st.header("Internal Consistency")
    st.caption(
        f"Cross-checks facts across documents (Headcount, Cash Flow, Revenue) against tolerance **${tolerance:,.1f}M**."
    )
    results = internal_consistency.run_all_checks(annual_df, quarterly_df, tolerance=tolerance)
    for name, df in results.items():
        st.subheader(name)
        st.dataframe(df, use_container_width=True)
        render_variance_chart(df, f"{name}: Annual-to-Quarterly Variance")
        if "Flag" in df.columns and df["Flag"].any():
            st.warning(f"{int(df['Flag'].sum())} period(s) flagged exceeding tolerance.")
    st.session_state["consistency_results"] = results


def tab_financial_ratios(annual_df):
    st.header("Financial Ratios & Risk Profiling")
    st.caption("Computes financial health metrics and the Altman Z-Score bankruptcy risk model.")

    ratios_df = financial_ratios.compute_financial_ratios(annual_df)
    zscore_df = financial_ratios.compute_altman_z_score(annual_df)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Operating & Liquidity Ratios")
        st.dataframe(ratios_df, use_container_width=True)
    with col2:
        st.subheader("Altman Z-Score Bankruptcy Risk Model")
        st.dataframe(zscore_df, use_container_width=True)

    ratio_chart_columns = [c for c in ratios_df.columns if c != "Year"]
    if ratio_chart_columns:
        st.subheader("Ratio Trends")
        chosen_ratios = st.multiselect("Ratios to plot", ratio_chart_columns,
                                       default=ratio_chart_columns[:min(3, len(ratio_chart_columns))])
        if chosen_ratios:
            ratio_fig = px.line(ratios_df, x="Year", y=chosen_ratios, markers=True,
                                template="plotly_white", title="Financial Ratio Trend")
            ratio_fig.update_layout(margin=dict(l=20, r=20, t=45, b=20), legend_title_text="")
            st.plotly_chart(ratio_fig, use_container_width=True)

    # Plot Z-Score Trend
    fig = px.bar(zscore_df, x="Year", y="Altman Z-Score", color="Risk Zone", title="Altman Z-Score by Year", text_auto=True)
    fig.add_hline(y=2.99, line_dash="dash", line_color="green", annotation_text="Safe Zone (>2.99)")
    fig.add_hline(y=1.81, line_dash="dash", line_color="red", annotation_text="Distress Zone (<1.81)")
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)


def tab_grammar():
    st.header("Spelling & Grammar")
    st.caption(
        "Upload narrative PDF (annual/ESG report) to scan offline for spelling, basic grammar, and currency symbols."
    )
    pdf_file = st.file_uploader("Upload a PDF report", type="pdf", key="grammar_pdf")
    if pdf_file:
        with st.spinner("Extracting and scanning text..."):
            results = grammar_check.run_all_checks(pdf_file)
        st.write(f"Extracted {results['text_length_chars']:,} characters.")

        st.subheader("Spelling issues")
        st.dataframe(pd.DataFrame(results["spelling_issues"]), use_container_width=True)

        st.subheader("Grammar issues")
        st.dataframe(pd.DataFrame(results["grammar_issues"]), use_container_width=True)

        st.subheader("Currency format issues")
        st.dataframe(pd.DataFrame(results["currency_format_issues"]), use_container_width=True)

        st.session_state["grammar_results"] = results
    else:
        st.info("Upload a PDF to run the scan.")


def tab_wp514(annual_df):
    st.header("WP-514 Work Paper Generator")
    st.caption("Consolidates audit results into a standardized WP-514 Work Paper report.")

    col1, col2, col3 = st.columns(3)
    with col1:
        entity_name = st.text_input("Entity name", value="Cognizant Technology Solutions")
    with col2:
        years = sorted(annual_df["Year"].unique())
        period_current = st.selectbox("Current period", options=years, index=len(years) - 1)
    with col3:
        preparer_name = st.text_input("Preparer name", value="")

    prior_candidates = [y for y in years if y < period_current]
    period_prior = max(prior_candidates) if prior_candidates else None

    math_results = st.session_state.get("math_results", {})
    tieout_result = st.session_state.get("tieout_result", pd.DataFrame())
    consistency_results = st.session_state.get("consistency_results", {})
    grammar_results = st.session_state.get("grammar_results", {})

    if not math_results or tieout_result.empty or not consistency_results:
        st.warning("Run Mathematical Accuracy, Prior Year Tie-Out, and Internal Consistency "
                    "tabs at least once first, so this work paper has results to summarize.")

    if st.button("Generate WP-514 Work Paper"):
        wp = wp514.build_wp514(
            entity_name=entity_name,
            period_current=str(period_current),
            period_prior=str(period_prior),
            preparer_name=preparer_name,
            math_results=math_results,
            tieout_result=tieout_result,
            consistency_results=consistency_results,
            grammar_results=grammar_results,
        )
        
        html_report = wp514.to_html(wp)

        st.subheader("Export Options")
        dl_col1, dl_col2, dl_col3 = st.columns(3)
        with dl_col1:
            st.download_button(
                "📄 Download WP-514 (HTML Report)",
                data=html_report,
                file_name="WP-514_Report.html",
                mime="text/html",
            )
        with dl_col2:
            st.download_button(
                "📋 Download WP-514 (JSON)",
                data=wp514.to_json(wp),
                file_name="WP-514.json",
                mime="application/json",
            )
        with dl_col3:
            st.download_button(
                "📊 Download WP-514 (CSV)",
                data=wp514.to_dataframe(wp).to_csv(index=False),
                file_name="WP-514.csv",
                mime="text/csv",
            )

        # Show detailed exception tables for any checks that failed (were False)
        detailed_exceptions = wp.get("detailed_exceptions", {})
        if detailed_exceptions:
            st.subheader("Detailed Discrepancy & Exception Logs (Failed Checks Data)")
            for check_name, records in detailed_exceptions.items():
                st.error(f"❌ {check_name}")
                if isinstance(records, list) and len(records) > 0:
                    if isinstance(records[0], dict):
                        st.dataframe(pd.DataFrame(records), use_container_width=True)
                    else:
                        for item in records:
                            st.write(f"- {item}")
        else:
            st.success("✔ All checks verified clean. No discrepancies identified.")

        st.subheader("Auditor Executive Commentary")
        st.info(wp.get("audit_narrative", ""))

        st.subheader("WP-514 HTML Report Preview")
        st.components.v1.html(html_report, height=650, scrolling=True)

        with st.expander("View Raw WP-514 JSON Data"):
            st.json(wp)


def tab_qa():
    st.header("Q&A Assistant (optional)")
    st.caption(
        "Ask natural-language questions over uploaded PDF reports using your Google Gemini API key."
    )
    api_key = st.text_input("Google API key", type="password")
    pdf_files = st.file_uploader("Upload PDF(s)", type="pdf", accept_multiple_files=True, key="qa_pdfs")

    if st.button("Index documents"):
        if not api_key:
            st.error("Enter an API key first.")
        elif not pdf_files:
            st.error("Upload at least one PDF first.")
        else:
            try:
                from modules import qa_assistant
                with st.spinner("Extracting and indexing..."):
                    text = qa_assistant.get_pdf_text(pdf_files)
                    chunks = qa_assistant.get_text_chunks(text)
                    qa_assistant.build_vector_store(chunks, api_key)
                st.success("Documents indexed. Ask a question below.")
                st.session_state["qa_ready"] = True
                st.session_state["qa_api_key"] = api_key
            except ImportError as e:
                st.error(f"Missing dependency: {e}")

    question = st.text_input("Your question")
    if question and st.session_state.get("qa_ready"):
        from modules import qa_assistant
        with st.spinner("Thinking..."):
            answer = qa_assistant.answer_question(question, st.session_state["qa_api_key"])
        st.write(answer)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    st.title("Financial Statement Analysis & Audit Review Workspace")
    st.caption("Banking Use Case • Cognizant Hackathon Automated Audit Suite")

    annual_df, quarterly_df, tolerance = load_data_sidebar()
    if annual_df is None:
        st.stop()

    tab_names = [
        "Executive Dashboard",
        "Mathematical Accuracy",
        "Prior Year Tie-Out",
        "Internal Consistency",
        "Financial Ratios & Risk",
        "Spelling & Grammar",
        "WP-514 Generator",
        "Q&A Assistant",
    ]
    tabs = st.tabs(tab_names)

    with tabs[0]:
        tab_overview(annual_df, quarterly_df)
    with tabs[1]:
        tab_math_accuracy(annual_df, tolerance)
    with tabs[2]:
        tab_prior_year_tieout(annual_df, quarterly_df, tolerance)
    with tabs[3]:
        tab_internal_consistency(annual_df, quarterly_df, tolerance)
    with tabs[4]:
        tab_financial_ratios(annual_df)
    with tabs[5]:
        tab_grammar()
    with tabs[6]:
        tab_wp514(annual_df)
    with tabs[7]:
        tab_qa()


if __name__ == "__main__":
    main()
