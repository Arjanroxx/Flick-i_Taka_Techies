import itertools
import unittest
import numpy as np
from src.duration_model import phase_transition, infer_block, decode_duration


class DurationTests(unittest.TestCase):
    def setUp(self):
        self.base = np.array([[.999,.0004,.0006],[.0004,.999,.0006],[.0005,.0005,.999]])

    def test_age_changes_hazard_without_forced_minimum_or_maximum(self):
        t = phase_transition(self.base, 10., 25)
        self.assertGreater(t[1,2], t[0,2])
        self.assertGreater(t[0,2], 0)
        self.assertGreater(t[1,1], 0)
        np.testing.assert_allclose(t.sum(axis=1), 1)
        np.testing.assert_allclose(t[:4,4], .0006)
        np.testing.assert_allclose(t[4,[0,2,4]], self.base[2])

    def test_inference_matches_exhaustive_hidden_paths(self):
        t = phase_transition(self.base, 2., 10)
        e = np.array([[.6,.6,.3,.3,.1],[.2,.2,.7,.7,.1],[.1,.1,.2,.2,.7]])
        prior=np.array([1/6]*4+[1/3]); weights=[]; paths=list(itertools.product(range(5),repeat=3))
        expected=np.zeros_like(e)
        for path in paths:
            w=prior[path[0]]*e[0,path[0]]
            for i in range(1,3): w*=t[path[i-1],path[i]]*e[i,path[i]]
            weights.append(w)
            for i,k in enumerate(path): expected[i,k]+=w
        expected/=sum(weights)
        alpha,path=infer_block(e,t)
        np.testing.assert_allclose(alpha,expected)
        np.testing.assert_array_equal(path,paths[int(np.argmax(weights))])

    def test_half_reset_and_label_probabilities(self):
        e=np.tile([.8,.1,.1],(8,1)); halves=np.array([1,1,1,0,2,2,2,2])
        p,l=decode_duration(e,halves,self.base,{'scale_seconds':10.,'fps':25})
        np.testing.assert_allclose(p.sum(axis=1),1)
        np.testing.assert_array_equal(p[3],[0,0,1]); self.assertEqual(l[3],'X')
        q,_=decode_duration(e[4:],halves[4:],self.base,{'scale_seconds':10.,'fps':25})
        np.testing.assert_array_equal(p[4:],q)

    def test_invalid_scale_rejected(self):
        for scale in (0,-1,np.nan):
            with self.assertRaises(ValueError): phase_transition(self.base,scale,25)

    def test_duration_estimator_excludes_reference_window_edges(self):
        from scripts.evaluate_duration_model import uncensored_durations
        labels = np.array(list('HHHHAAAHHXXAAHHHAA'))
        periods = np.ones(len(labels), dtype=int)
        np.testing.assert_array_equal(uncensored_durations(labels, periods, 10), [.3, .3])

    def test_team_swap_equivariance(self):
        e = np.array([[.8,.1,.1]]*20+[[.1,.8,.1]]*20)
        halves = np.ones(40,dtype=int)
        settings={'scale_seconds':3.,'fps':25}
        p,l=decode_duration(e,halves,self.base,settings)
        q,m=decode_duration(e[:,[1,0,2]],halves,self.base,settings)
        np.testing.assert_allclose(q,p[:,[1,0,2]])
        np.testing.assert_array_equal(m,np.where(l=='H','A',np.where(l=='A','H',l)))
