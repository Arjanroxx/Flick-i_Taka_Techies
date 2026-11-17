from pathlib import Path
from copy import deepcopy
from itertools import product
import hashlib
import json
import tempfile
import unittest

import numpy as np
import pandas as pd
import yaml

from evaluation import possession_metrics as pm
from src import p2_deadball_detector as p2, p3_sequence_model as p3
from src import p4_arbiter_and_eval as p4
from src.contracts import day1_mocks, frame_halves, validate, write, SCHEMAS

ROOT = Path(__file__).resolve().parents[1]


class RepositoryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load((ROOT / 'configs/config.yaml').read_text())
        cls.a, cls.b = day1_mocks()
        cls.start = int(np.flatnonzero(frame_halves() == 1)[0]) + 100

    def test_exit_survives_occlusion_and_restart_ends_tag_prior(self):
        a = self.a.copy()
        f = self.start
        a.loc[f:f + 30, ['ball_x', 'ball_y']] = [50, 30]
        a.loc[f:f + 30, 'ball_is_imputed'] = False
        a.loc[f:f + 30, 'ball_speed'] = 1
        a.loc[f:f + 2, 'ball_x'] = -1
        a.loc[f + 3:f + 7, ['ball_x', 'ball_y', 'ball_speed']] = np.nan
        a.loc[f + 8, 'ball_speed'] = np.nan
        a.loc[f + 9:f + 12, 'ball_speed'] = 4
        a.loc[f + 13:f + 16, ['ball_x', 'ball_y', 'ball_speed']] = np.nan
        event = {'code': 'SET PIECES', 'tags': {'Type': 'Throw-in'},
                 'start_frame': f, 'end_frame': f + 30}
        b = p2.build_mask(self.config, a, [event])
        np.testing.assert_allclose(b.loc[f:f + 7, 'is_dead_ball_prob'], 0.98)
        self.assertFalse(b.loc[f + 3:f + 7, 'is_out_of_bounds'].any())
        self.assertTrue(b.at[f + 9, 'restart_frame_flag'])
        np.testing.assert_allclose(b.loc[f + 13:f + 16, 'is_dead_ball_prob'], 1 / 3)

    def test_contract_rejects_partial_coordinates_and_invalid_imputation(self):
        for column, value in [('ball_x', np.nan), ('gap_length_frames', 0)]:
            a = self.a.copy()
            a.at[self.start, 'ball_is_imputed'] = True
            a.at[self.start, column] = value
            with self.assertRaises(ValueError):
                validate('spatial', a)

    def test_prediction_contract_rejects_outside_play_labels(self):
        c = p3.run(self.config, self.a, self.b)
        c.at[0, 'raw_label'] = 'D'
        with self.assertRaises(ValueError):
            validate('predictions', c)

    def test_invalid_thresholds_cannot_silently_disable_guards(self):
        for value in (np.nan, np.inf, -0.1, 1.2):
            config = deepcopy(self.config)
            config['thresholds']['entropy'] = value
            a = self.a.iloc[self.start:self.start + 1]
            b = self.b.loc[a.index]
            with self.assertRaises(ValueError):
                p3.run(config, a, b)
            with self.assertRaises(ValueError):
                p4.apply_overrides(pd.DataFrame({'raw_label': ['H']}),
                                   pd.DataFrame(), value)

    def test_contract_rejects_duplicate_frames_and_nonfinite_probability(self):
        b = self.b.copy()
        b.index = pd.Index(np.zeros(len(b), dtype='int64'), name='frame')
        with self.assertRaises(ValueError):
            validate('deadball', b)
        b = self.b.copy()
        b.at[self.start, 'is_dead_ball_prob'] = np.inf
        with self.assertRaises(ValueError):
            validate('deadball', b)

    def test_arbitration_cannot_carve_opposite_team_island(self):
        a = self.a.loc[self.start:self.start + 9].copy()
        a[['ball_x', 'ball_y']] = [50, 30]
        a['ball_is_imputed'] = False
        a['gap_length_frames'] = 0
        a[['dist_nearest_H', 'dist_nearest_A']] = [1, 9]
        b = self.b.loc[a.index].copy()
        b['is_dead_ball_prob'] = 0.05
        c = pd.DataFrame({'raw_label': 'A'}, index=a.index)
        result = p4.local_arbiter(a, b, c, (self.start + 2, self.start + 6))
        self.assertTrue(result.empty)

    def test_nonempty_overrides_require_matching_provenance(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            folder = Path(directory)
            c = p3.run(self.config, self.a, self.b)
            d = pd.DataFrame([{'start_frame': self.start, 'end_frame': self.start + 2,
                               'override_label': 'H', 'confidence': .9}]).astype(SCHEMAS['overrides'])
            tables = {'spatial': self.a, 'deadball': self.b, 'predictions': c, 'overrides': d}
            paths = {kind: str(folder / (kind + '.parquet')) for kind in tables}
            for kind, table in tables.items():
                write(kind, table, Path(paths[kind]))
            config = {'paths': paths}
            with self.assertRaises(ValueError):
                p4.run(config, c)
            digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
            cache = {'inputs': {kind: {'sha256': digest(paths[kind])}
                                for kind in ('spatial', 'deadball', 'predictions')}}
            (folder / 'response_cache.json').write_text(json.dumps(cache))
            (folder / 'summary.json').write_text(json.dumps(
                {'outputs': {'llm_overrides.parquet': digest(paths['overrides'])}}))
            self.assertEqual(len(p4.run(config, c)), 1)
            cache['inputs']['predictions']['sha256'] = 'stale'
            (folder / 'response_cache.json').write_text(json.dumps(cache))
            with self.assertRaises(ValueError):
                p4.run(config, c)

    def test_metric_x_fill_and_deadball_split(self):
        gt = pm.label_codes(list('HHHH'))
        x = pm.label_codes(list('HXXH'))
        self.assertEqual(pm.evaluate(gt, x)['spell_f1_mean'], 1)
        self.assertLess(pm.evaluate(gt, x)['macro_f1'], pm.evaluate(gt, gt)['macro_f1'])
        d = pm.label_codes(list('HDHH'))
        self.assertEqual(len(pm.possession_spells(d, [(0, 4)])), 2)
        self.assertLess(pm.evaluate(gt, d)['spell_f1_mean'], 1)

    def test_metric_leading_x_and_half_gap_do_not_bridge(self):
        labels = pm.label_codes(list('XHXXA'))
        filled = pm.fill_abstentions(labels, [(0, 2), (4, 5)])
        np.testing.assert_array_equal(filled, pm.label_codes(list('HHXXA')))
        self.assertEqual(len(pm.possession_spells(filled, [(0, 2), (4, 5)])), 2)

    def test_hmm_matches_exhaustive_paths(self):
        emissions = np.array([[.8, .1, .1], [.2, .7, .1], [.1, .3, .6]])
        transition = np.array([[.8, .1, .1], [.2, .7, .1], [.1, .2, .7]])
        paths = list(product(range(3), repeat=3))
        weights = np.array([emissions[0, p[0]] / 3 * transition[p[0], p[1]]
                            * emissions[1, p[1]] * transition[p[1], p[2]]
                            * emissions[2, p[2]] for p in paths])
        posterior = np.array([[sum(w for p, w in zip(paths, weights) if p[t] == k)
                               for k in range(3)] for t in range(3)]) / weights.sum()
        halves = np.ones(3, dtype='int8')
        np.testing.assert_allclose(p3.forward_backward(emissions, halves, transition), posterior)
        np.testing.assert_array_equal(p3.viterbi(emissions, halves, transition),
                                      p3.STATES[list(paths[int(weights.argmax())])])


if __name__ == '__main__':
    unittest.main()
