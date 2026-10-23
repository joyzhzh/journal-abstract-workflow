# Independent review — 23 October 2026

Three separate reviewers examined privacy, failure behavior and real saved-response
replay. They did not implement the fixes they reviewed. The review took place
while the repository was private; the owner subsequently approved public release.

The reviewers rechecked the fixes, including the additional recovery issue found
during recheck. No unresolved actionable finding remained within the tested scope.

## Findings and changes

| Finding | Change | Regression evidence |
|---|---|---|
| Malformed API keys could appear in HTTP validation errors | Reject malformed keys before a request and suppress sensitive transport exception details | Synthetic newline, control-character and non-ASCII keys; forced transport exceptions |
| Redirects could forward credentials to another host or plain HTTP | Refuse redirects that change host, port or scheme | Both credential providers tested against host changes, HTTPS downgrade and port changes; same-origin HTTPS remains usable |
| Semantic Scholar error objects could be cached as permanent missing-abstract evidence | Validate new and saved paper projections, retry invalid entries, retain valid siblings and archive pre-repair cache bytes | Error objects, malformed fields, partial batches, cache repair and audit regressions |
| A failed rerun could overwrite completed journal tables while leaving old combined files | Snapshot derived outputs; restore them on failure and retain incomplete attempts | First-run failure, failed rerun, abandoned-run recovery and active-process checks |
| Combined output could include journals omitted from its manifest, or silently omit journals removed from the registry | Record the full combined population and hashes; reject a registry that omits existing journal outputs | Incremental two-journal collection and registry-omission regression |
| Existing reference tables could remain stale after a rerun without the optional switch | Rebuild an existing reference table whenever its journal is rebuilt | Changed duplicate target without `--references` |
| Malformed OpenAlex cache entries and conflicting review decisions were accepted | Retry invalid lookups; reject contradictory accept/reject decisions | Invalid `ok/null` cache repair and conflicting-decision regressions |
| The first recovery fix could roll back review decisions edited after a crash | Limit restoration to generated files; preserve authored reviews and notes in place | New post-crash review decision and reading note survive recovery and affect the next result |

No known private identities, machine paths, real credentials, copied session records
or harvested abstracts were found in the release files or available Git history.
Author and committer fields use a neutral project identity. The owning GitHub
account and platform activity remain visible, as explained in
[privacy boundaries](PRIVACY.md).

## What was exercised

The automated suite has **42 passing tests on Python 3.12.7**, including the new
failure and privacy regressions. The synthetic offline demo exercises collection,
enrichment, short-text handling, screening, explicit decisions, duplicates,
references and replay. Its audit has zero errors and warnings.

A separate real-data replay rebuilt all **21 historically demonstrated journals**
from saved provider responses and review decisions: **84,446 records**, with every
journal's `records.csv` byte-identical to its frozen source table. The combined
table equals the union of those journal tables. The output audit reported **zero
errors and warnings**. This reproduced 30 replacements of short Crossref texts,
869 retained short texts and the saved review decisions. Gap-table wording changed
for 2,204 rejection labels; review notes and resulting abstracts were unchanged.
The original source corpus was not modified.

The post-fix full replay and a subsequent single-journal rerun also verified that
both manifests covered all 21 journals in the combined table. All recorded source,
review and derived-file hashes matched, and the final manifest's tool hashes matched
the corrected scripts.

A bounded live check used the production transport and stages for one real DOI:
Crossref parsing, OpenAlex enrichment and abstract filling succeeded. Semantic
Scholar returned **HTTP 429**. There is no claim of a fresh successful live Semantic
Scholar batch or a new full-journal live harvest.

## Limits and reproducibility

The public offline demo and tests are reproducible from this repository alone:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/demo.py --output runs/review-demo
python3 scripts/audit_outputs.py runs/review-demo
```

Use a fresh demo directory. Detailed real-data inputs, review ledgers and review
logs remain private; this repository contains the methods and aggregate results,
not that corpus. The private replay establishes software consistency against those
saved inputs, not publisher completeness or independent correctness of each
abstract. Reference behavior was tested with synthetic cases; reference fidelity
across all 21 journals was not revalidated. The full 55-title registry has not had
an end-to-end collection test. Provider access and quotas can change.

Older Semantic Scholar responses lacking a returned DOI remain associated with
the DOI requested. This preserves historical compatibility and requires care when
reviewing identity. Automated screening and cache validation do not replace
reading the candidate text and checking the article.
