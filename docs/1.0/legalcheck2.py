#!/usr/bin/env python3
"""
legalcheck2.py - Legal citation scanner with AI usage analysis (POC2)

Extends POC1 (legalcheck.py) with LLM-based analysis of whether each citation
was used correctly in context.

Flow per citation:
  1. Find citation in document (citation_engine.scan)
  2. Validate citation coordinates via CourtListener (citation_engine.BaseCitation.validate)
  3. Fetch opinion text from CourtListener (cluster -> sub_opinions -> plain_text)
  4. Extract surrounding context from the document (sentence(s) around the citation)
  5. Send holding excerpt + usage context to LLM via OpenRouter
  6. Report: valid / suspect / likely hallucinated + one-sentence reason

Usage:
  python legalcheck2.py <filename>

Design notes: see GitHub issue #5
"""

import argparse
import sys

sys.stdout.reconfigure(encoding='utf-8')

from citation_engine import init, scan, normalize, logger, silence_console

silence_console()


def out(symbol, text):
    print(f"{symbol} {text}")


# ── POC2: Opinion Fetcher (stub) ──────────────────────────────────────────────

def fetch_opinion_text(cluster):
    """Fetch plain_text of the first sub_opinion from a CourtListener cluster.
    Returns the text string, or None on failure.
    """
    # TODO: implement — cluster['sub_opinions'][0] -> GET -> plain_text
    raise NotImplementedError


def extract_holding(plain_text, max_chars=3000):
    """Extract the most likely holding section from an opinion's plain text.
    Looks for 'we hold', 'we conclude', 'we affirm', 'we reverse' and returns
    surrounding context. Falls back to the final max_chars of the opinion.
    """
    # TODO: implement
    raise NotImplementedError


def extract_usage_context(full_text, citation, context_chars=500):
    """Return the sentence(s) surrounding a citation's position in the document."""
    # TODO: implement — find citation string in full_text, return ±context_chars
    raise NotImplementedError


# ── POC2: LLM Analysis (stub) ─────────────────────────────────────────────────

def analyze_citation_usage(citation, holding_text, usage_context):
    """Send holding + usage context to an LLM via OpenRouter.
    Returns dict: {verdict: 'valid'|'suspect'|'hallucinated', reason: str}
    """
    # TODO: implement — OpenRouter API call, low temp, structured prompt
    # Model: TBD (Qwen-2.5-72B or DeepSeek-V3 candidates)
    # Prompt strategy: provide only the text we fetched, forbid outside knowledge,
    #   ask for YES/NO/UNCERTAIN + one-sentence reason
    raise NotImplementedError


# ── Scan + Analyze ────────────────────────────────────────────────────────────

def cmd_analyze(filepath):
    logger.info(f"Analyzing: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    text = normalize(raw_text)
    citations = scan(text)

    if not citations:
        logger.warning("No citations found.")
        return

    for c in citations:
        matched, detail = c.validate()
        status = detail.get("status")

        if status == "unsupported":
            out("⚪", c)
            continue

        if not matched:
            symbol = "❌"
            suffix = f"  (found: {detail['found']})" if status == "mismatch" else ""
            out(symbol, f"{c}{suffix}")
            continue

        # Citation coordinates are valid — now analyze usage
        # TODO: wire up fetch_opinion_text, extract_holding, extract_usage_context,
        #       analyze_citation_usage once those are implemented
        out("✅", f"{c}  [usage analysis: not yet implemented]")


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Legal citation scanner with AI usage analysis (POC2)"
    )
    parser.add_argument("file", help="Document to analyze")
    args = parser.parse_args()

    init()
    cmd_analyze(args.file)


if __name__ == "__main__":
    main()
