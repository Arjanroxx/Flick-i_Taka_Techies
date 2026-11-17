# Step 4: short missing-ball continuity experiment

Research only; not promoted. The original model remains recommended.

P1 already interpolates short gaps, but original control evidence excludes imputed positions. The opt-in `gap_control` mode tests weak H/A continuity across missing or imputed stretches of at most 0.48 seconds. It requires immediate original confirmed-control endpoints agreeing on the same team, contiguous frames in one half, no out-of-bounds evidence and no D weight above neutral anywhere across the bracket. Accepted gaps get fixed weak 0.65/0.35 team likelihoods. Their observed-control mask remains false, so the existing uncertainty shield remains active. No coordinates or velocities are invented and long outages are not filled.

This is offline continuity evidence, not a new observation, true reception classifier or evidence for a turnover hidden inside the gap. It could incorrectly reinforce a team if a brief hidden opponent possession occurred; conservative bracketing limits but does not eliminate that risk. Broadcast/tactical fusion and new video detection are not implemented in this experiment.

Fixed settings were compared with original sustained control on the twelve development matches. Both methods scored mean partial-reference spellF1 **0.459170** and H/A macroF1 **0.785525**, with zero match wins. The predeclared development gate failed, so no public score or eight-match comparison was run. No parameter was loosened in response.

On competition tracking the rule activated on **zero frames**. Thus this strict formulation is inactive on that feed, rather than evidence that recovered observations improved the model. Original CSV checksum was verified unchanged. Broader missing-ball recovery remains unresolved and would require better observations or independently validated gap evidence.

All **118 tests passed**. The separate real-data candidate passed the official 199,319-row validator. Targeted tests cover weak support without claiming observation, opposite owners, D evidence, half changes, long gaps and nonconsecutive frame indices. Candidate configuration is `configs/gap_control_candidate.yaml`, with separate outputs under `artifacts/gap_control_candidate/`.

Run `python scripts/evaluate_gap_control.py` from the repository root to reproduce development scoring. Aggregate results and activation telemetry are in `docs/gap_control/`. Inference uses the same full-pipeline command as the original with the candidate configuration and `--skip-evaluation`; set the private data directory first. Previous Step 2 and Step 3 options are not enabled in this candidate.
