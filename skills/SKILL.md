---
name: academic-polish-ledger
description: Minimal-edit academic language polishing (English and Chinese, plus zh<->en translation of academic text) that returns the full polished text in its original format (plain text, Markdown, LaTeX, DOCX) with a sentence-by-sentence change ledger (original, revised, from -> to, type, reason). Scripts merge the edits and verify that numbers, units, citations, Fig./Table/Eq. references, math, hedges, negation, quantifiers, causal wording and conditions did not move, and sweep the text against a termbase. Use when asked to polish, copy-edit, proofread, 润色, 修改语病, 统一术语, 去口语化, or translate a manuscript, abstract, thesis chapter, grant proposal or reviewer response. Do not use for content questions, summaries, literature search or writing new content.
---

# academic-polish-ledger (v0.3.0)

You decide how each sentence reads; the scripts keep the format, write the ledger, check meaning and always write
`/app/output/result.json`. Python 3.8+ standard library. Target: **3-5 requests, one build.**

## Steps

1. **Init** (one call):
   ```bash
   PY=$(command -v python3 || command -v python)
   for d in "$SKILL_DIR" /skills/weekly-skill /app/submission /app/skills /app/skills/* /skills/* "$(pwd)"; do
     [ -f "$d/scripts/ap_init.py" ] && SKILL_DIR="$d" && break; done
   $PY $SKILL_DIR/scripts/ap_init.py --case /input/case.json --out /app/output --work /app/work
   cat /input/task.md /app/work/chunks/chunk_*.md
   ```
   Variables do not survive between calls: reuse the full build command printed on init's `next:` line.
   Init prints the manuscript it chose (case.json `role: primary` / `primary_file` wins over larger reference files),
   termbase, mode, genre. Wrong file: re-run with `--manuscript FILE`.
2. **Edit**: write `/app/work/edits/chunk_01.json` (one file per chunk) in a single write:
   ```json
   {"chunk": 1, "status": "done", "edits": [
     {"sid": "p1.s2", "revised": "The method has been widely used.", "type": "agreement", "reason": "singular subject"},
     {"sid": "p2.s1", "revised": "...", "changes": [{"from": "a lot of", "to": "many", "type": "register", "reason": "colloquial"},
                                                    {"from": "show", "to": "shows", "type": "agreement", "reason": "subject"}]}],
    "terms": [{"preferred": "hole transport layer", "variants": ["hole-transporting layer"], "abbr": "HTL"}],
    "needs_confirmation": [{"sid": "p3.s1", "issue": "question for the author"}]}
   ```
   List only sentences you change; `"status": "done"` means the whole chunk was reviewed. `revised` = the whole new
   sentence (JSON-escape backslashes: `\\cite{x}`). Give `type`+`reason` per edit, or `changes` records per span.
3. **Build** (one call, always exit 0):
   ```bash
   $PY $SKILL_DIR/scripts/ap_build.py --work /app/work --out /app/output
   ```
   Missing records are completed from the diff (`AUTO-RECORDED`). A sentence whose revision moved a fact or claim
   strength is kept as the original and listed for the author (`REVERTED`). Warnings are informational.
4. **Stop** when it prints `DONE: status success`. Rebuild only if init chose the wrong file or a chunk is still
   unreviewed (`NEXT:` line). Optional: to keep a reverted revision on purpose, add
   `"accept": {"I05": "why"}` to that edit and rebuild once. Never edit result.json by hand.

## Editing rules

- **Minimal edit**: fix real errors (agreement, tense, articles, prepositions, punctuation, 搭配不当, 主语缺失, 中英文标点混用),
  keep the author's sentence. Restructure only unreadable sentences (`type`: restructure / sentence-split).
- **Never move a fact**: numbers, units, p values, citations (`[3]`, `\cite{}`), `\ref{}`, Fig./Table/Eq., math, names.
  Formatting only (1,248 -> 1248, 10nm -> 10 nm) is fine.
- **Keep claim strength**: hedges (may, suggest, 可能, 表明), no added boosters (clearly, 证明, 完全), approximators (about, 约),
  negation, quantifiers (all/some/only, 所有/仅), conditions (if, under, 在…下), association ≠ causation (有关 ≠ 导致).
- **Register**: remove colloquial and promotional wording (a lot of, huge, 非常, 国际领先); keep the claim itself.
- **Terminology**: follow the termbase; otherwise one form per concept (list it in `terms`), abbreviation defined once.
- **Genre**: journal/abstract - past tense for methods/results; thesis - 本文/本研究; grant - planned work (拟, will, aim to);
  reviewer response - polite, point by point, no new concessions.
- **Translation mode** (`translate_zh_en` / `translate_en_zh`): every source sentence needs an edit; records optional.
- **Do not invent** facts, data or references. Unclear, garbled or conflicting input -> keep it, add `needs_confirmation`.

## Outputs (`/app/output`)

`result.json` (case_id, every contract field, status, sources, change_summary, checks, needs_confirmation, uncertainty) ·
`polished.<ext>` in the input format (+ `polished.md`; DOCX keeps styles/tables) · `change_log.json|.md|.csv` ·
`diff.html` · `fact_map.json` · `check_report.json` · `review.md` (+ `bilingual.*` for translation, previews if available).
Status `success` = every in-scope sentence reviewed and nothing unresolved; `partial` only for unreviewed chunks,
untranslated sentences or no edits; `failed` = no manuscript text could be read.

Audit two versions made elsewhere: `$PY $SKILL_DIR/scripts/ap_check.py --orig a.md --rev b.md --json audit.json`.
Details (check codes, field mapping, limits): `README.md`.
