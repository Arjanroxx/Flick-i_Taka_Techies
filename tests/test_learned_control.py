from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from src.learned_control import (FEATURE_NAMES, control_features, fit_model, calibrate_model,
                                 predict_model, learned_control_evidence)
from src.control_evidence import sustained_control_evidence

ROOT = Path(__file__).resolve().parents[1]


class LearnedControlTests(unittest.TestCase):
    def setUp(self):
        index = pd.Index(range(100), name='frame')
        self.a = pd.DataFrame({'dist_nearest_H': np.linspace(1, 3, 100),
                               'dist_nearest_A': np.linspace(4, 1, 100),
                               'ball_x': 50., 'ball_y': 30., 'ball_speed': 2., 'half': 1,
                               'ball_is_imputed': False, 'gap_length_frames': 0}, index=index)
        self.b = pd.DataFrame({'is_dead_ball_prob': .05, 'is_out_of_bounds': False}, index=index)
        self.zero = {'version': 1, 'features': FEATURE_NAMES, 'coef': [0.] * len(FEATURE_NAMES),
                     'scale': [1.] * len(FEATURE_NAMES), 'temperature': 1.}

    def test_features_are_team_symmetric_and_do_not_read_labels(self):
        original, _ = control_features(self.a, self.b, 25)
        swapped = self.a.copy()
        swapped[['dist_nearest_H', 'dist_nearest_A']] = self.a[['dist_nearest_A', 'dist_nearest_H']].to_numpy()
        reverse, _ = control_features(swapped, self.b, 25)
        np.testing.assert_allclose(original, -reverse, atol=1e-12)
        self.a['possession'] = 'arbitrary reference must not enter model'
        repeated, _ = control_features(self.a, self.b, 25)
        np.testing.assert_array_equal(original, repeated)

    def test_future_observations_cannot_change_past_feature_history(self):
        original, _ = control_features(self.a, self.b, 25)
        self.a.loc[50:, ['dist_nearest_H', 'dist_nearest_A', 'ball_speed']] = [20, .1, 30]
        changed, _ = control_features(self.a, self.b, 25)
        np.testing.assert_array_equal(original[:50], changed[:50])

    def test_missing_and_period_boundaries_reset_histories(self):
        self.a['half'] = np.r_[np.ones(50), np.full(50, 2)]
        features, _ = control_features(self.a, self.b, 25)
        # First row of period 2 cannot inherit history from period 1.
        self.assertAlmostEqual(features[50, FEATURE_NAMES.index('margin_history_1.5')],
                               features[50, FEATURE_NAMES.index('margin')])
        self.a.loc[20:30, 'ball_x'] = np.nan
        features, eligible = control_features(self.a, self.b, 25)
        self.assertTrue(np.isfinite(features).all())
        self.assertFalse(eligible[20:31].any())

    def test_fit_calibration_and_probability_symmetry(self):
        x = np.zeros((100, len(FEATURE_NAMES)))
        x[:, 0] = np.linspace(-2, 2, len(x))
        labels = np.where(x[:, 0] > 0, 1., -1.)
        weights = np.ones(len(x))
        model = fit_model(x, labels, weights, .1)
        model = calibrate_model(model, x, labels, weights)
        probability = predict_model(model, x)
        self.assertGreater(probability[-1], probability[0])
        np.testing.assert_allclose(probability, 1 - predict_model(model, -x), atol=1e-12)

    def test_uncertain_classifier_exactly_preserves_original_evidence(self):
        original = sustained_control_evidence(self.a, self.b, 3., {})
        actual = learned_control_evidence(self.a, self.b, 3., {},
                                           {'model': self.zero, 'fps': 25, 'confidence': .85})
        np.testing.assert_array_equal(actual[0], original[0])
        np.testing.assert_array_equal(actual[1], original[1])

    def test_confident_classifier_cannot_replace_confirmed_original_control(self):
        self.a[['dist_nearest_H', 'dist_nearest_A']] = [1., 9.]
        model = deepcopy(self.zero)
        model['coef'][0] = -20.
        original = sustained_control_evidence(self.a, self.b, 3., {})
        actual = learned_control_evidence(self.a, self.b, 3., {},
                                           {'model': model, 'fps': 25, 'confidence': .75})
        self.assertTrue(original[1].all())
        np.testing.assert_array_equal(actual[0], original[0])

    def test_training_masks_unknowns_and_weights_matches_equally(self):
        from scripts.train_learned_control import training_data
        data = {
            'one': {'eligible': np.ones(3, dtype=bool), 'reference': pd.Series(['H','A','X']),
                    'x': np.zeros((3, len(FEATURE_NAMES)))},
            'two': {'eligible': np.ones(5, dtype=bool), 'reference': pd.Series(['H','H','A','A','X']),
                    'x': np.ones((5, len(FEATURE_NAMES)))}}
        x, y, weight = training_data(['one', 'two'], data)
        self.assertEqual(len(x), 6)
        self.assertTrue(np.isin(y, [-1, 1]).all())
        self.assertAlmostEqual(float(weight[:2].sum()), float(weight[2:].sum()))

    def test_model_file_must_match_recorded_hash(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            path = Path(directory) / 'model.json'
            content = json.dumps(self.zero).encode()
            path.write_bytes(content)
            settings = {'model_path': str(path), 'model_sha256': hashlib.sha256(content).hexdigest()}
            learned_control_evidence(self.a, self.b, 3., {}, settings)
            path.write_bytes(content + b' ')
            with self.assertRaises(ValueError):
                learned_control_evidence(self.a, self.b, 3., {}, settings)


if __name__ == '__main__':
    unittest.main()
