"""Regenerate the frozen team submission, validate it, and require its exact hash."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path)
    args=parser.parse_args()
    manifest=json.loads((ROOT/'submission/manifest.json').read_text())
    for name,expected in manifest['source_sha256_lf'].items():
        actual=hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if actual!=expected:
            raise ValueError('Frozen release source changed: '+name)
    config=ROOT/'configs/final_submission.yaml'
    cfg=yaml.safe_load(config.read_text())
    overrides=ROOT/cfg['paths']['overrides']
    if overrides.exists() and len(pd.read_parquet(overrides)):
        raise ValueError('The final submission does not use arbitration overrides')
    command=[sys.executable,str(ROOT/'scripts/run_full_pipeline.py'),'--config',str(config),'--skip-evaluation']
    if args.data_dir:
        command+=['--data-dir',str(args.data_dir.resolve())]
    subprocess.run(command,cwd=ROOT,check=True)
    path=ROOT/cfg['paths']['submission']
    table=pd.read_csv(path)
    table.to_csv(path,index=False,lineterminator='\n',encoding='utf-8')
    subprocess.run([sys.executable,str(ROOT/'evaluation/validate_submission.py'),str(path)],cwd=ROOT,check=True)
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual!=manifest['csv_sha256']:
        raise ValueError('Submission differs from frozen release: '+actual)
    print('FINAL SUBMISSION VERIFIED: '+str(path))
    print('SHA-256: '+actual)


if __name__=='__main__':main()
