# Flick-i_Taka_Techies — team roadmap

Our goal is one reproducible CSV with 199,319 rows, one per tactical-video frame. Every row says Home (`H`), Away (`A`), Dead ball (`D`) or Uncertain (`X`).

## Dates and data arrival

**Data arrived on Nov 6, 2026**, ahead of the original Nov 8 planning estimate. The submission deadline remains **Nov 17, 2026**.

P4 has completed today's external sample loader and source assessment, plus a real tactical baseline run, tracking/tag alignment checks, local video extraction checks and an initial uncertainty-window queue. See [the Nov 6 report](docs/p4/nov06_completion.md). These checks accelerate preparation. Each teammate still owns the quality of their method.

P1, P2 and P3 can start reviewing real inputs now. Keep Nov 16 for exact reproduction and Nov 17 for submission. Broadcast video has a one-frame count discrepancy, and broadcast homography is absent from the supplied folder. Continue tactical development while investigating optional broadcast alignment.

## Who owns what

| Person | Responsibility in plain language | Main file | Handoff |
|---|---|---|---|
| P1 | Work out where the ball and both teams are. Fill only suitable short ball gaps. | `src/p1_spatial_features.py` | **A** — `artifacts/spatial_features.parquet` |
| P2 | Estimate when play has stopped and when it restarts. | `src/p2_deadball_detector.py` | **B** — `artifacts/deadball_mask.parquet` |
| P3 | Turn A and B into a stable possession sequence. | `src/p3_sequence_model.py` | **C** — `artifacts/base_predictions.parquet` and the final CSV |
| P4 | Check difficult windows with an automated local method and own evaluation and reproduction checks. | `src/p4_arbiter_and_eval.py` | **D** — `artifacts/llm_overrides.parquet` and evaluation reports |

**A handoff is a file another person can use.** Tell the team which code commit created it, which input version it used, where to get it privately, and whether its contract check passed. Generated files stay out of Git. Team code goes into Git.

**WAIT FOR P# · Nov #** marks a prerequisite from another person. A same-day marker means the producing teammate hands off first. Tasks without that marker need no new handoff from another teammate that day. Existing shared setup code and previous work by the same person are assumed available.

## Setup everyone completes on Nov 5

