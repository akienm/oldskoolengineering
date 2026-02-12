
from collections import OrderedDict
from pprint import pprint as pp

import json
import logging
import os
import re
import requests
import sys
import unicodedata


def setup_logging():
    # Get the base name of the script (e.g., testit.py → testit.log)
    script_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    log_filename = f"{script_name}.log"

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture everything

    # File handler (DEBUG and above)
    file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler.setFormatter(file_formatter)

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

setup_logging()



unit_test_citations = '.\\UnitTestCitations.txt'
unit_test_filing_with_invalid_citations = '.\\UnitTestFilingWithInvalidCitations.txt'

CLASS_REGISTRY = "CLASS_REGISTRY"
class SmartDict(OrderedDict):
    def show():
        pp(self.__dict__)

master_config = SmartDict()
master_config[CLASS_REGISTRY] = SmartDict()


class ImportedClass:

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        global master_config
        my_name = cls.__name__
        registry = master_config[CLASS_REGISTRY]
        if my_name not in registry:
            registry[my_name] = cls

    @classmethod
    def read_config_dat(cls, data_source_file=None):
        global master_config

        if not data_source_file:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_source_file = os.path.join(script_dir, "config.dat")

        try:
            with open(data_source_file, "r", encoding="utf-8") as f:
                config_data = json.load(f, object_pairs_hook=SmartDict)
        except Exception as e:
            print(e)

        for section in config_data:
            for category_name, class_defs in section.items():
                master_config[category_name] = []

                for class_def in class_defs:
                    class_fields = class_def.copy()

                    # Determine class name
                    name_key = next((k for k in class_fields if k.endswith("ClassName")), None)
                    if not name_key:
                        raise ValueError(f"No class name key found in {class_fields}")
                    class_name = class_fields[name_key]

                    # Determine base class
                    base_class_name = class_fields.pop("SubOf", "ImportedClass")
                    base_class = master_config[CLASS_REGISTRY].get(base_class_name, None)

                    if not base_class:
                        raise ValueError(f"Unknown base class: {base_class_name}")

                    # Create the class
                    new_class = type(class_name, (base_class,), class_fields)
                    master_config[category_name].append(new_class)

class BaseLookup(ImportedClass):
    key = None

    def __init__(self, citation_instance):
        self.citation = citation_instance

    def lookup(self):
        if not self.__class__.key:
            self.__class__.key = os.getenv(self.EnvKeyName, None)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Token {self.__class__.key}"
        }
        # TODO: PROTOTYPE CODE - FIX THIS!
        data = SmartDict()
        data['text'] = self.citation.case_name
        # data['reporter'] = ""
        data["volume"] = self.citation.volume
        data["page"] = self.citation.page

        self.response = requests.post(self.url, json=data, headers=headers)
        print(f'/n{self.response._content}\n\n')

        if self.response.status_code == 200:
            self.lookup_result = "✅"
        else:
            self.lookup_result = "❌"
        return self.lookup_result

class BaseCitation(ImportedClass):

    lookup_engine = None # this one is a class variable

    # Here to define the workings, but overridden in _init_
    exists = None
    initializing_match = None
    match_fields = None
    normalizing_fields = None
    regex = None

    # Private members
    _matches_found = None
    _normalized = None
    _raw_text = None

    @classmethod
    def collect_instances(cls, text):
        # This method will return a list of citation class instances for this class
        matches = re.findall(cls.regex, text)
        results = []
        for match in matches:
            if isinstance(match, str):
                match = (match,)
            new_instance = cls(match=match)
            results.append(new_instance)
        return results

    def __init__(self, match=None, match_fields=None, normalizing_fields=None, regex=None):
        # make everybody instance data
        self.exists = type(self).exists
        self.initializing_match = type(self).initializing_match
        self.match_fields = type(self).match_fields
        self.normalizing_fields = type(self).normalizing_fields
        self.regex = type(self).regex
        self._matches_found = type(self)._matches_found
        self._normalized = type(self)._normalized
        self._raw_text = type(self)._raw_text

        # now let's check our args
        if regex:
            self.regex = regex
        if normalizing_fields:
            self.normalizing_fields = normalizing_fields
        if match_fields:
            self.match_fields = match_fields
        self.initializing_match = match

        # check status before continuing
        if not self.initializing_match:
            raise NotImplementedError("No match defined, TODO: this will go away")

        if not self.match_fields:
            raise NotImplementedError("No match_fields defined")
        if not self.normalizing_fields:
            raise NotImplementedError("No normalizing_fields defined")

        #print(f'self.__class__.__name__ = {self.__class__.__name__}')
        #print(f'self.initializing_match = {self.initializing_match}')
        #print(f'self.match_fields = {self.match_fields}')
        #print(f'self.normalization_fields = {self.match_fields}')

        # now we can assume we got the match record, extract it's data
        # and apply it as properties of the object
        for index in range(0, len(self.match_fields)):
            name = self.match_fields[index]
            setattr(self, name, self.initializing_match[index])
            #print(f'{name} = {self.initializing_match[index]}')
        self._raw_text = f'{self.initializing_match}'

    @property
    def normalized(self):
        if self._normalized:
            return self._normalized
        self._normalized = SmartDict()
        # This could be shorter, but not more readable ;)
        for index in range(0, len(self.normalizing_fields)):
            match_field_name = self.match_fields[index]
            match_field_value = getattr(self, match_field_name)
            normalized_key_name = self.normalizing_fields[index]
            self.normalized[normalized_key_name] = match_field_value
        return self._normalized

    @property
    def raw_text(self):
        return self._raw_text

    def lookup(self):
        if not self.lookup_engine:
            for LookupClass in master_config["LookupClasses"]:
                if self.normalizing_fields == LookupClass.ExpectedFields:
                    # now give us an instance all members of the
                    # class will share... can you say single login?
                    self.__class__.lookup_engine = LookupClass(self)
                    break
        if self.lookup_engine:
            return self.lookup_engine.lookup()

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self._raw_text}>"

