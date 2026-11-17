# First research pass: nine approaches to over-merging

The protected Step 6 duration candidate has the highest recorded public spellF1 in this pass: **0.557143**, versus original sustained control **0.542857**. Its public macroF1 is lower (0.688999 versus 0.696450), and public uncertainty is broad. Neither figure is a full-match score or a reliable qualification prediction. No submission/default has been replaced.

| Step | Approach tested | Main finding | Public spellF1 |
|---|---|---|---:|
| 1 | Error diagnosis | Separate missed teams, missed D, merging and timing; no model change | 0.542857 unchanged |
| 2 | Hold confirmed exit through quiet on-pitch return | Tested opt-in D handling; sample score unchanged | 0.542857 |
| 3 | Sustained moving-contact evidence | Development gain, no public spell gain; macroF1 fell | 0.542857 |
| 4 | Weak continuity across bracketed short gaps | No development gain; zero competition activation | Not scored |
| 5 | Easier switching after longer confirmed contact | Development gain; public regression | 0.462500 |
| 6 | Learned duration scale with two hidden age phases | All twelve development matches improved; modest public gain | **0.557143** |
| 7 | Local midpoint boundary refinement | Hurt the stronger duration candidate | Not scored |
| 8 | Propose splits, verify with tracking rules | Extra splits reduced precision and spellF1 | Not scored |
| 9 | Train split decisions on counterfactual spell utility | Same-fold 0.509491 to 0.511721, 7/12 wins; uncertainty includes zero | Not scored |

Each row is a specific experiment within a method family, not an exhaustive search or proof that every alternative in that family fails. Detailed reports are linked by name: [diagnosis](POSSESSION_ERROR_DIAGNOSIS.md), [Step 3](STABLE_CONTACT.md), [Step 4](GAP_CONTROL.md), [Step 5](SUSTAINED_SWITCHING.md), [Step 6](DURATION_MODEL.md), [Step 7](BOUNDARY_REFINEMENT.md), [Step 8](SELECTIVE_SPLITS.md), [Step 9](SEGMENT_VERIFIER.md). The Step 2 option is `thresholds.hold_confirmed_exit_until_motion`, with its dedicated regression test; it is absent from protected configurations.

Steps 7–9 failed their predeclared development gates and were not checked against the public window. Step 9 uses separate coefficient-fit/calibration/validation matches, so its baseline is not identical to Step 6's leave-one-match-out baseline. The eight reused comparison matches were not used to choose settings in this pass.

The most useful findings are that more possessions can lower spellF1, explicit duration modelling helped this data, and proximity/movement checks alone still admit false splits. Fresh compatible H/A/D validation and stronger evidence of actual controlled reception are the next priorities. All raw/private match processing remained local; exported research parameters and aggregate results are reproducible, with protected original and Step 6 outputs preserved.
