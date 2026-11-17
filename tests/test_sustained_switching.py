from copy import deepcopy
import unittest
import numpy as np
import pandas as pd
from src.contact_transitions import transition_schedule
from src.p3_sequence_model import build_emissions


class SustainedSwitchTests(unittest.TestCase):
    def fixture(self, length):
        a = pd.DataFrame({'half': 1, 'ball_x': 40., 'ball_y': 30.,
            'dist_nearest_H': [1.]*20+[8.]*length+[1.]*20,
            'dist_nearest_A': [8.]*20+[1.]*length+[8.]*20,
            'ball_is_imputed': False, 'gap_length_frames': 0}, index=range(40+length))
        b = pd.DataFrame({'is_dead_ball_prob': .05, 'is_out_of_bounds': False}, index=a.index)
        t = np.array([[.999,.0004,.0006],[.0004,.999,.0006],[.0005,.0005,.999]])
        cfg={'hmm':{'team_evidence':'sustained_control','contact_switch_probability':.02,
            'emission_temperature':3.,'contact_minimum_seconds':.4,'contact_fps':25}}
        return a,b,t,cfg

    def test_short_confirmed_contact_cannot_reduce_switch_cost(self):
        a,b,t,cfg=self.fixture(6)
        schedule=transition_schedule(a,b,t,cfg)
        np.testing.assert_array_equal(schedule,np.broadcast_to(t,schedule.shape))

    def test_long_contact_changes_only_turnover_entries_and_not_emissions(self):
        a,b,t,cfg=self.fixture(12)
        schedule=transition_schedule(a,b,t,cfg)
        np.testing.assert_array_equal(np.flatnonzero(np.any(schedule!=t,axis=(1,2))),[20,32])
        old=deepcopy(cfg);del old['hmm']['contact_minimum_seconds']
        before,after=build_emissions(a,b,old),build_emissions(a,b,cfg)
        np.testing.assert_array_equal(before[0],after[0])
        np.testing.assert_array_equal(before[1],after[1])

    def test_half_boundary_breaks_confirmation(self):
        a,b,t,cfg=self.fixture(12)
        a.loc[26:,'half']=2
        schedule=transition_schedule(a,b,t,cfg)
        np.testing.assert_array_equal(schedule,np.broadcast_to(t,schedule.shape))
