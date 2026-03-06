#!/usr/bin/env python3
"""
legalcheck.py - Legal citation scanner and validator (POC1)

Usage:
  python legalcheck.py <filename>              scan a document
  python legalcheck.py --selftest              run unit tests (UnitTestCitations.txt)
  python legalcheck.py --selftest <file>       run unit tests against a specific file
"""

import argparse
import sys

sys.stdout.reconfigure(encoding='utf-8')

from citation_engine import init, scan, normalize, logger, silence_console

silence_console()


def out(symbol, text):
    print(f"{symbol} {text}")


# ── Scan Mode ─────────────────────────────────────────────────────────────────

def cmd_scan(filepath):
    logger.info(f"Scanning: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        text = normalize(f.read())

    citations = scan(text)
    if not citations:
        logger.warning("No citations found.")
        return

    passed = failed = unsupported = 0
    for c in citations:
        matched, detail = c.validate()
        status = detail.get("status")
        if status == "unsupported":
            logger.info(f"  [unsupported] {c}")
            out("⚪", f"{c}  (Westlaw -- requires subscription to validate)")
            unsupported += 1
        elif matched:
            logger.info(f"  [valid]       {c}")
            out("✅", c)
            passed += 1
        elif status == "mismatch":
            logger.warning(f"  [mismatch]    {c} -- found: {detail['found']}")
            out("❌", f"{c}  (found: {detail['found']})")
            failed += 1
        else:
            logger.warning(f"  [not found]   {c}")
            out("❌", c)
            failed += 1

    summary = f"{passed} valid, {failed} invalid, {unsupported} unsupported -- {len(citations)} total"
    logger.info(f"Results: {summary}")
    print(f"\n{summary}")


# ── Selftest Mode ─────────────────────────────────────────────────────────────

def cmd_selftest(filepath):
    logger.info(f"Self-test: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    section = None
    errors = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if "GOOD" in line:
                section = "GOOD"
            elif "BAD" in line:
                section = "BAD"
            continue

        citations = scan(normalize(line))

        if not citations:
            logger.warning(f"  no match: {line}")
            if section == "GOOD":
                errors.append(f"GOOD line had no match: {line}")
            continue

        for c in citations:
            matched, detail = c.validate()
            if detail.get("status") == "unsupported":
                logger.info(f"  [unsupported] {c}")
                out("⚪", c)
                continue
            if section == "GOOD":
                if matched:
                    logger.info(f"  [PASS] GOOD validated: {c}")
                    out("✅", c)
                else:
                    logger.error(f"  [FAIL] GOOD failed validation: {c}")
                    out("❌", c)
                    errors.append(f"GOOD failed: {c}")
            elif section == "BAD":
                if matched:
                    logger.warning(f"  [FAIL] BAD unexpectedly validated (false positive): {c}")
                    out("⚠️ ", f"UNEXPECTED PASS: {c}")
                    errors.append(f"BAD false positive: {c}")
                else:
                    logger.info(f"  [PASS] BAD correctly rejected: {c}")
                    out("❌", f"NOT FOUND (expected): {c}")

    if errors:
        logger.error(f"Self-test FAILED -- {len(errors)} error(s):")
        print(f"\nSelf-test FAILED -- {len(errors)} error(s):")
        for e in errors:
            logger.error(f"  {e}")
            print(f"  {e}")
        sys.exit(1)
    else:
        logger.info("Self-test PASSED")
        print("\nSelf-test PASSED")


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Legal citation scanner and validator")
    parser.add_argument("file", nargs="?", help="Document to scan")
    parser.add_argument(
        "--selftest", nargs="?", const="UnitTestCitations.txt", metavar="FILE",
        help="Run unit tests (default: UnitTestCitations.txt)"
    )
    args = parser.parse_args()

    init()

    if args.selftest:
        cmd_selftest(args.selftest)
    elif args.file:
        cmd_scan(args.file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
