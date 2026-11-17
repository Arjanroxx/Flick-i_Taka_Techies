"""Predeclared contact-transition comparison on twelve development matches only."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_skillcorner import digest
from scripts.validate_skillcorner import verify_source
from src.learned_control_cache import load_cached
from src.skillcorner_validation import native_config, evaluate_reference
from src.p3_sequence_model import run


def main():
    out = ROOT / 'artifacts/contact_boundaries'
    out.mkdir(exist_ok=True)
    protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())
    plan = json.loads((ROOT / 'configs/contact_transition_protocol.json').read_text())
    blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
    names = ['src/contact_transitions.py', 'src/p3_sequence_model.py', 'src/control_evidence.py',
             'src/skillcorner_validation.py', 'src/learned_control_cache.py', 'src/p2_deadball_detector.py',
             'scripts/evaluate_contact_transitions.py', 'configs/contact_transition_protocol.json',
             'configs/skillcorner_protocol.json']
    sources = {name: digest(ROOT / name) for name in names}
    (out / 'protocol_lock.json').write_text(json.dumps({'sources': sources, 'plan': plan}, indent=2))
    rows = []
    for match in protocol['development_matches']:
        folder = ROOT / 'artifacts/external/skillcorner' / match
        tracking = verify_source(folder, match, protocol, blobs)
        a, b, reference = load_cached(folder, protocol,
            ROOT / 'artifacts/learned_control/feature_cache' / match, tracking)
        for probability in [None] + plan['switch_probabilities']:
            cfg = native_config(protocol, 'sustained_control')
            if probability is not None:
                cfg['hmm']['contact_switch_probability'] = probability
            c = run(cfg, a, b)
            metrics = evaluate_reference(reference, c.raw_label, a.half, protocol['source_fps'])
            row = {'match': match, 'variant': 'original' if probability is None else str(probability)}
            row.update({k: metrics[k] for k in ('partial_reference_spellF1', 'macroF1_HA',
                'fragmentation', 'spell_count_ratio')})
            row.update(precision_05=metrics['per_iou'][.5]['precision'], recall_05=metrics['per_iou'][.5]['recall'])
            rows.append(row)
            pd.DataFrame(rows).to_csv(out / 'development_per_match.csv', index=False)
        print(match + ': original and two predeclared variants evaluated', flush=True)
    frame = pd.DataFrame(rows)
    comparisons = {}
    for probability in plan['switch_probabilities']:
        pivot = frame.pivot(index='match', columns='variant', values='partial_reference_spellF1')
        delta = (pivot[str(probability)] - pivot.original).to_numpy()
        interval = np.quantile(np.random.default_rng(0).choice(delta, (10000, len(delta))).mean(axis=1), [.05, .95])
        gate = plan['development_gate']
        comparisons[str(probability)] = {'mean_gain': float(delta.mean()), 'wins': int((delta > 0).sum()),
            'paired_match_bootstrap_90pct': interval.tolist(),
            'development_gate_passed': bool(delta.mean() >= gate['minimum_mean_spell_gain']
                and (delta > 0).sum() >= gate['minimum_match_wins'] and interval[0] > gate['bootstrap_lower_bound'])}
    if sources != {name: digest(ROOT / name) for name in names}:
        raise RuntimeError('Experiment changed during evaluation')
    summary = frame.groupby('variant').mean(numeric_only=True).reset_index().to_dict(orient='records')
    report = {'development_only': True, 'sources': sources, 'plan': plan, 'summary': summary,
              'comparisons': comparisons, 'public_or_reused_eight_evaluated': False,
              'promoted': False, 'fresh_validation_still_required': True}
    (out / 'development_report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