# "CitationClassName": "FederalCaseCitation",
# "SubOf": "BaseCitation",
# "regex": "\\*?([\\w\\s.,&'()\\-]+? v\\. [\\w\\s.,&'()\\-]+?)\\*?, (\\d+) (F\\.(?:2d|3d|4th)) (\\d+)",
# "match_fields": ["case_name", "volume", "reporter", "page"],
# "normalizing_fields": ["case_name", "volume", "reporter", "page"]

# master init
def master_init():
    # read the config
    ImportedClass.read_config_dat()
    # master_config is now set, has loaded CitationClasses and LookupClasses
    # print(master_config)
    master_config.current_lookup_class = master_config["LookupClasses"][0]
master_init()

def scan_file_test():
    # Path to the test file
    testfile = unit_test_filing_with_invalid_citations
    print('\n' * 20)
    print('----------' * 6)
    print('')
    print(f'Testing file: {testfile}')

    # Read the test file
    with open(testfile, "r", encoding="utf-8") as f:
        text = f.read()

    # normalize it
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r'\s+', ' ', text)

    # and start the scan:
    print(f'Testing file: Read and filter complete. Length {len(text)}')
    print('')
    print('Now processing file...')
    print('-----------------')
    result_text = ''

    for CitationType in master_config["CitationClasses"]:
        # print((f':::{CitationType.CitationClassName}'+('-'*80))[:80])

        found_citation_instances = CitationType.collect_instances(text)
        if found_citation_instances:
            for current_citation in found_citation_instances:
                result_text += f"✅ {CitationType} Match: {current_citation}\n"
        else:
            result_text += f'❌ {CitationType}:{current_citation}'
        result_text += '-----------------\n'
    print(result_text)


def lookup_citation(citation):
    url = "https://www.courtlistener.com/api/rest/v3/search/"
    params = {
        "q": citation,
    }
    headers = {
        "Accept": "application/json"
    }

    # Optional: include token if available
    token = os.getenv('COURTLISTENER_KEY')
    if token:
        headers["Authorization"] = f"Token {token}"

    logging.debug(f'url={url}')
    logging.debug(f'params={params}')
    logging.debug(f'headers={headers}')
    logging.debug('GETTING...')

    try:
        response = requests.get(url, params=params, headers=headers)
        logging.debug("Response Details:")
        logging.debug(f"  Status Code: {response.status_code}")
        logging.debug(f"  Headers: {response.headers}")
        logging.debug(f"  Encoding: {response.encoding}")

        if response.text.lstrip().lower().startswith("<!doctype html>"):
            logging.debug("  Text: 404 Page HTML")
            return []
        else:
            logging.debug(f"  Text: {response.text[:50]}")
            try:
                json_data = response.json()
                logging.debug(f"  JSON: {json_data}")
                return json_data.get("results", [])
            except Exception as e:
                logging.debug(f"  JSON decode failed: {e}")
                return []
    except requests.RequestException as e:
        logging.error(f"❌ Request failed for '{citation}': {e}")
        return []

def perform_lookup_test():
    filename = unit_test_citations
    with open(filename, 'r', encoding='utf-8') as f:
        file_lines = f.readlines()

    for line in file_lines:
        line = line.strip()
        if not line or line.startswith('#'):
            logging.debug(f'comment: {line}')
            continue

        # Extract the citation string from between the asterisks
        if line.startswith('*') and line.endswith('*'):
            citation_text = line.strip('*').strip()
        else:
            citation_text = line

        logging.info(f"Looking up: {citation_text}")
        result = lookup_citation(citation_text)

        if result:
            logging.info(f"✅ Found: {result[0].get('case_name', 'Unknown')} — {result[0].get('citation', 'No citation')}")
        else:
            logging.error(f"❌ No match found for: {citation_text}")


perform_lookup_test()
