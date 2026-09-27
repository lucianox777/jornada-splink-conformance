#!/usr/bin/env python3
"""Independent synthetic u estimator from explicitly supplied PUBLIC IBGE marginals.

This is not an estimator of real-world joint full-name frequencies.
"""
import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from runner import SCHEMA, run

MARGINAL_SCHEMA = "JORNADA_IBGE_PUBLIC_MARGINALS_V1"
REPORT_SCHEMA = "JORNADA_SPLINK_INDEPENDENT_U_V1"
SEEDS = (20261001, 20261002, 20261003)
STATES = ("EXACT", "HIGH", "MEDIUM", "LOW")


def validate_marginals(document):
    if not isinstance(document, dict) or set(document) != {
        "schema_version", "reference_code", "reference_content_sha256",
        "first_name_sex", "surname_sex", "first_names", "surnames"
    }:
        raise ValueError("Unexpected marginal document fields")
    if (document["schema_version"] != MARGINAL_SCHEMA
        or document["reference_code"] != "CENSO2022_NOMES_BRASIL_V1"
        or document["first_name_sex"] not in ("TODOS", "FEMININO")
        or document["surname_sex"] != "TODOS"):
        raise ValueError("Invalid public marginal metadata")
    sha = document["reference_content_sha256"]
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("Invalid reference SHA-256")
    for key in ("first_names", "surnames"):
        values = document[key]
        if not isinstance(values, list) or not values:
            raise ValueError("Empty marginal")
        seen = set()
        for entry in values:
            if not isinstance(entry, dict) or set(entry) != {"name", "occurrences"}:
                raise ValueError("Invalid marginal row")
            name, count = entry["name"], entry["occurrences"]
            if (not isinstance(name, str) or not name or name != name.strip()
                or name != name.upper() or name in seen
                or not isinstance(count, int) or isinstance(count, bool) or count <= 0):
                raise ValueError("Invalid marginal name/frequency")
            seen.add(name)
    return document


def wilson_interval(support, total, z=1.96):
    p = support / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total)) / denominator
    half = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [max(0., center-half), min(1., center+half)]


def sample_pairs(document, seed, pair_count):
    rng = random.Random(seed)  # independent from Jornada SHA-256 high-multiply sampler
    first = document["first_names"]
    last = document["surnames"]
    f_names = [x["name"] for x in first]
    f_weights = [x["occurrences"] for x in first]
    l_names = [x["name"] for x in last]
    l_weights = [x["occurrences"] for x in last]
    # Separate independent draws for each side of each synthetic distinct-identity pair.
    draws_first = rng.choices(f_names, weights=f_weights, k=pair_count*2)
    draws_last = rng.choices(l_names, weights=l_weights, k=pair_count*2)
    return [
        dict(pair_index=i, left_name=draws_first[2*i] + " " + draws_last[2*i],
             right_name=draws_first[2*i+1] + " " + draws_last[2*i+1],
             c_sharp_state="LOW")  # placeholder required by replay schema, NOT a C# prediction
        for i in range(pair_count)
    ]


def exact_collision_probability(document):
    def collision(entries):
        total = sum(row["occurrences"] for row in entries)
        return sum((row["occurrences"]/total)**2 for row in entries)
    return collision(document["first_names"]) * collision(document["surnames"])


def estimate(source, destination, pair_count, seeds=SEEDS):
    if not 1 <= pair_count <= 100_000:
        raise ValueError("pair_count must be 1..100000")
    if not seeds or len(set(seeds)) != len(seeds) or any(not isinstance(s, int) for s in seeds):
        raise ValueError("Seeds must be distinct integers")
    raw = source.read_bytes()
    document = validate_marginals(json.loads(raw))
    analytic_exact = exact_collision_probability(document)
    reports = []
    destination.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        pairs = sample_pairs(document, seed, pair_count)
        replay = {
            "schema_version": SCHEMA,
            "reference_code": document["reference_code"],
            "reference_content_sha256": document["reference_content_sha256"],
            "comparison_version": "WHOLE_NAME_JARO_WINKLER_V1",
            "first_name_sex": document["first_name_sex"],
            "surname_sex": document["surname_sex"],
            "observation_channel_version": "CLEAN_PUBLISHED_REFERENCE_NO_ERROR_CHANNEL_V1",
            "seed": seed,
            "pair_count": pair_count,
            "pairs": pairs,
        }
        # Splink is the sole classifier here. The placeholder C# state is ignored
        # in this independent estimation, and disagreements are not meaningful.
        replay_path = destination / f"independent-{seed}.replay.json"
        replay_path.write_text(json.dumps(replay, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        result_path = destination / f"independent-{seed}.splink-result.json"
        run(replay_path, result_path, enforce_hash=False, emit_comparison_diagnostics=False)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        counts = {state: 0 for state in STATES}
        for row in result["pairs"]:
            counts[row["splink_state"]] += 1
        reports.append({
            "seed": seed,
            "pair_count": pair_count,
            "replay_sha256": hashlib.sha256(replay_path.read_bytes()).hexdigest(),
            "splink_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            "states": {
                state: {"support": counts[state], "probability": counts[state]/pair_count,
                        "wilson_95": wilson_interval(counts[state], pair_count)}
                for state in STATES
            },
            "empirical_exact_minus_analytic": counts["EXACT"]/pair_count - analytic_exact,
        })
    report = {
        "schema_version": REPORT_SCHEMA,
        "marginals_sha256": hashlib.sha256(raw).hexdigest(),
        "reference_code": document["reference_code"],
        "reference_content_sha256": document["reference_content_sha256"],
        "first_name_sex": document["first_name_sex"],
        "surname_sex": document["surname_sex"],
        "joint_construction": "INDEPENDENT_FIRST_NAME_SURNAME_MARGINALS_V1",
        "observation_channel": "CLEAN_PUBLISHED_REFERENCE_NO_ERROR_CHANNEL_V1",
        "classifier": "SPLINK_4.0.17_JARO_WINKLER_0.92_0.80",
        "analytic_exact_collision_probability": analytic_exact,
        "runs": reports,
        "limitations": [
            "Synthetic independent identities; no observed real-world full-name joint distribution.",
            "Splink classifier may differ from C# V1 at boundaries; compare separately.",
            "Wilson intervals are within-run only; seeds and marginal model uncertainty require separate analysis.",
            "No independent u validation claim until real public marginal export and C# comparison are completed."
        ],
    }
    output = destination / "independent-u-report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public_marginals", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--pairs", type=int, default=10_000)
    args = parser.parse_args()
    report = estimate(args.public_marginals, args.output_dir, args.pairs)
    print(json.dumps({"schema_version": report["schema_version"],
                      "marginals_sha256": report["marginals_sha256"],
                      "seeds": [r["seed"] for r in report["runs"]]}))


if __name__ == "__main__":
    main()
