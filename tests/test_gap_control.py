import unittest
import numpy as np
import pandas as pd
from src.gap_control import gap_control_evidence


class GapControlTests(unittest.TestCase):
    def fixture(self):
        a = pd.DataFrame({'ball_x': 30., 'ball_y': 20., 'half': 1,
            'dist_nearest_H': 1., 'dist_nearest_A': 8.,
            'ball_is_imputed': False, 'gap_length_frames': 0}, index=range(20))
        a.loc[8:11, ['ball_x', 'ball_y', 'dist_nearest_H', 'dist_nearest_A']] = np.nan
        a.loc[8:11, 'gap_length_frames'] = 4
        b = pd.DataFrame({'is_dead_ball_prob': .05, 'is_out_of_bounds': False}, index=a.index)
        b.loc[8:11, 'is_dead_ball_prob'] = 1/3
        return a, b

    def test_short_bracketed_gap_has_weak_support_but_remains_unobserved(self):
        a,b = self.fixture()
        teams,known = gap_control_evidence(a,b,3.,{}, {'fps':25})
        np.testing.assert_allclose(teams[8:12,0], .65)
        self.assertFalse(known[8:12].any())

    def test_opposite_owner_deadball_half_long_gap_and_frame_jump_reject(self):
        for case in ('opposite','dead','half','long','jump'):
            a,b = self.fixture()
            if case == 'opposite': a.loc[12:, ['dist_nearest_H','dist_nearest_A']] = [8.,1.]
            if case == 'dead': b.loc[9,'is_dead_ball_prob'] = .5
            if case == 'half': a.loc[12:, 'half'] = 2
            if case == 'jump': a.index = b.index = np.r_[np.arange(10),np.arange(11,21)]
            teams,_ = gap_control_evidence(a,b,3.,{}, {'fps':5 if case=='long' else 25})
            np.testing.assert_allclose(teams[8:12], .5)
