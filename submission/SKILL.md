---
name: academic-polish-ledger
description: Minimal-edit academic language polishing (English and Chinese, plus zh<->en translation of academic text) that returns the full polished text in its original format (plain text, Markdown, LaTeX, DOCX) together with a sentence-by-sentence change ledger (original, revised, from -> to, change type, reason). Deterministic scripts merge the edits and check that every revised sentence still says what the original said - numbers and units, citation markers, Fig./Table/Eq. references, math/LaTeX, hedge strength, boosters, approximators, significance and novelty wording, negation, quantifiers, causal vs correlational wording, conditions, direction words - and sweep the whole text against a termbase (variants, abbreviation first use, hyphen/case drift, US/UK mix). Use when asked to polish, copy-edit, language-edit, proofread, 润色, 修改语病, 统一术语, 去口语化, or translate a manuscript, abstract, thesis chapter, grant proposal or reviewer response while keeping its facts. Do not use for content questions about a paper, summaries, literature search, or writing new content from scratch - answer those directly without rewriting anything.
---

# academic-polish-ledger (v0.1.0)

You decide how each sentence should read; the scripts keep the text in its format, record every change and check
that no fact, number, citation or claim strength moved. Python 3.8+ standard library (PyMuPDF only for PDF input).
`SKILL_DIR` = the directory of this file (`/skills/weekly-skill`). Paths below use the evaluator layout
(`/input`, `/app/work`, `/app/output`); change them if yours differ.

## Workflow (about 5-10 model requests; a valid result.json exists after step 1)

1. **Init** (seconds):
   ```bash
   python $SKILL_DIR/scripts/ap_init.py --case /input/case.json --out /app/output --work /app/work
   ```
   Prints case_id, contract fields, detected **mode** (`polish` | `translate_zh_en` | `translate_en_zh`) and **genre**
   (journal | thesis | grant | response | abstract), which file is the manuscript / termbase / style guide / reference,
   termbase conflicts, encoding repairs. Writes `work/chunks/chunk_NN.md` (sentences with ids `p<para>.s<n>`, headings `h<n>`,
   the tokens that must survive under `keep:`, candidate problems under `hint`) and empty `work/edits/chunk_NN.json`.
   Wrong guess? Re-run with `--manuscript FILE`, `--termbase FILE`, `--mode`, `--genre`, `--chunk 20` (long sentences).
2. **Read** `task.md`, `case.json` and the style notes printed by init (target journal, British/American English, person,
   audience, sections to edit). Then read `chunk_01.md`.
3. **Edit** one chunk at a time: write `work/edits/chunk_NN.json` (format below) with only the sentences you change,
   set `"status": "done"` when every sentence of the chunk was reviewed (unchanged = deliberately kept).
4. **Build + check**:
   ```bash
   python $SKILL_DIR/scripts/ap_build.py --work /app/work --out /app/output
   ```
   Prints status and every `FAIL` / `warn` with sentence id, code and the triggering words. Exit 1 = fails remain.
5. **Fix every FAIL**, re-run step 4 (idempotent). For each fail either correct the sentence/record, or keep it and add
   `"accept": {"CODE": "why this change is intended"}` - accepted flags are listed for the author, never hidden.
   Read warnings; fix or accept. Then do the next chunk. Out of budget: build anyway - unreviewed chunks stay as
   original, status `partial`, and the result says which sentences were not reviewed.

## Edit file (`work/edits/chunk_NN.json`)

