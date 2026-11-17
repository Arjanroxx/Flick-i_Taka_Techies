# Flick-i_Taka_Techies — technical document

Updated Nov 18, 2026 after the end-to-end audit. This document describes the audited method and its separately generated candidate. Earlier candidate hashes and scores in dated reports are historical; the previously packaged submission is preserved. No form submission or replacement has been performed by this audit.

## Candidate record

| Item | Record |
|---|---|
| Public repository | https://github.com/Arjanroxx/Flick-i_Taka_Techies |
| Audited implementation | `40fc2caa90f3b48adb761e1aa7a85d6276140083` |
| Configuration SHA-256 | 02742593FAC5EEE870FE81DE909DDCE80062DA771D280606939DB7E0AE2B1F43 |
| Candidate CSV SHA-256 | 75C89431B452D7727938A1C2B6127B58630EF80E89C7A7FEEF669D9FF52165E8 |
| Format/reproduction | 199,319 rows; two identical full-pipeline runs; standalone freeze agrees |
| Public five-minute sanity | spellF1 0.229630; macroF1 0.655278 |

Full A/B/C/D/CSV hashes, exact findings and limitations are in [the repository audit](docs/REPOSITORY_AUDIT.md). The earlier root CSV is not this new candidate. The new file is under `artifacts/repository_audit/Flick-i_Taka_Techies.csv` locally; generated outputs stay outside Git.

## Task and inputs

The system labels every tactical video frame H (Home live possession), A (Away live possession), D (dead ball), or X (abstention). The CSV contains exactly `frame,label`, ordered frames 0–199318. SpellF1 is the ranking metric and macroF1 the tie-breaker.

We use tactical ATD metadata/raw tracking and automatic Smart Tagging XML. Tracking maps through `video_frame = frame_id - 1`; normalized positions scale to 105.3×68 metres. Tag times are rounded seconds×25 with exclusive ends. Published play blocks are 11185–90651 and 110808–190197; outputs outside them are X and both halves have independent inference context.

The possession method consumes neither video pixels nor homography. Those assets supported earlier preparation/alignment checks. Broadcast was dropped because its cuts/replays require separate synchronization; the supplied local copy also had a video/tracking frame-count discrepancy and no broadcast homography. We do not infer a tactical offset from it.

## Spatial features — P1

Team membership is attached to track slots, not stable player identities. P1 computes ball geometry, missing gaps, nearest-team distances, motion, local densities and a distance-based control proxy. Only nearest-team distances and availability enter P3's team emissions.

Ball gaps up to 12 frames are linearly filled only inside a half, with observed endpoints and endpoint-implied speed at most 40 m/s. Long/edge gaps stay missing. Derivatives require observed positions and do not cross imputed frames or half boundaries. NaN coordinates remain missing; out-of-bounds positions remain unclipped for P2. Source teleports and slot switches are not fully repaired. No geometric Voronoi or explicit player-control model is claimed.

## Stoppages and restarts — P2

Observed unconfirmed/live geometry starts at D weight 0.05. Missing/imputed ball evidence starts at 1/3, which gives equal H/A/D emissions when team preference is also unavailable. Automatic set-piece tags supply weak D evidence (0.5) during occlusions preceding a detected restart. Tagged stationary support can supply 0.6; supported lead-up supplies 0.7. These are heuristic likelihood weights, not calibrated probabilities.

A boundary exit requires at least three observed out-of-bounds frames and at least one beyond a 0.35 m margin. Confirmed boundary evidence supplies 0.98 and persists through consecutive missing samples until another observed position. A sustained in-bounds return can establish restart evidence despite an intervening outage. No stoppage state carries across halves.

Stillness is speed ≤0.3 m/s; sustained restart motion is ≥3 m/s for three frames. Quiet-to-fast evidence additionally requires acceleration ≥8 m/s². Supported lead-up is limited to three seconds and stops at earlier observed live motion. The restart frame is live-weighted, and broad tags cannot reapply their missing-ball prior after their detected restart. These rules can miss in-bounds stoppages or infer too much persistence when a restart is fully occluded.

## Sequence model and possession rules — P3

Observed nearest-team distances pass through a softmax with temperature 3.0; missing/imputed team distances are neutral. H/A preferences receive weight `(1-D)` and P2 supplies D weight. Float32's neutral 1/3 representation is restored exactly before decoding.

