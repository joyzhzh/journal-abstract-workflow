"""Synthetic regression cases for the read-only audit; no network or article data.

Fixtures are retained in a temporary directory. Tests never delete files.
"""
import contextlib
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "audit_outputs", Path(__file__).resolve().parents[1] / "scripts" / "audit_outputs.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def record(doi="10.0000/example-a", text="", source="", **changes):
    row = {
        "journal": "example-journal", "doi": doi, "kind_guess": "article",
        "duplicate_of": "", "duplicate_note": "", "abstract": text,
        "abstract_source": source, "abstract_words": str(len(text.split())),
        "has_abstract": str(bool(text.strip())),
        "abstract_placeholder": str(bool(text.strip()) and len(text.split()) < 30),
    }
    row.update(changes)
    return row


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="journal-audit-test-"))
        self.data = self.root / "data" / "example-journal"
        self.data.mkdir(parents=True)

    def write_rows(self, rows):
        with (self.data / "records.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(record()))
            writer.writeheader()
            writer.writerows(rows)

    def write_cache(self, source, payload):
        if source == "crossref":
            path = self.data / "records.jsonl.gz"
        else:
            filename = "works.jsonl.gz" if source == "openalex" else "abstract_batch.json.gz"
            path = self.root / "raw" / source / "example-journal" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            if source == "semanticscholar":
                json.dump(payload, handle)
            else:
                for row in payload:
                    handle.write(json.dumps(row) + "\n")
        return path

    def run_audit(self):
        return audit.audit_journal(self.root, "example-journal")

    def codes(self, result, level="errors"):
        return {x["code"] for x in result[level]}

    def test_valid_counts_preserve_short_crossref_and_read_only_inputs(self):
        rows = [record(text="A short synthetic summary.", source="crossref"),
                record("10.0000/example-b", text=" ".join(["synthetic"] * 30), source="openalex"),
                record("10.0000/example-c"),
                record("10.0000/example-d", duplicate_of="10.0000/example-a", duplicate_note="Synthetic second registration."),
                record("10.0000/example-e", kind_guess="book_review")]
        self.write_rows(rows)
        self.write_cache("crossref", [{"DOI": r["doi"]} for r in rows])
        self.write_cache("openalex", [{"doi": r["doi"], "status": "ok", "response": {"id": "synthetic"}} for r in rows])
        self.write_cache("semanticscholar", {"ids": [], "response": []})
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob("*") if p.is_file()}
        result = self.run_audit()
        self.assertEqual([], result["errors"])
        self.assertEqual(5, result["counts"]["records"])
        self.assertEqual(3, result["counts"]["papers"])
        self.assertEqual(1, result["counts"]["papers_with_short_text"])
        self.assertEqual({"unreported": 1}, result["counts"]["papers_without_abstract_by_resolution"])
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})

    def test_duplicate_missing_self_chain_and_cycle_are_errors(self):
        self.write_rows([record("10.0000/a", duplicate_of="10.0000/a"),
                         record("10.0000/b", duplicate_of="10.0000/absent"),
                         record("10.0000/c", duplicate_of="10.0000/d"),
                         record("10.0000/d", duplicate_of="10.0000/c")])
        self.assertTrue({"duplicate_self_link", "duplicate_target_missing", "duplicate_target_is_duplicate"} <= self.codes(self.run_audit()))

    def test_source_word_count_boolean_and_short_fill_inconsistencies(self):
        self.write_rows([record(text="Synthetic short fill", source="openalex",
                                has_abstract="False", abstract_words="200", abstract_placeholder="False"),
                         record("10.0000/b", source="crossref"),
                         record("10.0000/c", text="Synthetic text", source="invented")])
        codes = self.codes(self.run_audit())
        self.assertTrue({"has_abstract_mismatch", "abstract_words_mismatch", "abstract_placeholder_mismatch",
                         "fill_below_minimum_words", "abstract_source_without_text", "abstract_source_missing_or_unknown"} <= codes)

    def test_missing_cache_is_limited_evidence_not_content_failure(self):
        self.write_rows([record(text="Synthetic deposited summary", source="crossref")])
        result = self.run_audit()
        self.assertEqual([], result["errors"])
        self.assertIn("source_cache_absent", self.codes(result, "warnings"))
        self.assertFalse(result["caches"]["crossref"]["present"])

    def test_failed_missing_and_unlabelled_openalex_lookups_are_visible(self):
        self.write_rows([record("10.0000/a", text=" ".join(["synthetic"] * 30), source="openalex"),
                         record("10.0000/b"), record("10.0000/c")])
        self.write_cache("openalex", [{"doi": "10.0000/a", "status": "error", "response": None},
                                      {"doi": "10.0000/b", "response": None}])
        result = self.run_audit()
        self.assertIn("used_source_cache_unavailable", self.codes(result))
        self.assertEqual({"error": 1, "missing_status": 1}, result["caches"]["openalex"]["statuses"])
        self.assertEqual(1, result["caches"]["openalex"]["record_dois_without_entry"])
        self.assertTrue({"openalex_lookups_missing", "openalex_errors_need_retry", "source_cache_unknown_status"} <= self.codes(result, "warnings"))

    def test_semantic_scholar_batch_truncation_and_null_used_response(self):
        self.write_rows([record(text=" ".join(["synthetic"] * 30), source="semanticscholar")])
        self.write_cache("semanticscholar", {"ids": ["10.0000/example-a", "10.0000/example-b"], "response": [None]})
        self.assertTrue({"source_cache_batch_length_mismatch", "used_source_cache_unavailable"} <= self.codes(self.run_audit()))

    def test_missing_resolution_is_reported_without_inventing_reason(self):
        self.write_rows([record()])
        (self.data / "abstract_gaps.csv").write_text("doi,resolution\n10.0000/example-a,\n", encoding="utf-8")
        result = self.run_audit()
        self.assertEqual({"unreported": 1}, result["counts"]["papers_without_abstract_by_resolution"])
        self.assertIn("gap_resolution_missing", self.codes(result, "warnings"))

    def test_bad_csv_and_missing_file_return_errors(self):
        self.assertIn("records_unreadable", self.codes(self.run_audit()))
        (self.data / "records.csv").write_text("doi\n10.0000/a,extra\n", encoding="utf-8")
        self.assertIn("records_unreadable", self.codes(self.run_audit()))

    def test_truncated_cache_is_an_error_instead_of_a_traceback(self):
        self.write_rows([record()])
        cache = self.data / "records.jsonl.gz"
        cache.write_bytes(b"\x1f\x8b\x08\x00")
        self.assertIn("source_cache_unreadable", self.codes(self.run_audit()))

    def test_cli_auto_discovery_json_and_exit_status(self):
        self.write_rows([record(abstract_words="bad")])
        output = self.root / "audit.json"
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            code = audit.main([str(self.root), "--output", str(output)])
        self.assertEqual(1, code)
        self.assertEqual(json.loads(stream.getvalue()), json.loads(output.read_text()))
        self.assertEqual(1, json.loads(output.read_text())["errors"])

    def test_empty_review_template_uses_only_consumed_maps(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "review.json"
        template = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual({"duplicates": {}, "kinds": {}, "abstract_rejections": {}, "abstract_accepts": {}}, template)


if __name__ == "__main__":
    unittest.main()