```json
{"chunk": 1, "status": "done",
 "edits": [
  {"sid": "p1.s2", "revised": "However, the long-term stability of PSCs is still limited by moisture and heat.",
   "changes": [{"from": "PSC are", "to": "PSCs is", "type": "agreement", "reason": "subject is 'stability'"}]},
  {"sid": ["p3.s1", "p3.s2"], "revised": "one merged sentence", "changes": [{"from": "...", "to": "...", "type": "merge", "reason": "..."}]},
  {"sid": "p4.s1", "revised": "...", "changes": [...], "accept": {"I06": "removed 'completely': sentence p4.s3 reports residual agglomeration"},
   "confirm": "question the author must answer"}
 ],
 "terms": [{"preferred": "hole transport layer", "variants": ["hole-transporting layer"], "abbr": "HTL", "zh": "空穴传输层"}],
 "needs_confirmation": [{"sid": "p2.s3", "issue": "..."}],
 "fields": {"<contract field>": {"kind": "polished_text"}},
 "notes": ["anything the author should know"]}
```
- `revised` = the whole new sentence. Keep LaTeX commands, math, citation keys exactly; JSON-escape backslashes (`\\cite{x}`).
- One record per change: `from` must be a substring of the original sentence, `to` of the revised one (`""` for pure
  deletion/insertion). Every changed span needs a record (R02); a record that does not match the text fails (R01).
- `type` ∈ grammar, agreement, number-agreement, tense, voice, article, preposition, collocation, word-choice, spelling,
  punctuation, format, terminology, abbreviation, register, hedging, concision, chinglish, clarity, sentence-split, merge,
  restructure, reorder, translation, consistency, style, subject, connective, other.
- `terms`: terminology decisions you make (agent termbase). They are swept over the whole text (D01 warn).
- `fields`: only if a contract field is not mapped automatically. Kinds: `polished_text`, `change_log`, `termbase`,
  `bilingual`, `fact_map`, `check_report`, `needs_confirmation`, `uncertainty`, `sources`, `summary`, `status`, or `{"value": ...}`.
- Translation mode: every sentence of the source language needs an edit (untranslated = fail S02); records are optional
  (use them for translation decisions: subject change, split, term choice).

## Editing rules (minimal edit)

- **Fix real errors, keep the author's sentence.** Change the smallest span that removes the error: agreement, tense,
  articles, prepositions, plurals, dangling modifiers, punctuation, 主语缺失, 搭配不当, 两面对一面, 中英文标点混用.
  Restructure only when the sentence is ungrammatical or unreadable, and type it `restructure` / `sentence-split`.
- **Never move a fact.** Numbers, units, ranges, CIs, p values, sample sizes, citation numbers/keys, Fig./Table/Eq. numbers,
  math, gene/chemical names stay exactly. Number formatting (1,248 -> 1248, hyphen -> en dash, 10nm -> 10 nm) is allowed.
- **Keep claim strength.** Do not drop or swap hedges (may/might/suggest/表明/可能/有望/拟/以期), do not add boosters
  (clearly, demonstrate, 证明, 完全, 彻底), keep approximators (about, ~, 约, 以上), significance words, negation and its scope,
  quantifiers (all/most/some/only, 所有/大部分/仅), conditions (if, under ..., after adjusting for, 当…时, 在…下),
  and association vs causation (associated with ≠ increases/causes; 有关 ≠ 导致).
- **Register**: remove colloquial, promotional and absolute wording (huge, perfect, 非常, 国际领先, 彻底解决) - but removing
  a booster or a priority claim weakens the author's claim: record it, `accept` the flag with the reason, and add a `confirm`.
- **Terminology**: follow the given termbase; if none, pick one form per concept, list it under `terms`, define each
  abbreviation once at first use ("full form (ABBR)") and use the abbreviation afterwards.
- **Genre**: journal/abstract - impersonal or "we", past tense for methods/results; thesis (学位论文) - 本文/本研究 instead of
  我们; grant (基金申请书) - planned work in future/intent form (拟, will, aim to), no unsupported superlatives; reviewer
  response - polite, point by point, do not concede or add claims for the author. British vs American spelling as requested.
- **Chinglish / 直译腔** (zh->en): choose the English subject (often the finding or method, not 本文/我们), drop empty
  nominalisations ("carry out an analysis" -> "analyse"), keep logical connectives only where the logic needs them.
