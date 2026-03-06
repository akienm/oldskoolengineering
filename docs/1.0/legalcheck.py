#!/usr/bin/env python3
"""
legalcheck.py - Legal citation scanner and validator

Usage:
  python legalcheck.py <filename>              scan a document
  python legalcheck.py --selftest              run unit tests (UnitTestCitations.txt)
  python legalcheck.py --selftest <file>       run unit tests against a specific file
"""

import argparse
import difflib
import json
import os
import re
import sys
import unicodedata
import requests

import logging

sys.stdout.reconfigure(encoding='utf-8')

from amm_diagnostics import get_logger, SmartDict

logger = get_logger()

# Silence the console handler — keep file log verbose, console gets print() only
for _h in logger.handlers:
    if isinstance(_h, logging.StreamHandler) and not isinstance(_h, logging.FileHandler):
        _h.setLevel(logging.CRITICAL)


def out(symbol, text):
    print(f"{symbol} {text}")

# ── Config / Class Registry ────────────────────────────────────────────────────

CLASS_REGISTRY = "CLASS_REGISTRY"
master_config = SmartDict()
master_config[CLASS_REGISTRY] = SmartDict()

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


# ── Dynamic Class Loader ───────────────────────────────────────────────────────

class ImportedClass(SmartDict):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        master_config[CLASS_REGISTRY][cls.__name__] = cls

    @classmethod
    def read_config(cls, config_file=CONFIG_FILE):
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f, object_pairs_hook=SmartDict)
        for section, class_defs in config_data.items():
            master_config[section] = []
            for class_def in class_defs:
                name_key = next((k for k in class_def if k.endswith("ClassName")), None)
                if not name_key:
                    raise ValueError(f"No ClassName key in: {class_def}")
                class_name = class_def[name_key]
                base_class_name = class_def.pop("SubOf", "ImportedClass")
                base_class = master_config[CLASS_REGISTRY].get(base_class_name)
                if not base_class:
                    raise ValueError(f"Unknown base class: {base_class_name}")
                new_class = type(class_name, (base_class,), dict(class_def))
                master_config[section].append(new_class)
                logger.debug(f"Registered: {class_name} (base: {base_class_name})")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _name_similarity(a, b):
    """Case-insensitive fuzzy similarity ratio between two case names."""
    def norm(s):
        return re.sub(r'[^a-z0-9 ]', '', s.lower().strip())
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


# ── Base Citation ──────────────────────────────────────────────────────────────

class BaseCitation(ImportedClass):
    regexes = []
    match_fields = []
    normalizing_fields = []
    lookup = {}

    def __init__(self, match):
        self.initializing_match = match
        for i, field in enumerate(self.match_fields):
            setattr(self, field, match[i])
        self._raw_text = str(match)
        self._normalized = SmartDict({
            self.normalizing_fields[i]: match[i]
            for i in range(len(self.normalizing_fields))
        })

    @classmethod
    def collect_instances(cls, text):
        results = []
        seen = set()
        for regex in cls.regexes:
            for match in re.findall(regex, text):
                if isinstance(match, str):
                    match = (match,)
                # Dedupe: strip trailing commas/spaces from each field
                key = (cls.__name__,) + tuple(s.strip().rstrip(',') for s in match)
                if key not in seen:
                    seen.add(key)
                    results.append(cls(match))
        return results

    def validate(self):
        """Returns (matched: bool, detail: dict)"""
        cfg = self.lookup
        if not cfg or not cfg.get("supported", True):
            return False, {"status": "unsupported"}

        token = os.getenv(cfg["EnvKeyName"])
        if not token:
            return False, {"status": "error", "reason": f"Missing env var {cfg['EnvKeyName']}"}

        payload = {field: self._normalized[field] for field in cfg["ExpectedFields"]}
        headers = {"Authorization": f"Token {token}"}

        try:
            response = requests.post(cfg["url"], data=payload, headers=headers, timeout=10)
        except Exception as e:
            return False, {"status": "error", "reason": str(e)}

        if response.status_code != 200:
            return False, {"status": "error", "status_code": response.status_code}

        result = response.json()
        # CourtListener returns a list. Each entry has a nested 'status' and 'clusters'.
        # HTTP 200 with status=404 in the body means the citation was not found.
        if not (isinstance(result, list) and len(result) > 0
                and result[0].get("status") == 200
                and len(result[0].get("clusters", [])) > 0):
            return False, {"status": "not_found"}

        found_case_name = result[0]["clusters"][0].get("case_name", "")
        searched_name = self._normalized.get("case_name", "")
        similarity = _name_similarity(searched_name, found_case_name)
        if similarity < 0.6:
            return False, {"status": "mismatch", "found": found_case_name, "similarity": similarity}

        return True, {"status": "found", "found": found_case_name}

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self._raw_text}>"


# ── Engine ─────────────────────────────────────────────────────────────────────

def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii"))


def scan(text):
    results = []
    for CitationType in master_config.get("CitationClasses", []):
        results.extend(CitationType.collect_instances(text))
    return results


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
            out("⚪", c)
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

    ImportedClass.read_config()
    logger.info("Citation engine ready.")

    if args.selftest:
        cmd_selftest(args.selftest)
    elif args.file:
        cmd_scan(args.file)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
