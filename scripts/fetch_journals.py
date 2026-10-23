"""Download every Crossref record for a set of management journals and build tables.

Usage: python3 -I scripts/fetch_journals.py <corpus_dir> [--offline] [--combine-only] [slug ...]
  --offline        rebuild only from saved raw pages; stop instead of downloading
  --combine-only   only rebuild data/journals_crossref.csv.gz and data/summary.json from the
                   journal folders (run after scripts/fill_abstract_gaps.py)
  --no-combine     rebuild the named journals' folders only; leave the combined files alone
                   (useful before running enrichment)

For each journal, every known ISSN (print, electronic and older ones) is queried
through the Crossref REST API with cursor paging, and the results are united by
DOI: a single ISSN can miss records (INFORMS Journal on Computing does). Issue-
level container records (type journal-issue) are excluded from the tables.
Standard library only. CROSSREF_MAILTO optionally enables the Crossref polite pool.

Writes:
  raw/crossref/<slug>/snapshots/               full API responses in isolated attempts
  raw/crossref/<slug>/<issn>_manifest.json      completed snapshot, pages and hashes
  data/<slug>/records.jsonl.gz                 full Crossref records + plain-text abstract
  data/<slug>/records.csv                      one flat row per record
  data/<slug>/summary.json                     counts and provenance for the journal
  data/journals_crossref.csv.gz                the flat rows of every journal in this run
  data/summary.json                            all journal summaries of this run
"""
import argparse
import csv
import gzip
import hashlib
import html
import io
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import APIError, load_registry, normalize_doi, request_bytes
from collections import Counter, defaultdict
from datetime import datetime, timezone

API = "https://api.crossref.org/journals/{issn}/works"
ROWS = 500
OFFLINE = False
COMBINE_ONLY = False
NO_COMBINE = False

# The registry is data, not executable code. See config/journals.json for sources.
JOURNALS = []


def get(url):
    return request_bytes(url, "crossref")