From the repository folder, use Python 3.12:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-team.txt
.venv/Scripts/python.exe scripts/run_full_pipeline.py --mock
```

Success means the official validator prints `OK` and `199319 rows`. Synthetic outputs are in `artifacts/mock/`. To generate only mock A and B, run `scripts/generate_day1_mocks.py` with the same Python interpreter.

P4 also runs the official examples, which need no licensed match assets:

```powershell
.venv/Scripts/python.exe evaluation/run_evaluation.py --gt public --out artifacts/official_baseline_check
```

## Nov 5 — get everyone running

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Complete setup. Open mock A and understand its ball, distance and gap columns. | A mock file that passes `validate("spatial", table)`, plus a short setup status for the team. | None |
| P2 | Complete setup. Open mock B and map each column to stoppage or restart evidence. | A mock B that passes `validate("deadball", table)`, plus a list of tag types the parser must support. | None |
| P3 | Run the mock pipeline. Read C and inspect its probabilities and labels. | Valid mock C and a CSV accepted by the official validator. | None |
| P4 (Arjan) | Score the four bundled official baseline CSVs. Read the evaluation and rules documents. | **Complete on Nov 6** — [scoreboard and verification report](docs/p4/nov05_completion.md). Mock pipeline and contracts passed. | None |

## Nov 6 — data arrived; complete preparation and start real checks

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Review the delivered tactical tracking and the existing real A output. Try synthetic missing-observation cases as well. | Loader checks showing `frame_id - 1` alignment and missing-value handling on synthetic input. | None |
| P2 | Inspect real tag categories and timing, then try synthetic boundary cases for throw-ins, corners, kick-offs and unknown teams. | Parser examples showing category mapping, half-open intervals and safe handling of `N/A`. | None |
| P3 | Inspect the real baseline output and use synthetic turnovers, stoppages and occlusions to check behavior. | A short behavior report showing where smoothing changes labels and where X is emitted. | None |
| P4 | Select and load a public dataset from another match for development. Check that its licence and labels suit the intended use. | **Complete** — [working event loader and source assessment](docs/p4/nov06_completion.md). Direct frame-possession tuning remains unsupported without suitable labels. | None |

## Nov 7 — finish preparation

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Check metre conversion, short-gap interpolation, half resets and the inverse homography helper using fixtures. | Checks that preserve long gaps, avoid interpolation across halves and retain out-of-bounds coordinates. | None |
| P2 | Check tag rounding and exclusive end frames. Try restart detection with synthetic speed spikes. | Boundary examples and a list of provisional restart thresholds. | None |
| P3 | Verify that unavailable distances produce neutral team evidence and that each half starts independently. | Finite normalized probabilities on missing-input examples, with X outside play. | None |
| P4 | Frame extraction has passed locally on both delivered videos. Finish the local arbiter response format and invalid-response checks. | A frame-extraction example and a response schema with label, confidence and interval bounds. | None |

## Nov 8 — review and improve the first real handoffs

Initial ingestion passed on Nov 6. Use this day for teammate-reviewed handoffs and feature-quality checks. Earlier dates below describe baseline availability, not completed teammate method reviews.

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Review the Nov 6 spatial baseline. Verify team-slot mapping, metre conversion and missing-ball quality; publish P1's reviewed A v0. | **A v0** at the agreed handoff path, passing its contract, with missing-ball and gap-length summaries. | Data email |
| P2 | Build on the passed Nov 6 time-base check. Review real categories, overlap and restart-window quality. | A tag-count summary and examples of parsed intervals, with no manual possession labels. | Data email |
| P3 | Compare delivered frame counts with the published half blocks. Keep the mock pipeline ready for A/B replay. | An integration checklist identifying the exact A and B files needed for the first real run. | Data email |
| P4 | Build on the Nov 6 local video checks. Document the broadcast discrepancy, start the technical document and design the local arbitration experiment. | Video-read status and a technical-document outline covering inputs, method, training sources and reproduction. | Data email |

P1 starts with tactical tracking. Broadcast is an optional extension because it needs a separately verified synchronization method.

## Nov 9 — first connected run on the real data

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Inspect A v0 for unreasonable speeds, missing-team distances and gap behavior. Fix clear processing bugs. | **A v1**, validated, with a brief description of changes from A v0. | None |
| P2 | Combine automatic tags, unclipped ball positions and kinematics into the first stoppage mask. | **B v0**, validated, with candidate restart frames and confidence assumptions. | **WAIT FOR P1 · Nov 8 — A v0** |
| P3 | Run the sequence model with the first real A and B. Validate its output format. | **C v0** and a first real-data CSV that passes the official format validator. | **WAIT FOR P1 · Nov 8 — A v0; P2 · Nov 9 — B v0** |
| P4 | Implement structured-response parsing and rejection of malformed arbiter output using synthetic examples. | Parser examples rejecting invalid labels, confidence values and interval bounds. | None |

## Nov 10 — improve stoppages and inspect difficult windows

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Improve imputation only where evidence supports it. Compare short linear filling with a candidate alternative. | A comparison based on fixtures or other-match data, and an updated A if justified. | None |
| P2 | Recompute restart candidates using improved spatial features. Review tag-window limits and out-of-bounds behavior. | **B v1** and a restart-detection summary. | **WAIT FOR P1 · Nov 9 — A v1** |
| P3 | Compare posterior labels with a Viterbi path on external or synthetic examples. Export disputed windows from C v0. | A decoder comparison and a list of high-entropy windows for P4. | None |
| P4 | Use C v0 to test local automated arbitration on a small set of windows. Keep competition frames and features on the local machine. Log model, inputs and response. | **D v0**, possibly empty, plus an auditable response cache. No hand-labelled overrides. | **WAIT FOR P3 · Nov 9 — C v0** |

## Nov 11 — check feature quality and tune externally

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Check duplicate slots, nearest-team distances and relative-velocity spikes. Assess whether geometric control adds value. | **A v2** with a feature-quality summary. | None |
| P2 | Test whether B v1 splits continuous play or misses plausible stoppages. Develop thresholds on other games or fixtures. | **B v2** and a record of the evidence used for threshold choices. | None |
| P3 | Tune transition settings using suitable other-match labels or fixtures. Keep a record of each experiment. | A candidate configuration and an external-development comparison. | **WAIT FOR P4 · Nov 6 — external sample loader/source assessment**, if using it |
| P4 | Check confidence filtering, overlapping overrides and half-boundary rejection. Assess arbitration on licensed other-match examples. | An override-application check and a provisional confidence threshold. | None |

## Nov 12 — refresh the complete team handoff

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Freeze the next spatial candidate and document remaining limitations. | **A candidate 1**, validated and reproducible from code. | None |
| P2 | Rebuild B using the agreed spatial candidate. | **B candidate 1**, validated, with its A version recorded. | **WAIT FOR P1 · Nov 12 — A candidate 1** |
| P3 | Run the agreed sequence settings on the new A and B. | **C candidate 1**, a valid CSV and an updated disputed-window list. | **WAIT FOR P1 · Nov 12 — A candidate 1; P2 · Nov 12 — B candidate 1** |
| P4 | Start with the prior C while waiting, then regenerate arbitration for the new disputed windows. | **D candidate 1**, or an explicit empty D if arbitration is not ready. Record the C version used. | **WAIT FOR P3 · Nov 12 — C candidate 1** |

Order this day's handoffs **P1 → P2 → P3 → P4**. P4 can finish the refreshed D on Nov 13 if needed.

## Nov 13 — resolve integration problems

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Resolve reproducible feature-processing bugs and review long-gap behavior. | Final proposed A changes, or confirmation that A candidate 1 is retained. | None |
| P2 | Resolve reproducible category or restart-processing bugs. | Final proposed B changes, or confirmation that B candidate 1 is retained. | None |
| P3 | Check the X shield on other-match data or fixtures. Confirm it cannot bridge a half boundary. | Final proposed sequence settings and a description of X behavior. | None |
| P4 | Complete D candidate 1 and integrate it with the candidate CSV. Check its effect on external examples. | Validated override integration and an updated technical-document draft. | **WAIT FOR P3 · Nov 12 — C candidate 1** |

## Nov 14 — freeze the feature inputs

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Choose the spatial version to ship. Keep broadcast only if its alignment is verified and the full run works. | **Frozen A**, its code commit and regeneration command. | None |
| P2 | Rebuild and freeze the stoppage mask against frozen A. | **Frozen B**, its code commit and the A version used. | **WAIT FOR P1 · Nov 14 — frozen A** |
| P3 | Finalize sequence choices using external evidence. Prepare the final A/B integration run. | Frozen model settings and a written rationale based on external development. | None |
| P4 | Complete external arbitration comparisons and decide whether the optional arbiter is ready to ship. | A documented include/omit decision, cached responses and the technical-document draft. | None |

## Nov 15 — freeze predictions and overrides

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Run frozen A generation again and compare results. | Reproduction confirmation or a clearly reported processing bug. | None |
| P2 | Run frozen B generation again and compare results. | Reproduction confirmation or a clearly reported processing bug. | None |
| P3 | Generate the final base predictions from frozen A and B. | **Frozen C**, its settings and a valid candidate CSV. | **WAIT FOR P1 · Nov 14 — frozen A; P2 · Nov 14 — frozen B** |
| P4 | Regenerate or confirm local overrides against frozen C. Freeze the output cache and document model settings. | **Frozen D**, including an empty D if arbitration is omitted, plus reproduction instructions. | **WAIT FOR P3 · Nov 15 — frozen C** |

## Nov 16 — reproduce the submission from a clean checkout

| Person | What to do | Deliverable by end of day | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Verify input discovery and A generation in the clean-checkout run. | Confirmation that documented data paths work without personal machine paths. | None |
| P2 | Verify tag loading and B generation in the same run. | Confirmation that tags, missing data and restart candidates are handled consistently. | None |
| P3 | Run the full workflow with the frozen versions. Verify exact CSV reproduction and format. | A release-candidate CSV, its SHA-256 checksum and a successful validator log. | **WAIT FOR P4 · Nov 15 — frozen D** |
| P4 | Use the public five-minute ground truth once for pipeline sanity checks. Finish the technical document and reproduction checklist. | Sanity-check report, final document draft and confirmation that the documented command reproduces the candidate CSV. | **WAIT FOR P3 · Nov 16 — release-candidate CSV** |

Use the public ground truth to check alignment and pipeline correctness. Model selection and threshold tuning use other games or fixtures.

## Nov 17 — validate and submit

| Person | What to do | Deliverable before submission | Cross-teammate prerequisite |
|---|---|---|---|
| P1 | Confirm the frozen spatial code and input instructions are in the repository. | P1 sign-off. | None |
| P2 | Confirm the frozen stoppage code and assumptions are documented. | P2 sign-off. | None |
| P3 | Regenerate `Flick-i_Taka_Techies.csv` and validate that exact file. | Final CSV, checksum, code commit and validator log. | **WAIT FOR P1 · Nov 17 — sign-off; P2 · Nov 17 — sign-off** |
| P4 | Verify the CSV and technical document use the team name, check the public repository, and coordinate the team's single submission. | Final document, public repo URL and a submission receipt saved privately by the person submitting. | **WAIT FOR P3 · Nov 17 — final CSV** |

The organiser's deadline is Nov 17. Confirm the exact cutoff time from their email or form and agree an earlier internal cutoff. P4 coordinates who submits the form.

## Commands after the data arrives

Unpack the bundle as described in `DATA.md`, then run:

```powershell
.venv/Scripts/python.exe scripts/run_full_pipeline.py
# If the bundle is stored elsewhere:
.venv/Scripts/python.exe scripts/run_full_pipeline.py --data-dir 'D:/match-data'
# Reuse teammates' real A and B:
.venv/Scripts/python.exe scripts/run_full_pipeline.py --from-artifacts
```

The full run creates A, B, C, D and `Flick-i_Taka_Techies.csv`, validates the CSV, then scores it against the public five-minute sample. `--skip-evaluation` keeps format validation and skips scoring. `MTAH_DATA_DIR` is supported. Reports are in `artifacts/evaluation/`.

To validate the final team-named file:

```powershell
.venv/Scripts/python.exe evaluation/validate_submission.py Flick-i_Taka_Techies.csv
```

## Working together

Each person owns their main `src/p#_*.py` file. Agree changes to `src/contracts.py` and `configs/config.yaml` with affected teammates before merging. Use a small branch and pull request for each change. Include the command run, its result and any handoff versions in the pull request.

