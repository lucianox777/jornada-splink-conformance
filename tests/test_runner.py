"""Synthetic-only offline integration checks; run with real pinned Splink in CI."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runner import EXPECTED, RESULT, SCHEMA, run


def synthetic_doc():
    return {
        "schema_version": SCHEMA,
        "reference_code": "CENSO2022_NOMES_BRASIL_V1",
        "reference_content_sha256": "a" * 64,
        "comparison_version": "WHOLE_NAME_JARO_WINKLER_V1",
        "first_name_sex": "TODOS",
        "surname_sex": "TODOS",
        "observation_channel_version": "CLEAN_PUBLISHED_REFERENCE_NO_ERROR_CHANNEL_V1",
        "seed": 20260927,
        "pair_count": 3,
        "pairs": [
            {"pair_index": 0, "left_name": "ANA SILVA",
             "right_name": "ANA SILVA", "c_sharp_state": "EXACT"},
            {"pair_index": 1, "left_name": "MARIA SILVA",
             "right_name": "MARIA VIOL", "c_sharp_state": "MEDIUM"},
            {"pair_index": 2, "left_name": "JOSE SILVA",
             "right_name": "ANA SANTOS", "c_sharp_state": "LOW"},
        ],
    }


class RunnerContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "synthetic.json"
        self.destination = Path(self.tmp.name) / "results" / "synthetic.splink-result.json"

    def write(self, doc):
        self.source.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_same_pair_real_splink_and_strict_output_contract(self):
        self.write(synthetic_doc())
        summary = run(self.source, self.destination, enforce_hash=False)
        output = json.loads(self.destination.read_text(encoding="utf-8"))
        self.assertEqual(output["schema_version"], RESULT)
        self.assertEqual(output["source_schema_version"], SCHEMA)
        self.assertEqual(output["input_sha256"],
                         hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(output["pair_count"], 3)
        self.assertEqual([p["pair_index"] for p in output["pairs"]], [0, 1, 2])
        self.assertEqual(output["pairs"][0]["splink_state"], "EXACT")
        self.assertTrue(all(p["splink_state"] in
                            ("EXACT", "HIGH", "MEDIUM", "LOW")
                            for p in output["pairs"]))
        self.assertEqual(summary["pair_count"], 3)
        self.assertEqual(summary["output_sha256"],
                         hashlib.sha256(self.destination.read_bytes()).hexdigest())
        self.assertEqual(summary["disagreements"],
                         len(json.loads(self.destination.with_suffix(
                             ".divergences.json").read_text(encoding="utf-8"))))
        self.assertTrue(self.destination.with_suffix(".summary.json").exists())

    def test_known_input_hash_is_default_deny(self):
        self.write(synthetic_doc())
        self.assertIn("ibge-u-todos.json", EXPECTED)
        with self.assertRaisesRegex(ValueError, "Unexpected input hash"):
            run(self.source, self.destination, enforce_hash=True)
        self.assertFalse(self.destination.exists())

    def test_rejects_cross_pair_and_duplicate_indexes(self):
        doc = synthetic_doc()
        doc["pairs"][1]["pair_index"] = 0
        self.write(doc)
        with self.assertRaisesRegex(ValueError, "Pair indexes"):
            run(self.source, self.destination, enforce_hash=False)
        self.assertFalse(self.destination.exists())

    def test_rejects_invalid_state(self):
        doc = synthetic_doc()
        doc["pairs"][0]["c_sharp_state"] = "INVALID"
        self.write(doc)
        with self.assertRaisesRegex(ValueError, "Invalid pair"):
            run(self.source, self.destination, enforce_hash=False)
        self.assertFalse(self.destination.exists())

    def test_rejects_wrong_reference(self):
        doc = synthetic_doc()
        doc["reference_code"] = "OTHER"
        self.write(doc)
        with self.assertRaisesRegex(ValueError, "metadata"):
            run(self.source, self.destination, enforce_hash=False)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
