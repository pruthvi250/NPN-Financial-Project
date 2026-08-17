"""
grammar_check.py
Replaces grammer.py.

grammer.py only scanned for non-'$' currency symbols and called that
"error scanning" - despite the module name, it never checked spelling or
grammar at all. This version does three things, offline (no external API
needed, which matters for a hackathon demo with no guaranteed internet):

  1. Spelling - via `pyspellchecker`, a local dictionary-based checker.
  2. Basic grammar heuristics - repeated words ("the the"), double
     spaces, sentences not starting with a capital letter. This is not a
     full grammar engine (that would need a hosted LLM call - see the
     Q&A Assistant tab for where you'd wire that in with your own API
     key), but it is real, not decorative.
  3. Currency-format scan - kept from the original grammer.py, since a
     stray non-$ currency symbol in a USD-denominated report is a
     legitimate red flag, just relabeled as what it actually checks.
"""

import re
from pypdf import PdfReader

try:
    from spellchecker import SpellChecker
    _SPELL = SpellChecker()
    _SPELL.word_frequency.load_words({
        "ceo", "hfcs", "pfcs", "www", "ipcc", "cfo", "cpa", "sec",
        "gaap", "ifrs", "ebit", "ebitda", "esg", "hfc", "pfc",
    })
except ImportError:
    _SPELL = None

# Financial/company terms that a general dictionary will wrongly flag.
DOMAIN_WHITELIST = {
    "cognizant", "esg", "sasb", "tcfd", "gri", "ebitda", "capex", "opex",
    "yoy", "10-k", "10k", "eps", "npn", "wp-514", "wp", "kpmg", "pwc",
    "roa", "roe",
}


def _is_acronym_like(word: str) -> bool:
    return word.isupper() or re.fullmatch(r"[A-Z]{2,}s", word) is not None


def extract_text(pdf_path_or_file) -> str:
    reader = PdfReader(pdf_path_or_file)
    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"
    return text


def check_spelling(text: str, max_results: int = 100) -> list:
    if _SPELL is None:
        return [{
            "error": "pyspellchecker not installed - run: pip install pyspellchecker"
        }]
    words = re.findall(r"[A-Za-z]+", text)
    candidates = {
        w.lower()
        for w in words
        if len(w) > 2
        and w.lower() not in DOMAIN_WHITELIST
        and not _is_acronym_like(w)
    }
    misspelled = _SPELL.unknown(candidates)
    results = []
    for word in list(misspelled)[:max_results]:
        suggestion = _SPELL.correction(word)
        if suggestion and suggestion != word:
            results.append({"word": word, "suggestion": suggestion})
    return results


def check_grammar_heuristics(text: str) -> list:
    issues = []

    # Repeated consecutive words, e.g. "the the"
    for m in re.finditer(r"\b(\w+)\s+\1\b", text, flags=re.IGNORECASE):
        issues.append({"type": "Repeated word", "detail": f"'{m.group(0)}'"})

    # Double spaces
    if re.search(r"\S  +\S", text):
        issues.append({"type": "Formatting", "detail": "Double spaces found between words"})

    # Sentences not starting with a capital letter (rough heuristic:
    # look at the first letter after '. ')
    for m in re.finditer(r"\.\s+([a-z])", text):
        snippet = text[max(0, m.start() - 20): m.start() + 20].replace("\n", " ")
        issues.append({"type": "Capitalization", "detail": f"...{snippet}..."})

    return issues[:50]  # cap for readability


def check_currency_format(text: str, expected_currency: str = "$") -> list:
    """Flags amounts written with a currency symbol other than the expected one."""
    pattern = r"(?P<currency>[$\u20ac\u00a3\u00a5\u20b9])\s?(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
    flagged = []
    for m in re.finditer(pattern, text):
        currency, amount = m.group("currency"), m.group("amount")
        if currency != expected_currency:
            flagged.append({"currency": currency, "amount": amount})
    return flagged


def run_all_checks(pdf_path_or_file) -> dict:
    text = extract_text(pdf_path_or_file)
    return {
        "text_length_chars": len(text),
        "spelling_issues": check_spelling(text),
        "grammar_issues": check_grammar_heuristics(text),
        "currency_format_issues": check_currency_format(text),
    }
