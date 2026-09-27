"""Contract and real-Splink tests for the independent synthetic u estimator."""
import json
import tempfile
import unittest
from pathlib import Path

from independent_u import (MARGINAL_SCHEMA, REPORT_SCHEMA, estimate,
                           exact_collision_probability, sample_pairs,
                           validate_marginals, wilson_interval)


def fixture():
    return {
        "schema_version": MARGINAL_SCHEMA,
        "reference_code": "CENSO2022_NOMES_BRASIL_V1",
        "reference_content_sha256": "a"*64,
        "first_name_sex": "TODOS",
        "surname_sex": "TODOS",
        "first_names": [
            {"name": "ANA", "occurrences": 3},
            {"name": "MARIA", "occurrences": 1}
        ],
        "surnames": [
            {"name": "SILVA", "occurrences": 2},
            {"name": "SANTOS", "occurrences": 2}
        ]
    }


class IndependentUTest(unittest.TestCase):
    def test_analytic_collision_and_sampling_reproducible(self):
        document = validate_marginals(fixture())
        self.assertAlmostEqual(exact_collision_probability(document), 0.3125)
        self.assertEqual(sample_pairs(document, 42, 8), sample_pairs(document, 42, 8))
        self.assertNotEqual(sample_pairs(document, 42, 8), sample_pairs(document, 43, 8))
        self.assertEqual(wilson_interval(0, 100)[0], 0.)
        self.assertAlmostEqual(wilson_interval(100, 100)[1], 1.)

    def test_invalid_marginal_fails_closed(self):
        doc = fixture()
        doc["first_names"][0]["occurrences"] = 0
        with self.assertRaisesRegex(ValueError, "frequency"):
            validate_marginals(doc)
        doc = fixture()
        doc["first_names"].append({"name": "ANA", "occurrences": 5})
        with self.assertRaisesRegex(ValueError, "frequency"):
            validate_marginals(doc)
        doc = fixture()
        doc["unknown"] = 123
        with self.assertRaisesRegex(ValueError, "fields"):
            validate_marginals(doc)

    def test_independent_three_seed_real_splink(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "public.json"
            source.write_text(json.dumps(fixture()), encoding="utf-8")
            out = Path(tmp) / "results"
            report = estimate(source, out, pair_count=20, seeds=(41, 42, 43))
            self.assertEqual(report["schema_version"], REPORT_SCHEMA)
            self.assertEqual(len(report["runs"]), 3)
            self.assertAlmostEqual(report["analytic_exact_collision_probability"], 0.3125)
            for run in report["runs"]:
                self.assertEqual(sum(v["support"] for v in run["states"].values()), 20)
                self.assertEqual(set(run["states"]), {"EXACT", "HIGH", "MEDIUM", "LOW"})
            self.assertTrue((out / "independent-u-report.json").exists())
            self.assertTrue((out / "independent-41.splink-result.json").exists())
            self.assertFalse((out / "independent-41.splink-result.divergences.json").exists())
            summary = json.loads((out / "independent-41.splink-result.summary.json").read_text())
            self.assertNotIn("disagreements", summary)
            self.assertNotIn("c_sharp_support", summary)


if __name__ == "__main__":
    unittest.main()
