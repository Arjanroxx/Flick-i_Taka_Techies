import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from evaluation import possession_metrics as pm
from scripts.train_segment_verifier import utility_targets,fold_splits
from src.segment_verifier import (FEATURES,propose,apply_proposals,fit_model,predict,
                                  canonical_digest,refine_predictions)


class SegmentVerifierTests(unittest.TestCase):
    def fixture(self):
        a=pd.DataFrame({'ball_x':40.,'ball_y':30.,'half':1,'dist_nearest_H':1.,
            'dist_nearest_A':8.,'ball_speed':3.,'ball_is_imputed':False,
            'gap_length_frames':0},index=range(100))
        a.loc[40:51,['dist_nearest_H','dist_nearest_A']]=[2.,1.]
        b=pd.DataFrame({'is_dead_ball_prob':.05,'is_out_of_bounds':False},index=a.index)
        c=pd.DataFrame({'raw_label':'H','prob_H':.8,'prob_A':.1,'prob_D':.1,'state_entropy':.6},index=a.index)
        return a,b,c

    def test_geometry_proposal_features_and_team_symmetry(self):
        a,b,c=self.fixture();settings={'fps':10,'long_spell_seconds':5}
        proposals=propose(c,a,b,3.,{'confirmation_frames':2},settings)
        self.assertEqual(len(proposals),1)
        self.assertEqual((proposals[0]['start'],proposals[0]['stop']),(40,52))
        self.assertEqual(len(proposals[0]['features']),len(FEATURES))
        a[['dist_nearest_H','dist_nearest_A']]=a[['dist_nearest_A','dist_nearest_H']].to_numpy()
        c['raw_label']='A';c[['prob_H','prob_A']]=c[['prob_A','prob_H']].to_numpy()
        swapped=propose(c,a,b,3.,{'confirmation_frames':2},settings)
        np.testing.assert_allclose(proposals[0]['features'],swapped[0]['features'])
        self.assertEqual(swapped[0]['opponent'],0)

    def test_D_conflict_and_missing_proposal_are_rejected(self):
        a,b,c=self.fixture();settings={'fps':10,'long_spell_seconds':5}
        b.loc[45,'is_dead_ball_prob']=.8
        self.assertEqual(propose(c,a,b,3.,{},settings),[])
        a,b,c=self.fixture();a.loc[40:51,'ball_x']=np.nan
        self.assertEqual(propose(c,a,b,3.,{},settings),[])

    def test_decision_preserves_D_X_and_resolves_overlaps(self):
        labels=np.array(list('HHHXHHDDHHHH'))
        proposals=[{'start':2,'stop':6,'owner':0,'opponent':1},
                   {'start':4,'stop':7,'owner':0,'opponent':1}]
        output=apply_proposals(labels,proposals,np.array([.9,.8]),.5)
        self.assertEqual(''.join(output),'HHAXAADDHHHH')
        np.testing.assert_array_equal(labels== 'X',output=='X')
        np.testing.assert_array_equal(labels== 'D',output=='D')
        np.testing.assert_array_equal(apply_proposals(labels,proposals,[.9,.8],1.1),labels)

    def test_counterfactual_utility_positive_negative_and_exact_global_metric(self):
        proposal={'start':10,'stop':14,'owner':0,'opponent':1}
        labels=np.array(list('H'*24+'XX'+'A'*10))
        for first in ('H'*10+'A'*4+'H'*10,'H'*24):
            reference=np.array(list(first+'XX'+'A'*10))
            targets=utility_targets(reference,labels,np.ones(len(labels)),[proposal])
            self.assertEqual(len(targets),1)
            changed=apply_proposals(labels,[proposal],[1.],.5)
            gt=pm.label_codes(reference);runs=pm.valid_runs(gt)
            score=lambda x:pm.spell_scores(gt,pm.fill_abstentions(pm.label_codes(x),runs),runs)['mean_f1']
            self.assertAlmostEqual(targets[0]['gain'],score(changed)-score(labels))
            self.assertEqual(targets[0]['positive'],int(first!= 'H'*24))
        reference=np.array(list('H'*11+'XXX'+'H'*10+'XX'+'A'*10))
        self.assertEqual(utility_targets(reference,labels,np.ones(len(labels)),[proposal]),[])

    def test_training_only_scaling_and_constant_fallback(self):
        x=np.zeros((20,len(FEATURES)));x[10:,0]=1
        y=np.r_[np.zeros(10),np.ones(10)]
        model=fit_model(x,y,np.ones(20))
        scores=predict(model,[{'features':row.tolist()} for row in x])
        self.assertGreater(scores[10],scores[0])
        self.assertEqual(fit_model([],[],[])['kind'],'constant')
        bad=dict(model,features=['invalid'])
        with self.assertRaises(ValueError):predict(bad,[])

    def test_outer_validation_fit_and_calibration_are_disjoint(self):
        splits=fold_splits([str(i) for i in range(12)])
        validation=[]
        for split in splits:
            self.assertEqual(len(split['fit']),6);self.assertEqual(len(split['calibration']),2)
            self.assertFalse(set(split['fit'])&set(split['calibration']))
            self.assertFalse(set(split['validation'])&set(split['fit']+split['calibration']))
            validation+=split['validation']
        self.assertEqual(len(set(validation)),12)

    def test_canonical_model_hash_is_format_independent_and_tampering_fails(self):
        a,b,c=self.fixture()
        model={'version':1,'features':FEATURES,'kind':'constant','score':0.,'threshold':1.1}
        self.assertEqual(canonical_digest(model),canonical_digest(json.loads(json.dumps(model,indent=2))))
        with tempfile.TemporaryDirectory(dir='artifacts/tmp') as temp:
            path=Path(temp)/'model.json';path.write_text(json.dumps(model))
            cfg={'hmm':{},'segment_verifier':{'fps':10,'long_spell_seconds':5,
                'model_path':str(path.resolve()),'model_canonical_sha256':canonical_digest(model)}}
            np.testing.assert_array_equal(refine_predictions(c,a,b,cfg),c.raw_label)
            model['score']=1.;path.write_text(json.dumps(model))
            with self.assertRaisesRegex(ValueError,'checksum'):
                refine_predictions(c,a,b,cfg)
