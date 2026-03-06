# Legal Citation Checker

Scans legal documents for citations, validates them against CourtListener, and detects hallucinated or incorrect citations.

Test case: the *Mata v. Avianca* filing, where ChatGPT-generated citations got an attorney sanctioned. The tool correctly flags all citations in that document as invalid.

---

## Requirements

- Python 3.11+
- `pip install requests`
- CourtListener API token → set `COURTLISTENER_KEY` env var
  - Free account at [courtlistener.com](https://www.courtlistener.com)

---

## Usage

**Scan a document:**
```
python legalcheck.py <filename>
```

**Run unit tests:**
```
python legalcheck.py --selftest
python legalcheck.py --selftest <custom_test_file>
```

**POC2 (AI usage analysis — work in progress):**
```
python legalcheck2.py <filename>
```

**Run both (batch):**
```
testit.bat
```

---

## Output

```
✅  citation found and case name matches
❌  citation not found, or coordinates exist but wrong case
⚪  citation type not supported for lookup (e.g. WL citations)
```

On mismatch, the found case is shown:
```
❌ <CaseCitation: ('Petersen v. Iran Air', '905', 'F. Supp. 2d', '121')>  (found: United States of America v. Iss Marine Services, Inc.)
```

---

## Files

| File | Purpose |
|------|---------|
| `legalcheck.py` | POC1 CLI — scan and validate |
| `legalcheck2.py` | POC2 CLI — scan + AI usage analysis (WIP) |
| `citation_engine.py` | Shared library — citation detection, CourtListener lookup |
| `config.json` | Citation type definitions (regexes, lookup config) |
| `amm_diagnostics.py` | Logging utility (SmartDict, contextual logger) |
| `UnitTestCitations.txt` | Unit test data — GOOD and BAD citation examples |
| `UnitTestFilingWithInvalidCitations.txt` | The Mata v. Avianca hallucinated filing |
| `testit.bat` | Runs both tools for quick validation |

Verbose logs are written to `legalcheck.log` / `legalcheck2.log`.

---

## Architecture

```
legalcheck.py / legalcheck2.py
        |
        v
citation_engine.py
  - ImportedClass: config-driven dynamic class loader
  - BaseCitation: regex matching, CourtListener lookup, fuzzy case name check
  - scan(text): runs all citation types against a document
  - normalize(text): Unicode normalization + whitespace cleanup
        |
        v
config.json
  - CaseCitation: comprehensive regex covering federal, SCOTUS, regional,
                  and state-specific reporters (50+ reporter types)
  - IllinoisAppCitation: IL App (year) (district) (number) format
  - UnsupportedCitation: Westlaw WL citations (detected, not validated)
        |
        v
CourtListener API  (courtlistener.com/api/rest/v4/citation-lookup/)
  - Validates citation by volume + reporter + page
  - Returns matched case; tool fuzzy-matches case name against searched name
  - 5,000 req/hour with free token
```

---

## Citation Types Covered

**Federal courts:**
F., F.2d, F.3d, F.4th, F. Supp., F. Supp. 2d, F. Supp. 3d, F. App'x, Fed. Appx.

**SCOTUS:**
U.S., S. Ct., L. Ed. 2d

**Specialty:**
B.R. (Bankruptcy), T.C. (Tax Court), Vet. App., Fed. Cl.

**Regional reporters (all series):**
A., A.2d, A.3d, P., P.2d, P.3d, S.W., S.W.2d, S.W.3d,
S.E., S.E.2d, N.W., N.W.2d, N.E., N.E.2d, N.E.3d, So., So.2d, So.3d

**State-specific:**
N.Y., N.Y.2d, N.Y.3d, Cal., Cal.2d–5th, Cal. App., Ill., Ill.2d,
Tex., Pa., Fla., Ohio St., Mich., Ga., Mass., N.J., Md., Mo., Ind.,
Wis., Minn., Kan., Neb., Or., Colo., Conn., Ala., Miss., Ark., Okla.,
S.C., N.C., Tenn., Ky., La., W. Va., Del., Ariz., Nev., Utah, Mont.,
Wyo., N.D., S.D., Idaho, N.M., Haw., Alaska, R.I., Vt., Me., N.H.

**Detected but not validated (unsupported):**
WL (Westlaw)

**Known gaps:**
- U.S. reporter (SCOTUS) for recent terms (~2010–present): use S. Ct. cite instead — see issue #8
- IllinoisAppCitation lookup not reliable via CourtListener structured endpoint
- Rate limiting: rapid bulk scans may see intermittent failures — see issue #9

---

## How Validation Works

1. Citation regex extracts: `case_name`, `volume`, `reporter`, `page`
2. POST to CourtListener `/api/rest/v4/citation-lookup/` with those fields
3. Response is HTTP 200 always; check nested `status` field and `clusters` array
4. If clusters non-empty: fuzzy-compare returned `case_name` against searched name
   - Similarity ≥ 0.6 → valid
   - Similarity < 0.6 → mismatch (coordinates exist, wrong case)
   - No clusters → not found

---

## POC2 Plan

See [GitHub issue #5](https://github.com/akienm/oldskoolengineering/issues/5).

For each valid citation: fetch opinion text from CourtListener, extract the holding,
compare against how the attorney used the citation in context, send to LLM via
OpenRouter for verdict (valid / suspect / hallucinated) + one-sentence reason.
