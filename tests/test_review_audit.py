"""The output audit must distinguish a provider error from an explicit miss."""
import contextlib
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_outputs
import common
import demo
import pipeline


class ProviderAuditTests(unittest.TestCase):
    def test_malformed_batch_item_is_not_a_successful_lookup(self):
        root = Path(tempfile.mkdtemp(prefix="journal-audit-tests-")) / "corpus"
        registry = demo.create_fixture(root)
        with patch.object(common._opener, "open", side_effect=AssertionError("unexpected network")), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            pipeline.run(root, [demo.SLUG], registry, offline=True)
        path = root / "raw" / "semanticscholar" / demo.SLUG / "abstract_batch.json.gz"
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            saved = json.load(handle)
        index = saved["ids"].index(demo.PREFIX + "scholar")
        saved["response"][index] = {"error": "upstream temporarily unavailable"}
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(saved, handle)
        report = audit_outputs.audit_journal(root, demo.SLUG)
        codes = {item["code"] for item in report["errors"]}
        self.assertIn("source_cache_invalid_response", codes)
        self.assertIn("used_source_cache_unavailable", codes)


if __name__ == "__main__":
    unittest.main()
