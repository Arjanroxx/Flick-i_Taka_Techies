# Flick-i Taka Techies

Technical document — More Than a Hack 2027, Phase 1: Ball Possession

Technical document | More Than a Hack 2027 | Phase 1: Ball Possession

Final method: observed sustained-control evidence with a two-phase possession-duration decoder. The output is one H, A, D or X label for every tactical-video frame. The submitted file contains exactly 199,319 ordered rows, frames 0 through 199318.


## 1. Assets and processing

The final pipeline uses BAR-ATH tactical ATD metadata and tracking text, plus automatic tactical Smart Tagging. It takes the published frame rate, play blocks and pitch dimensions from games.py. ATD frame IDs are converted from one-based to zero-based video frames; normalized coordinates become metres on the 105.3 x 68 m pitch. Team membership comes from tracking metadata. No stable player identities are assumed.

Broadcast tracking, both videos and homography files were available but are not consumed by final inference. We use the supplied normalized tracking geometry directly. Video-based recovery, hosted models, learned ownership classifiers, local split verifiers and boundary refinements are not enabled in this release.


## 2. Spatial and dead-ball evidence

Missing coordinate pairs remain missing. Gaps of at most 12 frames may be linearly interpolated only inside a half and when endpoint displacement implies at most 40 m/s. Imputed positions are marked; ball derivatives require observed endpoints, and imputed positions supply no confirmed team-control evidence. This avoids treating missing balls as (0,0) or producing velocity spikes across gaps.

A team supplies control evidence when the observed, non-imputed ball is within 2 m of its nearest tracked player and that distance has at least a 2 m advantage over the opponent for three consecutive frames. The frame must be in play, in bounds and have dead-ball weight at most 0.2. Confirmation is offline and backdated to the first supported contact. Other frames supply neutral H/A evidence.

Dead-ball evidence combines confirmed pitch exits, stationary-ball patterns inside automatic set-piece windows and restart motion. Exit confirmation uses at least three observations and a 0.35 m boundary margin. Confirmed exits persist across missing observations. Restart cues use sustained speed and, for quiet-to-fast kicks, acceleration. Smart Tagging is treated as noisy evidence rather than a ground-truth boundary. Half breaks reset all temporal inference.


## 3. Duration-aware sequence decoding

Team likelihoods use a softmax of negative nearest-team distances with temperature 3 m. They combine with dead-ball weights into H/A/D emissions. Missing evidence receives neutral treatment. We then decode five hidden states: home-young, home-established, away-young, away-established and dead. The two age phases are latent and collapse to the required H/A labels.

The duration scale is 9.51291250794194 seconds, estimated from other-match labels. Phase progression and established-team exit use 1 - exp(-2 / (scale * fps)). Young-team H/A exit is 0.1 times the original team-switch probability. Original team-to-D and D exit probabilities remain. The two-phase structure and 0.1 multiplier are fixed modelling choices, not fitted optima. Young possessions can end, and established possessions have a self-loop: there is no imposed minimum or maximum possession length.

Exact forward-backward inference produces phase probabilities; their sums produce H/A/D probabilities and entropy. Viterbi gives the most likely hidden-state path. High uncertainty with unavailable control or short tracking gaps can yield X. Conditional H/A entropy uses a normalized 0.9 threshold; three-state entropy uses 0.9 nats. Frames outside official play blocks are X. Arbitration overrides are empty and explicitly disallowed by the final build command.


## 4. External labelled data and fitting

We used SkillCorner Open Data, pinned revision 4340d274572876239c154c90bc507a9b3250a656. Its possession.group field automatically supplies home/away team references; null means unknown, not D. No human annotations of the challenge match, private ground truth or third-party events about that match were used. Credit: SkillCorner and PySport; the source snapshot is MIT-licensed. Source: https://github.com/SkillCorner/opendata

The 12 duration-fit matches are 2011166, 2013725, 1925299, 2006229, 2006363, 2015213, 1927964, 1959846, 1899585, 2007721, 2010085 and 1886347. The scale is the equal-match average of mean complete H/A spell durations, pooling teams; spells touching known-reference run edges are excluded as censored. This is an empirical scale estimate, not maximum-likelihood fitting of every transition hazard. No D duration was trained because those references have no D labels.

For duration validation, each match was excluded from its own scale estimate. The final scale uses all 12 development matches. Eight additional external matches were used in earlier frozen control-model comparisons; they did not fit this duration parameter. External data and all fitted values/protocols are reproducible through the pinned downloader and scripts/evaluate_duration_model.py. External data are not needed to rerun final inference because the fitted scale is in the final configuration.


## 5. Possession semantics and measured results

A defensive touch alone is not intended to establish possession. Sustained observed control provides evidence; loose or distant ball phases remain neutral and sequence continuity supplies context. D ends a possession even when the same team restarts. These are algorithmic proxies for controlled possession, not proof of control. There are no manual corrections or match-frame-specific rules.

The duration method improved partial spellF1 on all 12 development matches. These are partial automatic H/A references, not official H/A/D challenge scores. The public sample has 17 reference possessions; our method predicts 11 and matches eight at IoU 0.5. The small mean-spell gain has broad uncertainty: public 90% intervals are approximately [0.343, 0.745] for the original and [0.357, 0.745] for the final candidate. Public data were inspected during experiments, so this is not an untouched holdout. No model parameter was fitted or threshold-selected on the public labels.


## 6. Limitations and reproducibility

Around 41% of scored frames lack the ball. Long outages, tracking noise and ambiguous challenges can merge possessions or misplace boundaries. D recovery remains limited (public D F1 about 0.485). External references have unknown gaps, no D annotations and potentially different ownership semantics. Duration estimates can be biased by censoring exclusions. No full-match accuracy or qualification guarantee is claimed. Fresh compatible H/A/D labels and stronger reception evidence would be the next priorities.

Use Python 3.12 and the pinned requirements-team.txt. From the repository root:

```
python -m pip install -r requirements-team.txt
python scripts/build_submission.py --data-dir "PATH/TO/DATASET"
```

The build uses configs/final_submission.yaml, regenerates all intermediate stages from the original licensed bundle, exports canonical UTF-8/LF CSV, validates every row and requires the manifest checksum. It performs no public scoring or external training download. Original/protected duration outputs were checked and regenerated byte-identically before release packaging. Raw tracking and videos are not redistributed. Repository: https://github.com/Arjanroxx/Flick-i_Taka_Techies

```
9841111b9b3ed93a93fe80ff61934ab2ac747872a1794582662ab05a04a9c2aa
```
