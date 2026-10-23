"""Build one journal's reference table: one row per reference a record cites.

Usage: python3 -I scripts/build_references.py <corpus_dir> <journal-slug>

Sources, per citing record:
  crossref   the reference list the publisher deposited (data/<slug>/records.jsonl.gz);
  openalex   for a record without one, OpenAlex's referenced_works
             (raw/openalex/<slug>/works.jsonl.gz, from scripts/enrich_openalex.py). These are
             OpenAlex work IDs only; their DOIs and titles need a separate lookup.
Every record's rows are kept, including front matter and second registrations. `paper_doi`
is the record kept for the article (`duplicate_of` where set), so grouping by it merges a
second registration's list with its kept record's: the two lists are near-copies, and a few
cited DOIs appear on only one of them.

Writes:
  data/<slug>/references.csv.gz   one row per reference
  data/<slug>/summary.json        gains a "references" section
"""
import argparse
import csv
import hashlib
import gzip
import io
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import normalize_doi, validate_slug

FRONT_KINDS = {"author_bios", "front_back_matter", "call", "index", "correction", "reviewer_list", "test_record", "retraction", "book_review"}
COLUMNS = ["paper_doi", "citing_doi", "citing_kind", "citing_is_paper", "citing_year", "source", "position", "ref_key",
           "cited_doi", "doi_asserted_by", "cited_openalex_id", "unstructured", "author", "year", "article_title",
           "journal_title", "volume", "first_page"]


def main(corpus, slug):
    validate_slug(slug)
    data_dir = os.path.join(corpus, "data", slug)
    with open(os.path.join(data_dir, "records.csv"), encoding="utf-8") as f:
        meta = {r["doi"]: r for r in csv.DictReader(f)}
    works_path = os.path.join(corpus, "raw", "openalex", slug, "works.jsonl.gz")
    works = {}
    if os.path.exists(works_path):
        with gzip.open(works_path, "rt", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("status") != "error":
                    works[rec["doi"]] = rec["response"] or {}
    out_path = os.path.join(data_dir, "references.csv.gz")
    stats = Counter()
    per_paper = defaultdict(set)      # paper_doi -> cited DOIs or OpenAlex IDs
    paper_has_list = defaultdict(str)  # paper_doi -> best source with a list
    with io.TextIOWrapper(gzip.GzipFile(filename="", mode="wb", fileobj=open(out_path, "wb"), mtime=0), encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        with gzip.open(os.path.join(data_dir, "records.jsonl.gz"), "rt", encoding="utf-8") as src:
            for line in src:
                rec = json.loads(line)
                doi = normalize_doi(rec["DOI"])
                m = meta[doi]
                paper = m.get("duplicate_of") or doi
                is_paper = m["kind_guess"] not in FRONT_KINDS
                base = {"paper_doi": paper, "citing_doi": doi, "citing_kind": m["kind_guess"],
                        "citing_is_paper": is_paper, "citing_year": m["year"]}
                refs = rec.get("reference") or []
                if refs:
                    stats["records_with_crossref_list"] += 1
                    for i, x in enumerate(refs, 1):
                        cited = normalize_doi(x.get("DOI"))
                        w.writerow({**base, "source": "crossref", "position": i, "ref_key": x.get("key", ""),
                                    "cited_doi": cited, "doi_asserted_by": x.get("doi-asserted-by", ""),
                                    "cited_openalex_id": "", "unstructured": x.get("unstructured", ""),
                                    "author": x.get("author", ""), "year": x.get("year", ""),
                                    "article_title": x.get("article-title", ""), "journal_title": x.get("journal-title", ""),
                                    "volume": x.get("volume", ""), "first_page": x.get("first-page", "")})
                        stats["crossref_references"] += 1
                        stats["crossref_references_with_doi"] += bool(cited)
                        per_paper[paper].add(cited or f"{doi}#{i}")
                    paper_has_list[paper] = "crossref"  # a deposited list wins over OpenAlex's
                    continue
                work = works.get(doi) or {}
                oa_refs = work.get("referenced_works") or []
                if oa_refs and normalize_doi(work.get("doi")) != doi:
                    stats["openalex_lists_skipped_doi_mismatch"] += 1
                    oa_refs = []
                if oa_refs:
                    stats["records_with_openalex_list_only"] += 1
                    for i, wid in enumerate(oa_refs, 1):
                        wid = wid.replace("https://openalex.org/", "")
                        w.writerow({**base, "source": "openalex", "position": i, "ref_key": "", "cited_doi": "",
                                    "doi_asserted_by": "", "cited_openalex_id": wid, "unstructured": "", "author": "",
                                    "year": "", "article_title": "", "journal_title": "", "volume": "", "first_page": ""})
                        stats["openalex_references"] += 1
                        per_paper[paper].add(wid)
                    paper_has_list[paper] = paper_has_list[paper] or "openalex"
                else:
                    stats["records_without_any_list"] += 1

    papers = [d for d, m in meta.items() if m["kind_guess"] not in FRONT_KINDS and not m.get("duplicate_of")]
    by_decade = defaultdict(lambda: Counter())
    for d in papers:
        dec = meta[d]["year"][:3] + "0s"
        by_decade[dec]["papers"] += 1
        src = paper_has_list.get(d, "")
        by_decade[dec][f"with_{src}_list" if src else "without_list"] += 1
    summary_path = os.path.join(data_dir, "summary.json")
    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)
    summary["references"] = {
        "openalex_responses": os.path.relpath(works_path, corpus) if works else "",
        **dict(stats),
        "papers": len(papers),
        "papers_with_crossref_list": sum(paper_has_list.get(d) == "crossref" for d in papers),
        "papers_with_openalex_list_only": sum(paper_has_list.get(d) == "openalex" for d in papers),
        "papers_without_list": sum(not paper_has_list.get(d) for d in papers),
        "distinct_cited_items_per_paper_total": sum(len(per_paper[d]) for d in papers),
        "by_decade": {k: dict(v) for k, v in sorted(by_decade.items())},
    }
    with open(out_path, "rb") as f:
        summary.setdefault("files_sha256", {})["references.csv.gz"] = hashlib.sha256(f.read()).hexdigest()
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary["references"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus")
    parser.add_argument("journal")
    args = parser.parse_args()
    try:
        main(args.corpus, args.journal)
    except ValueError as error:
        parser.exit(1, str(error) + "\n")