def load_raw(issn, raw_dir):
    """Read a committed snapshot, or the original flat saved-page format."""
    manifest_path = os.path.join(raw_dir, f"{issn}_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        pages = manifest["pages"]
        # Reject paths outside this journal's cache.
        root = Path(raw_dir).resolve()
        if any(not (root / p).resolve().is_relative_to(root) for p in pages):
            raise SystemExit("invalid Crossref cache manifest path")
        for page in pages:
            expected = manifest.get("files_sha256", {}).get(page)
            if not expected or not (root / page).is_file() or sha256(root / page) != expected:
                raise SystemExit("Crossref cache integrity check failed; preserve this snapshot and use a new output directory")
    else:
        pages = sorted(p for p in os.listdir(raw_dir) if p.startswith(f"{issn}_page_") and p.endswith(".json.gz"))
        if pages:
            numbers = sorted(int(re.search(r"_page_(\d+)\.json\.gz$", p).group(1)) for p in pages)
            if numbers != list(range(1, len(pages) + 1)):
                return None
    if not pages:
        return None
    items, total = [], None
    for p in pages:
        with gzip.open(os.path.join(raw_dir, p), "rb") as f:
            msg = json.loads(f.read())["message"]
        total = msg["total-results"] if total is None else total
        items.extend(msg["items"])
    # Repeated cursor pages must never masquerade as complete coverage.
    unique = {normalize_doi(it.get("DOI")) for it in items}
    if len(items) < total or len(unique) != len(items) or "" in unique:
        return None
    print(f"  {issn}: reused {len(pages)} saved pages ({len(items)}/{total})", file=sys.stderr)
    return items, len(pages), total


def download_issn(issn, raw_dir):
    saved = load_raw(issn, raw_dir)
    if saved is not None:
        return saved
    if OFFLINE:
        raise SystemExit(f"offline: no complete saved pages for ISSN {issn} in {raw_dir}")
    # A failed attempt stays in its own snapshot directory. Never mix old and new pages.
    snapshot = Path(raw_dir) / "snapshots" / f"{issn}-{uuid4().hex}"
    snapshot.mkdir(parents=True)
    cursor, items, n, total, pages, seen = "*", [], 0, None, [], set()
    while True:
        q = urllib.parse.urlencode({"rows": ROWS, "cursor": cursor})
        body = get(f"{API.format(issn=issn)}?{q}")
        try:
            msg = json.loads(body)["message"]
            batch = msg["items"]
            reported = int(msg["total-results"])
            if not isinstance(batch, list):
                raise ValueError()
            batch_dois = [normalize_doi(it["DOI"]) for it in batch]
        except (ValueError, KeyError, TypeError):
            raise SystemExit("Crossref returned an invalid page; snapshot remains incomplete") from None
        if len(set(batch_dois)) != len(batch_dois) or seen.intersection(batch_dois) or "" in batch_dois:
            raise SystemExit("Crossref repeated DOI records during pagination; snapshot remains incomplete")
        total = reported if total is None else total
        seen.update(batch_dois)
        n += 1
        path = snapshot / f"page_{n:06d}.json.gz"
        with gzip.open(path, "wb") as f:
            f.write(body)
        pages.append(str(path.relative_to(raw_dir)))
        items.extend(batch)
        print(f"  {issn} page {n}: {len(items)}/{total}", file=sys.stderr)
        if len(items) >= total:
            break
        if not batch or not msg.get("next-cursor"):
            raise SystemExit("Crossref snapshot ended before its reported total; rerun to retry")
        cursor = msg["next-cursor"]
    manifest = {"issn": issn, "pages": pages, "total_results": total,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "files_sha256": {p: sha256(os.path.join(raw_dir, p)) for p in pages}}
    manifest_path = os.path.join(raw_dir, f"{issn}_manifest.json")
    with open(manifest_path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(manifest_path + ".tmp", manifest_path)
    return items, n, total


def ymd(obj):
    parts = (obj or {}).get("date-parts", [[None]])[0]
    if not parts or parts[0] is None:
        return ""
    return "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(parts))


def clean(s):
    # Unescape twice: a few deposits are double-encoded (e.g. "&amp;rsquo;").
    return re.sub(r"\s+", " ", html.unescape(html.unescape(re.sub(r"<[^>]+>", " ", s or "")))).strip()


def clean_title(s):
    """Plain-text title. Each run of adjacent tags becomes a space or nothing, depending on
    what it separates (tested on every tagged title in the 15 journals, 22 October 2026):
    a space between two words ("the<i>Columbia</i>Space"), after , ; : ! ? . or ) before a
    word ("Products:<i>Analyzing"), and around < > = ("0 &lt;<i>q</i>&lt; 1"); nothing where
    a subscript or superscript opens ("M/E<sub>k</sub>/1"), inside a word in small
    capitals ("P<scp>a</scp>PILO"), or next to a space. A closing subscript or superscript
    before a letter gives a space. A trailing footnote marker in superscript is dropped."""
    s = re.sub(r"<sup>\s*[\d*†‡§]+\s*</sup>\s*$", "", s or "")
    out, pos = [], 0
    for m in re.finditer(r"(?:<[^>]+>)+", s):
        out.append(s[pos:m.start()])
        before, after = s[:m.start()], s[m.end():]
        tags = re.findall(r"<\s*(/?)\s*([\w:.-]+)", m.group(0))
        names = {n.lower().split(":")[-1] for _, n in tags}
        a, b = before[-1:], after[:1]
        word_a = bool(a) and bool(re.match(r"[\ẁ-ͯ]", a))
        word_b = bool(b) and bool(re.match(r"\w", b))
        opening_math = any(not c and n.lower() in ("sub", "sup") for c, n in tags)
        closing_math = any(c and n.lower() in ("sub", "sup") for c, n in tags)
        if not a or not b or a.isspace() or b.isspace():
            sep = ""
        elif names & {"scp", "sc"} and word_a and word_b:
            sep = ""
        elif opening_math:
            sep = ""
        elif closing_math:
            sep = " " if b.isalpha() else ""
        elif (word_a or a in ",;:!?.)") and word_b:
            sep = " "
        elif (re.search(r"(&lt;|&gt;|=)$", before) and word_b) or (word_a and re.match(r"(&lt;|&gt;|=)", after)):
            sep = " "
        else:
            sep = ""
        out.append(sep)
        pos = m.end()
    out.append(s[pos:])
    return clean("".join(out))


def jats_to_text(s):
    if not s:
        return ""
    s = re.sub(r"<jats:title>\s*abstract\s*</jats:title>", " ", s, flags=re.I | re.S)
    paras = [clean(p) for p in re.split(r"</jats:p>|</jats:sec>", s)]
    return "\n\n".join(p for p in paras if p)


# Heuristic item-kind tags from the title, first match wins; documented in the README.
KIND_RULES = [
    ("test_record", r"^test$"),
    ("retraction", r"\bretract"),
    ("correction", r"\b(erratum|errata|corrigendum)\b|^correction\b|\bcorrection to\b"),
    ("author_bios", r"\babout (the )?authors?\b"),
    ("call", r"\bcall for (papers|proposals|science|nominations)\b"),
    ("reviewer_list", r"\b(reviewers|referees)\b.*\b(thank|acknowledg|list)|\b(thank|acknowledg)\w*\b.*\b(reviewers|referees)\b"),
    ("index", r"\bauthor index\b|\bsubject index\b|^index\b|\bindex to volume\b"),
    ("front_back_matter", r"^(front|back) matter\b|^volume information\b|^issue information\b|^masthead\b|^editorial board\b|^announcements?\b|^(table of )?contents\b|^(publications|books) received\b"),
    ("book_review", r"^book reviews?\b|\bbook review\b|^review of\b"),
    ("editorial", r"\beditorial\b|\bfrom the editors?\b|\beditor'?s (note|introduction|comments?|essay|forum)\b|\bintroduction to the special (issue|section|research forum)\b|\bspecial issue introduction\b|^introduction to (part|the focused issue|focused issue)\b|\bfocused issue\b"),
    ("crossroads", r"^crossroads\b"),
    ("perspective", r"^perspective\s*([—–:-]|$)"),
    ("commentary", r"\bcommentary\b|\bcomment on\b|^comment\b|\breply to\b|^reply\b|\bresponse to\b|\brejoinder\b|^dialogue\b"),
]


def kind_guess(title):
    t = (title or "").lower()
    for kind, pat in KIND_RULES:
        if re.search(pat, t):
            return kind
    return "article"


# Kinds that are not papers: front and back matter, notices.
FRONT_KINDS = {"author_bios", "front_back_matter", "call", "index", "correction", "reviewer_list", "test_record", "retraction", "book_review"}
PLACEHOLDER_WORDS = 30  # short text is flagged for scrutiny, not automatically removed

def load_review(corpus, slug):
    """Decisions made by hand for one journal, kept in data/<slug>/review.json:
    "duplicates": {second DOI: {"kept": DOI, "note": why}}, "kinds": {DOI: {"kind", "note"}},
    "abstract_rejections": {DOI: {"note"}} (used by scripts/fill_abstract_gaps.py)."""
    path = os.path.join(corpus, "data", slug, "review.json")
    review = {"duplicates": {}, "kinds": {}, "abstract_rejections": {}}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            review.update(json.load(f))
    allowed = FRONT_KINDS | {"article", "perspective", "crossroads", "commentary", "editorial"}
    for section in ("duplicates", "kinds", "abstract_rejections", "abstract_accepts"):
        decisions = review.setdefault(section, {})
        if not isinstance(decisions, dict):
            raise ValueError(f"review.json {section} must be an object")
        normalized = {}
        for doi, decision in decisions.items():
            if not isinstance(decision, dict) or not isinstance(decision.get("note"), str) or not decision["note"].strip():
                raise ValueError(f"review.json {section} requires a nonempty note for every decision")
            key = normalize_doi(doi)
            if key in normalized:
                raise ValueError(f"review.json {section} contains repeated normalized DOI {key}")
            decision = dict(decision)
            if section == "duplicates":
                decision["kept"] = normalize_doi(decision.get("kept"))
            if section == "kinds" and decision.get("kind") not in allowed:
                raise ValueError(f"review.json contains an unsupported kind for {key}")
            if section == "abstract_accepts" and decision.get("source") not in {"openalex", "semanticscholar"}:
                raise ValueError(f"review.json contains an unsupported abstract source for {key}")
            normalized[key] = decision
        review[section] = normalized
    return review


def author_fields(authors):
    names, orcids, affs = [], [], []
    for a in authors or []:
        name = a.get("name") or ", ".join(x for x in (a.get("family"), a.get("given")) if x)
        names.append(name)
        orcids.append((a.get("ORCID") or "").replace("http://orcid.org/", "").replace("https://orcid.org/", ""))
        aff = " | ".join(clean(x.get("name", "")).rstrip(";") for x in a.get("affiliation") or [] if x.get("name"))
        affs.append(f"{name}: {aff}" if aff else "")
    return names, orcids, affs


def to_row(item, j, found_via, review):
    title = clean_title(" ".join(item.get("title") or []))
    abstract = jats_to_text(item.get("abstract"))
    names, orcids, affs = author_fields(item.get("author"))
    print_d, online_d, issued_d = ymd(item.get("published-print")), ymd(item.get("published-online")), ymd(item.get("issued"))
    pages = item.get("page") or ""
    doi = normalize_doi(item["DOI"])
    k = review["kinds"].get(doi)
    kind, kind_note = (k["kind"], k["note"]) if k else (kind_guess(title), "")
    dup = review["duplicates"].get(doi)
    duplicate_of, duplicate_note = (dup["kept"], dup["note"]) if dup else ("", "")
    return {
        "journal": j["slug"],
        "journal_title": j["title"],
        "container_title": clean(" ".join(item.get("container-title") or [])),
        "publisher": j["publisher"],
        "utd24": j["utd24"],
        "ft50_2016": j["ft50_2016"],
        "ft50_2026": j["ft50_2026"],
        "doi": doi,
        "doi_prefix": doi.split("/")[0],
        "url": item.get("URL", ""),
        "volume": item.get("volume", ""),
        "issue": item.get("issue", ""),
        "pages": pages,
        "first_page": pages.split("-")[0] if pages else "",
        "print_date": print_d,
        "online_date": online_d,
        "issued_date": issued_d,
        "year": (print_d or issued_d)[:4],
        "in_issue": bool(item.get("volume") and item.get("issue")),
        "type": item.get("type", ""),
        "title": title,
        "subtitle": clean_title(" ".join(item.get("subtitle") or [])),
        "n_authors": len(names),
        "authors": "; ".join(names),
        "orcids": "; ".join(orcids) if any(orcids) else "",
        "affiliations": "; ".join(affs) if any(affs) else "",
        "abstract": abstract.replace("\n\n", " "),
        "abstract_source": "crossref" if abstract else "",
        "has_abstract": bool(abstract),
        "abstract_words": len(abstract.split()),
        "abstract_placeholder": bool(abstract) and len(abstract.split()) < PLACEHOLDER_WORDS,
        "kind_guess": kind,
        "kind_note": kind_note,
        "reference_count": item.get("reference-count", ""),
        "references_deposited": len(item.get("reference") or []),
        "cited_by_crossref": item.get("is-referenced-by-count", ""),
        "license_urls": "; ".join(sorted({l.get("URL", "") for l in item.get("license") or []})),
        "update_to": json.dumps(item.get("update-to"), ensure_ascii=False) if item.get("update-to") else "",
        "relations": json.dumps(item.get("relation"), ensure_ascii=False) if item.get("relation") else "",
        "found_via_issns": " ".join(found_via),
        "dup_candidate_of": "",
        "duplicate_of": duplicate_of,
        "duplicate_note": duplicate_note,
    }


def num(s, default):
    d = re.sub(r"\D", "", s or "")
    return int(d) if d else default


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_journal(j, corpus):
    raw_dir = os.path.join(corpus, "raw", "crossref", j["slug"])
    os.makedirs(raw_dir, exist_ok=True)
    print(f"{j['title']}", file=sys.stderr)
    by_doi, found, per_issn = {}, defaultdict(list), {}
    for issn in j["issns"]:
        items, calls, total = download_issn(issn, raw_dir)
        per_issn[issn] = {"total_results": total, "received": len(items), "calls": calls}
        for it in items:
            doi = normalize_doi(it["DOI"])
            by_doi.setdefault(doi, it)

            if issn not in found[doi]:
                found[doi].append(issn)
    # Containers, not content: issue-level DOIs and the journal's own DOI.
    containers = {"journal-issue", "journal", "journal-volume"}
    records = [it for d, it in by_doi.items() if it.get("type") not in containers]
    issue_level = sorted(d for d, it in by_doi.items() if it.get("type") in containers)
    review = load_review(corpus, j["slug"])
    record_dois = {normalize_doi(it["DOI"]) for it in records}
    unknown = set().union(*(set(review[k]) for k in ("duplicates", "kinds", "abstract_rejections", "abstract_accepts"))) - record_dois
    if unknown:
        raise SystemExit(f"review.json names DOIs not in {j['slug']}: {sorted(unknown)[:5]}")
    for second, decision in review["duplicates"].items():
        kept = decision["kept"]
        if kept not in record_dois or kept == second or kept in review["duplicates"]:
            raise SystemExit(f"invalid duplicate target for {second}: expected a retained DOI in this journal")
    rows = [to_row(it, j, found[normalize_doi(it["DOI"])], review) for it in records]
    rows.sort(key=lambda r: (num(r["volume"], 9999), num(r["issue"], 99), num(r["first_page"], 0), r["online_date"], r["doi"]))

    # Same article under two DOIs (e.g. an archive DOI and a publisher DOI): flag, never drop.
    seen = {}
    for r in rows:
        key = (re.sub(r"\W+", "", r["title"].lower())[:80], r["volume"], r["issue"], r["first_page"])
        if key[0] and r["volume"] and re.search(r"\d", r["first_page"]) and key in seen:
            r["dup_candidate_of"] = seen[key]
        else:
            seen.setdefault(key, r["doi"])

    order = {r["doi"]: i for i, r in enumerate(rows)}
    records.sort(key=lambda it: order[normalize_doi(it["DOI"])])
    out_dir = os.path.join(corpus, "data", j["slug"])
    os.makedirs(out_dir, exist_ok=True)
    jsonl = os.path.join(out_dir, "records.jsonl.gz")
    with gz_text(jsonl) as f:
        for it in records:
            rec = dict(it)
            rec["abstract_text"] = jats_to_text(it.get("abstract"))
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    csv_path = os.path.join(out_dir, "records.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else list(to_row({"DOI": ""}, j, [], review).keys()))
        w.writeheader()
        w.writerows(rows)

    # Papers: not front or back matter, and not a second registration of another record.
    papers = [r for r in rows if r["kind_guess"] not in FRONT_KINDS and not r["duplicate_of"]]
    decade = defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in rows:
        if r["year"]:
            decade[f"{r['year'][:3]}0s"][0] += 1
            decade[f"{r['year'][:3]}0s"][1] += r["has_abstract"]
    for r in papers:
        if r["year"]:
            v = decade[f"{r['year'][:3]}0s"]
            v[2] += 1
            v[3] += r["has_abstract"]
            v[4] += r["references_deposited"] > 0
    vols = sorted({num(r["volume"], 0) for r in rows if r["volume"]})
    summary = {
        "title": j["title"], "publisher": j["publisher"], "utd24": j["utd24"],
        "ft50_2016": j["ft50_2016"], "ft50_2026": j["ft50_2026"],
        "issns_queried": per_issn,
        "records": len(rows),
        "issue_level_records_excluded": issue_level,
        "types": dict(Counter(r["type"] for r in rows)),
        "container_titles": dict(Counter(r["container_title"] for r in rows)),
        "doi_prefixes": dict(Counter(r["doi_prefix"] for r in rows)),
        "years": [min((r["year"] for r in rows if r["year"]), default=""), max((r["year"] for r in rows if r["year"]), default="")],
        "volumes": [vols[0], vols[-1]] if vols else [],
        "missing_volume_numbers": sorted(set(range(vols[0], vols[-1] + 1)) - set(vols)) if vols else [],
        "without_volume_issue": sum(not r["in_issue"] for r in rows),
        "ahead_of_print_articles": sum(not r["in_issue"] for r in papers),
        "with_abstract": sum(r["has_abstract"] for r in rows),
        "with_references_deposited": sum(r["references_deposited"] > 0 for r in rows),
        "dup_candidates": sum(bool(r["dup_candidate_of"]) for r in rows),
        "duplicates_reviewed": sum(bool(r["duplicate_of"]) for r in rows),
        "distinct_records": len(rows) - sum(bool(r["duplicate_of"]) for r in rows),
        "papers": len(papers),
        "papers_with_abstract": sum(r["has_abstract"] for r in papers),
        "papers_with_abstract_of_30_words_or_more": sum(r["has_abstract"] and not r["abstract_placeholder"] for r in papers),
        "papers_with_reference_list": sum(r["references_deposited"] > 0 for r in papers),
        "abstract_placeholders": sum(r["abstract_placeholder"] for r in rows),
        "kind_guess": dict(Counter(r["kind_guess"] for r in rows).most_common()),
        "kinds_reviewed": sum(bool(r["kind_note"]) for r in rows),
        "by_decade": {k: {"records": v[0], "with_abstract": v[1], "papers": v[2], "papers_with_abstract": v[3],
                          "papers_with_reference_list": v[4]} for k, v in sorted(decade.items())},
        "files_sha256": {"records.jsonl.gz": sha256(jsonl), "records.csv": sha256(csv_path)},
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return rows, summary


def gz_text(path):
    # mtime=0 and no stored file name, so identical content gives an identical file.
    return io.TextIOWrapper(gzip.GzipFile(filename="", mode="wb", fileobj=open(path, "wb"), mtime=0), encoding="utf-8")


def main(corpus, only):
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    os.makedirs(os.path.join(corpus, "data"), exist_ok=True)
    if not COMBINE_ONLY:
        for j in JOURNALS:
            if not only or j["slug"] in only:
                run_journal(j, corpus)
    if NO_COMBINE:
        return
    # Combine registered journals already present in this output directory.
    all_rows, summaries = [], {}
    for j in JOURNALS:
        d = os.path.join(corpus, "data", j["slug"])
        if not os.path.exists(os.path.join(d, "records.csv")):
            continue
        with open(os.path.join(d, "records.csv"), encoding="utf-8") as f:
            all_rows.extend(csv.DictReader(f))
        with open(os.path.join(d, "summary.json"), encoding="utf-8") as f:
            summaries[j["slug"]] = json.load(f)
    # A DOI should belong to one journal only; report any overlap.
    owners = defaultdict(list)
    for r in all_rows:
        owners[r["doi"]].append(r["journal"])
    cross = {d: js for d, js in owners.items() if len(js) > 1}
    csv_path = os.path.join(corpus, "data", "journals_crossref.csv.gz")
    with gz_text(csv_path) as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()) if all_rows else ["journal", "doi", "abstract", "abstract_source"])
        w.writeheader()
        w.writerows(all_rows)
    out = {"built_utc": started, "offline_rebuild": OFFLINE, "api": API, "rows_per_call": ROWS, "journals": summaries,
           "total_records": len(all_rows), "dois_in_more_than_one_journal": cross,
           "csv_sha256": sha256(csv_path)}
    with open(os.path.join(corpus, "data", "summary.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"{'journal':<46}{'records':>8}{'CR_abs':>8}{'years':>12}{'ahead':>7}{'dups':>6}{'papers':>8}")
    for s in summaries.values():
        print(f"{s['title']:<46}{s['records']:>8}{s['with_abstract']:>8}{'-'.join(s['years']):>12}"
              f"{s['ahead_of_print_articles']:>7}{s['dup_candidates']:>6}{s['papers']:>8}")
    print("CR_abs counts the initial Crossref abstract fields; final filled counts are in each summary's abstract_gaps section.")
    print(f"total records {len(all_rows)}; DOIs in more than one journal: {len(cross)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", help="output directory, reused on later runs")
    parser.add_argument("journals", nargs="*", help="journal slugs from the registry")
    parser.add_argument("--registry", help="custom JSON registry path")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--combine-only", action="store_true")
    parser.add_argument("--no-combine", action="store_true")
    parser.add_argument("--all", action="store_true", help="fetch every registry entry with default=true")
    args = parser.parse_intermixed_args()
    try:
        JOURNALS = load_registry(args.registry)
        available = {j["slug"] for j in JOURNALS}
        unknown = set(args.journals) - available
        if unknown:
            parser.error("unknown journal(s): " + ", ".join(sorted(unknown)))
        if args.all and args.journals:
            parser.error("choose --all or explicit journal slugs")
        if not args.combine_only and not args.all and not args.journals:
            parser.error("choose a journal slug or --all")
        chosen = set(args.journals) if args.journals else {j["slug"] for j in JOURNALS if j.get("default", True) and j.get("retrieval_available", True)}
        unavailable = [j["slug"] for j in JOURNALS if j["slug"] in chosen and not j.get("retrieval_available", True)]
        if unavailable and not args.offline and not args.combine_only:
            parser.error("Crossref ISSN retrieval unavailable: " + ", ".join(unavailable) + "; see registry notes")
        if not chosen and not args.combine_only:
            parser.error("the registry has no default journals")
        OFFLINE, COMBINE_ONLY, NO_COMBINE = args.offline, args.combine_only, args.no_combine
        main(args.corpus, chosen)
    except (APIError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