- **Do not invent.** No new facts, references or data. Material missing, ambiguous, contradictory, garbled (mojibake) or
  a termbase conflict -> keep the text, explain in `needs_confirmation`.

## Check codes (ap_check.py; same input -> same report)

Meaning (per sentence, original vs revised): I01 numbers/units · I02 citation markers (incl. `\cite`) · I03 Fig./Table/Eq./
Section references (incl. `\ref`) · I04 math/LaTeX/URL tokens · I05 hedge removed or strengthened (fail) / added (warn) ·
I06 booster added (fail) / removed (warn) · I07 approximator or bound changed · I08 significance wording · I09 novelty claim or
promotional wording added (fail) / removed (warn) · I10 negation count · I11 quantifier class added/removed · I12 causal wording
introduced / association turned into an effect verb · I13 condition dropped (fail) / added (warn) · I14 direction flipped.
Record: R01 record not verifiable / no type or reason · R02 change without a record · R03 heavy rewrite (>55 % tokens) without a
restructure type · R04 residual style problem (rules marked residual) · R05 record without effect / unknown type.
Document: D01 termbase variant in the revised text (given termbase: fail; agent terms: warn) · D02 source term not rendered with
its target (translation) · D03 abbreviation defined late/twice/differently, termbase abbreviation never defined, undefined
abbreviations (info) · D04 hyphen/space/case drift of one term · D05 mixed US/UK spelling · S02 untranslated sentence.
In translation mode hedge levels may shift by one (warn), negation/universal quantifier/condition/direction differences warn.

## Outputs (`/app/output`)

`result.json` (case_id, every contract field, status, status_reason, sources with SHA-256, change_summary, checks,
needs_confirmation, uncertainty, termbase_conflicts) · `polished.<ext>` in the input format (+ `polished.md`; DOCX input ->
`polished.docx`) · `change_log.json|.md|.csv` · `diff.md`, `diff.html` (rendered side-by-side preview) · `bilingual.md|.csv`
(translation or when the contract asks for bilingual) · `termbase.csv` (terms, counts, enforced/conflict) · `fact_map.json`
(per sentence: numbers, citations, references, hedges, negation, quantifiers, causal words, conditions before/after, preserved
flag) · `check_report.json` · `review.md`.
Status: `success` only if every in-scope sentence was reviewed, no fail is left and every contract field is filled; else
`partial` with the reason; `failed` if no manuscript text could be read. Never edit result.json by hand to change the status.

## Failure handling

| Situation | Scripts | You |
|---|---|---|
| No case.json / no manuscript | `failed` result with reason | report; do not invent text |
| Manuscript guessed wrong | classification printed | re-run init with `--manuscript` |
| Mojibake / U+FFFD | UTF-8-as-CP1252 runs repaired and reported; GB18030 read | do not guess unreadable words; `needs_confirmation` |
| Japanese/Korean sentences | noted; only numbers/citations/refs/math checked there | edit cautiously or leave |
| Termbase conflict | listed, not enforced, added to needs_confirmation | choose only if the task decides it |
| Target style unclear | genre defaults to journal | state the assumption in `notes` |
| Only some sections requested | init marks out-of-scope sentences (left unchanged) | check the printed filter |
| Long text / budget short | chunks of 30; unreviewed chunks stay original, listed | edit the most important sections first, build often |
| Edit file invalid JSON / unknown sid | file or edit ignored, noted in uncertainty | fix and rebuild |
| A check is wrong for your sentence | — | `accept` with a reason (shown to the author) |

Standalone audit of any two versions (e.g. a rewrite made elsewhere):
`python $SKILL_DIR/scripts/ap_check.py --orig a.md --rev b.md [--termbase t.csv] [--mode translate_zh_en] --json audit.json`.
Candidate finder alone: `python $SKILL_DIR/scripts/ap_lint.py FILE`. See `README.md` for field dictionary, method and limits.
