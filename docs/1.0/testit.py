
from collections import OrderedDict
import re
import unicodedata

import json
import os

master_config = {}

class ImportedClass:
    @classmethod
    def read_config_dat(cls, data_source_file=None):

        if not data_source_file:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_source_file = os.path.join(script_dir, "config.dat")

        with open(data_source_file, "r", encoding="utf-8") as f:
            config_data = json.load(f, object_pairs_hook=OrderedDict)

        global master_config
        master_config = {}

        for section in config_data:
            for category_name, class_defs in section.items():
                master_config[category_name] = []

                for class_def in class_defs:
                    class_fields = class_def.copy()

                    # Determine class name
                    name_key = next((k for k in class_fields if k.endswith("ClassName")), None)
                    if not name_key:
                        raise ValueError(f"No class name key found in {class_fields}")
                    class_name = class_fields.pop(name_key)

                    # Determine base class
                    base_class_name = class_fields.pop("SubOf", "ImportedClass")
                    base_class = BASE_CLASS_REGISTRY.get(base_class_name)
                    if not base_class:
                        raise ValueError(f"Unknown base class: {base_class_name}")

                    # Create the class
                    new_class = type(class_name, (base_class,), class_fields)
                    master_config[category_name].append(new_class)

class BaseLookup(ImportedClass):
    pass

class BaseCitation(ImportedClass):

    # Here to define the workings, but overridden in _init_
    exists = None
    initializing_match = None
    match_fields = None
    normalizing_fields = None
    regex = None

    _matches_found = None
    _normalized = None
    _raw_text = None
    
    @classmethod
    def test_text(cls, text):
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
        self._normalized = OrderedDict()
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
        raise NotImplementedError

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self._raw_text}>"

BASE_CLASS_REGISTRY = {
    "ImportedClass": ImportedClass,
    "CitationTypeBase": BaseCitation,
    "LookupProviderBase": BaseLookup,
    # Add more as needed
}

CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST = ['case_name', 'volume', 'reporter', 'page']



class FederalCaseCitation(BaseCitation):
    regex = r"\*?([\w\s.,&'()\-]+? v\. [\w\s.,&'()\-]+?)\*?, (\d+) (F\.(?:2d|3d|4th)) (\d+)"
    # regex = r"\b([\w\s.,&'()\-]+? v\. [\w\s.,&'()\-]+?), (\d+) (F\.(?:2d|3d|4th)) (\d+)"
    # regex = r"\b([A-Z][\w\s.,&'()\-]+? v\. [A-Z][\w\s.,&'()\-]+?), (\d+) (F\.(?:2d|3d|4th)) (\d+)"
    # regex = r"\b([A-Z][\w&'().\-]+(?: [\w&'().\-]+)* v\. [A-Z][\w&'().\-]+(?: [\w&'().\-]+)*), (\d+) (F\.(?:2d|3d|4th)) (\d+)"
    match_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]
    normalizing_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]

class DistrictCourtCitation(BaseCitation):
    regex = r"\*?([\w\s.,&'()\-]+? v\. [\w\s.,&'()\-]+?)\*?, (\d+) (F\. Supp\. 2d) (\d+)"
    match_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]
    normalizing_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]
    
class WestlawCitation(BaseCitation):
    regex = r"(\d{4}) WL (\d+)"
    match_fields = ['year', 'wl_number']
    normalizing_fields = ['year', 'wl_number']

class StateAppellateCitation(BaseCitation):
    regex = r"\*?([\w\s.,&'()\-]+? v\. [\w\s.,&'()\-]+?)\*?, (\d{4}) IL App \((\d+[a-z]*)\) (\d+[-U]*)"
    match_fields = ['case_name', 'year', 'district', 'case_number']
    normalizing_fields = ['case_name', 'year', 'jurisdiction', 'case_number']

class StateCourtCitation(BaseCitation):
    regex = r"\*?([\w\s.,&'()\-]+? v\. [\w\s.,&'()\-]+?)\*?, (\d{4}) ([A-Z][a-z]+\.) App\. ?,? ([A-Za-z]+\. \d{1,2}, \d{4})"
    match_fields = ['case_name', 'year', 'court', 'date']
    normalizing_fields = ['case_name', 'year', 'court', 'date']

class SupremeCourtCitation(BaseCitation):
    regex = r"\*?([\w\s.,&'()\-]+? v\. [\w\s.,&'()\-]+?)\*?, (\d+) (U\.S\.) (\d+)"
    match_fields = ['case_name', 'volume', 'reporter', 'page']
    normalizing_fields = ['case_name', 'volume', 'reporter', 'page']
    
class FederalSupplementCitation(BaseCitation):
    regex = r"\*?([\w\s.,&'()\-]+? v\. [\w\s.,&'()\-]+?)\*?, (\d+) (F\. Supp\.) (\d+)"
    match_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]
    normalizing_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]

class BankruptcyCitation(BaseCitation):
    regex = r"\*?([\w\s.,&'()\-]+? v\. [\w\s.,&'()\-]+?)\*?, (\d+) (B\.R\.) (\d+)\b"
    match_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]
    normalizing_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]

class RegionalReporterCitation(BaseCitation):
    regex = r"\*?([\w\s.,&'()\-]+? v\. [\w\s.,&'()\-]+?)\*?, (\d+) ([A-Z]\.3d) (\d+)"
    match_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]
    normalizing_fields = CASE_NAME_VOLUME_REPORTER_PAGE_FIELD_LIST[:]

list_of_types_to_test_for = [
    FederalCaseCitation,
#    DistrictCourtCitation,
#    WestlawCitation,
#    StateAppellateCitation,
#    StateCourtCitation,
#    SupremeCourtCitation,
#    FederalSupplementCitation,
#    BankruptcyCitation,
#    RegionalReporterCitation,
]

ImportedClass.read_config_dat()

# Path to the test file
testfile = './testdata.txt'
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

if True:
    for CitationType in master_config["CitationTypes"]:
        print(f'{CitationType.__name__} regex="{CitationType.regex}"')
        results = CitationType.test_text(text)
        if results:
            for item in results:
                result_text += f"{CitationType.__name__} Match: {item}\n"
                print(f'FOUND {item}')
        else:
            print(f'NO FINDS ON regex={regex}')
        result_text += '-----------------\n'
