# Demonstrated behavior and limits

Evidence snapshot: **23 October 2026**. The reusable workflow was exercised on saved responses for **21 journals**. The resulting population contained **84,446 records**, **64,583 papers**, **50,062 populated abstract fields** and **49,193 fields of at least 30 words**. Nineteen of those journals belong to the current UTD24/FT50 union; the two additional demonstrations are labeled below. [Journal scope](JOURNALS.md) identifies every catalog entry and its evidence status.

These are aggregate observations checked against local records and final summaries, not a publicly reproducible benchmark. The underlying private corpus, raw responses, research notes and record-level judgments are intentionally not distributed. The public tools therefore do not reproduce these exact counts from an empty workspace: APIs change, and the source-specific review decisions were part of the historical result. Public tests can verify software behavior on the included synthetic fixtures; they cannot certify the original corpus's content.

A **paper** here means a record that is neither a marked second registration nor a notice/book review/front-matter kind. Editorials, comments and perspectives can count as papers. “Populated” means a stored nonempty field. It does not necessarily mean a complete, author-written, publisher-verified abstract: the stored results include short summaries, truncated previews, third-party synopses and explicitly uncertain cases. A 30-word threshold is a diagnostic, not a quality certificate.

## Observed source contributions

Counts below were recalculated from the final per-journal tables. C = Crossref; OA = OpenAlex; S2 = Semantic Scholar. Source counts describe **final fields**, so a longer replacement is counted under its replacement source rather than under the original short Crossref text. Empty fields remain visible.

| Journal | Papers | C | OA | S2 | Empty | ≥30 words |
|---|---:|---:|---:|---:|---:|---:|
| Academy of Management Annals | 385 | 0 | 356 | 1 | 28 | 357 |
| Academy of Management Journal | 4,188 | 0 | 2,490 | 13 | 1,685 | 2,503 |
| Academy of Management Review | 2,612 | 0 | 1,846 | 8 | 758 | 1,854 |
| Administrative Science Quarterly | 1,812 | 593 | 702 | 1 | 516 | 1,296 |
| American Sociological Review | 5,642 | 1,157 | 1,243 | 5 | 3,237 | 2,405 |
| Entrepreneurship Theory and Practice | 1,913 | 1,700 | 13 | 0 | 200 | 1,709 |
| Information Systems Research | 1,757 | 1,720 | 1 | 2 | 34 | 1,695 |
| Journal of Business Venturing | 1,589 | 0 | 198 | 207 | 1,184 | 405 |
| Journal of International Business Studies | 2,674 | 182 | 42 | 115 | 2,335 | 339 |
| Journal of Management | 2,750 | 2,583 | 33 | 0 | 134 | 2,615 |
| Journal of Management Studies | 2,987 | 2,353 | 79 | 2 | 553 | 2,433 |
| Management Science | 11,577 | 11,420 | 11 | 6 | 140 | 11,271 |
| Manufacturing & Service Operations Management | 1,649 | 1,605 | 5 | 2 | 37 | 1,610 |
| Marketing Science | 2,030 | 1,928 | 9 | 14 | 79 | 1,524 |
| Operations Research | 7,320 | 7,049 | 23 | 11 | 237 | 6,863 |
| Organization Science | 2,424 | 2,380 | 0 | 0 | 44 | 2,367 |
| Organization Studies (historical FT50) | 2,474 | 2,276 | 5 | 2 | 191 | 2,282 |
| Research Policy | 4,503 | 0 | 794 | 696 | 3,013 | 1,490 |
| Strategic Entrepreneurship Journal | 542 | 508 | 1 | 0 | 33 | 508 |
| Strategic Management Journal | 3,481 | 2,981 | 441 | 0 | 59 | 3,417 |
| Strategy Science (out of list) | 274 | 250 | 0 | 0 | 24 | 250 |
| **Total** | **64,583** | **40,685** | **8,292** | **1,085** | **14,521** | **49,193** |

