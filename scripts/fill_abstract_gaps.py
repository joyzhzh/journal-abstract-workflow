"""Fill abstracts that Crossref lacks for one journal, screening every candidate text.

Usage: python3 -I scripts/fill_abstract_gaps.py <corpus_dir> <journal-slug> [--offline]
  --offline   use only saved responses; stop instead of calling Semantic Scholar

Run after scripts/fetch_journals.py (which rewrites records.csv without fills) and
scripts/enrich_openalex.py (which saves OpenAlex's records); then run
`scripts/fetch_journals.py <corpus_dir> --combine-only` to refresh the combined table, or
combine after processing the selected journals. Reruns start again from Crossref's abstracts: a filled record
gets its Crossref text back from records.jsonl.gz first.

For every record in data/<slug>/records.csv without a Crossref abstract, and every paper
whose Crossref text has fewer than 30 words (a placeholder, an indexer's note, or the
one-sentence summary INFORMS deposits for Marketing Science since 2019):
  1. OpenAlex's text, from raw/openalex/<slug>/works.jsonl.gz (or, for Organization Science,
     the earlier abstract_lookups.jsonl.gz). OpenAlex stores abstracts as an inverted index
     of word positions; the text is rebuilt from it.
  2. Semantic Scholar, by DOI in batches of 500, for records OpenAlex could not fill.
Only research-type records are filled (kind_guess article, perspective, crossroads,
commentary, editorial). Front and back matter is "no abstract expected"; a second
registration (`duplicate_of`) is never filled, because its article's abstract is on the
record kept for it; a text listed in review.json "abstract_rejections" is never used; a flagged text listed in
"abstract_accepts" ({DOI: {"source": "openalex" or "semanticscholar", "note"}}) is used.
A short Crossref text is replaced only by a screened text of 30 words or more; otherwise it
stays, and its gap row says why. Replacements and flagged candidates keep the existing
resolution wording so the reading helpers still find them; `review_note` explains what
happened to the short text. The gap row keeps the Crossref text in `crossref_text`, so
every replacement can be seen. Offline, a short text
whose Semantic Scholar lookup was never saved is kept rather than stopping the run.

Every candidate text of 30 words or more is screened. Flags: `other_work` (OpenAlex returned
a different DOI), `citations` (three or more parenthetical citations with years: the text
reads like the article's body), `heading` (opens with a numbered heading, "Introduction"
or "Preface"), `long` (more than 500 words), `title` (the text is the title). A flagged
text is not used; the gap row says why, so it can be read and judged by hand. Tested on
Organization Science: the screen catches 4 of the 6 texts rejected by hand, and flags 21
of its 2,379 Crossref abstracts of 30 words or more, so sample reading is still needed.

Writes:
  raw/semanticscholar/<slug>/abstract_batch.json.gz   Semantic Scholar responses as received
  data/<slug>/abstract_gaps.csv                       one row per record without a Crossref abstract,
                                                      and per paper with a short Crossref text
  data/<slug>/records.csv                             filled abstracts, with abstract_source
  data/<slug>/summary.json                            gains an "abstract_gaps" section
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import APIError, normalize_doi, request_json, validate_slug
from fetch_journals import load_review

FILL_KINDS = {"article", "perspective", "crossroads", "commentary", "editorial"}
FRONT_KINDS = {"author_bios", "front_back_matter", "call", "index", "correction", "reviewer_list", "test_record", "retraction", "book_review"}
MIN_WORDS = 30
MAX_WORDS = 500  # Organization Science: 10 of 2,379 Crossref abstracts are longer
S2_BATCH = 500
OPENING_TEXT = "candidate text rejected by review; see review_note"
SHORT = "short Crossref text "  # report wording for a paper's Crossref text below MIN_WORDS
GAP_FIELDS = [
    "doi", "year", "volume", "issue", "pages", "n_pages", "title", "kind_guess",
    "openalex_found", "openalex_abstract_words", "s2_checked", "s2_abstract_words",
    "resolution", "abstract_source", "flags", "title_word_overlap", "check",
    "dup_candidate_of", "duplicate_of", "review_note", "crossref_text",
]
STOP = set("the and for with from that this into over under between among their its of in on to a an by as at or".split())
CITATION = re.compile(r"\([^()]{0,120}?\b(1[89]\d\d|20\d\d)[a-z]?\s*[;,)]")
HEADING = re.compile(r"^\s*(\d+(\.\d+)*\.?\s+[A-Z]|[IVX]+\.\s+[A-Z]|(introduction|preface)\b)", re.I)


def request(url, data=None):
    return request_json(url, "semanticscholar", data=data)


def from_inverted(index):
    if not index:
        return ""
    pos = [(p, w) for w, ps in index.items() for p in ps]
    return re.sub(r"\s+", " ", " ".join(w for _, w in sorted(pos))).strip()


def tidy(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return re.sub(r"^abstract[:.]?\s+", "", text, flags=re.I)


def screen(text, title, other_work=False):
    flags = []
    if other_work:
        flags.append("other_work")
    if len(CITATION.findall(text)) >= 3:
        flags.append("citations")
    if HEADING.match(text):
        flags.append("heading")
    if len(text.split()) > MAX_WORDS:
        flags.append("long")
    if re.sub(r"\W+", "", text.lower()) == re.sub(r"\W+", "", title.lower()):
        flags.append("title")
    return flags


def title_overlap(title, abstract):
    words = {w for w in re.findall(r"[a-z]+", title.lower()) if len(w) > 3 and w not in STOP}
    if not words:
        return None
    text = abstract.lower()
    return round(sum(w in text for w in words) / len(words), 2)


def load_openalex(corpus, slug):
    works = os.path.join(corpus, "raw", "openalex", slug, "works.jsonl.gz")
    legacy = os.path.join(corpus, "raw", "openalex", slug, "abstract_lookups.jsonl.gz")
    path = works if os.path.exists(works) else legacy if os.path.exists(legacy) else None
    if not path:
        raise SystemExit(f"no OpenAlex responses for {slug}: run scripts/enrich_openalex.py first")
    oa = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("status") != "error":  # a failed lookup counts as missing
                oa[rec["doi"]] = rec["response"]
    return oa, os.path.relpath(path, corpus)


def main(corpus, slug, offline):
    validate_slug(slug)
    data_dir = os.path.join(corpus, "data", slug)
    s2_path = os.path.join(corpus, "raw", "semanticscholar", slug, "abstract_batch.json.gz")
    with open(os.path.join(data_dir, "records.csv"), encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames
    if not fields:
        raise SystemExit("records.csv has no header")
    review_path = os.path.join(data_dir, "review.json")
    rejections, accepts = {}, {}
    if os.path.exists(review_path):
        review = load_review(corpus, slug)
        rejections = review.get("abstract_rejections", {})
        accepts = review.get("abstract_accepts", {})  # flagged texts read and judged to be abstracts
    # Start from Crossref's abstracts only, so a rerun gives the same result. A filled record gets its
    # Crossref text back from records.jsonl.gz: empty, or a short text an earlier run replaced.
    filled = [r for r in rows if r["abstract_source"] not in ("crossref", "")]
    if filled:
        crossref = {}
        with gzip.open(os.path.join(data_dir, "records.jsonl.gz"), "rt", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                crossref[normalize_doi(rec["DOI"])] = (rec.get("abstract_text") or "").replace("\n\n", " ")
        missing_crossref = [r["doi"] for r in filled if r["doi"] not in crossref]
        if missing_crossref:
            raise SystemExit(f"{len(missing_crossref)} filled records have no Crossref record in records.jsonl.gz; cannot restore their original texts")
        for r in filled:
            text = crossref[r["doi"]]
            r.update({"abstract": text, "abstract_source": "crossref" if text else "", "has_abstract": bool(text),
                      "abstract_words": len(text.split()), "abstract_placeholder": bool(text) and len(text.split()) < MIN_WORDS})
    gaps = [r for r in rows if not r["abstract"].strip()]
    # Papers whose Crossref text is shorter than an abstract can be: placeholders, indexer's notes, summaries.
    short = [r for r in rows if r["abstract"].strip() and len(r["abstract"].split()) < MIN_WORDS
             and r["kind_guess"] in FILL_KINDS and not r.get("duplicate_of")]
    short_dois = {r["doi"] for r in short}
    oa, oa_file = load_openalex(corpus, slug) if gaps or short else ({}, "")
    missing_oa = [r["doi"] for r in gaps + short if r["doi"] not in oa]
    if missing_oa:
        raise SystemExit(f"{len(missing_oa)} gap records have no OpenAlex response in {oa_file}; run scripts/enrich_openalex.py")
    print(f"{slug}: {len(rows)} records, {len(gaps)} without a Crossref abstract, {len(short)} papers with a Crossref "
          f"text under {MIN_WORDS} words; OpenAlex from {oa_file}", file=sys.stderr)

    def oa_candidate(r):
        resp = oa.get(r["doi"]) or {}
        text = tidy(from_inverted(resp.get("abstract_inverted_index")))
        other = bool(resp) and normalize_doi(resp.get("doi")) != r["doi"]
        flags = screen(text, r["title"], other) if len(text.split()) >= MIN_WORDS else []
        if flags and accepts.get(r["doi"], {}).get("source") == "openalex":
            flags = []
        return text, flags

    eligible = [r for r in gaps + short if r["kind_guess"] in FILL_KINDS and not r.get("duplicate_of") and r["doi"] not in rejections]
    need_s2 = [r["doi"] for r in eligible if (lambda t, fl: len(t.split()) < MIN_WORDS or fl)(*oa_candidate(r))]

    s2 = {}
    if os.path.exists(s2_path):
        with gzip.open(s2_path, "rb") as f:
            saved = json.loads(f.read())
        if len(saved["ids"]) != len(saved["response"]):
            raise SystemExit("invalid Semantic Scholar cache: unequal IDs and responses")
        s2 = {d: p for d, p in zip(saved["ids"], saved["response"])}
    missing = [d for d in need_s2 if d not in s2]
    if missing and offline:
        stop = [d for d in missing if d not in short_dois]
        if stop:
            raise SystemExit(f"offline: {len(stop)} Semantic Scholar lookups missing from {s2_path}")
        missing = []  # a short Crossref text whose lookup was never saved is kept as it is
    for i in range(0, len(missing), S2_BATCH):
        chunk = missing[i:i + S2_BATCH]
        body = json.dumps({"ids": [f"DOI:{d}" for d in chunk]}).encode()
        resp = request("https://api.semanticscholar.org/graph/v1/paper/batch?fields=title,abstract,externalIds", data=body)
        if not isinstance(resp, list) or len(resp) != len(chunk) or any(p is not None and not isinstance(p, dict) for p in resp):
            raise APIError("semanticscholar: invalid batch response; nothing from this batch cached")
        for d, p in zip(chunk, resp):
            s2[d] = p
        # Checkpoint each successful batch; a later failed batch cannot erase it.
        os.makedirs(os.path.dirname(s2_path), exist_ok=True)
        ids = sorted(s2)
        temporary = s2_path + ".tmp"
        with open(temporary, "wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as f:
                f.write(json.dumps({"ids": ids, "response": [s2[d] for d in ids]}, ensure_ascii=False).encode())
        os.replace(temporary, s2_path)
        print(f"  Semantic Scholar {min(i + S2_BATCH, len(missing))}/{len(missing)}", file=sys.stderr)


    out, fills = [], Counter()
    by_doi = {r["doi"]: r for r in rows}
    for r in gaps + short:
        doi = r["doi"]
        is_short = doi in short_dois
        crossref_text = r["abstract"] if is_short else ""
        oa_text, oa_flags = oa_candidate(r)
        s2_text = tidy((s2.get(doi) or {}).get("abstract") or "")
        s2_doi = normalize_doi(((s2.get(doi) or {}).get("externalIds") or {}).get("DOI"))
        s2_flags = screen(s2_text, r["title"], bool(s2_doi) and s2_doi != doi) if len(s2_text.split()) >= MIN_WORDS else []
        if s2_flags and accepts.get(doi, {}).get("source") == "semanticscholar":
            s2_flags = []
        try:
            a, b = r["pages"].split("-")
            n_pages = int(b) - int(a) + 1
        except ValueError:
            n_pages = ""
        note, text, source, flags = "", "", "", []
        if r["kind_guess"] not in FILL_KINDS:
            resolution = "no abstract expected (not a paper: front or back matter, notice or book review)"
        elif r.get("duplicate_of"):
            resolution = "second registration; the abstract is on the record kept for it"
            note = f"kept record: {r['duplicate_of']}"
        elif doi in rejections:
            resolution = SHORT + "kept: a replacement was read and rejected (reviewed)" if is_short else OPENING_TEXT
            note = rejections[doi]["note"]
        elif len(oa_text.split()) >= MIN_WORDS and not oa_flags:
            resolution = "filled from OpenAlex"
            note = SHORT + "replaced" if is_short else ""
            text, source = oa_text, "openalex"
        elif len(s2_text.split()) >= MIN_WORDS and not s2_flags:
            resolution = "filled from Semantic Scholar"
            note = SHORT + "replaced" if is_short else ""
            text, source = s2_text, "semanticscholar"
            flags = [f"openalex:{x}" for x in oa_flags]
        elif oa_flags or s2_flags:
            resolution = "text found but flagged by the screen; not used"
            flags = [f"openalex:{x}" for x in oa_flags] + [f"semanticscholar:{x}" for x in s2_flags]
            if is_short:
                note = SHORT + "kept"
                if doi not in s2:
                    note += "; Semantic Scholar not looked up (offline run)"
        elif is_short and doi not in s2:
            resolution = SHORT + "kept: Semantic Scholar not looked up (offline run)"
        else:
            resolution = SHORT + "kept: no longer text found" if is_short else "no abstract found"
        overlap = title_overlap(r["title"], text) if text else ""
        if text:
            by_doi[doi].update({"abstract": text, "abstract_source": source, "has_abstract": True,
                                "abstract_words": len(text.split()), "abstract_placeholder": False})
        fills[resolution] += 1
        out.append({
            "doi": doi, "year": r["year"], "volume": r["volume"], "issue": r["issue"], "pages": r["pages"],
            "n_pages": n_pages, "title": r["title"], "kind_guess": r["kind_guess"],
            "openalex_found": bool(oa.get(doi)), "openalex_abstract_words": len(oa_text.split()),
            "s2_checked": doi in s2, "s2_abstract_words": len(s2_text.split()) if doi in s2 else "",
            "resolution": resolution, "abstract_source": source, "flags": " ".join(flags),
            "title_word_overlap": overlap,
            "check": "yes" if text and overlap not in ("", None) and overlap < 0.2 else "",
            "dup_candidate_of": r["dup_candidate_of"],
            "duplicate_of": r.get("duplicate_of", ""),
            "review_note": note,
            "crossref_text": crossref_text,
        })

    with open(os.path.join(data_dir, "abstract_gaps.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=GAP_FIELDS)
        w.writeheader()
        w.writerows(out)
    with open(os.path.join(data_dir, "records.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    summary_path = os.path.join(data_dir, "summary.json")
    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)
    papers = [r for r in rows if r["kind_guess"] not in FRONT_KINDS and not r.get("duplicate_of")]
    summary["abstract_gaps"] = {
        "openalex_responses": oa_file,
        "without_crossref_abstract": len(gaps),
        "by_kind_guess": dict(Counter(r["kind_guess"] for r in gaps).most_common()),
        "papers_with_short_crossref_text": len(short),
        "resolution": dict(fills.most_common()),
        "flags": dict(Counter(x for o in out for x in o["flags"].split()).most_common()),
        "with_abstract_after_fill": sum(bool(str(r["abstract"]).strip()) for r in rows),
        "papers_with_abstract_after_fill": sum(bool(str(r["abstract"]).strip()) for r in papers),
        "papers_with_abstract_of_30_words_or_more_after_fill": sum(len(str(r["abstract"]).split()) >= MIN_WORDS for r in papers),
        "flagged_for_check": sum(o["check"] == "yes" for o in out),
    }
    # records.csv was rewritten above; keep its recorded hash current.
    with open(os.path.join(data_dir, "records.csv"), "rb") as f:
        summary.setdefault("files_sha256", {})["records.csv"] = hashlib.sha256(f.read()).hexdigest()
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary["abstract_gaps"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus")
    parser.add_argument("journal")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        main(args.corpus, args.journal, args.offline)
    except (APIError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
