import unittest
import numpy as np
import pandas as pd
from src.stable_contact import stable_contact_evidence


class StableContactTests(unittest.TestCase):
    def test_only_sustained_moving_observed_contact_adds_evidence(self):
        a = pd.DataFrame({'ball_x': 30., 'ball_y': 20., 'half': 1,
            'dist_nearest_H': 1., 'dist_nearest_A': 2., 'ball_speed': 3.,
            'ball_is_imputed': False, 'gap_length_frames': 0}, index=range(12))
        b = pd.DataFrame({'is_dead_ball_prob': .05, 'is_out_of_bounds': False}, index=a.index)
        _, known = stable_contact_evidence(a, b, 3., {}, {'fps':25})
        self.assertTrue(known.all())
        for column, value in [('ball_speed', 0.), ('ball_is_imputed', True), ('ball_x', np.nan)]:
            changed = a.copy(); changed[column] = value
            _, mask = stable_contact_evidence(changed, b, 3., {}, {'fps':25})
            self.assertFalse(mask.any())
        a.loc[6, 'ball_x'] = np.nan
        _, mask = stable_contact_evidence(a, b, 3., {}, {'fps':25})
        self.assertFalse(mask.any())
