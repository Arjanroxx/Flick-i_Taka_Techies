"""Diagnose the protected original; never tune, relabel or write model artifacts."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation import possession_metrics as pm
from scripts.download_skillcorner import digest
from scripts.validate_skillcorner import verify_source
from src.contracts import read
from src.control_evidence import sustained_control_evidence
from src.learned_control_cache import load_cached
from src.p3_sequence_model import run
from src.skillcorner_validation import native_config
from src.spell_diagnostics import diagnose


def evidence(a, b, config):
    teams, known = sustained_control_evidence(a, b,
        config['hmm']['emission_temperature'], config['control'])
    return pd.Series(np.where(known, np.array(['H', 'A'])[teams.argmax(axis=1)], 'X'), index=a.index)


def save(out, name, result, provenance):
    summary, tables = result
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    for kind, table in tables.items():
        table.to_csv(folder / (kind + '.csv'), index=False)
    summary.update(provenance)
    (folder / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(name + ': ' + json.dumps({k: summary[k] for k in ('spellF1',
        'reference_spell_categories', 'merge_bridge_categories', 'stoppage_categories')}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', choices=['public', 'development', 'all'], default='all')
    args = parser.parse_args()
    out = ROOT / 'artifacts/possession_diagnosis'
    out.mkdir(exist_ok=True)
    sources = {name: digest(ROOT / name) for name in ('src/spell_diagnostics.py',
        'scripts/diagnose_possession_errors.py', 'src/control_evidence.py', 'src/p3_sequence_model.py',
        'src/p2_deadball_detector.py', 'src/skillcorner_validation.py', 'src/learned_control_cache.py',
        'evaluation/possession_metrics.py', 'configs/control_candidate.yaml', 'configs/skillcorner_protocol.json')}
    summaries, protected = {}, {}
    if args.scope in ('public', 'all'):
        config = yaml.safe_load((ROOT / 'configs/control_candidate.yaml').read_text())
        manifest = json.loads((ROOT / 'artifacts/control_candidate/verification.json').read_text())['hashes']
        for key in ('spatial', 'deadball', 'predictions', 'overrides', 'submission'):
            path = ROOT / config['paths'][key]
            if digest(path).upper() != manifest[path.name]:
                raise ValueError('Protected original differs from its verification record: ' + key)
            protected[str(path)] = digest(path)
        a, b = (read(kind, ROOT / config['paths'][kind]) for kind in ('spatial', 'deadball'))
        gt_path = ROOT / 'evaluation/gt/BAR-ATH_possession_gt_public.csv'
        reference = pm.read_label_csv(gt_path)
        prediction = pm.read_label_csv(ROOT / config['paths']['submission'])
        for table in (reference, prediction):
            reason = pm.validate_submission(table, len(a))
            if reason:
                raise ValueError(reason)
        reference, prediction = (table.set_index('frame').label for table in (reference, prediction))
        result = diagnose(reference, prediction, a.half, 25, control_support=evidence(a, b, config),
                          ball_observed=a.ball_x.notna() & ~a.ball_is_imputed)
        summaries['public'] = save(out, 'public', result, {'scope': 'public_sanity_only',
            'reference_sha256': digest(gt_path), 'prediction_sha256': digest(ROOT / config['paths']['submission'])})
    if args.scope in ('development', 'all'):
        protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())
        blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
        if set(protocol['development_matches']) & set(protocol['test_matches']):
            raise ValueError('Development and comparison matches overlap')
        for match in protocol['development_matches']:
            folder = ROOT / 'artifacts/external/skillcorner' / match
            tracking = verify_source(folder, match, protocol, blobs)
            a, b, reference = load_cached(folder, protocol,
                ROOT / 'artifacts/learned_control/feature_cache' / match, tracking)
            config = native_config(protocol, 'sustained_control')
            c = run(config, a, b)
            result = diagnose(reference, c.raw_label, a.half, protocol['source_fps'],
                dead_reference_available=False, control_support=evidence(a, b, config),
                ball_observed=a.ball_x.notna() & ~a.ball_is_imputed)
            summaries[match] = save(out, match, result, {'scope': 'development', 'tracking_sha256': tracking})
    if sources != {name: digest(ROOT / name) for name in sources}:
        raise RuntimeError('Diagnostic source changed during execution')
    if protected != {path: digest(path) for path in protected}:
        raise RuntimeError('Original artifacts changed during execution')
    report = {'sources': sources, 'summaries': summaries, 'original_artifacts_unchanged': True,
        'model_parameters_changed': False, 'public_used_for_tuning': False,
        'comparison_matches_evaluated': False,
        'limits': ['Categories describe prediction/reference interval geometry, not proven physical causes.',
                  'Spell categories partition GT spells; merge bridges and D coverage overlap them and must not be added.',
                  'Public edge intervals are censored; candidate errors there are not full-spell boundary estimates.',
                  'External references have unknown gaps and no D labels; missed external stoppages cannot be measured.']}
    (out / ('report_' + args.scope + '.json')).write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
