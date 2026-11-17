# Flick-i_Taka_Techies — technical document

Prepared for release review Nov 17, 2026. Candidate integration and clean-source reproduction are verified for the locally generated provisional candidate. Final reviewed A/B/C/D sign-offs and the release checksum remain pending. Complete the [release checklist](docs/p4/release_checklist.md) before treating this document as the submitted version.

## Release record

| Item | Current record |
|---|---|
| Public repository | https://github.com/Arjanroxx/Flick-i_Taka_Techies |
| Reviewed merged source | `e89498c8898dc321501ec6de15d2cf9571f7c559`; includes P3 integration test and P4 reproduction report |
| Final source commit and configuration hash | Pending release freeze |
| Frozen A / B / C / D hashes | Pending owner-confirmed release manifest |
| Submission | `Flick-i_Taka_Techies.csv`; final SHA-256 pending |
| Final format validation and independent regeneration | Pending release-candidate checks |
| Public-window sanity result | Pending; no threshold selection on this sample |

The source above is the preparation baseline, not a claim that a final candidate was generated from it. The earlier reproduction used `0e6fe9122dca0a20b922791dfc0f61e331720108`.

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

Nearest-team distance scores form H/A emissions. Missing or imputed team-distance evidence is neutral between the teams. P2 supplies D evidence. A three-state forward-backward HMM smooths emissions independently within each half using the transition matrix in `configs/config.yaml`.

The strongest posterior selects H, A or D. An uncertainty shield can emit X for disputed short gaps or unavailable spatial evidence. The official spell scorer fills abstentions within each half, which can preserve an occluded possession but can also extend the preceding label past a turnover.

Loose-ball and challenge decisions therefore depend on the distance evidence, temporal context and uncertainty rule. The current baseline has no explicit player-control classifier. Restarts depend on P2's observed kinematics and automatic tag evidence. P3's final configuration and external-development rationale require its owner sign-off.

## Optional arbitration — P4

The local experiment examines up to eight windows above entropy 0.9, with requests capped at 125 frames. Its deterministic proximity rule requires at least three consecutive observed frames with a nearest team within two metres, a two-metre advantage, low dead-ball evidence and an in-bounds ball. Proposals pass structured JSON validation, inclusive interval checks and a provisional score threshold of 0.8.

The Nov 16 refresh reviewed eight competition windows and eight external windows. Both produced zero proposals. The decision is to omit optional arbitration for the current candidate and supply an explicit empty D. Its integration reproduces the base CSV exactly. Refresh this decision against P3's reviewed C before the Nov 15-style final freeze is signed off.

## Development data and validation

No supervised possession training was performed in the documented P4 experiments. Synthetic fixtures provide controlled evidence for interpolation, missingness, turnovers, stoppages and override mechanics. Public Metrica Sample Game 1 tracking exercises another match's coordinate and period handling. It uses its own 105 × 68 metre pitch and source frame identifiers. Its weak boundary proxy can miss in-bounds stoppages.

The external assessment lacks independent continuous possession labels. Accuracy improvements and score calibration remain unmeasured. The documented experiments retain provisional settings and provide no evidence for selecting them on the competition's public sample.

Metrica Sports' sample revision is `e706dd506b360d69d9d123d5b8026e7294b13996`. Its public README invites analytics use and requests attribution. Downloaded input URLs and checksums are recorded locally. [External source and usage statement](https://github.com/metrica-sports/sample-data/blob/e706dd506b360d69d9d123d5b8026e7294b13996/README.md)

The provided public five-minute labels are reserved for pipeline sanity checks. Competition data and extracts stay local. Outputs and overrides are algorithmic. Match-specific cached evidence remains outside the public repository.

## Reproduction

Use Python 3.12 and `requirements-team.txt`. Unpack the authorised bundle as described in `DATA.md`, or set `MTAH_DATA_DIR` to its folder. From a clean checkout of the final recorded source commit:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-team.txt
.venv/Scripts/python.exe scripts/run_full_pipeline.py --skip-evaluation
.venv/Scripts/python.exe evaluation/validate_submission.py Flick-i_Taka_Techies.csv
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Create `.venv` first with `py -3.12 -m venv .venv`. The commands above use the committed configuration; if the team freezes different settings, commit those settings and record that source version before release. A clean checkout has no saved overrides, so the pipeline writes a valid empty D. Existing workspaces must verify that their configured D is empty for the omission decision.

`--from-artifacts --skip-evaluation` reads saved A and B and regenerates C; it does not read P3's existing C. Before using that route, preserve the reviewed C separately and require the regenerated C to match its recorded hash. Record configuration, code commit, input hashes, A/B/C/D and final CSV checksum together. See the release checklist for exact checks and the public sanity-scoring command. External arbitration experiments are optional development steps and are not needed to regenerate the chosen empty-D submission.

The Nov 16 local candidate and manifest are under `artifacts/p4/nov14/candidate/`. Private configurations and trial caches are described in `docs/p4/nov12_14_completion.md`. A separate clean clone reproduced all five output fingerprints and passed all 45 tests, as recorded in `docs/p4/nov16_reproduction.md`. The final document needs the reviewed release versions and their reproduction result before submission.
