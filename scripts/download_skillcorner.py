"""Download a pinned public SkillCorner snapshot and verify its LFS objects."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'configs/skillcorner_protocol.json'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(url, target, *, expected_sha=None, expected_size=None):
    target = Path(target)
    if target.exists() and (expected_sha is None or digest(target) == expected_sha):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.part')
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Flick-i-Taka-validation'}),
                         timeout=45) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if expected_size is not None and temporary.stat().st_size != expected_size:
                raise ValueError('LFS size mismatch')
            if expected_sha is not None and digest(temporary) != expected_sha:
                raise ValueError('LFS checksum mismatch')
            temporary.replace(target)
            return
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(1)


def download_match(folder, revision, match_id):
    stem = f'data/matches/{match_id}/{match_id}'
    raw = f'https://raw.githubusercontent.com/SkillCorner/opendata/{revision}/'
    destination = folder / match_id
    tracking = destination / 'tracking.jsonl'
    pointer = destination / 'tracking.lfs'
    fetch(raw + stem + '_tracking_extrapolated.jsonl', pointer)
    fields = dict(line.split(' ', 1) for line in pointer.read_text().splitlines())
    expected_sha = fields['oid'].removeprefix('sha256:')
    expected_size = int(fields['size'])
    fetch(raw + stem + '_match.json', destination / 'match.json')
    fetch(raw + stem + '_phases_of_play.csv', destination / 'phases.csv')
    url = (f'https://media.githubusercontent.com/media/SkillCorner/opendata/{revision}/'
           + stem + '_tracking_extrapolated.jsonl?download=true')
    fetch(url, tracking, expected_sha=expected_sha, expected_size=expected_size)
    manifest = {'match_id': match_id, 'revision': revision, 'tracking_url': url,
                'tracking_sha256': expected_sha, 'tracking_bytes': expected_size,
                'metadata_sha256': digest(destination / 'match.json'),
                'phases_sha256': digest(destination / 'phases.csv')}
    (destination / 'source.json').write_text(json.dumps(manifest, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/external/skillcorner')
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    revision = protocol['revision']
    args.out.mkdir(parents=True, exist_ok=True)
    raw = f'https://raw.githubusercontent.com/SkillCorner/opendata/{revision}/'
    for name in ('README.md', 'LICENSE'):
        fetch(raw + name, args.out / ('SOURCE_' + name))
    manifests, errors = [], {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_match, args.out, revision, match): match
                   for match in protocol['match_ids']}
        for future in as_completed(futures):
            match = futures[future]
            try:
                manifests.append(future.result())
                print(f'{match}: downloaded and verified', flush=True)
            except Exception as error:
                errors[match] = str(error)
                print(f'{match}: download failed: {error}', flush=True)
    (args.out / 'download_manifest.json').write_text(json.dumps(
        {'revision': revision, 'matches': manifests, 'errors': errors}, indent=2))
    if errors:
        raise SystemExit('Some downloads failed; rerun to retry verified missing files')


if __name__ == '__main__':
    main()
