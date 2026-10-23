"""Failure and incremental-run regressions from the independent review."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import demo
import common
import pipeline
import run_recovery

FIXTURES = Path(tempfile.mkdtemp(prefix="journal-recovery-tests-"))


def rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class RunRecoveryTests(unittest.TestCase):
    def fixture(self):
        root = FIXTURES / self._testMethodName
        registry = demo.create_fixture(root)
        return root, registry

    def run_quiet(self, root, registry, journals=None, references=False):
        with patch.object(common._opener, "open", side_effect=AssertionError("unexpected network")), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            pipeline.run(root, journals or [demo.SLUG], registry, offline=True, references=references)

    def snapshot(self, root):
        paths = list((root / "data").rglob("*")) + [root / "run_manifest.json"]
        return {str(path.relative_to(root)): path.read_bytes() for path in paths if path.is_file()}

    def remove_one_cached_lookup(self, root):
        path = root / "raw" / "openalex" / demo.SLUG / "works.jsonl.gz"
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            entries = [json.loads(line) for line in handle]
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            for entry in entries:
                if entry["doi"] != demo.PREFIX + "scholar":
                    handle.write(json.dumps(entry) + "\n")

    def test_failed_rerun_restores_all_completed_outputs_and_keeps_attempt(self):
        root, registry = self.fixture()
        self.run_quiet(root, registry, references=True)
        before = self.snapshot(root)
        self.remove_one_cached_lookup(root)
        with self.assertRaisesRegex(SystemExit, "no saved OpenAlex response"):
            self.run_quiet(root, registry)
        self.assertEqual(self.snapshot(root), before)
        state = json.loads((root / "run_state.json").read_text())
        self.assertEqual(state["status"], "failed_restored")
        self.assertTrue((root / state["archive"] / "incomplete" / "data" / demo.SLUG / "records.csv").exists())

    def test_failed_first_run_exposes_no_partial_completed_table(self):
        root, registry = self.fixture()
        before = self.snapshot(root)
        self.remove_one_cached_lookup(root)
        with self.assertRaises(SystemExit):
            self.run_quiet(root, registry)
        self.assertEqual(self.snapshot(root), before)
        self.assertFalse((root / "run_manifest.json").exists())

    def test_interrupted_run_recovers_before_rerunning(self):
        root, registry = self.fixture()
        self.run_quiet(root, registry)
        records = root / "data" / demo.SLUG / "records.csv"
        before = records.read_bytes()
        state = run_recovery.begin(root, [demo.SLUG])
        records.write_text("unfinished output\n")
        with patch.object(run_recovery.os, "kill", side_effect=ProcessLookupError):
            self.run_quiet(root, registry)
        self.assertEqual(records.read_bytes(), before)
        self.assertEqual((root / state["archive"] / "incomplete" / "data" / demo.SLUG / "records.csv").read_text(), "unfinished output\n")

    def test_active_run_is_not_overwritten(self):
        root, registry = self.fixture()
        self.run_quiet(root, registry)
        before = self.snapshot(root)
        run_recovery.begin(root, [demo.SLUG])
        with patch.object(run_recovery.os, "kill", return_value=None), self.assertRaisesRegex(ValueError, "another pipeline"):
            self.run_quiet(root, registry)
        self.assertEqual(self.snapshot(root), before)

    def test_recovery_preserves_review_and_notes_authored_after_a_crash(self):
        root, registry = self.fixture()
        self.run_quiet(root, registry)
        folder = root / "data" / demo.SLUG
        run_recovery.begin(root, [demo.SLUG])
        (folder / "records.csv").write_text("unfinished output\n")
        review_path = folder / "review.json"
        review = json.loads(review_path.read_text())
        review["abstract_rejections"][demo.PREFIX + "openalex"] = {"note": "New synthetic reading decision after interruption."}
        review_path.write_text(json.dumps(review))
        review_bytes = review_path.read_bytes()
        note = folder / "reading-notes.txt"
        note.write_text("A newly authored note must survive recovery.\n")
        with patch.object(run_recovery.os, "kill", side_effect=ProcessLookupError):
            self.run_quiet(root, registry)
        self.assertEqual(review_path.read_bytes(), review_bytes)
        self.assertEqual(note.read_text(), "A newly authored note must survive recovery.\n")
        target = next(row for row in rows(folder / "records.csv") if row["doi"] == demo.PREFIX + "openalex")
        self.assertEqual(target["abstract"], "")

    def test_existing_reference_table_rebuilds_after_decision_change(self):
        root, registry = self.fixture()
        self.run_quiet(root, registry, references=True)
        path = root / "data" / demo.SLUG / "review.json"
        review = json.loads(path.read_text())
        review["duplicates"][demo.PREFIX + "duplicate"]["kept"] = demo.PREFIX + "openalex"
        path.write_text(json.dumps(review))
        self.run_quiet(root, registry, references=False)
        duplicate_refs = [row for row in rows(path.parent / "references.csv.gz") if row["citing_doi"] == demo.PREFIX + "duplicate"]
        self.assertTrue(duplicate_refs)
        self.assertTrue(all(row["paper_doi"] == demo.PREFIX + "openalex" for row in duplicate_refs))
        self.assertIn("references", json.loads((path.parent / "summary.json").read_text()))
        manifest = json.loads((root / "run_manifest.json").read_text())
        self.assertEqual(manifest["reference_journals_rebuilt"], [demo.SLUG])

    def test_manifest_covers_combined_population_and_registry_omission_fails(self):
        root, registry = self.fixture()
        self.run_quiet(root, registry)
        second = {**demo.JOURNAL, "slug": "second-journal", "title": "Second Synthetic Journal", "issns": ["0000-0027"]}
        registry.write_text(json.dumps({"journals": [demo.JOURNAL, second]}))
        cr = root / "raw" / "crossref" / second["slug"]
        cr.mkdir(parents=True)
        with gzip.open(cr / "0000-0027_page_01.json.gz", "wt") as handle:
            json.dump({"message": {"total-results": 1, "items": [{"DOI": "10.0000/second", "type": "journal-article", "title": ["Second item"], "abstract": demo.TEXT}]}}, handle)
        oa = root / "raw" / "openalex" / second["slug"]
        oa.mkdir(parents=True)
        with gzip.open(oa / "works.jsonl.gz", "wt") as handle:
            handle.write(json.dumps({"doi": "10.0000/second", "status": "not_found", "response": None}) + "\n")
        self.run_quiet(root, registry, [second["slug"]])
        manifest = json.loads((root / "run_manifest.json").read_text())
        self.assertEqual(manifest["requested_journal_slugs"], [second["slug"]])
        self.assertEqual(set(manifest["journal_slugs"]), {demo.SLUG, second["slug"]})
        self.assertEqual({Path(p).parts[2] for p in manifest["saved_source_sha256"]}, {demo.SLUG, second["slug"]})
        self.assertIn(f"data/{demo.SLUG}/review.json", manifest["review_sha256"])
        self.assertIn("data/journals_crossref.csv.gz", manifest["derived_sha256"])
        before = self.snapshot(root)
        registry.write_text(json.dumps({"journals": [demo.JOURNAL]}))
        with self.assertRaisesRegex(ValueError, "absent from this registry"):
            self.run_quiet(root, registry)
        self.assertEqual(self.snapshot(root), before)

    def test_conflicting_review_actions_fail_without_publishing_outputs(self):
        root, registry = self.fixture()
        path = root / "data" / demo.SLUG / "review.json"
        review = json.loads(path.read_text())
        review["abstract_rejections"][demo.PREFIX + "accepted"] = {"note": "Contradictory synthetic decision."}
        path.write_text(json.dumps(review))
        with self.assertRaisesRegex(ValueError, "cannot accept and reject"):
            self.run_quiet(root, registry)
        self.assertFalse((path.parent / "records.csv").exists())


if __name__ == "__main__":
    unittest.main()
