"""Regressions for independently reproduced review findings; synthetic inputs only."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common


class CredentialPrivacyTests(unittest.TestCase):
    def test_malformed_environment_keys_never_reach_transport_or_error_text(self):
        for provider, variable in [("openalex", "OPENALEX_API_KEY"), ("semanticscholar", "SEMANTIC_SCHOLAR_API_KEY")]:
            for suffix in ["\n", "\r\ninjected: value", "\u2603", "\x7f"]:
                key = "synthetic-private-key" + suffix
                with self.subTest(provider=provider, suffix=repr(suffix)), patch.dict("os.environ", {variable: key}), patch.object(common._opener, "open") as opener:
                    with self.assertRaises(common.APIError) as caught:
                        common.request_json("https://example.invalid", provider)
                    self.assertNotIn("synthetic-private-key", str(caught.exception))
                    opener.assert_not_called()

    def test_transport_validation_exception_does_not_echo_header(self):
        with patch.object(common, "_throttle"), patch.object(common._opener, "open", side_effect=ValueError("Invalid header: synthetic-private-key")):
            with self.assertRaises(common.APIError) as caught:
                common.request_json("https://example.invalid", "test-provider")
        self.assertNotIn("synthetic-private-key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
