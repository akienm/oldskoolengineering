
"""
Case citation (federal appellate)
([A-Z][A-Za-z0-9.&' ]+ v\. [A-Z][A-Za-z0-9.&' ]+), (\d+) F\.(?:2d|3d) (\d+)

District court (F. Supp.)
([A-Z][A-Za-z0-9.&' ]+ v\. [A-Z][A-Za-z0-9.&' ]+), (\d+) F\. Supp\. ?(?:2d|3d)? (\d+)

Supreme Court
([A-Z][A-Za-z0-9.&' ]+ v\. [A-Z][A-Za-z0-9.&' ]+), (\d+) U\.S\. (\d+)

Statutes
(\d+)\s+U\.S\.C\.\s+§+\s*([\w.-]+)

Regulations
(\d+)\s+C\.F\.R\.\s+§+\s*([\w.-]+)

Slip opinions (WL)
(\d{4})\s+WL\s+(\d+)

Docket numbers
No\.\s+[0-9:.\-A-Za-z]+
"""

import re

# Path to the test file
testfile = './testdata.txt'

# List of regex patterns for different citation types
regex_patterns = [
    # Federal appellate cases
    r"([A-Z][A-Za-z0-9.&' ]+ v\. [A-Z][A-Za-z0-9.&' ]+), (\d+) F\.(?:2d|3d) (\d+)",
    
    # District court (F. Supp.)
    r"([A-Z][A-Za-z0-9.&' ]+ v\. [A-Z][A-Za-z0-9.&' ]+), (\d+) F\. Supp\. ?(?:2d|3d)? (\d+)",
    
    # Supreme Court
    r"([A-Z][A-Za-z0-9.&' ]+ v\. [A-Z][A-Za-z0-9.&' ]+), (\d+) U\.S\. (\d+)",
    
    # Statutes
    r"(\d+)\s+U\.S\.C\.\s+§+\s*([\w.-]+)",
    
    # Regulations
    r"(\d+)\s+C\.F\.R\.\s+§+\s*([\w.-]+)",
    
    # Slip opinions (WL)
    r"(\d{4})\s+WL\s+(\d+)",
    
    # Docket numbers
    r"No\.\s+[0-9:.\-A-Za-z]+"
]

# Read the test file
with open(testfile, 'r', encoding='utf-8') as f:
    text = f.read()

# Apply each regex and print matches
for i, pattern in enumerate(regex_patterns, 1):
    print(f"\nPattern {i}: {pattern}")
    matches = re.findall(pattern, text)
    for match in matches:
        print("  Match:", match)