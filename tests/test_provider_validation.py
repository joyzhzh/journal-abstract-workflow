"""Provider shape, cache-repair and real urllib redirect regressions; synthetic data only.

No network sockets are opened. Temporary fixtures remain available for inspection.
"""
import contextlib
import csv
import email.message
import gzip
import io
import itertools
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
import urllib.response

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common
import demo
import enrich_openalex as enrich
import fetch_journals as fetch
import fill_abstract_gaps as fill

FIXTURES = Path(tempfile.mkdtemp(prefix="journal-provider-validation-"))
_COUNTER = itertools.count()


class RedirectPrivacyTests(unittest.TestCase):
    def make_wire(self, origin, target):
        seen = []

        class SyntheticWire(urllib.request.BaseHandler):
            handler_order = 100

            def https_open(self, request):
                seen.append({"url": request.full_url, "headers": dict(request.header_items())})
                headers = email.message.Message()
                code = 302 if len(seen) == 1 else 200
                if code == 302:
                    headers["Location"] = target
                response = urllib.response.addinfourl(io.BytesIO(b'{"synthetic": true}'), headers, request.full_url, code)
                response.msg = "Found" if code == 302 else "OK"
                return response

            http_open = https_open

        # Real urllib error processing and redirect machinery, stopped at this fake wire.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), common.SafeRedirectHandler(), SyntheticWire())
        return opener, seen

    def test_cross_origin_and_downgrade_never_receive_credentials(self):
        for provider, variable, origin in [
            ("openalex", "OPENALEX_API_KEY", "https://api.openalex.org/works/example"),
            ("semanticscholar", "SEMANTIC_SCHOLAR_API_KEY", "https://api.semanticscholar.org/graph/v1/paper/batch"),
        ]:
            for target in ["https://collector.example.invalid/capture", "http://collector.example.invalid/capture",
                           origin.replace("https:", "http:"), origin.replace(".org/", ".org:444/")]:
                opener, seen = self.make_wire(origin, target)
                with self.subTest(provider=provider, target=target), patch.dict(os.environ, {variable: "SYNTHETIC_PRIVATE_KEY"}, clear=True), patch.object(common, "_opener", opener), patch.object(common, "_throttle"):
                    with self.assertRaises(common.APIError) as caught:
                        common.request_bytes(origin, provider, data=b'{}' if provider == "semanticscholar" else None, attempts=1)
                self.assertEqual(len(seen), 1)
                self.assertEqual(seen[0]["url"], origin)
                self.assertIn("SYNTHETIC_PRIVATE_KEY", str(seen[0]["headers"]))
                self.assertNotIn("SYNTHETIC_PRIVATE_KEY", str(caught.exception))
                self.assertNotIn("collector.example.invalid", str(caught.exception))

    def test_same_https_origin_redirect_preserves_authentication(self):
        origin = "https://api.openalex.org/works/example"
        target = "https://api.openalex.org:443/works/final"
        opener, seen = self.make_wire(origin, target)
        with patch.dict(os.environ, {"OPENALEX_API_KEY": "SYNTHETIC_PRIVATE_KEY"}, clear=True), patch.object(common, "_opener", opener), patch.object(common, "_throttle"):
            self.assertEqual(json.loads(common.request_bytes(origin, "openalex", attempts=1)), {"synthetic": True})
        self.assertEqual(len(seen), 2)
        self.assertTrue(all("SYNTHETIC_PRIVATE_KEY" in str(request["headers"]) for request in seen))

    def test_contact_query_redirect_is_also_confined_to_origin(self):
        origin = "https://api.crossref.org/journals/0000-0000/works"
        opener, seen = self.make_wire(origin, "https://collector.example.invalid/capture")
        with patch.dict(os.environ, {"CROSSREF_MAILTO": "synthetic-contact@example.invalid"}, clear=True), patch.object(common, "_opener", opener), patch.object(common, "_throttle"):
            with self.assertRaises(common.APIError) as caught:
                common.request_bytes(origin, "crossref", attempts=1)
        self.assertEqual(len(seen), 1)
        self.assertNotIn("synthetic-contact", str(caught.exception))


