from copy import deepcopy
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
import yaml

from src.control_evidence import sustained_control_evidence
from src.p3_sequence_model import run


class ControlEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load(Path('configs/config.yaml').read_text())
        self.config['hmm']['team_evidence'] = 'sustained_control'
        self.a = pd.DataFrame({'ball_x': 50., 'ball_y': 30., 'half': 1,
                               'dist_nearest_H': 1., 'dist_nearest_A': 9.,
                               'ball_is_imputed': False, 'gap_length_frames': 0},
                              index=pd.Index(range(200), name='frame'))
        self.b = pd.DataFrame({'is_dead_ball_prob': .05, 'is_out_of_bounds': False},
                              index=self.a.index)

    def evidence(self):
        return sustained_control_evidence(self.a, self.b, 3., {})

    def test_brief_deflection_does_not_create_opponent_evidence(self):
        self.a.loc[90:91, ['dist_nearest_H', 'dist_nearest_A']] = [9, 1]
        teams, known = self.evidence()
        np.testing.assert_allclose(teams[90:92], .5)
        self.assertFalse(known[90:92].any())
        self.assertTrue(run(self.config, self.a, self.b).raw_label.eq('H').all())

    def test_persistent_turnover_starts_at_first_supported_contact(self):
        self.a.loc[100:, ['dist_nearest_H', 'dist_nearest_A']] = [9, 1]
        teams, known = self.evidence()
        self.assertTrue(known.all())
        self.assertGreater(teams[100, 1], teams[100, 0])
        labels = run(self.config, self.a, self.b).raw_label
        self.assertTrue(labels.iloc[:100].eq('H').all())
        self.assertTrue(labels.iloc[100:].eq('A').all())

    def test_far_contested_missing_imputed_and_stopped_are_neutral(self):
        for column, value in [('dist_nearest_H', 8.), ('dist_nearest_A', 1.5),
                               ('ball_x', np.nan), ('ball_is_imputed', True),
                               ('gap_length_frames', 1)]:
            a = self.a.copy()
            a[column] = value
            teams, known = sustained_control_evidence(a, self.b, 3., {})
            self.assertFalse(known.any())
            np.testing.assert_allclose(teams, .5)
        b = self.b.copy()
        b['is_dead_ball_prob'] = .98
        _, known = sustained_control_evidence(self.a, b, 3., {})
        self.assertFalse(known.any())
        self.assertTrue(run(self.config, self.a, b).raw_label.eq('D').all())

    def test_confirmation_cannot_bridge_missing_frame_or_half(self):
        a, b = self.a.iloc[:4].copy(), self.b.iloc[:4].copy()
        a['half'] = [1, 1, 2, 2]
        _, known = sustained_control_evidence(a, b, 3., {})
        self.assertFalse(known.any())
        a['half'] = 1
        a.index = b.index = pd.Index([0, 1, 3, 4], name='frame')
        _, known = sustained_control_evidence(a, b, 3., {})
        self.assertFalse(known.any())

    def test_legacy_mode_unchanged_and_invalid_settings_fail(self):
        legacy = deepcopy(self.config)
        del legacy['hmm']['team_evidence']
        explicit = deepcopy(legacy)
        explicit['hmm']['team_evidence'] = 'distance'
        pd.testing.assert_frame_equal(run(legacy, self.a, self.b), run(explicit, self.a, self.b))
        for settings in ({'confirmation_frames': 1}, {'max_distance_m': np.nan}):
            with self.assertRaises(ValueError):
                sustained_control_evidence(self.a, self.b, 3., settings)


if __name__ == '__main__':
    unittest.main()
