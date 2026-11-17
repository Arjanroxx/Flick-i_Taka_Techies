import json,sys
from pathlib import Path
import pandas as pd
root=Path.cwd();sys.path.insert(0,str(root))
from scripts.validate_skillcorner import verify_source
from src.learned_control_cache import load_cached
from src.skillcorner_validation import native_config,evaluate_reference
from src.p3_sequence_model import run
from scripts.download_skillcorner import digest
p=json.loads(Path('configs/skillcorner_protocol.json').read_text());blobs=json.loads(Path('configs/skillcorner_source_blobs.json').read_text());out=Path('artifacts/stable_contact');out.mkdir(exist_ok=True)
sources={n:digest(Path(n)) for n in ['src/stable_contact.py','src/p3_sequence_model.py','configs/skillcorner_protocol.json']};(out/'protocol.json').write_text(json.dumps({'sources':sources,'settings':'0.4 seconds, distance <=2m, advantage >=0.5m, speed 1..12m/s, distance rate <=2m/s','selection':'development only; no tuning; public only if mean gain >=0.01 and >=8 wins'},indent=2))
rows=[]
for match in p['development_matches']:
 folder=root/'artifacts/external/skillcorner'/match;t=verify_source(folder,match,p,blobs);a,b,ref=load_cached(folder,p,root/'artifacts/learned_control/feature_cache'/match,t)
 for mode in ['sustained_control','stable_contact']:
  cfg=native_config(p,'sustained_control');cfg['hmm']['team_evidence']=mode;cfg['stable_contact']={'fps':p['source_fps']}
  c=run(cfg,a,b);m=evaluate_reference(ref,c.raw_label,a.half,p['source_fps']);rows.append({'match':match,'mode':mode,'spellF1':m['partial_reference_spellF1'],'macroF1':m['macroF1_HA']})
 pd.DataFrame(rows).to_csv(out/'development.csv',index=False);print(match,flush=True)
f=pd.DataFrame(rows);v=f.pivot(index='match',columns='mode',values='spellF1');delta=v.stable_contact-v.sustained_control
assert sources=={n:digest(Path(n)) for n in sources}
r={'mean':f.groupby('mode')[['spellF1','macroF1']].mean().to_dict(),'gain':float(delta.mean()),'wins':int((delta>0).sum()),'development_gate_passed':bool(delta.mean()>=.01 and (delta>0).sum()>=8),'public_evaluated':False};(out/'report.json').write_text(json.dumps(r,indent=2));print(json.dumps(r),flush=True)
