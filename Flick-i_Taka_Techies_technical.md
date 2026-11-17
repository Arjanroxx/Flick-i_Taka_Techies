# Flick-i_Taka_Techies — technical document draft

Prepared Nov 16, 2026; P3 release fields updated Nov 17, 2026. The final CSV is generated, validated and reproduced. P1/P2 sign-offs, a P4 refresh against the P3-reviewed C, and official full-match scoring remain outside what this repository can complete locally.

## Task and output

We estimate Home possession (H), Away possession (A), dead ball (D) or abstention (X) for each of 199,319 frames in the tactical Barcelona–Athletic recording. The submission is a UTF-8 CSV with exactly `frame,label` and frames 0–199318 in order. The ranking metric is spellF1, with macroF1 as the first tie-breaker.

## Inputs

The baseline uses the provided tactical ATD metadata and raw tracking, plus automatic Smart Tagging XML. Normalized tracking positions are scaled to the official 105.3 × 68 metre pitch. Delivered tracking maps through `video_frame = frame_id - 1`. Smart Tagging seconds convert to frames at 25 fps, and its intervals exclude their end frame.

Published play blocks are 11185–90651 and 110808–190197. The output is X outside those blocks. Each half has independent interpolation and sequence context.

Tactical homography alignment and local sample video decoding have passed preparation checks. The possession baseline currently consumes tracking and tagging. Broadcast integration remains incomplete because its delivered video is one frame shorter than its published tracking count and broadcast homography is absent from the supplied folder.

## Spatial features — P1

P1 retains team-slot membership without assigning stable player identities. Features include ball position, observed motion, missing-ball gaps, nearest-team distances, relative velocities, local slot densities and a distance-based spatial-control proxy.

Short ball gaps of at most 12 frames are filled linearly only within a half, with observations at both ends and implied endpoint speed at most 40 m/s. Longer, edge and implausible gaps stay missing. Derivatives require observed endpoints, avoiding velocity or acceleration inferred from filled positions. Out-of-bounds coordinates remain available to P2.

Remaining source tracking jumps and slot identity switches can produce extreme motion estimates. The Voronoi-named feature currently represents a distance proxy. Neither that proxy nor relative velocities currently enter P3's emissions.

## Stoppage evidence — P2

P2 combines automatic set-piece windows with observed boundary exits, stillness and sustained motion. Boundary confirmation requires three consecutive observed out-of-bounds frames and at least one observation beyond the 0.35 metre margin. Restart candidates use sustained motion at least 3 m/s for three frames after supported boundary/stillness evidence. Stillness is at or below 0.3 m/s, and the stillness restart case requires acceleration at least 8 m/s².

Inferred dead-ball lead-up stops at earlier observed live motion, including movement below the restart-speed threshold. Missing and imputed observations cannot establish observed derivative evidence. Tag overlap combines evidence by strength.

The dead-ball values are heuristic emission weights. Untagged in-bounds stoppages, occlusions and projection errors remain limitations. The handoff command records A/XML/config hashes, B's hash, timing diagnostics and optional byte-for-byte regeneration.

## Sequence model and possession rules — P3

Nearest-team distance scores form H/A emissions, with the metre distance divided by a calibrated temperature of 3.0 before the softmax. Missing or imputed team-distance evidence is neutral between the teams. P2 supplies D evidence. A three-state HMM smooths emissions independently within each half using the transition matrix in `configs/config.yaml` (persistence 0.999). The decoded label path uses Viterbi; forward-backward still supplies the reported probabilities and entropy.

The strongest path selects H, A or D. An uncertainty shield can emit X for disputed short gaps or unavailable spatial evidence. The official spell scorer fills abstentions within each half, which can preserve an occluded possession but can also extend the preceding label past a turnover.

Loose-ball and challenge decisions therefore depend on the distance evidence, temporal context and uncertainty rule. The current baseline has no explicit player-control classifier. Restarts depend on P2's observed kinematics and automatic tag evidence. Temperature 3.0, persistence 0.999 and Viterbi were selected on five fixed-seed synthetic spell fixtures, not on the public competition labels; the evidence is in `docs/p3/p3_completion.md`. External frame-level possession labels are unavailable, so the transition settings have not been validated on another match.

