# Step 3: sustained moving-contact evidence

Research only. Keep the original candidate recommended.

Adds opt-in `hmm.team_evidence: stable_contact`. Original sustained-control evidence remains intact. Additional evidence requires 0.4 seconds of consecutive observed nearby moving contact: nearest distance <=2 m, advantage >=0.5 m, ball speed 1..12 m/s and nearest-distance change <=2 m/s. Half changes, frame gaps, invalid/imputed positions and conflicting teams break continuity. D evidence and smoothing settings are unchanged. Missing evidence is not treated as control.

This is a nearest-team distance-stability proxy, not true player-relative co-motion or a reception classifier. Tracking identity/slot switches make existing player-velocity features unreliable without further work. Stable nearest distance can still occur without genuine control. No provider possession labels enter inference.

Fixed physical-prior settings were compared only on twelve external development matches, without a parameter sweep. The predeclared gate required mean spell gain >=0.01 and >=8 match wins. Mean partial-reference spellF1 rose 0.459170 to 0.469284, with 9/12 wins; H/A macroF1 rose 0.785525 to 0.792264. This is development evidence, not independent validation; automatic partial H/A references cannot assess D errors.

After passing that gate, unchanged settings were checked on the public sample: spellF1 stayed 0.542857 with 11 possessions; macroF1 fell 0.696450 to 0.693669. No post-score tuning occurred. The new method therefore does not establish an improvement on the challenge. Eight reused comparison matches were not evaluated. Original configurations and submission outputs remain protected.

All 116 tests passed. The real-data pipeline with `configs/stable_contact_candidate.yaml` passed the official submission validator. Outputs are separate under `artifacts/stable_contact_candidate/`. Aggregate development/public results are in `docs/stable_contact/`.

Run `python scripts/evaluate_stable_contact.py` from the repository root for the development comparison, or `python scripts/run_full_pipeline.py --config configs/stable_contact_candidate.yaml --skip-evaluation` for inference after setting the private data directory. The earlier Step 2 dead-ball option is not enabled in this candidate; its results are separate.
