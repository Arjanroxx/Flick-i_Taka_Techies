# P2 output — team release verification, Nov 17

Arjan (P4) completed the remaining technical release verification for B using P2's merged implementation. P2 was unavailable for personal confirmation. This record accepts the verified output for the current team candidate; it does not claim P2's personal approval or new detector development.

## Frozen release inputs and output

| Item | Record |
|---|---|
| P2 implementation | Final handoff commit `ed3b96bf24443a79d9aeb4db43e167ad09427126`, merged through PR #9 |
| Verified complete implementation | `783d20d1fc6e32d4ee62a3c3ea87bf7e07aa407a` |
| Frozen A SHA-256 | `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` |
| Frozen B SHA-256 | `13A2E7D25083CF615FDE65F296511497ACAE784BD33B1E2817C833DAE4DBA624` |
| Final CSV SHA-256 | `D51E19A05ACAEA0A36DA065AD37C42DCFCB4B45E9FDD3CF8668FF96BA4E90FAA` |
| Inputs | Frozen A, authorised tactical Smart Tagging XML and committed `configs/config.yaml` |
| Private output | `artifacts/p4/final/checkout/artifacts/deadball_mask.parquet` |

The later merged P1/P4 release documentation does not change pipeline implementation or settings. Input XML and private configuration fingerprints are retained in the local P2 handoff evidence; licensed assets and generated B remain outside Git.

## Checks completed

- Two complete real-data pipeline runs produced identical A/B/C/D/CSV hashes and matched P3's published candidate.
- P2's `--deadball-only --verify-deadball` command passed with `reproduced_byte_for_byte: true` and the B hash above.
- Contract checks and official final CSV validation passed.
- All 57 tests passed without skips, including the real-data integration class.
- A newly installed Python 3.12 runtime environment reproduced all five hashes and passed all 57 tests again.

Evidence: `artifacts/p4/final/deadball.log`, `hash_comparison.json`, `verification.json`, `fresh_environment.json` and test logs. See [P4's final verification](../p4/nov17_release_signoff.md) and [P2's method and commands](stoppage_mask.md).

## Scope and remaining work

This completes the reproducibility and release-record work for B against the agreed frozen A. P2's heuristic thresholds and limited detection of in-bounds stoppages remain documented limitations. No thresholds were changed using the public sample. Personal confirmation from P2 can follow; it is not a missing file or technical dependency for the verified candidate. Actual submission and its receipt remain pending with the submitter.
