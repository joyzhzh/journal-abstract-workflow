# Sharing message and quick start

## Ready-to-share message

Sharing **Journal Abstract Workflow**, an open-source Python toolkit for collecting
journal metadata and available abstracts from **Crossref, OpenAlex and Semantic
Scholar**. It exports CSV files, records each abstract's source, and supports
resuming downloads and rebuilding from saved responses.

The focus is **UTD24/FT50 management research**, with demonstrated runs for **21
journals**, including Academy of Management Journal, Academy of Management Review,
Administrative Science Quarterly, Organization Science, Strategic Management
Journal, Journal of Management and Journal of Management Studies. The wider
registry includes all UTD24 titles and dated FT50 lists; some titles remain untested.

To get started, download the repository, use **Python 3.10+**, try the offline demo,
then choose a journal. No extra Python packages are required. Abstract availability
varies by journal, and flagged texts need review.

Repository: https://github.com/joyzhzh/journal-abstract-workflow

## Run your first example

Download the repository using GitHub's **Code → Download ZIP**, extract it, and
open a terminal in the extracted folder. Run this demo with invented papers; it
needs no API access:

```sh
python3 scripts/demo.py --output runs/first-demo
python3 scripts/audit_outputs.py runs/first-demo
```

Use a fresh demo folder each time. For real collection, first read the
[API access instructions](SOURCES.md), then list journals and select one:

```sh
python3 scripts/pipeline.py --list
python3 scripts/pipeline.py --output runs/my-corpus organization-science
python3 scripts/audit_outputs.py runs/my-corpus
```

Open `runs/my-corpus/data/organization-science/records.csv` for the results and
`abstract_gaps.csv` in the same folder for unresolved or flagged cases. API limits
may interrupt collection; rerun the same collection command to resume.

## Understand the coverage

The **55-title catalog** covers UTD24, the 2016 and 2026 FT50 lists, and an optional
Strategy Science example. Of the 21 demonstrated journals, **19 are in the current
list union**; Organization Studies is a historical FT50 example, and Strategy
Science is outside both lists. Harvard Business Review's Crossref route is
currently unsupported. Catalog membership does not establish a successful full run
or complete abstract coverage.

See the [full journal list](JOURNALS.md), [journal-by-journal evidence](EVIDENCE.md),
[review guide](REVIEW.md) and [complete instructions](../README.md). The repository
shares the tools and synthetic examples; it does not include the earlier harvested
abstract collection.
