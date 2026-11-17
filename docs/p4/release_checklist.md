# Final release checks — Flick-i_Taka_Techies

Prepared Nov 17, 2026, after PRs #11 and #12 merged into `e89498c8898dc321501ec6de15d2cf9571f7c559`. This is a ready-to-run checklist, not a completed release report. The organiser's stated deadline is Nov 17; the submitter must check the exact cutoff and form in the email.

## 1. Agree the files to ship

- [ ] P1 confirms frozen A: source commit, settings, private file location and SHA-256. The documented Nov 12 candidate hash is `0E0D790EDDAFBDCF74F31525B9A032E4419BE25BD429CBB0D05CB4A6D6A629CB`; confirm whether it is retained.
- [ ] P2 confirms frozen B, with the exact A hash, tactical XML hash, configuration and successful repeat-generation report. Use `scripts/run_full_pipeline.py --deadball-only --verify-deadball` only after the correct A is installed at the configured path.
- [ ] P3 confirms frozen model settings, C, candidate CSV and uncertainty-window list, with matching A/B hashes and source commit. Record fixture/external-development evidence and remaining limitations.
- [ ] P4 refreshes the arbitration decision against that C and confirms a validated empty D if omission is retained.
- [ ] Record those hashes in a private manifest. Keep reviewed files separately from working output paths so regeneration cannot overwrite the only handoff copy.

Code is already runnable. These confirmations establish which runnable versions constitute the team's submission; private file delivery cannot be inferred from a merged PR.

## 2. Generate and validate the candidate

Use a clean checkout of the agreed source commit, Python 3.12, the committed release settings and the authorised tactical bundle. The clean checkout must have no old D file. In PowerShell, from its repository root:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-team.txt
# Set MTAH_DATA_DIR to your authorised bundle folder if it is outside ./data.
.venv/Scripts/python.exe scripts/run_full_pipeline.py --skip-evaluation
if ($LASTEXITCODE -ne 0) { throw 'Candidate generation failed' }
.venv/Scripts/python.exe evaluation/validate_submission.py Flick-i_Taka_Techies.csv
if ($LASTEXITCODE -ne 0) { throw 'Final CSV validation failed' }
Get-FileHash -Algorithm SHA256 Flick-i_Taka_Techies.csv
```

- [ ] Validator accepts exactly 199,319 ordered frames, 0–199318, with header `frame,label` and H/A/D/X labels.
- [ ] Contracts A/B/C/D pass; labels outside the two published play blocks are X.
- [ ] Regenerated A/B/C match the agreed handoff hashes. D is valid and empty for omission; final labels match C inside play and X outside play.
- [ ] Save the exact command, source commit, configuration hash, Python/dependency versions, input hashes and output hashes privately. Save successful validator output with the candidate.

Important: `--from-artifacts` reuses A/B but **regenerates C**. It is not an export of an existing C. Compare regenerated C against the separately preserved P3 handoff before accepting that route. A valid CSV alone does not prove the agreed model or inputs were used.

## 3. Reproduce independently

- [ ] Run the same commands in another clean checkout, with the same frozen settings and inputs. Install the pinned dependencies there and record installation success.
- [ ] Require identical A/B/C/D and CSV SHA-256 hashes between both runs and the reviewed candidate.
- [ ] Run the test suite and record passes and skips separately:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

The new real-data integration class skips if assets cannot be found. Set `MTAH_DATA_DIR` before this check and require its four tests to actually run for release evidence. A skipped class is not a real-data pass. The previous clean-source check passed 45 tests and matched two runs, but reused existing dependencies and predates this integration-test merge.

## 4. Public-window sanity check

After freezing the candidate, score only that file. Use a fresh results folder containing exactly one CSV:

```powershell
New-Item -ItemType Directory -Path artifacts/release/sanity_input -ErrorAction Stop
Copy-Item -LiteralPath Flick-i_Taka_Techies.csv -Destination artifacts/release/sanity_input/Flick-i_Taka_Techies.csv
.venv/Scripts/python.exe evaluation/run_evaluation.py --gt public --results artifacts/release/sanity_input --out artifacts/release/sanity_report --no-detail
if ($LASTEXITCODE -ne 0) { throw 'Sanity scoring failed' }
Get-FileHash -Algorithm SHA256 Flick-i_Taka_Techies.csv
```

If the folder already exists, choose a new empty run folder. Record the public spellF1 and macroF1, input CSV hash and evaluation commit. Use this for pipeline/alignment sanity only; do not choose thresholds, model settings or manual corrections from its scores. No target accuracy or minimum score has been established. If a processing bug requires a change, document it and repeat the release checks for the changed candidate.

## 5. Package and submit

- [ ] Fill the release record in `Flick-i_Taka_Techies_technical.md`: final source commit, configuration hash, output hashes, validation/reproduction result and public sanity result.
- [ ] Confirm the document describes the exact frozen method, assets, missing-data behavior, possession rules, external evidence and limitations. Resolve all pending release fields.
- [ ] Confirm the public repository contains the frozen source, pinned dependencies and regeneration instructions; licensed data, predictions and private manifests remain excluded.
- [ ] P1/P2/P3/P4 confirm their respective release records. Agree one submitter.
- [ ] Submit the exact validated `Flick-i_Taka_Techies.csv`, public repository URL and technical document through the organiser's emailed form. Confirm the form's document-format requirements.
- [ ] Save the submitted CSV checksum, submitted document, timestamp and receipt privately. No submission has been made by preparing this checklist.