class ProviderValidationTests(unittest.TestCase):
    def fixture(self):
        root = FIXTURES / (self._testMethodName + "-" + str(next(_COUNTER)))
        demo.create_fixture(root)
        fetch.OFFLINE = True
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            fetch.run_journal(demo.JOURNAL, str(root))
        return root

    def s2_path(self, root):
        return root / "raw/semanticscholar" / demo.SLUG / "abstract_batch.json.gz"

    def read_s2(self, root):
        with gzip.open(self.s2_path(root), "rt") as handle:
            saved = json.load(handle)
        return dict(zip(saved["ids"], saved["response"]))

    def write_s2(self, root, entries):
        with gzip.open(self.s2_path(root), "wt") as handle:
            json.dump({"ids": list(entries), "response": list(entries.values())}, handle)

    def run_fill(self, root, offline):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            fill.main(str(root), demo.SLUG, offline)

    def test_semantic_scholar_shapes_distinguish_empty_success_from_error(self):
        for valid in [None, {"abstract": None}, {"abstract": ""}, {"abstract": demo.TEXT},
                      {"paperId": "synthetic", "title": "Synthetic title", "abstract": None, "externalIds": {"DOI": None}}]:
            with self.subTest(value=valid):
                self.assertTrue(common.valid_semantic_scholar_paper(valid))
        for invalid in [{}, {"error": "temporary"}, {"title": "Synthetic title"}, {"abstract": [], "paperId": "synthetic"},
                        {"abstract": None, "error": "temporary"}, {"abstract": demo.TEXT, "externalIds": []},
                        {"abstract": demo.TEXT, "externalIds": {"DOI": 123}}, {"abstract": demo.TEXT, "title": {}},
                        {"abstract": demo.TEXT, "paperId": []}]:
            with self.subTest(value=invalid):
                self.assertFalse(common.valid_semantic_scholar_paper(invalid))

    def test_cached_semantic_error_is_retryable_and_original_is_preserved(self):
        root = self.fixture()
        doi = demo.PREFIX + "scholar"
        entries = self.read_s2(root)
        entries[doi] = {"error": "upstream temporarily unavailable"}
        self.write_s2(root, entries)
        original = self.s2_path(root).read_bytes()
        records = root / "data" / demo.SLUG / "records.csv"
        before = records.read_bytes()
        with patch.object(common._opener, "open", side_effect=AssertionError("offline network")), self.assertRaisesRegex(SystemExit, "Semantic Scholar lookups missing or invalid"):
            self.run_fill(root, True)
        self.assertEqual(original, self.s2_path(root).read_bytes())
        self.assertEqual(before, records.read_bytes())
        replacement = {"abstract": demo.TEXT, "externalIds": {"DOI": doi}}
        with patch.object(fill, "request", return_value=[replacement]) as request:
            self.run_fill(root, False)
        self.assertEqual(json.loads(request.call_args.kwargs["data"]), {"ids": ["DOI:" + doi]})
        expected = dict(entries)
        expected[doi] = replacement
        self.assertEqual(self.read_s2(root), expected)
        archives = list((self.s2_path(root).parent / "history").glob("*.gz"))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_bytes(), original)
        with patch.object(fill, "request", side_effect=AssertionError("cached entry retried")):
            self.run_fill(root, True)

    def test_new_item_error_does_not_poison_cache_and_good_sibling_is_reused(self):
        root = self.fixture()
        scholar, short = demo.PREFIX + "scholar", demo.PREFIX + "short"
        entries = self.read_s2(root)
        entries = {doi: value for doi, value in entries.items() if doi not in {scholar, short}}
        self.write_s2(root, entries)
        records = root / "data" / demo.SLUG / "records.csv"
        before = records.read_bytes()
        with patch.object(fill, "request", return_value=[{"error": "temporary"}, None]), self.assertRaisesRegex(common.APIError, "invalid paper responses"):
            self.run_fill(root, False)
        self.assertEqual(before, records.read_bytes())
        saved = self.read_s2(root)
        self.assertNotIn(scholar, saved)
        self.assertIn(short, saved)
        self.assertIsNone(saved[short])
        self.assertTrue(all(common.valid_semantic_scholar_paper(value) for value in saved.values()))
        with patch.object(fill, "request", return_value=[{"abstract": demo.TEXT}]) as request:
            self.run_fill(root, False)
        self.assertEqual(json.loads(request.call_args.kwargs["data"]), {"ids": ["DOI:" + scholar]})

    def test_short_text_with_invalid_cache_keeps_text_and_reports_unverified_lookup(self):
        root = self.fixture()
        doi = demo.PREFIX + "short"
        entries = self.read_s2(root)
        entries[doi] = {"error": "temporary"}
        self.write_s2(root, entries)
        original = self.s2_path(root).read_bytes()
        self.run_fill(root, True)
        data = root / "data" / demo.SLUG
        with (data / "records.csv").open() as handle:
            rows = {row["doi"]: row for row in csv.DictReader(handle)}
        with (data / "abstract_gaps.csv").open() as handle:
            gaps = {row["doi"]: row for row in csv.DictReader(handle)}
        self.assertEqual(rows[doi]["abstract"], demo.SHORT)
        self.assertEqual(gaps[doi]["s2_checked"], "False")
        self.assertIn("saved response invalid; retry needed", gaps[doi]["resolution"])
        self.assertEqual(self.s2_path(root).read_bytes(), original)

    def test_openalex_ok_null_is_missing_then_repaired_without_losing_original(self):
        root = self.fixture()
        cache = root / "raw/openalex" / demo.SLUG / "works.jsonl.gz"
        doi = demo.PREFIX + "short"
        with gzip.open(cache, "rt") as handle:
            entries = [json.loads(line) for line in handle]
        for entry in entries:
            if entry["doi"] == doi:
                entry["status"] = "ok"
                entry["response"] = None
        with gzip.open(cache, "wt") as handle:
            handle.write("\n".join(json.dumps(entry) for entry in entries) + "\n")
        original = cache.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(SystemExit, "no saved OpenAlex response"):
            enrich.main(str(root), demo.SLUG, True, 0)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(SystemExit, "no OpenAlex response"):
            fill.main(str(root), demo.SLUG, True)
        self.assertEqual(cache.read_bytes(), original)
        with patch.object(enrich, "get", return_value=("not_found", None, {})) as request, contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            enrich.main(str(root), demo.SLUG, False, 0)
        self.assertEqual(request.call_count, 1)
        with gzip.open(cache, "rt") as handle:
            repaired = {entry["doi"]: entry for entry in map(json.loads, handle)}
        self.assertEqual(len(repaired), len(entries))
        self.assertEqual(repaired[doi]["status"], "not_found")
        for entry in entries:
            if entry["doi"] != doi:
                self.assertEqual(repaired[entry["doi"]], entry)
        archives = list((cache.parent / "history").glob("*.gz"))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_bytes(), original)

    def test_openalex_new_invalid_work_and_legacy_schema(self):
        invalid = demo.work("short")
        invalid["abstract_inverted_index"] = "invalid"
        with patch.object(enrich, "request_json", return_value=invalid), self.assertRaisesRegex(common.APIError, "invalid work response"):
            enrich.get("https://api.openalex.org/works/example")
        legacy = {"doi": demo.PREFIX + "short", "response": demo.work("short")}
        self.assertFalse(common.valid_openalex_record(legacy))
        self.assertTrue(common.valid_openalex_record(legacy, allow_legacy=True))
        self.assertFalse(common.valid_openalex_record({"doi": demo.PREFIX + "short", "status": "ok", "response": None}))
        self.assertTrue(common.valid_openalex_record({"doi": demo.PREFIX + "short", "status": "not_found", "response": None}))


if __name__ == "__main__":
    print(f"Retained synthetic fixtures: {FIXTURES}")
    unittest.main(verbosity=2)
