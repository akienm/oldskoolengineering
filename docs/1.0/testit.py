
from collections import OrderedDict
from pprint import pprint as pp

import json
import os
import re
import requests
import unicodedata

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

def perform_lookup_test():
    filename = unit_test_citations
    with open(filename, 'r', encoding='utf-8') as f:
        file_lines = f.readlines()
    for line in file_lines:
        line = line.strip()
        if not line:
            continue # skip comments and blank lines
        if line[0] == '#':
            continue # skip comments and blank lines
        else:
            # OK so now line has a citation in it wrapdbpped with **
            print(line)

perform_lookup_test()
