import hashlib
import json
from pathlib import Path
import unittest
import pandas as pd
import yaml
from evaluation import possession_metrics as pm


class SubmissionReleaseTests(unittest.TestCase):
    def test_exact_final_csv_and_official_format(self):
        manifest=json.loads(Path('submission/manifest.json').read_text())
        path=Path(manifest['csv'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),manifest['csv_sha256'])
        self.assertIsNone(pm.validate_submission(pd.read_csv(path),199319))

    def test_team_named_pdf_and_frozen_duration_only(self):
        manifest=json.loads(Path('submission/manifest.json').read_text())
        pdf=Path(manifest['pdf'])
        self.assertTrue(pdf.read_bytes().startswith(b'%PDF-'))
        self.assertEqual(hashlib.sha256(pdf.read_bytes()).hexdigest(),manifest['pdf_sha256'])
        cfg=yaml.safe_load(Path('configs/final_submission.yaml').read_text())
        self.assertEqual(cfg['hmm']['decoder'],'duration')
        self.assertEqual(cfg['hmm']['team_evidence'],'sustained_control')
        self.assertEqual(cfg['duration']['scale_seconds'],9.51291250794194)
        self.assertEqual(Path(cfg['paths']['submission']).name,'Flick-i Taka Techies.csv')
        for option in ('selective_splits','segment_verifier','boundary_refinement'):
            self.assertFalse(cfg.get(option,{}).get('enabled',False))
