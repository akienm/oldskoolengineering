@echo off
echo -----------------------------------------------------------------
python legalcheck.py --selftest
echo -----------------------------------------------------------------
python legalcheck2.py UnitTestFilingWithInvalidCitations.txt
echo -----------------------------------------------------------------
