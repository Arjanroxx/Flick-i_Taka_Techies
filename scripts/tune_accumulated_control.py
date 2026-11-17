"""Small, development-only selection; never reads public or eight-test scores."""
from itertools import product
import json
from pathlib import Path
import sys

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_skillcorner import digest
from scripts.validate_skillcorner import verify_source
from scripts.validate_accumulated_control import load_cached
from src.skillcorner_validation import native_config, evaluate_reference
from src.p3_sequence_model import run


def main():
    protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())
    blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
    path = ROOT / 'configs/accumulated_control_candidate.yaml'
    candidate = yaml.safe_load(path.read_text())
    out = ROOT / 'artifacts/accumulated_validation'
    grid = [{'confirmation_seconds': seconds, 'min_evidence_probability': probability}
            for seconds, probability in product((.16, .20, .24), (2 / 3, .70, .75))]
    declaration = {'grid': grid, 'matches': protocol['development_matches'],
                   'primary': 'mean partial_reference_spellF1', 'tie_breaker': 'mean macroF1_HA',
                   'script_sha256': digest(Path(__file__)), 'starting_config_sha256': digest(path),
                   'public_and_test_scores_used': False}
    (out / 'development_search_protocol.json').write_text(json.dumps(declaration, indent=2))
    rows = []
    for match in protocol['development_matches']:
        folder = ROOT / 'artifacts/external/skillcorner' / match
        tracking = verify_source(folder, match, protocol, blobs)
        a, b, reference = load_cached(folder, protocol, out / 'feature_cache' / match, tracking)
        for index, setting in enumerate(grid):
            cfg = native_config(protocol, 'sustained_control')
            cfg['hmm']['team_evidence'] = 'accumulated_control'
            cfg['control'] = {**candidate['control'], **setting, 'fps': protocol['source_fps']}
            prediction = run(cfg, a, b)
            metrics = evaluate_reference(reference, prediction.raw_label, a.half, protocol['source_fps'])
            rows.append({'match': match, 'variant': index, **setting,
                         **{k:metrics[k] for k in ('partial_reference_spellF1', 'macroF1_HA',
                                                  'fragmentation', 'spell_count_ratio')}})
        pd.DataFrame(rows).to_csv(out / 'development_grid_per_match.csv', index=False)
        print(match + ': completed nine development-only variants', flush=True)
    scores = pd.DataFrame(rows).groupby('variant')[['partial_reference_spellF1', 'macroF1_HA',
                                                  'fragmentation', 'spell_count_ratio']].mean()
    scores = scores.sort_values(['partial_reference_spellF1', 'macroF1_HA'], ascending=False)
    scores.to_csv(out / 'development_grid_summary.csv')
    chosen = int(scores.index[0])
    candidate['control'].update(grid[chosen])
    path.write_text(yaml.safe_dump(candidate, sort_keys=False))
    (out / 'development_selection.json').write_text(json.dumps(
        {'selected_variant': chosen, 'selected_settings': grid[chosen],
         'development_results': scores.reset_index().to_dict(orient='records'),
         'test_or_public_selection': False}, indent=2))
    print('Selected on development partial spellF1, then H/A macroF1:', grid[chosen], flush=True)


if __name__ == '__main__':
    main()
