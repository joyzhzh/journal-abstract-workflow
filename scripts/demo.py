"""Create a synthetic journal and exercise every stage offline; no publisher text.

Run: python3 scripts/demo.py --output runs/demo
The output directory must be new so existing work cannot be replaced.
"""
import argparse
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline

SLUG = "synthetic-journal"
PREFIX = "10.0000/synthetic-"
SHORT = "A deliberately short synthetic summary."
TEXT = ("This invented passage demonstrates a journal abstract workflow using synthetic organizations and imaginary observations. "
        "The example contains no published research and makes no empirical claim. It exists only to exercise metadata merging, source selection, and reproducible processing.")
FLAGGED = "Introduction " + TEXT
JOURNAL = {"slug": SLUG, "title": "Synthetic Journal for Offline Demonstration", "publisher": "Synthetic publisher",
           "issns": ["0000-0000", "0000-0019"], "utd24": False, "ft50_2016": False, "ft50_2026": False,
           "default": True, "evidence_status": "synthetic_demo"}


def inverted(text):
    index = {}
    for position, word in enumerate(text.split()):
        index.setdefault(word, []).append(position)
    return index


def work(name, text="", doi_name=None, references=None):
    doi = PREFIX + (doi_name or name)
    return {"id": "https://openalex.org/W0000000" + str(len(name)), "doi": "https://doi.org/" + doi,
            "display_name": "Synthetic demonstration", "abstract_inverted_index": inverted(text),
            "referenced_works": references or [], "authorships": []}


def create_fixture(output):
    """Write only generated test content. Preserve the directory for inspection."""
    root = Path(output)
    if root.exists():
        raise ValueError("demo output directory already exists; choose a new directory")
    root.mkdir(parents=True)
    registry = root / "synthetic-registry.json"
    registry.write_text(json.dumps({"journals": [JOURNAL]}, indent=2) + "\n", encoding="utf-8")
    names = ["crossref", "openalex", "scholar", "short", "replacement", "duplicate", "front", "flagged",
             "accepted", "rejected", "mismatch", "kind-override"]
    records = []
    for n, name in enumerate(names):
        record = {"DOI": PREFIX + name, "title": ["Synthetic demonstration " + name],
                  "container-title": [JOURNAL["title"]], "type": "journal-article", "volume": "1", "issue": "1",
                  "page": f"{n * 10 + 1}-{n * 10 + 8}", "published-print": {"date-parts": [[2020, 1]]}}
        if name == "crossref":
            record["abstract"] = "<jats:p>" + TEXT + "</jats:p>"
            record["reference"] = [{"DOI": "10.0000/synthetic-citation", "key": "ref1", "article-title": "Synthetic cited item"}]
        if name in {"short", "replacement"}:
            record["abstract"] = SHORT
        if name == "duplicate":
            record["title"] = ["Synthetic demonstration crossref"]
            record["page"] = "1-8"
            record["reference"] = [{"DOI": "10.0000/synthetic-citation-second", "key": "ref1"}]
        if name == "front":
            record["title"] = ["Front matter"]
        records.append(record)
    container = {"DOI": PREFIX + "issue", "type": "journal-issue", "title": ["Synthetic issue"]}
    raw = root / "raw" / "crossref" / SLUG
    raw.mkdir(parents=True)
    for issn, items in zip(JOURNAL["issns"], [records + [container], [{**records[0], "DOI": records[0]["DOI"].upper()}]]):
        with gzip.open(raw / f"{issn}_page_01.json.gz", "wt", encoding="utf-8") as handle:
            json.dump({"message": {"total-results": len(items), "items": items}}, handle)
    responses = {name: None for name in names}
    responses.update({"crossref": work("crossref", "Unused lower priority synthetic text."),
                      "openalex": work("openalex", TEXT, references=["https://openalex.org/W000001"]),
                      "replacement": work("replacement", TEXT), "flagged": work("flagged", FLAGGED),
                      "accepted": work("accepted", FLAGGED), "rejected": work("rejected", TEXT),
                      "mismatch": work("mismatch", TEXT, doi_name="different", references=["https://openalex.org/W000002"])})
    oa = root / "raw" / "openalex" / SLUG / "works.jsonl.gz"
    oa.parent.mkdir(parents=True)
    with gzip.open(oa, "wt", encoding="utf-8") as handle:
        for name in names:
            json.dump({"doi": PREFIX + name, "status": "ok" if responses[name] else "not_found", "response": responses[name]}, handle)
            handle.write("\n")
    s2 = root / "raw" / "semanticscholar" / SLUG / "abstract_batch.json.gz"
    s2.parent.mkdir(parents=True)
    s2_results = {"scholar": {"abstract": TEXT, "externalIds": {"DOI": PREFIX + "scholar"}},
                  "short": None, "flagged": None,
                  "mismatch": {"abstract": TEXT, "externalIds": {"DOI": PREFIX + "different"}}}
    with gzip.open(s2, "wt", encoding="utf-8") as handle:
        json.dump({"ids": [PREFIX + name for name in s2_results], "response": list(s2_results.values())}, handle)
    data = root / "data" / SLUG
    data.mkdir(parents=True)
    review = {"duplicates": {PREFIX + "duplicate": {"kept": PREFIX + "crossref", "note": "Synthetic second registration."}},
              "kinds": {PREFIX + "kind-override": {"kind": "front_back_matter", "note": "Synthetic manual item-kind decision."}},
              "abstract_accepts": {PREFIX + "accepted": {"source": "openalex", "note": "Synthetic decision to exercise a reviewed screen override."}},
              "abstract_rejections": {PREFIX + "rejected": {"note": "Synthetic decision to exercise rejection of a candidate."}}}
    (data / "review.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    return registry


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default="runs/demo")
    args = parser.parse_args()
    try:
        registry = create_fixture(args.output)
        pipeline.run(args.output, [SLUG], registry, offline=True, references=True)
    except ValueError as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
