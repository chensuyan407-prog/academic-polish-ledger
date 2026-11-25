# academic-polish-ledger 0.2.0 — submission bundle for 写作02｜学术语言润色

Skill for **minimal-edit academic polishing** (English, Chinese, zh↔en translation of academic text). The agent edits
sentence by sentence; scripts merge the edits back into the original format (txt / Markdown / LaTeX / DOCX), record every
change (original → revised, from → to, type, reason) and check that the polish did not move a fact or change claim
strength: numbers and units, citation markers, Fig./Table/Eq. references, math, hedges, boosters, approximators,
significance and novelty wording, negation, quantifiers, causal vs correlational wording, conditions, direction words; plus a
termbase sweep (variants, abbreviation first use, hyphen/case drift, US/UK mix).

| path | content |
|---|---|
| `submission/` | **the Skill** (`SKILL.md`, `scripts/`, `rules/`, `templates/`, `examples/`, `README.md` = field dictionary, method, results, limits) |
| `skills/SKILL.md` | copy of the Skill entry file |
| `src/reproduce.py` | reruns the whole self-evaluation (≈ 20 s, CPU, standard library) |
| `tests/` | 6 author-written cases (`cases/*/input`), gold edits (`eval/gold`), planted defects (`eval/mutations_dev.json`, `eval/mutations_holdout.json`), planted language errors, `run_eval.py`, `FREEZE_holdout.sha256`, `make_zip.py` |
| `execution/` | `run.log`, `results/metrics.json`, `results/metrics_holdout_at_freeze.json`, `results/eval_rows*.json`, `results/commands.json`, per-case outputs (`results/cases/*/output`: polished text, change log, diff.html preview, fact map, check report, result.json), robustness runs, fresh-directory run |
| `arm_manifest.json`, `characterization.json`, `trace/trace.jsonl` | ARM bundle metadata |

## Reproduce

```bash
python src/reproduce.py        # optional: pip install pymupdf (only the PDF robustness check needs it)
```

## Results (author-written cases; not the platform's fixed cases; no model was run)

| set | planted defects caught (fail) | incl. warnings | benign edits passed | clean gold edits failing | baseline: numbers + citations only |
|---|---:|---:|---:|---:|---:|
| dev (4 cases, rules tuned on it) | 42/42 | 42/42 | — | 0/27 | 10/42 |
| held-out (2 cases written after the code freeze) | 13/18 | 15/18 | 3/4 | 0/10 | 5/18 |
| held-out after the post-freeze lexicon fix | 17/18 | 18/18 | 4/4 | 0/10 | 5/18 |

Defects are bad edits disguised with plausible change records (so "undocumented change" alone cannot catch them).
A record-coverage-only check catches 3/42 and 1/18. 8 of 37 clean gold edits needed an explicit `accept` with a reason
(intended weakening of absolute wording etc.). Robustness: 13/13 checks pass. The held-out set is no longer clean after
the fix; both numbers are kept. Details and limits: `submission/README.md`.
