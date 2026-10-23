"""Synthetic regression checks; retained fixtures contain no publisher abstracts.

Run: python3 -B -m unittest discover -s tests -v
Temporary fixture directories remain available for inspection; no file deletion is used.
"""
import contextlib
import csv
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common
import demo
import enrich_openalex as enrich
import fetch_journals as fetch
import fill_abstract_gaps as fill
import pipeline

FIXTURES = Path(tempfile.mkdtemp(prefix="journal-workflow-tests-"))


def read_rows(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return {r["doi"]: r for r in csv.DictReader(handle)}


class PipelineTests(unittest.TestCase):
    def fixture(self):
        folder = FIXTURES / self._testMethodName
        registry = demo.create_fixture(folder)
        return folder, registry

    def run_offline(self, root, registry):
        with patch("urllib.request.urlopen", side_effect=AssertionError("offline attempted network")), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            pipeline.run(root, [demo.SLUG], registry, offline=True, references=True)

    def test_all_stages_offline_source_priority_reviews_and_replay(self):
        root, registry = self.fixture()
        raw_before = {str(p.relative_to(root)): p.read_bytes() for p in (root / "raw").rglob("*.gz")}
        self.run_offline(root, registry)
        data = root / "data" / demo.SLUG
        rows = read_rows(data / "records.csv")
        gaps = read_rows(data / "abstract_gaps.csv")
        self.assertEqual(len(rows), 12)
        doi = lambda name: demo.PREFIX + name
        self.assertNotIn(doi("issue"), rows)
        self.assertEqual(rows[doi("crossref")]["found_via_issns"], "0000-0000 0000-0019")
        self.assertEqual(rows[doi("crossref")]["abstract_source"], "crossref")
        self.assertEqual(rows[doi("openalex")]["abstract_source"], "openalex")
        self.assertEqual(rows[doi("scholar")]["abstract_source"], "semanticscholar")
        self.assertEqual(rows[doi("short")]["abstract"], demo.SHORT)
        self.assertEqual(rows[doi("short")]["abstract_placeholder"], "True")
        self.assertEqual(rows[doi("replacement")]["abstract"], demo.TEXT)
        self.assertEqual(gaps[doi("replacement")]["crossref_text"], demo.SHORT)
        self.assertEqual(rows[doi("accepted")]["abstract"], demo.FLAGGED)
        for name in ["flagged", "rejected", "mismatch", "duplicate", "front", "kind-override"]:
            self.assertEqual(rows[doi(name)]["abstract"], "", name)
        self.assertIn("openalex:other_work", gaps[doi("mismatch")]["flags"])
        self.assertIn("semanticscholar:other_work", gaps[doi("mismatch")]["flags"])
        self.assertEqual(rows[doi("duplicate")]["duplicate_of"], doi("crossref"))
        with gzip.open(data / "references.csv.gz", "rt", encoding="utf-8") as handle:
            references = list(csv.DictReader(handle))
        self.assertEqual(len(references), 3)
        self.assertEqual(sum(r["paper_doi"] == doi("crossref") for r in references), 2)
        summary = json.loads((data / "summary.json").read_text())
        self.assertEqual(summary["papers"], 9)
        self.assertEqual(summary["abstract_gaps"]["papers_with_abstract_after_fill"], 6)
        self.assertEqual(summary["references"]["openalex_lists_skipped_doi_mismatch"], 1)
        before = {p.name: p.read_bytes() for p in data.iterdir() if p.is_file()}
        combined = (root / "data/journals_crossref.csv.gz").read_bytes()
        self.run_offline(root, registry)
        self.assertEqual(before, {p.name: p.read_bytes() for p in data.iterdir() if p.is_file()})
        self.assertEqual(combined, (root / "data/journals_crossref.csv.gz").read_bytes())
        self.assertEqual(raw_before, {str(p.relative_to(root)): p.read_bytes() for p in (root / "raw").rglob("*.gz")})

    def test_unknown_slug_fails_without_network_or_outputs(self):
        root, registry = self.fixture()
        with patch("urllib.request.urlopen", side_effect=AssertionError("unexpected network")), self.assertRaisesRegex(ValueError, "unknown journal"):
            pipeline.run(root / "new-output", ["not-a-journal"], registry)
        self.assertFalse((root / "new-output").exists())

    def test_empty_journal_supported(self):
        root, registry = self.fixture()
        for issn in demo.JOURNAL["issns"]:
            with gzip.open(root / "raw/crossref" / demo.SLUG / f"{issn}_page_01.json.gz", "wt") as handle:
                json.dump({"message": {"total-results": 0, "items": []}}, handle)
        (root / "data" / demo.SLUG / "review.json").write_text("{}")
        self.run_offline(root, registry)
        self.assertEqual(read_rows(root / "data" / demo.SLUG / "records.csv"), {})

    def test_missing_cache_is_not_silently_treated_as_missing_abstract(self):
        root, registry = self.fixture()
        self.run_offline(root, registry)
        cache = root / "raw/semanticscholar" / demo.SLUG / "abstract_batch.json.gz"
        with gzip.open(cache, "wt") as handle:
            json.dump({"ids": [], "response": []}, handle)
        records = root / "data" / demo.SLUG / "records.csv"
        before = records.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(SystemExit, "Semantic Scholar lookups missing"):
            fill.main(str(root), demo.SLUG, offline=True)
        self.assertEqual(before, records.read_bytes())

    def test_openalex_failure_checkpoints_success_and_resumes(self):
        root, registry = self.fixture()
        self.run_offline(root, registry)
        cache = root / "raw/openalex" / demo.SLUG / "works.jsonl.gz"
        with gzip.open(cache, "wt") as handle:
            handle.write("")
        response = ("not_found", None, {})
        with patch.object(enrich, "get", side_effect=[response, common.APIError("openalex: HTTP 401")]) as lookup, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(common.APIError):
                enrich.main(str(root), demo.SLUG, False, 0)
        self.assertEqual(lookup.call_count, 2)
        with gzip.open(cache, "rt") as handle:
            saved = [json.loads(line) for line in handle]
        self.assertEqual(len(saved), 1)
        with patch.object(enrich, "get", return_value=response) as lookup, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            enrich.main(str(root), demo.SLUG, False, 0)
        self.assertEqual(lookup.call_count, 11)

    def test_invalid_semantic_batch_is_not_cached(self):
        root, registry = self.fixture()
        self.run_offline(root, registry)
        cache = root / "raw/semanticscholar" / demo.SLUG / "abstract_batch.json.gz"
        with gzip.open(cache, "wt") as handle:
            json.dump({"ids": [], "response": []}, handle)
        before = cache.read_bytes()
        with patch.object(fill, "request", return_value={"error": "failed"}), contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(common.APIError, "invalid batch"):
            fill.main(str(root), demo.SLUG, offline=False)
        self.assertEqual(before, cache.read_bytes())

    def test_duplicate_target_must_be_retained_journal_record(self):
        root, registry = self.fixture()
        path = root / "data" / demo.SLUG / "review.json"
        review = json.loads(path.read_text())
        review["duplicates"][demo.PREFIX + "duplicate"]["kept"] = demo.PREFIX + "absent"
        path.write_text(json.dumps(review))
        fetch.OFFLINE = True
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(SystemExit, "invalid duplicate target"):
            fetch.run_journal(demo.JOURNAL, str(root))
        self.assertFalse((path.parent / "records.csv").exists())

    def test_manifest_detects_modified_cached_page(self):
        folder = FIXTURES / self._testMethodName
        folder.mkdir()
        payload = json.dumps({"message": {"total-results": 1, "items": [{"DOI": "10.0000/synthetic"}]}}).encode()
        fetch.OFFLINE = False
        with patch.object(fetch, "get", return_value=payload):
            fetch.download_issn("0000-0000", str(folder))
        manifest = json.loads((folder / "0000-0000_manifest.json").read_text())
        page = folder / manifest["pages"][0]
        page.write_bytes(page.read_bytes() + b"changed")
        with self.assertRaisesRegex(SystemExit, "integrity check failed"):
            fetch.load_raw("0000-0000", str(folder))


class TransportTests(unittest.TestCase):
    def test_auth_failure_is_not_retried_or_logged_with_secrets(self):
        error = urllib.error.HTTPError("https://example.invalid/?api_key=secret-value", 401, "secret-value", {}, None)
        with patch.dict("os.environ", {"OPENALEX_API_KEY": "secret-value"}), patch.object(common, "_throttle"), patch("urllib.request.urlopen", side_effect=error) as request:
            with self.assertRaises(common.APIError) as caught:
                common.request_json("https://api.openalex.org/works/example", "openalex")
        self.assertEqual(request.call_count, 1)
        self.assertNotIn("secret-value", str(caught.exception))
        self.assertEqual(request.call_args.args[0].get_header("Authorization"), "Bearer secret-value")

    def test_404_is_only_not_found_when_explicitly_allowed(self):
        error = urllib.error.HTTPError("https://example.invalid", 404, "not found", {}, None)
        with patch.object(common, "_throttle"), patch("urllib.request.urlopen", side_effect=error):
            self.assertIsNone(common.request_json("https://api.openalex.org/works/example", "openalex", allow_not_found=True))
            with self.assertRaises(common.APIError):
                common.request_json("https://api.semanticscholar.org/graph/v1/paper/batch", "semanticscholar")

    def test_rate_limit_honors_retry_after(self):
        error = urllib.error.HTTPError("https://example.invalid", 429, "slow down", {"Retry-After": "120"}, None)
        response = io.BytesIO(b'{"ok": true}')
        with patch.object(common, "_throttle"), patch("urllib.request.urlopen", side_effect=[error, response]), patch.object(common.time, "monotonic", return_value=1000):
            result = common.request_json("https://example.invalid", "test-provider")
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(common._next["test-provider"], 1120)
        self.assertEqual(common.retry_after({"Retry-After": "not a date"}), 0)


if __name__ == "__main__":
    print(f"Synthetic fixtures retained at: {FIXTURES}")
    unittest.main(verbosity=2)