The inactive INFORMS Journal on Computing snapshot contained 2,664 records. It is excluded from this table and was not a demonstration of the full abstract-enrichment pipeline. All other catalog titles have no journal-wide demonstration in this evidence set.

## What was demonstrated

1. **Enumerate deposits with Crossref.** Query the configured print/electronic/predecessor ISSNs with cursor pagination, save responses, combine by DOI, and distinguish container records from content. This enumerates Crossref deposits returned by those queries, not an independently verified publisher archive.
2. **Keep the original response and a derived table.** Preserve the original deposited text while converting title markup and abstract XML to readable text. Rebuild from saved inputs, recording source and unresolved gaps.
3. **Review identity and item type.** Title and publication-position comparisons identify possible second registrations. Review decisions mark a preferred DOI and item kinds; detection heuristics alone do not settle identity. Such decisions affect the paper denominator.
4. **Enrich by DOI with OpenAlex.** Save success, not-found and request-error outcomes separately, and reconstruct text from word-position indexes. Keep the returned DOI so a merge or redirection can be checked. A source-level journal search was not used as a substitute for DOI matching.
5. **Fill gaps with screened source text.** Consider an OpenAlex candidate, then a Semantic Scholar DOI lookup when the first candidate is absent, short or held for review. Screen for wrong-work identity, body headings, citation density, excessive length and title-only text. Save the candidate evidence and preserve the original short Crossref text.
6. **Read texts and record decisions.** Check full candidate texts, not just flags. Freeze sample membership before reviewing, include low title overlap and held-back candidates, and expand reading when errors show a systematic problem. Accepting a flagged candidate requires an explicit reason. A generic screen cannot establish that a paragraph is an abstract.
7. **Rebuild and check consistency.** Historical checks compared saved-source DOI populations, source-to-output mapping, review application and rebuilt files. Deterministic rebuilds show that the same inputs and decisions yield the same outputs; they do not show that every source text is correct.

An optional reference-list builder used deposited Crossref references first and OpenAlex work identifiers where a deposited list was absent. An OpenAlex identifier is not a resolved cited DOI or full citation. Reference completeness and all redirected work identities were not independently established.

## Journal-specific lessons

