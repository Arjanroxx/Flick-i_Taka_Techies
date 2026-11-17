import unittest
import numpy as np
import pandas as pd
from src.boundary_refinement import refine_boundaries


class BoundaryRefinementTests(unittest.TestCase):
    def fixture(self):
        a = pd.DataFrame({'ball_x': 40., 'ball_y': 30., 'half': 1,
            'dist_nearest_H': [1.]*25+[8.]*35, 'dist_nearest_A': [8.]*25+[1.]*35,
            'ball_is_imputed': False, 'gap_length_frames': 0}, index=range(60))
        b = pd.DataFrame({'is_dead_ball_prob': .05, 'is_out_of_bounds': False}, index=a.index)
        labels = np.array(list('H'*30+'A'*30))
        return a,b,labels

    def refine(self,a,b,l):
        return refine_boundaries(l,a,b,3.,{},{'fps':25})

    def test_localizes_existing_boundary_and_preserves_input(self):
        a,b,l=self.fixture(); saved=l.copy()
        result=self.refine(a,b,l)
        np.testing.assert_array_equal(result,np.array(list('H'*25+'A'*35)))
        np.testing.assert_array_equal(l,saved)

    def test_conflicting_missing_imputed_and_dead_evidence_skip(self):
        for kind in ('missing','imputed','dead','conflict'):
            a,b,l=self.fixture()
            if kind=='missing': a['ball_x']=np.nan
            if kind=='imputed': a['ball_is_imputed']=True
            if kind=='dead': b.loc[28,'is_dead_ball_prob']=.8
            if kind=='conflict':
                a.loc[35:40,['dist_nearest_H','dist_nearest_A']]=[1.,8.]
            np.testing.assert_array_equal(self.refine(a,b,l),l)

    def test_half_frame_gap_and_D_boundaries_are_protected(self):
        for kind in ('half','gap','D'):
            a,b,l=self.fixture()
            if kind=='half': a.loc[30:,'half']=2
            if kind=='gap': a.index=b.index=np.r_[np.arange(30),np.arange(31,61)]
            if kind=='D': l[30:]='D'
            np.testing.assert_array_equal(self.refine(a,b,l),l)

    def test_team_swap_and_adjacent_short_spells_preserve_sequence(self):
        a,b,l=self.fixture()
        result=self.refine(a,b,l)
        a[['dist_nearest_H','dist_nearest_A']]=a[['dist_nearest_A','dist_nearest_H']].to_numpy()
        swap=lambda x: np.where(x=='H','A',np.where(x=='A','H',x))
        np.testing.assert_array_equal(self.refine(a,b,swap(l)),swap(result))
        l=np.array(list('H'*20+'A'*2+'H'*8+'A'*30))
        result=self.refine(a,b,l)
        sequence=lambda x: x[np.r_[True,x[1:]!=x[:-1]]]
        np.testing.assert_array_equal(sequence(l),sequence(result))

    def test_two_neighboring_boundaries_move_without_deleting_possession(self):
        a,b,_=self.fixture()
        a['dist_nearest_H']=[1.]*18+[8.]*20+[1.]*22
        a['dist_nearest_A']=[8.]*18+[1.]*20+[8.]*22
        labels=np.array(list('H'*20+'A'*20+'H'*20))
        expected=np.array(list('H'*18+'A'*20+'H'*22))
        np.testing.assert_array_equal(self.refine(a,b,labels),expected)
