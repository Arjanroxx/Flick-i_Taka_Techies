# P4 final candidate verification and sign-off — Nov 17

## Decision

P4 accepts P3's final C and retains the omission of optional arbitration. D is explicitly empty. This completes P4's reviewed-C refresh for Nov 12–13 and frozen-D work for Nov 15. Release reproduction, public sanity checking and the technical document complete P4's Nov 16 preparation. Actual submission and its receipt remain pending.

## Independent verification

An isolated clean checkout of merged source `783d20d1fc6e32d4ee62a3c3ea87bf7e07aa407a` generated the complete tactical pipeline twice under Python 3.12.4. All five output hashes matched between runs and matched P3's published final handoff exactly:

| Output | SHA-256 |
|---|---|
| A | `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB` |
| B | `13A2E7D25083CF615FDE65F296511497ACAE784BD33B1E2817C833DAE4DBA624` |
| C | `5A2E686896DAEDF858019FE01D21A6A50BB00B5F6D5E31F7504743F36FB61872` |
| D | `6003E21FC6478FC506A5DA9A11569F5A4CBD99141C2D63C076EDE3659FA41177` |
| CSV | `D51E19A05ACAEA0A36DA065AD37C42DCFCB4B45E9FDD3CF8668FF96BA4E90FAA` |

Both CSVs passed the official 199,319-row validator. P2's separate `--deadball-only --verify-deadball` check passed. All 57 tests passed with no skips, including the four real-data integration tests. The checkout remained clean after generation and verification. Private configuration changes only locate the authorised bundle; model settings come from the merged configuration.

A newly created Python 3.12 environment then installed the pinned runtime packages (NumPy, pandas, SciPy, PyArrow, PyYAML and OpenCV). A third full pipeline run matched every published output hash, and all 57 tests passed again without skips. The complete `requirements-team.txt` install timed out downloading optional scikit-learn; the successful fresh check used the listed runtime packages, not the optional development stack. Installed versions and logs are recorded privately in `fresh_dependencies.txt` and `fresh_environment.json`.

## Arbitration and sanity

The current local rule reviewed eight windows from final C, accepted zero overrides and changed zero frames. Its baseline and candidate CSV hashes equal the release CSV above. The external Metrica run likewise reviewed eight windows with zero proposals and changes. This verifies omission against the final model, not just the older provisional C.

The frozen candidate was scored against the public five-minute labels without changing model settings: macroF1 **0.5188**, spellF1 **0.1926**, 37 predicted possessions and mean duration 8.0 s. The supplied smooth125 baseline scores higher (0.5812 / 0.4242). These are sanity results, not evidence of competitive accuracy or external generalisation. No private full-match score is available or required from the team.

## Evidence and remaining actions

Detailed local logs, configuration, hash comparison and verification manifest are under `artifacts/p4/final/`; the isolated checkout and its generated CSV are under `artifacts/p4/final/checkout/`. Match-derived inputs, caches and predictions remain ignored.

The validated CSV is also installed as `Flick-i_Taka_Techies.csv` at the repository root; the previous root CSV was backed up privately. `artifacts/p4/final/submission_package/` contains the final CSV, technical document and a private packaging record. This package has not been submitted.

P1's freeze/sign-off documentation is now merged through PR #15 and retains the same A hash. P4 completed the [team release record for B](../p2/nov17_release_verification.md); P2's personal confirmation remains unavailable and separate from the successful reproducibility checks. P4 does not sign on behalf of those owners. Confirm the submission form and cutoff from the organiser's email, submit the exact validated CSV with the public repository and technical document, and retain the receipt privately. No form submission has been performed here.
