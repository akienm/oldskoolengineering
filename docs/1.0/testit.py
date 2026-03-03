import os
import re
import json
import unicodedata
import requests
from amm_diagnostics import get_logger, SmartDict

logger = get_logger()

# === Global Config ===
CLASS_REGISTRY = "CLASS_REGISTRY"
master_config = SmartDict()
master_config[CLASS_REGISTRY] = SmartDict()


# === Dynamic Class Loader ===

class ImportedClass(SmartDict):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        master_config[CLASS_REGISTRY][cls.__name__] = cls
        logger.debug(f"Registered subclass: {cls.__name__}", obj=cls)

    @classmethod
    def read_config_dat(cls, data_source_file="config.json"):
        logger.debug(f"Reading config from: {data_source_file}")
        with open(data_source_file, "r", encoding="utf-8") as f:
            config_data = json.load(f, object_pairs_hook=SmartDict)

        for section, class_defs in config_data.items():
            master_config[section] = []
            for class_def in class_defs:
                name_key = next((k for k in class_def if k.endswith("ClassName")), None)
                class_name = class_def[name_key]
                base_class_name = class_def.pop("SubOf", "ImportedClass")
                base_class = master_config[CLASS_REGISTRY].get(base_class_name)
                new_class = type(class_name, (base_class,), class_def)
                master_config[section].append(new_class)
                logger.debug(f"Created class: {class_name} (base: {base_class_name})", obj=new_class)


# === Base Citation Class ===

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
        for regex in cls.regexes:
            try:
                matches = re.findall(regex, text)
                for match in matches:
                    if isinstance(match, str):
                        match = (match,)
                    results.append(cls(match))
            except Exception as e:
                logger.error(f"Regex error in {cls.__name__}: {e}", obj=cls)
        return results

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self._raw_text}>"

    def lookup_courtlistener(self):
        if not self.lookup or not self.lookup.get("supported", True):
            return {"status": "unsupported", "reason": "Lookup not supported for this citation type."}

        url = self.lookup["url"]
        token = os.getenv(self.lookup["EnvKeyName"])
        if not token:
            return {"status": "error", "reason": f"Missing API token in env var {self.lookup['EnvKeyName']}"}

        payload = {field: self._normalized[field] for field in self.lookup["ExpectedFields"]}
        headers = {"Authorization": f"Token {token}"}

        try:
            response = requests.post(url, data=payload, headers=headers, timeout=10)
            result = response.json()
            return {
                "status_code": response.status_code,
                "result": result,
                "matched": response.status_code == 200
            }
        except Exception as e:
            return {"status": "error", "reason": str(e)}


# === Initialization ===

def master_init():
    ImportedClass.read_config_dat()
    logger.info("Citation engine initialized.")


# === Utility ===

def normalize_text(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii"))


def scan_text_for_citations(text):
    results = []
    for CitationType in master_config.get("CitationClasses", []):
        found = CitationType.collect_instances(text)
        results.extend(found)
    return results


# === Test Routines ===

def validate_unit_test_citations(file_path):
    logger.info(f"Validating citations from: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_section = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            if "GOOD" in line:
                current_section = "GOOD"
            elif "BAD" in line:
                current_section = "BAD"
            continue

        normalized = normalize_text(line)
        matches = scan_text_for_citations(normalized)

        if not matches:
            logger.warning(f"❌ No match found: {line}")
            if current_section == "GOOD":
                logger.error(f"❌ Expected GOOD match but found none: {line}")
            continue

        for match in matches:
            logger.info(f"✅ Matched: {match}", obj=match)
            result = match.lookup_courtlistener()
            if result.get("matched"):
                logger.info(f"🔎 Lookup success: {match}", obj=match)
            else:
                logger.warning(f"❌ Lookup failed: {match} — {result}", obj=match)
                if current_section == "GOOD":
                    logger.error(f"❌ Expected GOOD match to validate but it failed: {match}", obj=match)
                if current_section == "BAD":
                    logger.info(f"✅ BAD match correctly failed validation: {match}", obj=match)


def scan_filing_for_citations(file_path):
    logger.info(f"Scanning legal filing: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    normalized = normalize_text(text)
    matches = scan_text_for_citations(normalized)

    if not matches:
        logger.warning("No citations found in filing.")
    else:
        for match in matches:
            logger.info(f"📌 Found citation: {match}", obj=match)
            result = match.lookup_courtlistener()
            if result.get("matched"):
                logger.info(f"🔎 Lookup success: {match}", obj=match)
            else:
                logger.warning(f"❌ Lookup failed: {match} — {result}", obj=match)


# === Entry Point ===

if __name__ == "__main__":
    master_init()
    validate_unit_test_citations("UnitTestCitations.txt")
    scan_filing_for_citations("UnitTestFilingWithInvalidCitations.txt")
