import unittest
import numpy as np
import pandas as pd
from src.selective_splits import split_verified_possessions


class SelectiveSplitTests(unittest.TestCase):
    def fixture(self):
        a=pd.DataFrame({'ball_x':40.,'ball_y':30.,'half':1,
            'dist_nearest_H':1.,'dist_nearest_A':8.,'ball_speed':3.,
            'ball_is_imputed':False,'gap_length_frames':0},index=range(100))
        a.loc[40:51,['dist_nearest_H','dist_nearest_A']]=[2.,1.]
        b=pd.DataFrame({'is_dead_ball_prob':.05,'is_out_of_bounds':False},index=a.index)
        return a,b,np.full(100,'H')

    def split(self,a,b,l,scale=5.):
        return split_verified_possessions(l,a,b,3.,{}, {'fps':10,'long_spell_seconds':scale})

    def test_verified_opponent_contact_splits_long_possession_only(self):
        a,b,l=self.fixture(); result=self.split(a,b,l)
        np.testing.assert_array_equal(result[40:52],np.full(12,'A'))
        self.assertTrue((result[:40]=='H').all() and (result[52:]=='H').all())
        self.assertTrue((l=='H').all())
        np.testing.assert_array_equal(self.split(a,b,l,20.),l)

    def test_brief_contact_and_stationary_ball_are_rejected(self):
        a,b,l=self.fixture();a.loc[42:51,['dist_nearest_H','dist_nearest_A']]=[1.,8.]
        np.testing.assert_array_equal(self.split(a,b,l),l)
        a,b,l=self.fixture();a['ball_speed']=0.
        np.testing.assert_array_equal(self.split(a,b,l),l)

    def test_gap_imputation_deadball_half_and_frame_jump_are_rejected(self):
        for kind in ('missing','imputed','dead','half','jump'):
            a,b,l=self.fixture()
            if kind=='missing': a.loc[40:51,'ball_x']=np.nan
            if kind=='imputed': a.loc[40:51,'ball_is_imputed']=True
            if kind=='dead': b.loc[40:51,'is_dead_ball_prob']=.8
            if kind=='half': a.loc[46:,'half']=2
            if kind=='jump': a.index=b.index=np.r_[np.arange(46),np.arange(47,101)]
            np.testing.assert_array_equal(self.split(a,b,l),l)

    def test_owner_must_be_observed_on_both_sides(self):
        a,b,l=self.fixture();a.loc[52:65,['dist_nearest_H','dist_nearest_A']]=[4.,4.]
        np.testing.assert_array_equal(self.split(a,b,l),l)

    def test_team_symmetry_and_D_labels_are_protected(self):
        a,b,l=self.fixture();original=self.split(a,b,l)
        a[['dist_nearest_H','dist_nearest_A']]=a[['dist_nearest_A','dist_nearest_H']].to_numpy()
        swapped=self.split(a,b,np.full(100,'A'))
        np.testing.assert_array_equal(swapped,np.where(original=='H','A','H'))
        labels=np.full(100,'D');np.testing.assert_array_equal(self.split(a,b,labels),labels)

    def test_unstable_contact_does_not_pass_movement_verification(self):
        a,b,l=self.fixture()
        a.loc[40:51,'dist_nearest_A']=[.1,1.9]*6
        a.loc[40:51,'dist_nearest_H']=4.
        np.testing.assert_array_equal(self.split(a,b,l),l)

    def test_two_separate_verified_candidates_preserve_owner_between(self):
        a,b,l=self.fixture()
        a.loc[65:72,['dist_nearest_H','dist_nearest_A']]=[2.,1.]
        result=self.split(a,b,l)
        self.assertTrue((result[40:52]=='A').all())
        self.assertTrue((result[52:65]=='H').all())
        self.assertTrue((result[65:73]=='A').all())
