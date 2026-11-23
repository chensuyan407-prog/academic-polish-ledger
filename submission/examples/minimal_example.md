# Minimal example (illustrative - not a platform case)

## Input

`input/case.json`
```json
{"case_id": "example-1", "manuscript": "draft.md",
 "output_contract": {"polished_text": "polished paragraph", "change_log": "sentence-level changes"}}
```
`input/task.md`: `Polish the English; keep numbers, citations and claim strength.`

`input/draft.md`
```
The results suggests that doping may increase the conductivity by about 25% (Fig. 3) [5]. This effect don't depend on temperature.
```

## Calls

```bash
python $SKILL_DIR/scripts/ap_init.py --case input/case.json --out output --work work
# read work/chunks/chunk_01.md, then write work/edits/chunk_01.json:
```
`work/chunks/chunk_01.md` (excerpt, as printed by the script):
```
[p1.s1] The results suggests that doping may increase the conductivity by about 25% (Fig. 3) [5].
    keep: nums 25; citation [5]; xref fig3; hedge:weak=may; hedge:moderate=suggests; approximator=about
    hint EN12 (grammar): "The results suggests" - subject-verb agreement (plural subject, singular verb)?; ...
[p1.s2] This effect don't depend on temperature.
    keep: negation=don't
    hint EN01 (register): "don't" - contraction in academic prose; ...
```
`work/edits/chunk_01.json`
```json
{"chunk": 1, "status": "done", "edits": [
 {"sid": "p1.s1", "revised": "The results suggest that doping may increase the conductivity by about 25% (Fig. 3) [5].",
  "changes": [{"from": "suggests", "to": "suggest", "type": "agreement", "reason": "plural subject 'results'"}]},
 {"sid": "p1.s2", "revised": "This effect does not depend on temperature.",
  "changes": [{"from": "don't", "to": "does not", "type": "grammar", "reason": "singular subject; no contractions"}]}]}
```
```bash
python $SKILL_DIR/scripts/ap_build.py --work work --out output
# status: success - all segments reviewed, no unresolved fail
# units: 2 edited / 2 in scope; verdicts {'pass': 2}
```

## Output (example)

`output/polished.md`
```
The results suggest that doping may increase the conductivity by about 25% (Fig. 3) [5]. This effect does not depend on temperature.
```
`output/change_log.md` (excerpt)
```
## [p1.s1] pass
- original: The results suggests that doping may increase the conductivity by about 25% (Fig. 3) [5].
- revised: The results suggest that doping may increase the conductivity by about 25% (Fig. 3) [5].
- diff: The results ~~suggests~~**suggest** that doping may increase ...
| # | from | to | type | reason |
| 1 | suggests | suggest | agreement | plural subject 'results' |
```
Also written: `result.json` (contract fields `polished_text`, `change_log` filled), `change_log.json|csv`, `diff.md`,
`diff.html`, `fact_map.json`, `check_report.json`, `termbase.csv`, `review.md`.

## What a bad edit looks like

Same sentence rewritten as `The results show that doping increases the conductivity by 25% (Fig. 3) [5].`
(records: "suggests that doping may increase" -> "show that doping increases", "about 25%" -> "25%"):
```
status: partial - 2 unresolved fail flags
FAIL [p1.s1] I05: hedge removed or weakened (claim strengthened): ['may', 'suggests'] -> none
FAIL [p1.s1] I07: approximator/bound changed (precision of a number): ['about'] -> []
```
The edit is grammatical and documented, but it turns a hedged, approximate finding into a certain, exact one.
