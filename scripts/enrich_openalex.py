"""Look up every record of one journal in OpenAlex by DOI and keep what OpenAlex holds.

Usage: python3 -I scripts/enrich_openalex.py <corpus_dir> <journal-slug> [--offline] [--limit N]
  --offline   use only the saved responses; stop if any record is missing
  --limit N   look up at most N new records (for a test)

One single-record lookup per DOI. OPENALEX_API_KEY optionally supplies API credentials.
Saved responses are reused, so a stopped run resumes from saved DOI lookups. A failed
request stops the run without storing an empty success. Successful lookups are checkpointed
every 25 records and on ordinary exceptions or interruption; an abrupt process kill can
require up to 24 lookups to be repeated. Legacy status "error" rows are retried.
Nothing is decided here: the abstract fill
(scripts/fill_abstract_gaps.py) and the reference table (scripts/build_references.py) read
the saved responses.

Writes:
  raw/openalex/<slug>/works.jsonl.gz   one line per DOI: {"doi", "status", "response"}
  data/<slug>/openalex.csv             one row per record: the OpenAlex work and what it adds
"""
import argparse
import csv
import gzip
import io
import json
import os
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (APIError, normalize_doi, preserve_cache, request_json, validate_slug,
                    valid_openalex_record, valid_openalex_work)

SELECT = ("id,doi,display_name,publication_year,type,language,abstract_inverted_index,"
          "referenced_works,referenced_works_count,cited_by_count,primary_topic,authorships")


def get(url):
    """Only HTTP 404 is cached as not_found; transport/auth failures stop this run."""
    response = request_json(url, "openalex", allow_not_found=True)
    if response is not None and not valid_openalex_work(response):
        raise APIError("openalex: invalid work response; nothing cached")
    return ("ok" if response is not None else "not_found"), response, {}


def gz_write(path, lines):
    tmp = path + ".tmp"
    with io.TextIOWrapper(gzip.GzipFile(filename="", mode="wb", fileobj=open(tmp, "wb"), mtime=0), encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    os.replace(tmp, path)


def from_inverted(index):
    if not index:
        return ""
    pos = [(p, w) for w, ps in index.items() for p in ps]
    return re.sub(r"\s+", " ", " ".join(w for _, w in sorted(pos))).strip()


def main(corpus, slug, offline, limit):
    validate_slug(slug)
    data_dir = os.path.join(corpus, "data", slug)
    out_path = os.path.join(corpus, "raw", "openalex", slug, "works.jsonl.gz")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(os.path.join(data_dir, "records.csv"), encoding="utf-8") as f:
        dois = [r["doi"] for r in csv.DictReader(f)]
    saved = {}
    invalid_cache = False
    if os.path.exists(out_path):
        with gzip.open(out_path, "rt", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if valid_openalex_record(rec):
                    saved[rec["doi"]] = rec
                else:
                    invalid_cache = True  # preserve original bytes, retry the missing DOI
    todo = [d for d in dois if d not in saved]
    if todo and offline:
        raise SystemExit(f"offline: {len(todo)} records have no saved OpenAlex response in {out_path}")
    if limit:
        todo = todo[:limit]
    print(f"{slug}: {len(dois)} records, {len(saved)} saved, {len(todo)} to look up", file=sys.stderr)

    def lookup(doi):
        url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi, safe="/") + "?select=" + SELECT
        status, resp, headers = get(url)
        return doi, status, resp, headers.get("x-ratelimit-remaining") or headers.get("X-RateLimit-Remaining")

    dirty = False

    def checkpoint():
        nonlocal invalid_cache, dirty
        if invalid_cache:
            preserve_cache(out_path)
            invalid_cache = False
        gz_write(out_path, (json.dumps(saved[d], ensure_ascii=False) for d in sorted(saved)))
        dirty = False

    try:
        for i, requested_doi in enumerate(todo, 1):
            doi, status, resp, _ = lookup(requested_doi)
            record = {"doi": doi, "status": status, "response": resp}
            if not valid_openalex_record(record):
                raise APIError("openalex: invalid work response; nothing cached for this DOI")
            saved[doi] = record
            dirty = True
            if i % 25 == 0 or i == len(todo):
                checkpoint()
                print(f"  {i}/{len(todo)} looked up", file=sys.stderr)
    finally:
        if dirty:
            checkpoint()

    rows, stats = [], Counter()
    for doi in dois:
        rec = saved.get(doi)
        if not rec:
            continue
        w = rec["response"] or {}
        oa_doi = normalize_doi(w.get("doi"))
        abstract = from_inverted(w.get("abstract_inverted_index"))
        inst, countries = [], []
        for a in w.get("authorships") or []:
            for ins in a.get("institutions") or []:
                if ins.get("display_name") and ins["display_name"] not in inst:
                    inst.append(ins["display_name"])
                if ins.get("country_code") and ins["country_code"] not in countries:
                    countries.append(ins["country_code"])
        topic = w.get("primary_topic") or {}
        row = {
            "doi": doi,
            "status": rec["status"],
            "openalex_id": (w.get("id") or "").replace("https://openalex.org/", ""),
            "openalex_doi": oa_doi,
            "same_doi": bool(oa_doi) and oa_doi == doi,
            "oa_type": w.get("type", ""),
            "oa_year": w.get("publication_year", ""),
            "oa_language": w.get("language", ""),
            "oa_abstract_words": len(abstract.split()),
            "referenced_works": len(w.get("referenced_works") or []),
            "cited_by_count_openalex": w.get("cited_by_count", ""),
            "primary_topic": topic.get("display_name", ""),
            "primary_field": (topic.get("field") or {}).get("display_name", ""),
            "n_authorships": len(w.get("authorships") or []),
            "institutions": "; ".join(inst),
            "countries": "; ".join(countries),
        }
        rows.append(row)
        stats[rec["status"]] += 1
        stats["different_doi"] += rec["status"] == "ok" and not row["same_doi"]
        stats["with_abstract"] += bool(abstract)
        stats["with_referenced_works"] += row["referenced_works"] > 0
    with open(os.path.join(data_dir, "openalex.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["doi", "status", "openalex_id", "openalex_doi", "same_doi", "oa_type", "oa_year", "oa_language", "oa_abstract_words", "referenced_works", "cited_by_count_openalex", "primary_topic", "primary_field", "n_authorships", "institutions", "countries"])
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({"records": len(dois), "looked_up": len(rows), **stats}, indent=1))
    failed = [r["doi"] for r in rows if r["status"] == "error"]
    if failed:
        raise SystemExit(f"{len(failed)} lookups failed for now; run the script again to retry them: "
                         + " ".join(failed[:20]) + (" ..." if len(failed) > 20 else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus")
    parser.add_argument("journal")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="maximum new lookups; 0 means all")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit cannot be negative")
    try:
        main(args.corpus, args.journal, args.offline, args.limit)
    except (APIError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
