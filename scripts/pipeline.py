"""Collect journal metadata and screened abstract candidates, or replay saved inputs.

Examples:
  python3 scripts/pipeline.py --list
  python3 scripts/pipeline.py --output runs/example organization-science --references
  python3 scripts/pipeline.py --output runs/example organization-science --references --offline

Retrieval and screening do not certify abstract content or complete publisher coverage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import APIError, DEFAULT_REGISTRY, load_registry
import build_references
import enrich_openalex
import fetch_journals
import fill_abstract_gaps


def run(output, journals, registry=None, offline=False, references=False):
    entries = load_registry(registry)
    known = {entry["slug"]: entry for entry in entries}
    unknown = set(journals) - set(known)
    if unknown:
        raise ValueError("unknown journal(s): " + ", ".join(sorted(unknown)))
    unavailable = [slug for slug in journals if not known[slug].get("retrieval_available", True)]
    if unavailable and not offline:
        raise ValueError("Crossref ISSN retrieval is unavailable for: " + ", ".join(unavailable) +
                         "; see the registry retrieval note and choose a supported journal")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fetch_journals.JOURNALS = entries
    fetch_journals.OFFLINE = offline
    fetch_journals.COMBINE_ONLY = False
    fetch_journals.NO_COMBINE = True
    for slug in journals:
        fetch_journals.run_journal(known[slug], str(output))
        enrich_openalex.main(str(output), slug, offline, 0)
        fill_abstract_gaps.main(str(output), slug, offline)
        if references:
            build_references.main(str(output), slug)
    fetch_journals.COMBINE_ONLY = True
    fetch_journals.NO_COMBINE = False
    fetch_journals.main(str(output), set(journals))
    # Relative paths only, with every saved response available to audit or replay.
    sources = {}
    for provider in ("crossref", "openalex", "semanticscholar"):
        for slug in journals:
            folder = output / "raw" / provider / slug
            if folder.exists():
                for path in sorted(folder.rglob("*")):
                    if path.is_file():
                        sources[str(path.relative_to(output))] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"workflow_version": "0.1", "journal_slugs": list(journals), "offline": offline,
                "reference_stage": references, "registry_sha256": hashlib.sha256(Path(registry or DEFAULT_REGISTRY).read_bytes()).hexdigest(),
                "saved_source_sha256": sources,
                "note": "Saved source files include any incomplete attempt snapshots; Crossref manifests identify active snapshots."}
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Saved outputs: {output / 'data'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("journals", nargs="*", help="one or more journal slugs")
    parser.add_argument("--output", default="runs/corpus", help="output/cache directory (default: runs/corpus)")
    parser.add_argument("--registry", help="custom JSON journal registry")
    parser.add_argument("--offline", action="store_true", help="use only saved responses; missing inputs stop the run")
    parser.add_argument("--references", action="store_true", help="also build references.csv.gz")
    parser.add_argument("--list", action="store_true", help="list configured journals and their evidence status")
    parser.add_argument("--all", action="store_true", help="select all default journals in the registry")
    parser.add_argument("--profile", choices=["utd24", "ft50-2016", "ft50-2026"], help="select a ranking profile, including untested journals")
    args = parser.parse_args()
    try:
        entries = load_registry(args.registry)
        if args.list:
            for entry in entries:
                print(f"{entry['slug']:<48} {entry.get('evidence_status', 'configured_only'):<26} {entry['title']}")
            return
        if sum((bool(args.journals), args.all, bool(args.profile))) != 1:
            parser.error("choose journal slugs, --all, or --profile (use --list to inspect the registry)")
        if args.all:
            selected = [e["slug"] for e in entries if e.get("default", True) and e.get("retrieval_available", True)]
        elif args.profile:
            key = args.profile.replace("-", "_")
            selected = [e["slug"] for e in entries if e[key] and e.get("retrieval_available", True)]
            for entry in entries:
                if entry[key] and not entry.get("retrieval_available", True):
                    print(f"Skipping {entry['slug']}: Crossref ISSN retrieval unavailable (see registry)", file=sys.stderr)
        else:
            selected = list(dict.fromkeys(args.journals))
        if not selected:
            parser.error("the selection contains no retrievable journals")
        run(args.output, selected, args.registry, args.offline, args.references)
    except (APIError, ValueError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
