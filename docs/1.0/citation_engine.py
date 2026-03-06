"""
citation_engine.py - Shared citation scanning and validation library

Provides:
  - Config-driven citation class loader (ImportedClass, BaseCitation)
  - normalize(text) / scan(text) engine
  - CourtListener lookup with fuzzy case name matching
"""

import difflib
import json
import logging
import os
import re
import unicodedata
import requests

from amm_diagnostics import get_logger, SmartDict

logger = get_logger()

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
                key = (cls.__name__,) + tuple(s.strip().rstrip(',') for s in match)
                if key not in seen:
                    seen.add(key)
                    results.append(cls(match))
        return results

    def validate(self):
        """Returns (matched: bool, detail: dict)

        detail keys:
          status       -- 'found' | 'not_found' | 'mismatch' | 'unsupported' | 'error'
          found        -- case name returned by CourtListener (when status is found/mismatch)
          cluster      -- full cluster dict from CourtListener (when status is found/mismatch)
          similarity   -- name similarity score (when status is mismatch)
        """
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
        if not (isinstance(result, list) and len(result) > 0
                and result[0].get("status") == 200
                and len(result[0].get("clusters", [])) > 0):
            return False, {"status": "not_found"}

        cluster = result[0]["clusters"][0]
        found_case_name = cluster.get("case_name", "")
        searched_name = self._normalized.get("case_name", "")
        similarity = _name_similarity(searched_name, found_case_name)

        if similarity < 0.6:
            return False, {"status": "mismatch", "found": found_case_name,
                           "similarity": similarity, "cluster": cluster}

        return True, {"status": "found", "found": found_case_name, "cluster": cluster}

    def display(self, detail):
        """Return human-readable display string for a citation + validate result."""
        status = detail.get("status")
        base = repr(self)
        if status == "unsupported":
            return f"{base}  (Westlaw -- requires subscription to validate)"
        if status == "mismatch":
            return f"{base}  (found: {detail['found']})"
        return base

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


def init(config_file=CONFIG_FILE):
    """Load config and initialize the citation engine."""
    ImportedClass.read_config(config_file)
    logger.info("Citation engine ready.")


def silence_console():
    """Suppress logger output to console — use print() for user-facing output."""
    for h in logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(logging.CRITICAL)
