#!/usr/bin/env python3
"""Independent, offline, synthetic-only Jornada × Splink 4.0.17 same-pair runner."""
import argparse
import collections
import hashlib
import json
from pathlib import Path

EXPECTED = {'ibge-u-todos.json': 'a5cea4f00027427190c726f92329724e6f92fc3bcd64c67f4d9f758ca4d2af64',
            'ibge-u-feminino.json': 'da89b9a7a6594f52065e64284732f032adb3033c347ba969684161cd028f378c'}
SCHEMA = 'JORNADA_SPLINK_IBGE_U_REPLAY_V1'
RESULT = 'JORNADA_SPLINK_IBGE_U_REPLAY_RESULT_V1'
STATES = {3: 'EXACT', 2: 'HIGH', 1: 'MEDIUM', 0: 'LOW'}


def run(source: Path, destination: Path, enforce_hash: bool, emit_comparison_diagnostics: bool = True):
    import pandas as pd
    import splink
    from splink import Linker, SettingsCreator, DuckDBAPI, block_on
    from splink.comparison_library import JaroWinklerAtThresholds
    if splink.__version__ != '4.0.17':
        raise RuntimeError(f'Splink 4.0.17 required; got {splink.__version__}')
    raw = source.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if enforce_hash and sha != EXPECTED.get(source.name):
        raise ValueError(f'Unexpected input hash for {source.name}: {sha}')
    doc = json.loads(raw)
    if (doc['schema_version'] != SCHEMA or doc['reference_code'] != 'CENSO2022_NOMES_BRASIL_V1'
        or doc['comparison_version'] != 'WHOLE_NAME_JARO_WINKLER_V1'
        or doc['first_name_sex'] not in ('TODOS', 'FEMININO')
        or doc['surname_sex'] != 'TODOS'
        or doc['observation_channel_version'] != 'CLEAN_PUBLISHED_REFERENCE_NO_ERROR_CHANNEL_V1'):
        raise ValueError('Replay metadata does not match expected synthetic IBGE contract')
    pairs = doc['pairs']; count = int(doc['pair_count'])
    if len(pairs) != count or not 1 <= count <= 100_000:
        raise ValueError('Invalid pair count')
    if [p['pair_index'] for p in pairs] != list(range(count)):
        raise ValueError('Pair indexes must be sequential')
    rows = []
    for p in pairs:
        i = p['pair_index']
        if p['c_sharp_state'] not in STATES.values() or not p['left_name'] or not p['right_name']:
            raise ValueError(f'Invalid pair {i}')
        rows.extend(({'unique_id': i*2, 'pair_index': i, 'name': p['left_name']},
                     {'unique_id': i*2+1, 'pair_index': i, 'name': p['right_name']}))
    settings = SettingsCreator(link_type='dedupe_only',
        comparisons=[JaroWinklerAtThresholds('name', [0.92, 0.80])],
        blocking_rules_to_generate_predictions=[block_on('pair_index')],
        retain_intermediate_calculation_columns=True)
    predicted = Linker(pd.DataFrame(rows), settings, DuckDBAPI()).inference.predict(threshold_match_weight=-1000).as_pandas_dataframe()
    actual = {}
    for row in predicted.itertuples(index=False):
        left = int(row.unique_id_l); right = int(row.unique_id_r)
        if left % 2 != 0 or right != left+1:
            raise ValueError(f'Unexpected cross-pair comparison: {left}, {right}')
        i = left // 2
        if i in actual or int(row.gamma_name) not in STATES:
            raise ValueError('Duplicate pair or unexpected Splink state')
        actual[i] = STATES[int(row.gamma_name)]
    if len(actual) != count or set(actual) != set(range(count)):
        raise ValueError(f'Missing pairs: expected {count}, got {len(actual)}')
    result = dict(schema_version=RESULT, source_schema_version=SCHEMA, input_sha256=sha,
        reference_content_sha256=doc['reference_content_sha256'],
        comparison_version=doc['comparison_version'], splink_version=splink.__version__,
        seed=int(doc['seed']), pair_count=count,
        pairs=[dict(pair_index=i, splink_state=actual[i]) for i in range(count)])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    summary = dict(input=source.name, input_sha256=sha, output=destination.name,
        output_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        pair_count=count, splink_support=dict(collections.Counter(actual.values())),
        limitation='State classification only; no independently trained u parameters')
    if emit_comparison_diagnostics:
        disagreements = [dict(pair_index=i, left_name=p['left_name'], right_name=p['right_name'],
            c_sharp_state=p['c_sharp_state'], splink_state=actual[i])
            for i, p in enumerate(pairs) if p['c_sharp_state'] != actual[i]]
        summary['disagreements'] = len(disagreements)
        summary['c_sharp_support'] = dict(collections.Counter(p['c_sharp_state'] for p in pairs))
        summary['limitation'] = 'Same-pair state agreement only; not independent u estimation'
        destination.with_suffix('.divergences.json').write_text(
            json.dumps(disagreements, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    destination.with_suffix('.summary.json').write_text(
        json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    return summary

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input_dir', type=Path)
    ap.add_argument('output_dir', type=Path)
    ap.add_argument('--allow-new-input-hashes', action='store_true', help='For new synthetic exports; retain actual hashes in reports')
    args = ap.parse_args()
    for name in EXPECTED:
        summary = run(args.input_dir/name, args.output_dir/name.replace('.json', '.splink-result.json'),
                      not args.allow_new_input_hashes)
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
