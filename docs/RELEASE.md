# Private review draft — 23 October 2026

Status: prepared for review in a private repository. Making it public requires
the owner's explicit approval. No public release has been authorized.

## What is included

- The four adapted collection stages, a journal-selecting runner, saved-response
  replay, an offline synthetic demo and a read-only output audit.
- A versioned 55-title registry: 24 UTD24 members, 50 members of each dated FT50
  list, historical removals and an optional out-of-list example. Evidence status
  distinguishes demonstrated, configured-only, snapshot-only and unsupported routes.
- Journal-by-journal observed source contributions and limitations, a complete
  tool-family inventory, practical reading instructions and a compatible review template.
- Neutral Git author metadata, synthetic examples, ignored local run directories,
  an MIT code license and provider/method attribution.

The management-focused historical evidence covers 21 journals; 19 are in the
current list union. The full catalog has not been collected end to end in this
release. The original corpus and its private history are not distributed.

## Verification scope

All **22 automated tests passed under Python 3.12.7**. The synthetic tests exercise extraction, source precedence, duplicate
decisions, missing and short text, review overrides, wrong-DOI candidates, failure
handling and offline replay. The demo produced 12 records, nine retained papers,
six populated text fields and five fields of at least 30 words. Its output audit
reported no errors or warnings.

The final file scan found no known private identities, private repository links,
local machine paths, access-token patterns or copied session identifiers. Relative
documentation links and Python syntax passed. This is a bounded release check,
not a guarantee against identification from external information.

Small live API checks on 23 October 2026 succeeded for a Crossref journal query
and an OpenAlex DOI lookup. The anonymous Semantic Scholar batch probe returned
HTTP 429 (rate limited); a new successful live Semantic Scholar retrieval is not
claimed. Its response parsing and fallback behavior are exercised offline.

Current source-corpus tables were also checked read-only using the portable audit:
all 22 folders had zero consistency errors. The inactive snapshot's three warnings
identify its missing enrichment/gap caches. This checks file consistency; it does
not reproduce the private content review or certify every abstract.

UTD membership was verified against its indexed official list. Current FT50
membership is institutionally corroborated because the official current shortlink
was unavailable. This is disclosed in the journal catalog. The primary Crossref
journal identifiers were checked for the 54 supported titles; that check is not a
full collection test.

## What remains and where to resume

Review the [README](../README.md), [journal evidence](EVIDENCE.md), and
[privacy boundaries](PRIVACY.md). The owning GitHub account remains visible by
design; files and Git author fields use a neutral project identity.

After explicit approval, update the draft-status text and change this repository's
visibility to public. Until then, keep the repository private. For continued
development, run the offline tests, use a new output directory for a new live
snapshot, and keep harvested data outside tracked files.