## Optional arbitration — P4

The local experiment examines up to eight windows above entropy 0.9, with requests capped at 125 frames. Its deterministic proximity rule requires at least three consecutive observed frames with a nearest team within two metres, a two-metre advantage, low dead-ball evidence and an in-bounds ball. Proposals pass structured JSON validation, inclusive interval checks and a provisional score threshold of 0.8.

The Nov 16 refresh reviewed eight competition windows and eight external windows. Both produced zero proposals. The decision is to omit optional arbitration for the current candidate and supply an explicit empty D. Its integration reproduces the base CSV exactly. Refresh this decision against P3's reviewed C before the Nov 15-style final freeze is signed off.

## Development data and validation

No supervised possession training was performed. Fixed-seed synthetic spells provide controlled evidence for interpolation, missingness, turnovers, stoppages, emission calibration and decoder choice. On five seeds, the final P3 settings raised fixture spellF1 from 0.687 to 0.807 and reduced predicted spells from 711 to 573. Public Metrica Sample Game 1 tracking exercises another match's coordinate and period handling. It uses its own 105 × 68 metre pitch and source frame identifiers. Its weak boundary proxy can miss in-bounds stoppages.

The external assessment lacks independent continuous possession labels. Accuracy improvements and score calibration remain unmeasured. Public five-minute labels were inspected for alignment and fragmentation diagnostics, and the final score was measured after the settings were frozen. They were not used to choose the settings. The final candidate scores macroF1 0.5188 and spellF1 0.1926 with 37 predicted spells, below `baseline_smooth125` at 0.5812/0.4242. This is reported as a limitation, not as external validation.

Metrica Sports' sample revision is `e706dd506b360d69d9d123d5b8026e7294b13996`. Its public README invites analytics use and requests attribution. Downloaded input URLs and checksums are recorded locally. [External source and usage statement](https://github.com/metrica-sports/sample-data/blob/e706dd506b360d69d9d123d5b8026e7294b13996/README.md)

The provided public five-minute labels are reserved for pipeline sanity checks. Competition data and extracts stay local. Outputs and overrides are algorithmic. Match-specific cached evidence remains outside the public repository.

## Reproduction

Use Python 3.12 and `requirements-team.txt`. Unpack the authorised bundle as described in `DATA.md`, or set `MTAH_DATA_DIR` to its folder.

```powershell
.venv/Scripts/python.exe scripts/run_full_pipeline.py --skip-evaluation
.venv/Scripts/python.exe scripts/run_full_pipeline.py --deadball-only --verify-deadball
.venv/Scripts/python.exe scripts/run_p3_experiments.py
.venv/Scripts/python.exe scripts/freeze_p3_candidate.py --out artifacts/p3/release/freeze --submission Flick-i_Taka_Techies.csv
.venv/Scripts/python.exe scripts/run_local_arbiter.py
.venv/Scripts/python.exe scripts/assess_external_arbiter.py --download
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

For the omission decision, supply the validated empty D at the configured override path, then export using the matching A/B configuration and `--from-artifacts --skip-evaluation`. Validate the exact final file with `evaluation/validate_submission.py`. Record the configuration, code commit, input hashes, D and final CSV checksum together.

The final release manifest is `artifacts/p3/release/freeze/manifest.json`. It records A `0E0D790E…A629CB`, B `13A2E7D2…4DBA624`, C `5A2E6868…FB61872`, empty D `6003E21F…A41177` and CSV `D51E19A0…E90FAA`. A second freeze reproduced the C and CSV hashes exactly. The candidate CSV passed the official 199,319-row validator, and all 57 tests passed on the merged source tree. The P3 experiment and freeze utilities are `scripts/run_p3_experiments.py` and `scripts/freeze_p3_candidate.py`.

The Nov 16 local candidate and manifest are under `artifacts/p4/nov14/candidate/`. Private configurations and trial caches are described in `docs/p4/nov12_14_completion.md`. The Nov 16 clean-clone check reproduced the then-current five outputs and passed the then-current 45 tests. P3's final C supersedes that provisional C; P4 must refresh its empty-D decision against this C before release sign-off. P2's real B reproduced byte for byte on Nov 17, and P1's A matches the published frozen candidate hash.
