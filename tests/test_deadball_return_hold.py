import unittest
from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from src.p2_deadball_detector import build_mask


class DeadballReturnHoldTests(unittest.TestCase):
    def test_confirmed_exit_waits_through_quiet_return_but_releases_on_motion(self):
        cfg = yaml.safe_load(Path('configs/control_candidate.yaml').read_text())
        a = pd.DataFrame({'half': 1, 'ball_x': [-2.]*4+[10.]*8,
            'ball_y': 30., 'ball_is_imputed': False,
            'ball_speed': [np.nan]+[0.]*3+[np.nan]+[0.]*3+[1.]*4,
            'ball_accel': 0.}, index=pd.Index(range(12), name='frame'))
        original = build_mask(cfg, a, [])
        enabled = deepcopy(cfg)
        enabled['thresholds']['hold_confirmed_exit_until_motion'] = True
        result = build_mask(enabled, a, [])
        self.assertTrue((result.is_dead_ball_prob.iloc[4:8] > .9).all())
        self.assertTrue((result.is_dead_ball_prob.iloc[8:] < .1).all())
        self.assertTrue((original.is_dead_ball_prob.iloc[4:] < .1).all())
        a['ball_x'] = 10.
        result = build_mask(enabled, a, [])
        self.assertTrue((result.is_dead_ball_prob < .1).all())
