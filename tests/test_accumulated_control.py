from copy import deepcopy
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
import yaml

from src.control_evidence import accumulated_control_evidence
from src.p3_sequence_model import run


class AccumulatedControlTests(unittest.TestCase):
    def setUp(self):
        self.cfg = yaml.safe_load(Path('configs/accumulated_control_candidate.yaml').read_text())
        self.a = pd.DataFrame({'ball_x': 50., 'ball_y': 30., 'half': 1,
                               'dist_nearest_H': 1., 'dist_nearest_A': 9.,
                               'ball_is_imputed': False, 'gap_length_frames': 0},
                              index=pd.Index(range(225), name='frame'))
        self.b = pd.DataFrame({'is_dead_ball_prob': .05, 'is_out_of_bounds': False}, index=self.a.index)

    def test_moderate_advantage_recovers_crowded_possession_without_hard_margin(self):
        self.a.loc[100:124, ['dist_nearest_H', 'dist_nearest_A']] = [1.5, 1.]
        old = deepcopy(self.cfg)
        old['hmm']['team_evidence'] = 'sustained_control'
        old['control'] = {'confirmation_frames': 3}
        self.assertTrue(run(old, self.a, self.b).raw_label.eq('H').all())
        result = run(self.cfg, self.a, self.b).raw_label
        self.assertTrue(result.iloc[100:125].eq('A').all())
        self.assertTrue(result.iloc[:100].eq('H').all())
        self.assertTrue(result.iloc[125:].eq('H').all())

    def test_extreme_six_frame_touch_does_not_overwhelm_temporal_model(self):
        self.a.loc[100:105, ['dist_nearest_H', 'dist_nearest_A']] = [100, .1]
        teams, known = accumulated_control_evidence(self.a, self.b, 3., self.cfg['control'])
        self.assertTrue(known[100:106].all())
        self.assertLessEqual(float(teams.max()), .9)
        self.assertTrue(run(self.cfg, self.a, self.b).raw_label.eq('H').all())

    def test_missing_frames_and_period_changes_reset_pending_support(self):
        a, b = self.a.iloc[:4].copy(), self.b.iloc[:4].copy()
        a['half'] = [1, 1, 2, 2]
        _, known = accumulated_control_evidence(a, b, 3., self.cfg['control'])
        self.assertFalse(known.any())
        a['half'] = 1
        a.loc[1, 'ball_x'] = np.nan
        _, known = accumulated_control_evidence(a, b, 3., self.cfg['control'])
        self.assertFalse(known.any())

    def test_neutral_gaps_decay_instead_of_accumulating_free_evidence(self):
        a, b = self.a.iloc[:4].copy(), self.b.iloc[:4].copy()
        a.loc[1:2, ['dist_nearest_H', 'dist_nearest_A']] = [8, 9]
        _, known = accumulated_control_evidence(a, b, 3., self.cfg['control'])
        self.assertFalse(known.any())

    def test_stoppage_stays_dead_and_invalid_confidence_bounds_fail(self):
        self.b['is_dead_ball_prob'] = .98
        self.assertTrue(run(self.cfg, self.a, self.b).raw_label.eq('D').all())
        cfg = deepcopy(self.cfg)
        cfg['control']['max_evidence_probability'] = .6
        with self.assertRaises(ValueError):
            run(cfg, self.a, self.b)

    def test_neutral_or_distant_ball_cannot_start_control(self):
        self.a[['dist_nearest_H', 'dist_nearest_A']] = [10, 20]
        teams, known = accumulated_control_evidence(self.a, self.b, 3., self.cfg['control'])
        self.assertFalse(known.any())
        np.testing.assert_allclose(teams, .5)


if __name__ == '__main__':
    unittest.main()
