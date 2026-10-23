"""Read-only consistency audit of journal records and optional saved evidence.

Usage: python3 -I scripts/audit_outputs.py CORPUS_DIR [SLUG ...] [--output report.json]
Without slugs, audit every data/*/records.csv. Exit 1 for inconsistent or unreadable
inputs; warnings identify missing evidence or unresolved collection, not bad content.
Only --output writes a file. No network calls or content judgments are made.
"""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

FRONT_KINDS = {
    "author_bios", "front_back_matter", "call", "index", "correction",
    "reviewer_list", "test_record", "retraction", "book_review",
}
SOURCES = {"crossref", "openalex", "semanticscholar"}
REQUIRED = {
    "doi", "journal", "kind_guess", "duplicate_of", "abstract", "abstract_source",
    "has_abstract", "abstract_words", "abstract_placeholder",
}
LIMITATIONS = [
    "Counts describe saved records, not completeness against publisher issue lists.",
    "A populated field, source label, cache entry or passing audit does not establish that text is the correct article abstract.",
    "Cache checks establish presence and lookup status; they do not compare source text, verify article identity or prove that a current provider response is unchanged.",
    "Short means fewer than 30 whitespace-separated words; length is a screening rule, not a content verdict.",
    "No review decisions, reference tables, combined tables or summary.json totals are certified by this audit.",
]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("CSV row length does not match its header")
    return fields, rows


def sorted_counts(values):
    return dict(sorted(Counter(values).items()))


