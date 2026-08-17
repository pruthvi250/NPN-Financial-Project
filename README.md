# Financial Statement Analysis / Review — Cognizant Hackathon

A Streamlit app that automates the manual checks an auditor runs on a bank's
financial statements: mathematical accuracy, prior-year tie-out, internal
consistency, spelling/grammar, and WP-514 generation — built on your real
`Annual.csv` / `Quarter.csv` data.

## 1. What changed from your original files, and why

| Old file | Problem | New file |
|---|---|---|
| `prag.py` | **Live API key hardcoded in source** — a real security issue | `modules/qa_assistant.py` — key entered at runtime, never stored in code |
| `All.py` | Hardcoded `/Users/pragyan/Desktop/bot/...` paths — only ran on one machine | `app.py` — direct imports, runs anywhere the repo is cloned |
| `grammer.py` | Named "grammar" but only scanned currency symbols — no spelling/grammar logic at all | `modules/grammar_check.py` — real spelling (dictionary-based) + grammar heuristics, keeps the currency scan as a bonus check, and skips common finance/technical acronyms so they do not get mis-flagged |
| `Accuracy.py` | Trained a regression model on 5 data points to "predict" revenue — not a math-accuracy check, and statistically unreliable with that little data | `modules/math_accuracy.py` — checks the balance sheet identity, cash-flow sum, and guidance accuracy using the `Predicted revenue` column already in your data |
| `Internal.py` | Computed a redundant column and expected two uploads of the same schema | `modules/internal_consistency.py` — cross-checks Annual vs Quarterly figures that should agree (headcount, cash flow, revenue) |
| `prior.py` | "Insights" were hardcoded text strings, not computed | `modules/prior_year_tieout.py` — ties Annual year-end figures to Quarterly Q4 figures, computes growth rates and correlations live |
| *(missing)* | WP-514 generation was in the problem statement but had no code | `modules/wp514.py` — new, builds the work paper from the other four modules' results |
| `Map.py` | Office map + autoplaying YouTube video — unrelated to the problem statement | Dropped. Add back only if you want a "company overview" tab; it does nothing for the review workflow. |

## 2. Project structure

```
npn_project/
├── app.py                       # Main Streamlit app — run this
├── requirements.txt
├── data/
│   ├── Annual.csv                # your real Cognizant annual data (bundled default)
│   └── Quarter.csv               # your real Cognizant quarterly data (bundled default)
└── modules/
    ├── data_loader.py            # CSV loading + schema validation
    ├── math_accuracy.py          # balance sheet identity, cash flow sum, guidance accuracy
    ├── prior_year_tieout.py      # Annual vs Q4 tie-out, growth rates, correlations
    ├── internal_consistency.py   # Annual vs sum/avg of Quarterly cross-checks
    ├── grammar_check.py          # spelling, grammar heuristics, currency-format scan
    ├── wp514.py                  # work paper generator
    └── qa_assistant.py           # optional RAG Q&A over an uploaded PDF
```

## 3. Setup — step by step

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app opens in your browser (usually `http://localhost:8501`). It loads
your bundled `Annual.csv` / `Quarter.csv` by default — you can upload
different files from the sidebar without touching code.

## 4. Walking through the tabs

1. **Overview** — loaded data + a revenue/operating-income chart, so a
   mentor sees what's being analyzed before any checks run.
2. **Mathematical Accuracy** — three checks: does Total Assets equal
   Total Liabilities + Total Equity; does the stated Net Cash Flow equal
   operating + investing + financing; how accurate was prior revenue
   guidance. On your real data, the balance sheet identity holds exactly,
   but the cash-flow sum is off by a small amount every year — a good,
   honest example to show mentors of a "planning analytics vs. reported
   totals" discrepancy.
3. **Prior Year Tie-Out** — matches each year's Annual-file closing
   figures against the Quarterly file's Q4 figures. Also shows live
   year-over-year growth and a correlation matrix (previously hardcoded
   text in `prior.py`).
4. **Internal Consistency** — checks whether annual headcount matches the
   average of the four quarters, and whether annual cash flow / revenue
   match the sum of the four quarters. Your data currently shows a real
   headcount mismatch every year — worth having an explanation ready
   (annual figures may use year-end headcount, not a quarterly average).
5. **Spelling & Grammar** — upload any of your Cognizant PDF reports here;
   it extracts text and flags spelling, basic grammar issues, and
   non-`$` currency symbols. Common acronyms and finance terms are
   whitelisted so the checker does not suggest nonsense like `ceo -> ce`.
6. **WP-514** — pulls the results already generated in the other tabs
   (run them first) into one work paper, downloadable as JSON or CSV.
7. **Q&A Assistant** — optional. Ask questions over an uploaded PDF using
   your own Google Gemini API key, entered at runtime. Needs the extra
   `langchain*` / `faiss-cpu` packages in `requirements.txt`.

## 5. Known limitations to be upfront about with mentors

- The spelling/grammar check is dictionary + heuristic based, not a full
   grammar engine (that would require a hosted LLM call — the Q&A tab
   shows where you'd wire one in with a user-supplied key). It also
   includes a whitelist for common acronyms so the output stays useful on
   financial and ESG reports.
- Tolerances (`TOLERANCE = 1`, i.e. $1M) are set conservatively for
  hackathon demo data; tune per real materiality thresholds if you extend
  this.
- The four annual reports/ESG PDFs you uploaded (2020 ESG, 2022, 2023
  annual reports) aren't auto-parsed into the CSV schema — that would
  need a table-extraction step (`pdfplumber`) per report layout, which
  varies year to year. The Spelling/Grammar and Q&A tabs work directly on
  those PDFs today; wiring their tables into `math_accuracy.py` is the
  natural next step if you want a live "upload the PDF, skip the CSV"
  flow.
