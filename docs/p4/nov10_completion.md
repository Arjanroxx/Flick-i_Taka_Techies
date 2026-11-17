# P4 — Nov 10 local arbitration dry run

Owner: Arjan (P4). Completed on Nov 12, 2026.

## Result

The local arbiter reviewed eight high-entropy windows from a freshly regenerated tactical baseline. Every request retained P3's sequence, producing a valid empty D v0. Both the baseline CSV and the arbitration CSV passed the official validator. Repeated runs produced byte-identical caches, D files and CSVs.

A, B and C were generated locally using merged team code at base commit `8b6270390a631fbcec7eefc2b0e56cf94d494205`. This exercises the current P3 implementation while the team prepares its reviewed candidate handoffs. Regenerate the experiment when those handoffs arrive. The input hashes identify the exact files used.

## Model and decisions

The deterministic model is `observed_proximity_v1`, following the Nov 7–8 experiment plan. It consumes validated A, B and C. It selects up to eight disjoint intervals above the configured entropy threshold of 0.9, ordered by peak entropy and then frame number. A request longer than 125 frames is cropped around its peak while staying inside its source interval and half.

An H or A proposal needs at least three consecutive frames satisfying all these conditions.

- Both ball coordinates and both nearest-team distances are finite.
- The ball is observed, the original missing-gap length is zero, and play is inside a published half.
- P2 reports in-bounds play with dead-ball evidence at or below 0.2.
- The nearest team is within two metres and at least two metres closer than the opponent.
- The same team remains nearest throughout the proposed run.

The model proposes an inclusive interval only when it would change at least one base label. Its score is the minimum of `farther_distance / (nearer_distance + farther_distance)` over the run. The existing override-confidence setting of 0.8 filters proposals. Every proposed response passes the existing structured-response parser and D contract before application.

These are provisional engineering settings chosen for the first experiment, with no search against competition labels. The score needs independent calibration. This rule reuses spatial and stoppage evidence already available to P3, so any accuracy benefit needs separate measurement. Video-based arbitration remains future development.

## Local evidence and handoff

The output directory is `artifacts/p4/nov10/dry_run/`.

| File | Purpose |
|---|---|
| `llm_overrides.parquet` | D v0, with zero accepted rows under the existing Contract D filename |
| `response_cache.json` | Model settings, A/B/C file hashes, source-code hashes, each requested window, local input rows, proposals, acceptance and retention decisions |
| `baseline.csv` | P3's labels before arbitration |
| `with_overrides.csv` | Labels after validated confidence-filtered overrides |
| `summary.json` | Run outcome and SHA-256 fingerprints for the output files |

The cache records all eight decisions as `retain_base` with reason `no_supported_change`. Zero accepted overrides also means zero changed frames. This completes the dry run without establishing an accuracy improvement.

Detailed inputs, caches and generated files remain in ignored local storage. Share D and its input fingerprints through the team's authorised private handoff location. Use this D with the matching C. The dry-run command stages and validates outputs before replacing its output files and writes its fingerprint manifest last. It also detects an input file changing while being read.

## Reproduction

This machine's input-regeneration configuration is stored privately at `artifacts/p4/nov10/input_config.yaml`. It points to the authorised downloaded bundle and isolated A/B/C output paths.

```powershell
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config artifacts/p4/nov10/input_config.yaml --skip-evaluation
.venv/Scripts/python.exe scripts/run_local_arbiter.py --config artifacts/p4/nov10/input_config.yaml
.venv/Scripts/python.exe scripts/run_local_arbiter.py --config artifacts/p4/nov10/input_config.yaml --out artifacts/p4/nov10/repeat_run
```

On another machine, prepare A, B and C using the same team code and configuration, then pass the configuration naming those files. The default command reads the standard artifact paths and writes into `artifacts/p4/nov10/dry_run/`. The dry run uses the official format validator. It uses no competition ground-truth file.

## Verification

All 34 tests passed, including seven new tests covering supported inclusive intervals, real turnovers in synthetic evidence, missing and imputed observations, contested distances, stoppages, short runs, agreement with the base, confidence filtering and bounded half-local selection. The command test generates synthetic A/B/C, runs the full arbiter twice, checks an accepted override and verifies deterministic output fingerprints. Malformed-response tests from Nov 9 continue to pass.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

The Windows verification run placed temporary test files under `artifacts/tmp` because the process could not write to its default temporary directory. Logs are saved locally at `artifacts/p4/nov10/tests.log`. Two final real runs also verified the cache's input/source fingerprints and byte-identical output files.

P4's next task is the Nov 11 override-application assessment, including overlap handling and independent evidence for the provisional confidence threshold. Reviewed candidate C versions will need refreshed window selection and D generation.