| Journal | Demonstrated behavior and remaining limitation |
|---|---|
| Academy of Management Annals | Crossref contained no abstracts; OA supplied most retained text. Long review summaries can be genuine, so length flags need reading. Some retained text is a source preview; publisher boundaries were not generally verified. |
| Academy of Management Journal | Crossref contained no abstracts; OA and S2 supplied retained fields. Citation-only text and unrelated-work matches occurred. Most retained fills were outside the bounded reading sets. |
| Academy of Management Review | Many duplicate/alias DOI registrations required identity review. Citation-only strings and mixed body text were rejected. Retained material includes third-party synopses and 25 source-truncated texts; not every fill was read. |
| Administrative Science Quarterly | Historical OA texts often included citation lines, funding notes or article-body material. The initial random reading found 8 unusable texts in 60; targeted review helped, but hundreds of retained fills remained outside retained reading evidence. |
| American Sociological Review | Every retained non-Crossref fill was read: 1,240 were judged abstracts and eight remained uncertain. The current 2,405 populated fields include those eight plus 1,157 Crossref fields outside that reading protocol. Publisher completeness and the remaining unused candidates were not certified. |
| Entrepreneurship Theory and Practice | Crossref supplied most fields; 13 OA fills remained. Editorial openings and a retraction statement were unsuitable. Some initially accepted OA candidates were rejected later without an S2 follow-up, so that alternative was not exhausted. |
| Information Systems Research | Three longer source texts replaced short Crossref fields; the populated-field count did not rise. Twenty-eight short fields and 34 empty fields remain. DOI identity and field length require separate checks. |
| Journal of Business Venturing | Crossref contained no abstracts; OA and S2 supplied 405 fields, leaving 1,184 empty. The random reading found 1 unsuitable text in 50; targeted checks also found OCR debris, highlights and affiliations. Some retained synopses have unverified authorship. |
| Journal of International Business Studies | Only 339 of 2,674 papers had text. Some valid S2 abstracts were multilingual and exceeded the length flag. A zero-error 50-text sample did not certify the 93 retained fills outside that reading set. |
| Journal of Management | All 51 candidate texts were read. Fourteen of 16 initially unflagged fills were unsuitable; 31 held candidates were accepted with identity evidence. Two accepted DOI correspondences rely on saved metadata rather than a fresh publisher check. |
| Journal of Management Studies | Reading expanded to all initial fills and held candidates after 11 errors in the first 30-text sample. All 81 final fills were read. One retained short Crossref field is an epigraph; the broad field count must not be called confirmed abstract coverage. |
| Management Science | All 22 initial fills were read; five were rejected. Six source-truncated previews and one uncertain text were retained. Most fields came directly from Crossref and were not all individually read. |
| Marketing Science | Many recent Crossref fields were one-sentence summaries. All 29 initial fills/replacements were read, six rejected, and 23 retained; 427 short fields remain. The ≥30-word count is substantially lower than the populated-field count. |
| Manufacturing & Service Operations Management | All ten initial fills were read; three rejected. Some retained candidates are truncated previews. Filling does not imply recovery of their unavailable continuations. |
| Operations Research | Predecessor-title deposits were queried. Reading expanded to all 48 first-pass fills after 9 errors in an initial 30-text sample. Thirty-four fills/replacements remain; older short texts and stale issue assignments remain limitations. |
| Organization Science | Crossref supplied all 2,380 final populated paper fields. Candidate supplements did not add a retained field. Thirteen short fields and 44 empty fields remain; saved-source coverage does not establish publisher completeness. |
| Organization Studies (historical FT50) | Crossref supplied most fields; seven supplementary texts remained. Blank and short fields persist. It is outside the revised 2026 FT50 list, despite its historical membership. |
| Research Policy | Crossref contained no abstracts. OA and S2 supplied 1,490 fields, leaving 3,013 empty, including many recent papers. The random sample had zero errors, but targeted reading found real errors; zero observed random errors is not a certificate for unread fills. |
| Strategic Entrepreneurship Journal | The three initial fills were all read and two rejected, leaving one OA fill. One short field and 33 empty fields remain. |
| Strategic Management Journal | OA supplied 441 fields after review of flagged cases and a bounded retained-field sample. Five short fields remain. A historical sampling log could not be reconstructed, and unreviewed fills remain outside the content guarantee. |
| Strategy Science (out of list) | Crossref supplied all 250 populated fields. Supplementary sources added none; the sole substantial candidate was an essay opening and was rejected. A pagination gap remains unexplained. |

## What “works” means here

The workflow has demonstrated that it can enumerate configured Crossref deposits, save responses, add usable supplementary text for many journals, expose gaps, apply review decisions and rebuild consistently. The scale of missing text varies greatly by journal. It has **not** demonstrated automatic recovery of every abstract, reliable content validation from heuristics alone, or complete coverage of all 24/50 journals.

A request failure, a not-found record, a found record with no abstract, a short text, a held candidate and a read rejection are different outcomes. Keep those distinctions in downstream analysis. Do not infer absence at the publisher from absence in these APIs. Do not infer an independent fresh content review from an offline rebuild passing.

## Attribution

The source information comes from article authors and journal publishers' Crossref deposits, [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [OpenAlex](https://docs.openalex.org/) and [Semantic Scholar](https://www.semanticscholar.org/product/api). Ranking-list credit belongs to [UT Dallas](https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/list-of-journals) and the [Financial Times](https://www.ft.com/ft50-journals), with the institutional verification limits stated in the scope document. The reusable methods were developed through Python collection/rebuild scripts, explicit record-level review and work assisted by Claude Code and Codex. This attribution does not imply endorsement by any provider.
