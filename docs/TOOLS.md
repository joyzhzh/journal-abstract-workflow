# Tools and their evidence

The four collection scripts below were used in the originating journal corpus. This
toolkit separates those reusable scripts from journal-specific helper programs and
saved decisions. A completed run means that saved inputs can produce inspectable
outputs. It does not mean that every retrieved text is a correct abstract or that
every publisher article is covered.

| Tool | Job | Evidence it leaves | Status here |
| --- | --- | --- | --- |
| `scripts/fetch_journals.py` | Fetch Crossref works for configured print and online ISSNs; deduplicate identical DOIs; derive metadata, title-based item kinds and duplicate candidates; combine journal tables | Raw response pages, `records.jsonl.gz`, `records.csv`, coverage tables, summaries and file hashes | Reusable collection script, adapted for anonymous configuration |
| `scripts/enrich_openalex.py` | Look up each DOI in OpenAlex; reconstruct words from its abstract position index; checkpoint completed lookups and retry missing or failed ones | `works.jsonl.gz` with DOI, status and response; `openalex.csv` | Reusable collection script, with saved responses reused on rerun |
| `scripts/fill_abstract_gaps.py` | Fill absent abstracts and attempt replacement of Crossref texts shorter than 30 words; prefer OpenAlex, then Semantic Scholar; screen candidates and apply explicit reading decisions | Saved Semantic Scholar batches, `abstract_gaps.csv`, source-labelled text fields, updated summary | Reusable collection script; the screen is a flagging aid |
| `scripts/build_references.py` | Use deposited Crossref reference lists, otherwise OpenAlex referenced-work IDs; preserve each citing record and map duplicate registrations to a kept record | `references.csv.gz` and source/decade counts | Reusable optional reference stage |
| `scripts/audit_outputs.py` | Inspect existing CSV consistency, duplicate targets, short-text fields, missing-text reasons and cache lookup status | JSON counts, errors, warnings and available input hashes | New portable extraction of checks used in the corpus validators |
| `scripts/pipeline.py` and `scripts/run_recovery.py` | Select journals, run stages, restore completed tables after a failed attempt, refresh existing references and record the full combined population | `run_manifest.json`, `run_state.json` and retained `.history/` snapshots | Portable orchestration with failure and incremental-run regression tests |

The four collection scripts use Python's standard library. The toolkit's shared
configuration helper supplies portable settings; it is packaging work, not a new
abstract source. Crossref, OpenAlex and Semantic Scholar supply metadata/text;
article authors and metadata depositors remain the sources of that content.
See [review practice](REVIEW.md) for the decisions that automation cannot make.

## Methods used alongside the collection scripts

These families were inspected in the originating workflow. Their methods are
documented here; the original programs and real decision ledgers are not shipped.
They contain journal-specific assumptions, fixed decisions or private project
history, and are not general commands for an arbitrary journal.

| Family and representative helper names | What the workflow did | Reusable method and limit |
| --- | --- | --- |
| Duplicate search: `dup_search.py`, `review_searches.py` | Compared normalized titles; title + issue + first page; authors + title prefixes; out-of-issue versus in-issue records; page overlap; shared long abstracts; shared deposited reference lists; selected DOI spelling patterns | Generate candidate pairs, then inspect identity evidence. A recurring heading, reply, correction or shared page is not automatically a duplicate. The shared fetcher includes a narrower candidate search. |
| Kind review: `review_kinds.py`, `derive_review.py`, `kinds_considered.csv`, `kind_decisions.csv` | Compared guessed item kinds with titles, authors, issue positions, pages and available source text; recorded corrections by DOI | Keep explicit `kinds` overrides with reasons. Short pages or a title keyword alone cannot establish the kind. |
| Reading preparation: `read_fills.py`, `reading_sample.py`, `prepare_reading.py`, `reading_selection.py`, `abstract_reading.py` | Saved pre-decision pools and seeded samples; reconstructed full candidate texts from saved sources; included flagged fills and selected short replacements or weak title matches | Preserve the original pool, seed, membership, complete text and its hash. Selection and display may be scripted; verdicts require reading. |
| Reading decisions: `record_reading.py`, `record_judgments.py`, `save_reading.py`, `reading_verdicts.json`, `fill_reading.csv` | Saved DOI-specific decisions, source, reasons, sample membership and text identity; applied rejects or explicit flagged accepts through `review.json` | Use the compatible empty [review template](../examples/review.json). Keep uncertainty and reading detail in a separate ledger. |
| Rebuild and delta validation: `validate_rebuild.py`, `validate_takeover.py`, `validate_phase2.py`, `validate_delta.py`, `validate_short_crossref_corpus.py` | Rebuilt temporary fixture copies offline; compared repeat output bytes and authorized field changes; checked source preservation, summary/reference counts and original short text | Preserve source inputs; compare declared changes and repeatable outputs. These project scripts are not ported; the supplied audit covers a narrower, explicitly listed set of consistency checks. |
| Full saved-text census: packet preparation, `validate_lane.py`, final judgment ledger | Assigned disjoint complete-text packets; saved abstract / not abstract / uncertain verdicts with concrete notes, short evidence excerpts and text hashes; checked exact coverage and preserved earlier decisions | A ledger can show which text was read and what was decided. Its validator checks coverage, hashes and schema, not whether the judgment is correct. The private assignment and integration machinery is not ported. |
| Release accounting: `account_numbers.py`, `phase2_numbers.py`, `build_source_limits.py`, `verify.py`, `check_combine.py` | Recounted saved outputs; checked reference attribution, combined-table row unions and declared file hashes; kept missingness and source limits visible | Count from current files. The toolkit audit does not replace a complete reference/combined-table or publisher-coverage check. |

