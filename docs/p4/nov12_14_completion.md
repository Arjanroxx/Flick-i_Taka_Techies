# P4 — Nov 12–14 work completed with available inputs

Executed Nov 16, 2026.

## Status

Nov 14's independent assessment, include/omit decision and technical-document draft are complete. Nov 12–13 integration is verified against a locally regenerated provisional C. Refresh and owner sign-off against P3's reviewed candidate remain pending.

## Candidate refresh

The working branch combines the Nov 11 P4 implementation with main through P2's final-handoff commit `ed3b96bf`. A, B and C were regenerated locally from this code into isolated output paths. A matches P1's published frozen-candidate SHA-256 `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB`. P2's real-data `--verify-deadball` command reproduced B byte for byte and saved its input/config/output fingerprints.

This records the exact inputs used for P4's local experiment. It leaves teammates' candidate sign-offs with their owners.

## Arbitration decision

The refreshed competition run and public Metrica external run each reviewed eight high-entropy windows. Both produced zero proposals, accepted overrides and changed frames. The score threshold remains uncalibrated. Omit optional arbitration for the current candidate and provide a validated empty D.

The empty D was replayed through the regular pipeline against the same A/B. The resulting candidate passed the official 199,319-row CSV validator and is byte-identical to the trial's base CSV. No public possession labels were used in this refresh or decision.

The decision needs a refresh when P3 supplies its reviewed/frozen C. An empty D remains an available release choice if further assessment supports it.

## Local evidence

All local files are under `artifacts/p4/nov14/` and remain ignored.

| Location | Contents |
|---|---|
| `inputs/` | Regenerated A/B/C and initial export |
| `p2_handoff.json` | Real-data B reproduction and fingerprints |
| `trial/` | Competition requests, response cache, trial D and before/after CSVs |
| `external/` | Refreshed other-match comparison and audit cache |
| `candidate/` | Explicit empty D, validated CSV and SHA-256 manifest |
| `input_config.yaml`, `candidate_config.yaml` | Private bundle and output paths |

```powershell
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config artifacts/p4/nov14/input_config.yaml --skip-evaluation
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config artifacts/p4/nov14/input_config.yaml --deadball-only --verify-deadball
.venv/Scripts/python.exe scripts/run_local_arbiter.py --config artifacts/p4/nov14/input_config.yaml --out artifacts/p4/nov14/trial
.venv/Scripts/python.exe scripts/assess_external_arbiter.py --out artifacts/p4/nov14/external
.venv/Scripts/python.exe scripts/run_full_pipeline.py --config artifacts/p4/nov14/candidate_config.yaml --from-artifacts --skip-evaluation
```

The candidate configuration selects the explicit empty D at `candidate/llm_overrides.parquet`. To create it from scratch, run this from the repository root before the final replay:

```powershell
.venv/Scripts/python.exe -c "from pathlib import Path; import pandas as pd; from src.contracts import SCHEMAS, write; table = pd.DataFrame({k: pd.Series(dtype=v) for k,v in SCHEMAS['overrides'].items()}); write('overrides', table, Path('artifacts/p4/nov14/candidate/llm_overrides.parquet'))"
```

On another machine, configure its authorised bundle location and preserve the same model settings. All 45 tests passed on the combined P2/P4 branch. A second candidate replay preserved every recorded A/B/C/D and CSV fingerprint.

## Technical draft and outstanding work

The [team technical draft](../../Flick-i_Taka_Techies_technical.md) covers the task, inputs, each stage's method, possession assumptions, external data, limitations, arbitration decision and reproduction. It still needs the final reviewed configurations, release checksum and clean-checkout result.

P4 can refresh D once P3's reviewed C arrives, then freeze the matching cache and complete the Nov 16 sanity/reproduction report. These are the remaining candidate-dependent steps.