def audit_journal(root, slug):
    root = Path(root)
    result = {"journal": slug, "counts": {}, "caches": {}, "errors": [], "warnings": []}

    def issue(level, code, doi="", detail=""):
        item = {"code": code}
        if doi:
            item["doi"] = doi
        if detail:
            item["detail"] = detail
        result[level].append(item)

    def error(code, doi="", detail=""):
        issue("errors", code, doi, detail)

    def warn(code, doi="", detail=""):
        issue("warnings", code, doi, detail)

    path = root / "data" / slug / "records.csv"
    try:
        fields, rows = read_csv(path)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        error("records_unreadable", detail=type(exc).__name__)
        return result
    result["records_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    missing = REQUIRED - fields
    if missing:
        error("required_columns_missing", detail=", ".join(sorted(missing)))
        return result
    by_doi = {}
    for row in rows:
        doi, text, source = row["doi"], row["abstract"], row["abstract_source"]
        present, words = bool(text.strip()), len(text.split())
        if not doi:
            error("doi_missing")
        elif doi != doi.lower().strip():
            error("doi_not_normalized", doi)
        if doi in by_doi:
            error("doi_repeated", doi)
        by_doi[doi] = row
        if row["journal"] != slug:
            error("journal_mismatch", doi)
        if not row["kind_guess"]:
            error("kind_missing", doi)
        if row["has_abstract"] not in ("True", "False"):
            error("has_abstract_invalid", doi)
        elif (row["has_abstract"] == "True") != present:
            error("has_abstract_mismatch", doi)
        try:
            if int(row["abstract_words"]) != words:
                error("abstract_words_mismatch", doi)
        except ValueError:
            error("abstract_words_invalid", doi)
        expected_short = present and words < 30
        if row["abstract_placeholder"] not in ("True", "False"):
            error("abstract_placeholder_invalid", doi)
        elif (row["abstract_placeholder"] == "True") != expected_short:
            error("abstract_placeholder_mismatch", doi)
        if present and source not in SOURCES:
            error("abstract_source_missing_or_unknown", doi)
        elif not present and source:
            error("abstract_source_without_text", doi)
        if source in {"openalex", "semanticscholar"} and words < 30:
            error("fill_below_minimum_words", doi)
    for row in rows:
        doi, target = row["doi"], row["duplicate_of"]
        if not target:
            continue
        if target == doi:
            error("duplicate_self_link", doi)
        elif target not in by_doi:
            error("duplicate_target_missing", doi)
        elif by_doi[target]["duplicate_of"]:
            error("duplicate_target_is_duplicate", doi)
        if "duplicate_note" in fields and not row["duplicate_note"].strip():
            warn("duplicate_note_missing", doi)

    papers = [r for r in rows if r["kind_guess"] not in FRONT_KINDS and not r["duplicate_of"]]
    nonempty = [r for r in papers if r["abstract"].strip()]
    absent = [r for r in papers if not r["abstract"].strip()]
    result["counts"] = {
        "records": len(rows), "papers": len(papers),
        "records_by_kind": sorted_counts(r["kind_guess"] or "missing" for r in rows),
        "records_by_abstract_source": sorted_counts(r["abstract_source"] or "none" for r in rows),
        "papers_by_abstract_source": sorted_counts(r["abstract_source"] or "none" for r in papers),
        "duplicates_marked": sum(bool(r["duplicate_of"]) for r in rows),
        "papers_with_nonempty_abstract": len(nonempty),
        "papers_with_abstract_ge30_words": sum(len(r["abstract"].split()) >= 30 for r in nonempty),
        "papers_with_short_text": sum(len(r["abstract"].split()) < 30 for r in nonempty),
        "papers_without_abstract": len(absent),
    }
    gap_path = path.with_name("abstract_gaps.csv")
    gaps = {}
    if gap_path.exists():
        try:
            gap_fields, gap_rows = read_csv(gap_path)
            if not {"doi", "resolution"} <= gap_fields:
                error("gap_columns_missing")
            else:
                for gap in gap_rows:
                    if gap["doi"] in gaps:
                        error("gap_doi_repeated", gap["doi"])
                    if gap["doi"] not in by_doi:
                        error("gap_doi_unknown", gap["doi"])
                    if not gap["resolution"].strip():
                        warn("gap_resolution_missing", gap["doi"])
                    gaps[gap["doi"]] = gap
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            error("gaps_unreadable", detail=type(exc).__name__)
    else:
        warn("gap_report_absent", detail="Missing abstract reasons cannot be checked.")
    result["counts"]["papers_without_abstract_by_resolution"] = sorted_counts(
        gaps.get(r["doi"], {}).get("resolution") or "unreported" for r in absent
    )

    cache_paths = {
        "crossref": root / "data" / slug / "records.jsonl.gz",
        "openalex": root / "raw" / "openalex" / slug / "works.jsonl.gz",
        "semanticscholar": root / "raw" / "semanticscholar" / slug / "abstract_batch.json.gz",
    }
    legacy = cache_paths["openalex"].with_name("abstract_lookups.jsonl.gz")
    if not cache_paths["openalex"].exists() and legacy.exists():
        cache_paths["openalex"] = legacy
    for source, cache_path in cache_paths.items():
        stats = {"present": cache_path.exists(), "records": 0}
        result["caches"][source] = stats
        if not cache_path.exists():
            warn("source_cache_absent", detail=source)
            continue
        entries = {}
        try:
            with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
                if source == "semanticscholar":
                    saved = json.load(handle)
                    ids, responses = saved["ids"], saved["response"]
                    if not isinstance(ids, list) or not isinstance(responses, list):
                        raise ValueError("batch arrays required")
                    if len(ids) != len(responses):
                        error("source_cache_batch_length_mismatch", detail=source)
                    pairs = [(doi, "response_present" if response else "null_response")
                             for doi, response in zip(ids, responses)]
                else:
                    pairs = []
                    for line in handle:
                        entry = json.loads(line)
                        if source == "crossref":
                            pairs.append((entry["DOI"].lower(), "record_present"))
                        else:
                            status = entry.get("status") or "missing_status"
                            pairs.append((entry["doi"], status))
                            if status not in {"ok", "not_found", "error"}:
                                warn("source_cache_unknown_status", entry["doi"], str(status))
                            if status == "ok" and not isinstance(entry.get("response"), dict):
                                error("source_cache_ok_without_response", entry["doi"], source)
                for doi, status in pairs:
                    if doi in entries:
                        error("source_cache_doi_repeated", str(doi), source)
                    entries[doi] = status
        except (OSError, EOFError, UnicodeError, ValueError, KeyError, TypeError, AttributeError) as exc:
            error("source_cache_unreadable", detail=source + ": " + type(exc).__name__)
            continue
        stats.update({
            "records": len(entries), "statuses": sorted_counts(entries.values()),
            "record_dois_without_entry": len(set(by_doi) - set(entries)),
            "sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest(),
        })
        if source == "openalex":
            if stats["record_dois_without_entry"]:
                warn("openalex_lookups_missing", detail=str(stats["record_dois_without_entry"]))
            if "error" in entries.values():
                warn("openalex_errors_need_retry")
        # A fallback source need not have been queried for every record.
        expected = {"crossref": "record_present", "openalex": "ok", "semanticscholar": "response_present"}[source]
        for row in rows:
            if row["abstract_source"] == source and entries.get(row["doi"]) != expected:
                error("used_source_cache_unavailable", row["doi"], source)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("slugs", nargs="*")
    parser.add_argument("--output", type=Path, help="Also save the JSON report at this path")
    args = parser.parse_args(argv)
    slugs = args.slugs or sorted(p.parent.name for p in (args.corpus_dir / "data").glob("*/records.csv"))
    if not slugs:
        parser.error("No data/*/records.csv files found")
    if any(slug in {".", ".."} or "/" in slug or "\\" in slug for slug in slugs):
        parser.error("Use journal directory names, not paths")
    report = {
        "scope": "Saved output consistency and cache availability; no content certification",
        "limitations": LIMITATIONS,
        "journals": [audit_journal(args.corpus_dir, slug) for slug in dict.fromkeys(slugs)],
    }
    report["errors"] = sum(len(j["errors"]) for j in report["journals"])
    report["warnings"] = sum(len(j["warnings"]) for j in report["journals"])
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    # Some journals contain long metadata fields; use the largest supported limit.
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            break
        except OverflowError:
            limit //= 10
    raise SystemExit(main())