At the end of each day, each person posts three things in the team's chosen channel: the deliverable location, the code commit and any blocker. If a handoff is late, notify the dependent teammate immediately so they can continue with mocks or the last valid version.

Keep licensed match assets in `data/` and generated tracking, video clips, API caches and reports in `artifacts/`. Share these only through an authorised private location. Keep API keys in environment variables. The official OVERVIEW.md prohibits sending competition videos, datasets or extracts to hosted LLMs. Use a local method for competition-match arbitration. The public repository contains code, instructions and the organisers' public example files.

## Technical conventions and current limits

- Submission frames follow the tactical video. Delivered ATD maps with `video_frame = frame_id - 1`.
- Official play blocks are 11185–90651 and 110808–190197. Contract A uses `half=0` outside play. The final export uses X there.
- Coordinates are scaled from normalized tracking to 105.3 × 68 metres. Out-of-bounds coordinates are preserved for P2.
- Spatial float features may contain NaN when an observation is unresolved. Density counts are zero if the ball-relative observation is unavailable; check coordinates before interpreting those counts.
- Short gaps are filled only within a half and with observations at both ends. Long and edge gaps remain missing.
- Relative velocity comes from adjacent observations of the nearest track slot and can spike when a slot changes identity. `voronoi_control_H` currently uses a distance-based proxy.
- Smart Tagging intervals exclude `end_frame`. D override intervals include `end_frame` and must stay within one half.
- P2's thresholds are starting values. Its restart flag marks an inferred candidate. Automatic tags provide uncertain evidence.
- P3 currently uses forward-backward HMM posteriors. X-shield and transition choices need external development.
- P4 loads an existing valid D or returns an empty table. Its window finder and frame extractor are implemented. External Metrica ingestion and local arbitration remain development work. Gemini experiments are limited to external examples whose terms permit upload.
- The provided public five-minute labels are for pipeline sanity checks. No human labels, manual corrections or frame-specific hand-coded possession rules on the competition match are allowed.

The official files came from upstream commit `f8f2629ff1e0985f81d7e59d8413678514ee1530`. Verification passed under Python 3.12 for the official baseline scores, mock pipeline, an official-format synthetic fixture, gap and half boundaries, saved overrides, artifact replay and CSV validation. Initial real-data ingestion, contracts and local decode checks passed on Nov 6. Possession accuracy and feature quality remain development work.
