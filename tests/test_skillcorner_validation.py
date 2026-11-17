from copy import deepcopy
import json
import tempfile
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from src.skillcorner_validation import (observation_features, reference_label, native_config,
                                        evaluate_reference, match_split, load_match)
from src import p2_deadball_detector as p2
from src import p3_sequence_model as p3

ROOT = Path(__file__).resolve().parents[1]


class SkillCornerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())

    def test_coordinate_conversion_and_possession_cannot_leak(self):
        metadata = {'pitch_length': 105, 'pitch_width': 68}
        row = {'period': 1, 'ball_data': {'x': 0., 'y': 0., 'is_detected': True},
               'player_data': [{'player_id': 1, 'x': 1., 'y': 0., 'is_detected': True},
                               {'player_id': 2, 'x': 8., 'y': 0., 'is_detected': True}],
               'possession': {'group': 'home team', 'player_id': 1}}
        before = observation_features(row, metadata, {1: 0, 2: 1})
        row['possession'] = {'group': 'away team', 'player_id': 2}
        after = observation_features(row, metadata, {1: 0, 2: 1})
        self.assertEqual(before, after)
        self.assertEqual(before, (1, 52.5, 34., 1., 8.))
        row['ball_data']['is_detected'] = False
        self.assertTrue(np.isnan(observation_features(row, metadata, {1: 0, 2: 1})[1:]).all())

    def test_null_is_unknown_not_dead_and_unmapped_labels_fail(self):
        self.assertEqual(reference_label({'period': 1, 'possession': {'group': None}}), 'X')
        self.assertEqual(reference_label({'period': 0, 'possession': {'group': 'home team'}}), 'X')
        with self.assertRaises(ValueError):
            reference_label({'period': 1, 'possession': {'group': 'unknown vendor string'}})

    def test_utf8_metadata_and_native_loader(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            folder = Path(directory)
            meta = {'pitch_length': 105, 'pitch_width': 68,
                    'home_team': {'id': 10, 'name': 'Tren\u010d\u00edn'},
                    'away_team': {'id': 20, 'name': 'Other'},
                    'players': [{'id': 1, 'team_id': 10}, {'id': 2, 'team_id': 20}]}
            (folder / 'match.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
            rows = [{'frame': i, 'period': 1, 'timestamp': f'00:00:00.{i}0',
                     'ball_data': {'x': 0., 'y': 0., 'is_detected': True},
                     'player_data': [{'player_id': 1, 'x': 1., 'y': 0., 'is_detected': True},
                                     {'player_id': 2, 'x': 6., 'y': 0., 'is_detected': True}],
                     'possession': {'group': 'home team'}} for i in range(4)]
            (folder / 'tracking.jsonl').write_text('\n'.join(json.dumps(row) for row in rows),
                                                  encoding='utf-8')
            a, b, truth, loaded = load_match(folder, self.protocol)
            self.assertEqual(loaded['home_team']['name'], meta['home_team']['name'])
            self.assertEqual(len(a), 4)
            self.assertTrue(truth.eq('H').all())
            self.assertTrue(b.index.equals(a.index))

    def test_timing_adaptation_is_predeclared_and_does_not_mutate_frozen_settings(self):
        saved = deepcopy(self.protocol)
        config = native_config(self.protocol, 'sustained_control')
        self.assertEqual(self.protocol, saved)
        self.assertEqual(config['control']['confirmation_frames'], 2)
        self.assertEqual(config['hmm']['emission_power'], 2.5)
        matrix = np.asarray(config['hmm']['transition'])
        np.testing.assert_allclose(matrix.sum(axis=1), 1)
        self.assertTrue((matrix >= 0).all())
        self.assertTrue(np.all(matrix.diagonal() < np.diag(self.protocol['frozen_settings']['hmm']['transition'])))

    def test_match_split_is_disjoint_and_complete(self):
        p = self.protocol
        self.assertFalse(set(p['development_matches']) & set(p['test_matches']))
        self.assertEqual(set(p['development_matches'] + p['test_matches']), set(p['match_ids']))
        self.assertEqual(len(p['test_matches']), 8)
        for match in p['match_ids']:
            self.assertIn(match_split(p, match), ('development', 'test'))

    def test_native_emission_exposure_matches_predeclared_time_conversion(self):
        config = native_config(self.protocol, 'distance')
        a = pd.DataFrame({'dist_nearest_H': [1.], 'dist_nearest_A': [8.],
                          'ball_is_imputed': [False]})
        b = pd.DataFrame({'is_dead_ball_prob': [.05]})
        unscaled = deepcopy(config)
        unscaled['hmm']['emission_power'] = 1.
        original, _ = p3.build_emissions(a, b, unscaled)
        adapted, _ = p3.build_emissions(a, b, config)
        expected = original ** 2.5
        expected /= expected.sum(axis=1, keepdims=True)
        np.testing.assert_allclose(adapted, expected)

    def test_partial_metrics_exclude_unknowns_and_reset_between_periods(self):
        gt = pd.Series(['H', 'X', 'A', 'H'])
        pred = pd.Series(['H', 'D', 'A', 'H'])
        result = evaluate_reference(gt, pred, [1, 1, 1, 2], 10)
        self.assertEqual(result['macroF1_HA'], 1)
        self.assertEqual(result['partial_reference_spellF1'], 1)
        self.assertEqual(result['labelled_frames'], 3)
        self.assertEqual(result['reference_spells'], 3)
        self.assertFalse(result['D_reference_available'])
        self.assertEqual(result['predicted_D_on_labelled'], 0)

    def test_actual_detector_uses_native_timeline_without_competition_row_count(self):
        config = native_config(self.protocol, 'distance')
        a = pd.DataFrame({'half': 1, 'ball_x': 50., 'ball_y': 34., 'ball_speed': 1.,
                          'ball_accel': 0., 'ball_is_imputed': False},
                         index=pd.Index(range(20), name='frame'))
        b = p2.build_mask(config, a, [], fps=10, pitch={'length': 105, 'width': 68})
        self.assertEqual(len(b), 20)
        self.assertTrue(b.index.equals(a.index))
        np.testing.assert_allclose(b.is_dead_ball_prob, .05)


if __name__ == '__main__':
    unittest.main()
