# Reading and recording decisions

Read the full saved candidate text before calling it an abstract. Provider fields
can contain article openings, adjacent articles, book reviews, citation strings or
other material. The screen catches some of these cases; it is not a substitute for
reading. A passing audit verifies selected file relationships, not universal
content accuracy.

## A practical pass

1. Keep the initial `records.csv`, `abstract_gaps.csv` and source responses in a
   separate run snapshot before changing decisions. Record which population you
   are reviewing. If sampling, save the pool, seed, draw order and membership so
   the result remains interpretable after corrections.
2. Inspect duplicate candidates and item kinds using the titles, authors, issue,
   pages and available source evidence. Mark a duplicate only when the records
   represent the same item. A repeated column title across issues can describe
   distinct printed items. Point the second registration directly to a retained
   record, with a concrete reason.
3. Read saved abstract candidates in full with the corresponding article title,
   DOI and source. Inspect flagged candidates, short-text replacements and any
   weak identity matches. Record `abstract`, `not abstract` or `uncertain` and a
   reason grounded in the text. Keep uncertainty visible when identity or the
   summary/opening boundary cannot be resolved from the evidence.
4. Put actionable decisions in `data/<slug>/review.json`, using the schema below.
   Rebuild metadata after duplicate/kind changes, then rerun enrichment as needed
   and the fill stage using saved responses. Rebuild references and combined
   outputs when those are part of your run. An offline rerun should stop or report
   missing cached evidence rather than silently fabricate it.
5. Inspect the resulting field changes and run the output audit. Report how much
   was read, what remains unread or uncertain, and the source-specific missingness.
   Keep prior readings and their original denominators; do not recalculate a
   pre-correction error rate on the corrected population.

The original bounded reading practice used a saved random sample of up to 30 fills
and all flagged cases up to 50, otherwise a seeded sample of 50 flagged cases. Some
journals added targeted reading, and one later campaign read every remaining
retained fill. These describe the methods used, not a universal sufficient sample
size. A sample result describes that sample; a deliberately selected flagged or
stratified set does not estimate the overall error rate. A census of one source
population does not certify Crossref fields or other journals outside that scope.

An abstract should summarize the corresponding work. A theoretical abstract need
not contain empirical methods or results. A citation, first-person wording,
historical publication year or unusual length does not settle the decision. Clear
article openings, bibliographies, reviews/notices, unrelated material and summaries
contaminated by body text warrant rejection. If accepting an indexer synopsis or
source-truncated preview, state that policy and preserve the source text exactly.
Do not silently rewrite, complete or trim an abstract.

## The file consumed by the scripts

Start from [examples/review.json](../examples/review.json), which contains four
empty maps. DOIs are lowercase strings matching the journal's saved records.
These are the actual fields the collection scripts read:

| Map | Key and value | Effect |
| --- | --- | --- |
| `duplicates` | Second DOI → `{"kept": "retained DOI", "note": "reason"}` | Preserves both records; excludes the second registration from paper counts and maps it to the kept record |
| `kinds` | DOI → `{"kind": "item kind", "note": "reason"}` | Replaces the title-based guess during metadata rebuild |
| `abstract_rejections` | DOI → `{"note": "reason"}` | Prevents a fallback fill for that DOI; an original short Crossref text is retained |
| `abstract_accepts` | DOI → `{"source": "openalex", "note": "reason"}` (or source `semanticscholar`) | Allows that source's flagged candidate after reading; the minimum 30-word fill rule still applies |

A rejection applies to the DOI, not only the source mentioned in its note. It does
not remove a deposited Crossref abstract. An acceptance only clears screening
flags for its named source; it does not force that source over an earlier eligible
source. Do not give a DOI both a rejection and an acceptance. These distinctions
matter when editing a prior decision or when upstream sources change.

Item kinds treated as front matter or other non-papers are `author_bios`,
`front_back_matter`, `call`, `index`, `correction`, `reviewer_list`, `test_record`,
`retraction` and `book_review`. Automatic fallback filling applies to `article`,
`perspective`, `crossroads`, `commentary` and `editorial`. Counts and filling therefore
have related but distinct rules; do not invent a new kind without examining both.

Uncertainty is not a supported action in `review.json`. Save it in your reading
ledger and describe the resulting treatment explicitly. The original census kept
unresolved texts unchanged and reported them separately from confirmed abstracts.

## A reading ledger

The ledger preserves evidence about decisions; the collection scripts do not read
it. A compact JSON object for each DOI can follow this shape, using your actual
saved text and its SHA-256 hash:

```json
{
  "doi": "10.0000/synthetic-example",
  "source": "openalex",
  "text_sha256": "replace-with-hash-of-complete-saved-text",
  "membership": ["random fill"],
  "verdict": "uncertain",
  "category": "summary-opening-boundary",
  "note": "Replace with concrete reasoning after reading the entire candidate.",
  "evidence_excerpt": "Replace with a short exact excerpt from the saved text.",
  "read_full_text": false
}
```

This is a synthetic, deliberately unfinished template. Set `read_full_text` to
`true` only after reading the complete text. Preserve complete candidate texts in
the local evidence snapshot, not in a public example. An excerpt should be short
and sufficient to support the reason. Ledger checks can require one decision per
assigned DOI, matching hashes, exact excerpt membership and valid verdicts. They
cannot verify that reading occurred or determine whether the verdict is correct.

When reporting coverage, distinguish all records from retained papers; populated
fields from fields of at least 30 words; Crossref from each fallback source; read
from unread; and confirmed from uncertain. `no abstract found` means none was
available in the checked saved sources, not that no abstract exists anywhere.

Method credit: the original Claude Code abstract-reading approach and subsequent
Codex source checks, complete-text reading ledgers and rebuild validation. Content
credit remains with article authors, depositors, Crossref, OpenAlex and Semantic
Scholar. These procedures support transparent decisions; they provide no universal
proof of content correctness or publisher coverage.
