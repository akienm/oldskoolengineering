
from collections import OrderedDict
import re
import unicodedata

import json
import os

CLASS_REGISTRY = "class_registry"
master_config = {
   CLASS_REGISTRY : {}
}

class ImportedClass:

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        registry = master_config[CLASS_REGISTRY]
        if cls.__name__ not in registry:
            registry[cls.__name__] = cls

    @classmethod
    def read_config_dat(cls, data_source_file=None):
        global master_config

        if not data_source_file:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_source_file = os.path.join(script_dir, "config.dat")

        try:
            with open(data_source_file, "r", encoding="utf-8") as f:
                config_data = json.load(f, object_pairs_hook=OrderedDict)
        except Exception as e: 
            print(e)
            import pdb ; pdb.set_trace()

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



# read the config
ImportedClass.read_config_dat()
# master_config is now set, has loaded CitationClasses and LookupClasses

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
    for CitationType in master_config["CitationClasses"]:
        print(f'{CitationType}')
        results = CitationType.test_text(text)
        if results:
            for item in results:
                result_text += f"{CitationType} Match: {item}\n"
                print(f'FOUND {item}')
        else:
            print(f'NO FINDS ON regex={regex}')
        result_text += '-----------------\n'