The reading method developed through the original Claude Code collection and
abstract-reading work and subsequent Codex review and verification. This toolkit
credits that methodological lineage without publishing contributors' identities,
session records or the private corpus. The journal coverage and evidence available
for a particular run must be stated separately; carrying a journal in a
configuration file is not proof that it was collected or read successfully.

## Source discovery and routes not implemented

The early source exploration compared Crossref's ISSN inventory with OpenAlex
journal-source lists and sampled abstract coverage. One OpenAlex source named
*Organization Science* mixed in a different journal and misfiled working papers.
That observation led to DOI lookups against the Crossref inventory instead of
treating a provider's journal-name match as the article population. Source-list
queries were exploratory; they are not the implemented collection route.

Later journal accounts document OpenAlex and Semantic Scholar HTTP 429 responses
(too many requests), retries and resumed runs. The collection scripts preserve
saved progress and distinguish unsuccessful OpenAlex lookups from a successful
lookup with no abstract. A failed local network attempt is also distinct from a
provider's negative response. Historical quota statements in early working notes
should not be treated as current API terms; check provider documentation for the
environment in which a new run will operate.

Both enrichment stages validate the fields they consume before trusting new or
cached responses. Semantic Scholar batch `null` is an explicit miss; an error
object or malformed projection is a failure to retry. Valid siblings from a mixed
batch remain checkpointed. Before repairing an invalid cache, its exact bytes are
retained in a content-addressed `history/` folder alongside it. Older Semantic
Scholar projections without a returned DOI remain associated with the requested
DOI; that association alone does not verify article identity.

The runner snapshots selected journal tables and combined outputs before rebuilding.
On an exception or ordinary interruption it moves incomplete outputs into the
snapshot and restores the prior tables and manifest. Raw API checkpoints remain
available for the retry. Recovery affects only generated files; authored reviews
and notes remain in place, including edits made after a crash. On POSIX systems,
a later run can recover an abandoned
attempt after checking that its recorded process is gone. Other systems stop on
an abandoned `running` state for manual recovery from the retained snapshot.
These protections require the documented one-process-per-output-directory rule;
they are not a general concurrent database or a backup against disk failure.

The manifest distinguishes requested journals from every journal in the combined
table and hashes their saved inputs, review decisions and derived files. Existing
reference tables are rebuilt with their journal even when `--references` is omitted.
Conflicting accept and reject decisions stop the run for correction.

Publisher pages, printed issues, subscription full texts, Unpaywall and additional
citation APIs were outside the documented saved-source work for the journal
accounts inspected. This toolkit supplies no publisher/JSTOR scraper, browser
automation, access-control workaround, PDF extractor or additional-source adapter.
JSTOR DOI registrations and text encountered through Crossref or OpenAlex are
source metadata, not evidence that the workflow directly retrieved JSTOR pages.
The inspected files do not establish a successful or failed general publisher/JSTOR
retrieval method, so none is presented as a proven route.

## Read-only audit

```sh
python3 -I scripts/audit_outputs.py ./corpus organization-science --output ./audit.json
python3 -I scripts/audit_outputs.py ./corpus
```

The second form discovers existing `data/*/records.csv` files. The command prints
JSON, optionally saves the same JSON, and returns exit status 1 for inconsistent or
unreadable inputs. Warnings identify missing evidence or unfinished lookup work.
No network calls, inferred content verdicts or changes to corpus inputs occur.

The audit checks DOI uniqueness, journal ownership, presence of item kinds,
duplicate targets (including chains and cycles), abstract/source agreement, word
counts and boolean flags. It reports paper counts using the same front-matter and
duplicate exclusions as the collection scripts. Empty abstract fields are grouped
by the saved gap resolution, or `unreported` when no reason was saved.

Where caches exist, it counts Crossref records, OpenAlex lookup statuses and
Semantic Scholar null/present responses. It flags missing OpenAlex lookups, retryable
errors, unlabelled statuses, repeated cache DOIs, malformed Semantic Scholar
responses and mismatched batch lengths. A missing whole cache is an evidence warning; a source-labelled
field whose available cache has no usable entry is an inconsistency. Semantic
Scholar need not have an entry for every record because it is a fallback source.

The audit does **not** compare abstract text with cached text, validate article
identity, verify manual decisions, inspect publisher pages, audit references or
prove the current combined table and summaries match their inputs. Cache hashes
identify the files inspected, not the truth of their contents. The automated
screen's acceptance and a successful audit remain separate from content review.
