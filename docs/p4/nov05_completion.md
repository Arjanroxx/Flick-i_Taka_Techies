# P4 — Nov 5 task completion

Owner: Arjan (P4). Completed on Nov 6, 2026 (Asia/Calcutta).

**Status — complete.** Scored the four official baselines, reviewed the evaluation and competition rules, and confirmed the mock pipeline passes. This task needs no match-data access or teammate handoff.

The tested workflow was commit `da79e70d8a4534710c41ddd185fe35282883bbb9`. Python 3.12.4 was used with numpy 2.5.4, pandas 3.1.1, scipy 1.18.1, pyarrow 26.0.1 and PyYAML 6.0.3.

## Official baseline scoreboard

Scored against the organisers' public five-minute sample, containing 7,500 graded frames and 17 possessions. The saved machine-readable output is [baseline_scoreboard.csv](baseline_scoreboard.csv).

| Public rank | Baseline | macroF1 | spellF1 | Predicted possessions | Mean duration (seconds) |
|---|---|---|---|---|---|
| 1 | baseline_smooth125 | 0.5812 | 0.4242 | 16 | 18.5 |
| 2 | baseline_smooth50 | 0.6207 | 0.3256 | 26 | 10.8 |
| 3 | baseline_smooth25 | 0.6200 | 0.2868 | 36 | 7.6 |
| 4 | baseline_raw | 0.5972 | 0.0378 | 131 | 2.0 |

All four entries scored successfully. Results match the public examples in the official README. This run verifies scorer setup. It provides no basis for choosing our smoothing settings. The organisers publish `baseline_smooth50` as the full-match floor with spellF1 0.2433; the private full-match labels were not used in this check.

## Mock pipeline checks

| Check | Result |
|---|---|
| A — spatial features | Contract passed, 199,319 rows |
| B — dead-ball mask | Contract passed, 199,319 rows |
| C — base predictions | Contract passed, 199,319 rows |
| D — overrides | Contract passed, empty table as expected for this mock run |
| Submission header and index | Exactly `frame,label`, frames 0–199318 in order |
| Official format validator | Passed |
| Frames outside the published halves | All 40,462 labelled X |

The synthetic CSV contains H 79,252, A 68,967, D 10,638 and X 40,462. It is an integration example. Match accuracy remains untested while the licensed assets are unavailable.

Mock CSV SHA-256:

```text
6c431c68ce422daab8bef9095a0c301ee7cad683817cdc661d857a00fa0c6679
```

## Rules P4 needs to apply

- Optimize possession structure using spellF1. macroF1 is the first tie-breaker. spellF1 averages possession matching over temporal IoU thresholds 0.3, 0.4, 0.5, 0.6 and 0.7.
- X counts as a miss on a graded frame under macroF1. For spellF1, X is forward-filled within each half, with leading gaps backfilled. An abstention can carry the old answer past a genuine turnover.
- Use the public five-minute ground truth for alignment and pipeline sanity checks only. Training, model selection and threshold tuning need other-match data or fixtures.
- No manual possession labels, tracking corrections or hand-crafted rules tied to specific frames of the competition game. Overrides must come from an algorithm.
- Keep competition videos, tracking and extracts out of hosted LLMs. Use local arbitration for match assets. External examples need terms that permit their intended use.
- Keep licensed assets and reconstructive derived data out of the public repository. Store them in ignored local folders and use authorised private sharing.
- The repository must regenerate the exact final CSV. Document external data, model settings and dependencies. Save automated arbitration outputs so the final run can reproduce them.

These points come from [EVALUATION.md](../../EVALUATION.md), [RULES.md](../../RULES.md), [OVERVIEW.md](../../OVERVIEW.md#use-of-large-language-models) and [SUBMISSION.md](../../SUBMISSION.md).

## Reproduce these checks

From the repository root after installing `requirements-team.txt`:

```powershell
.venv/Scripts/python.exe evaluation/run_evaluation.py --gt public --out artifacts/p4/nov05/baselines --no-detail
.venv/Scripts/python.exe scripts/run_full_pipeline.py --mock
```

Local evidence from this run is saved in `artifacts/p4/nov05/`: `baseline_run.log`, `mock_run.log`, `contracts_check.log`, and `baselines/` with the scoreboard and individual reports. Mock handoffs and the CSV are under `artifacts/mock/`. These generated files remain local. The public scoreboard is copied into this report folder so teammates can see the result.

P4's Nov 6 task is to select and load an appropriately licensed public dataset from another match and record whether its labels support supervised development.