A three-state HMM runs independently per half. The committed transition diagonal is 0.999; off-diagonal probabilities are recorded in the configuration. Viterbi supplies labels; forward-backward supplies probabilities and entropy. Exhaustive enumeration on a small fixture verifies both implementations.

There is no hard minimum possession duration. HMM penalties suppress some flicker but do not explicitly distinguish controlled receptions, defensive touches, loose balls and aerial duels. A missing/short-gap frame can emit X when three-state entropy is ≥0.9 nats or normalized conditional H/A entropy is ≥0.9, except for a decoded D. This is an uncertainty signal, not a guarantee of correct possession continuity: the spell scorer fills X from prior labels within scored runs, which can delay a true turnover.

## Optional arbitration — P4

The local deterministic arbiter samples up to eight windows with entropy ≥0.9, capped at 125 frames. A proposal needs at least three observed frames, nearest distance ≤2 m, team advantage ≥2 m, in-bounds geometry and D weight ≤0.2. Its proximity score and 0.8 acceptance threshold are uncalibrated. JSON types, inclusive bounds, labels and half containment are checked.

A proposal cannot carve an opposite-team island inside an uninterrupted base possession. Nonempty saved overrides require matching A/B/C fingerprints in the adjacent local response cache and a matching D fingerprint in its summary; stale or missing provenance fails closed. Current local and external trials accepted zero overrides, so the audited candidate uses explicit empty D. Arbitration has no demonstrated accuracy benefit.

## Development evidence, evaluation and limitations

No supervised possession training was performed. Synthetic fixtures tested missingness, interpolation, stoppages, turnovers and overrides. Historical temperature/transition/decoder experiments used five fixed seeds. Their idealized D weights and 355-frame spell scale do not establish independent real-match accuracy; that scale matches the published public-window mean. The new detector-pipeline stress test uses actual P2, incomplete synthetic tags, long outages and explicit spell lengths from one frame to one minute. Its settings were not selected on the competition labels.

Public Metrica Sample Game 1 tracking (revision `e706dd506b360d69d9d123d5b8026e7294b13996`) tests another match's 105×68 m coordinates and period handling. Its [README](https://github.com/metrica-sports/sample-data/blob/e706dd506b360d69d9d123d5b8026e7294b13996/README.md) invites analytics use and requests attribution. No independent continuous possession labels are available for this sample; external spellF1 and generalization remain unmeasured.

All 74 tests passed without skips, including real tactical integration. Mock and actual candidates passed the official validator. Two full runs matched every output hash; the standalone freeze matched C and CSV. Eight actual-match and eight external arbitration windows produced zero changes.

A final public-window sanity evaluation, after the implementation was fixed, yielded spellF1 0.229630 and macroF1 0.655278, with 37 predicted possessions. The public smooth125 reference is 0.4242 spellF1; our result is still weaker. The small change from the prior correction's 0.2222 is not evidence of better full-match performance. No parameter was changed after this sanity score. The private full-match score is unavailable. No competing versions are selected using public labels.

Runtime source inspection found no hosted model invocation or match-data upload. Competition assets, outputs and detailed caches stay local/ignored. No manually labelled or corrected competition data is used by these changes. Historical manual experiment provenance cannot be certified by source inspection alone.

## Reproduction

Use Python 3.12, the audited implementation commit above, and the authorised tactical bundle described in `DATA.md`. From its repository root:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-team.txt
# Set MTAH_DATA_DIR to the authorised bundle folder if it is outside ./data.
.venv/Scripts/python.exe scripts/run_full_pipeline.py --skip-evaluation
.venv/Scripts/python.exe evaluation/validate_submission.py Flick-i_Taka_Techies.csv
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Use a clean output directory with no old overrides. Existing nonempty D requires its matching `response_cache.json` and `summary.json`. `--from-artifacts` reuses A/B and regenerates C; it does not export an existing C. Compare exact hashes before accepting a replay.

`requirements-team.txt` pins all runtime packages. `requirements-development.txt` contains optional unpinned exploratory tools and is not needed to reproduce this method. `scripts/run_local_arbiter.py` and `scripts/assess_external_arbiter.py` are optional development checks, not required for the empty-D CSV. Only after freezing the implementation, use `evaluation/run_evaluation.py --gt public --results <folder-containing-only-the-candidate> --out <new-report-folder>` for pipeline sanity. Never use those labels to choose settings.
