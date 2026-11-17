"""Verified native geometry/reference cache; labels are stored separately."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from .skillcorner_validation import load_match

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def load_cached(folder, protocol, cache, tracking_sha):
    source = {name: digest(ROOT / name) for name in ('src/skillcorner_validation.py',
                'src/p2_deadball_detector.py', 'configs/skillcorner_protocol.json')}
    expected = {'sources': source, 'tracking': tracking_sha, 'metadata': digest(folder / 'match.json')}
    files = {kind: cache / (kind + '.parquet') for kind in ('spatial', 'deadball', 'reference')}
    # The earlier experiments cached the same label-free geometry. Reuse only
    # when all source and file fingerprints agree, never their predictions.
    legacy = ROOT / 'artifacts/accumulated_validation/feature_cache' / folder.name
    for candidate in (cache, legacy):
        manifest = candidate / 'inputs.json'
        if not manifest.exists():
            continue
        saved = json.loads(manifest.read_text())
        paths = {kind: candidate / (kind + '.parquet') for kind in files}
        if (saved['source'] == expected and all(path.exists() and digest(path) == saved['files'][kind]
                                               for kind, path in paths.items())):
            return (pd.read_parquet(paths['spatial']), pd.read_parquet(paths['deadball']),
                    pd.read_parquet(paths['reference']).reference)
    a, b, reference, _ = load_match(folder, protocol)
    cache.mkdir(parents=True, exist_ok=True)
    for kind, table in [('spatial', a), ('deadball', b), ('reference', reference.to_frame())]:
        table.to_parquet(files[kind])
    (cache / 'inputs.json').write_text(json.dumps({'source': expected,
                    'files': {kind: digest(path) for kind, path in files.items()}}, indent=2))
    return a, b, reference
