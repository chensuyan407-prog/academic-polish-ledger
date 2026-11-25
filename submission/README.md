# academic-polish-ledger 0.2.0 — reference

Minimal-edit academic polishing with a verifiable change ledger. The agent writes sentence-level edits; five
standard-library Python scripts segment the manuscript, merge the edits back into the original format, check
meaning invariants per sentence, sweep terminology over the whole text, and write the deliverables.

## Files

| path | role |
|---|---|
| `SKILL.md` | entry point: workflow, edit format, editing rules, check codes, failure handling |
| `scripts/ap_common.py` | reading (UTF-8/UTF-16/GB18030, mojibake repair, DOCX, PDF via PyMuPDF/pdftotext), format-aware segmentation (txt, Markdown, LaTeX), protected tokens, number extraction, lexicon matching, termbase loading |
| `scripts/ap_init.py` | step 1: case discovery, mode/genre detection, section filter, chunk files, edit templates, termbase + conflicts, skeleton result.json |
| `scripts/ap_build.py` | step 3: apply edits, run checks, write polished files, change log, diff, bilingual table, termbase, fact map, report, result.json |
| `scripts/ap_check.py` | the checks (importable) + standalone audit of any two versions (`--orig --rev`) |
| `scripts/ap_lint.py` | candidate finder (heuristic hints), also used for residual-problem warnings |
| `rules/lexicon.json` | meaning classes compared by the checks (hedges by strength, boosters, approximators, significance, novelty, promotional, negation, quantifiers, causal, correlational, conditions, direction), EN + ZH, with exclusions |
| `rules/style_rules.json` | 47 candidate rules (EN, ZH, LaTeX): contractions, colloquial/promotional/absolute wording, Chinglish formulas, uncountable plurals, prepositions, articles, agreement, abbreviation stops, unit spacing, ranges, 主语缺失, 名词化, 标点, 引号 ... |
| `templates/termbase_template.csv` | termbase columns |
| `examples/minimal_example.md` | input, calls and (illustrative) output |

Requirements: Python ≥ 3.8. Optional: `pymupdf` (PDF manuscripts), `pdftotext` as a fallback. No network, no model calls
inside the scripts.

## Inputs

`case.json` keys are read loosely; anything that resolves to a file is classified by key and file name:

- manuscript: keys like `manuscript, draft, text, document, source_text, original, abstract, section, 原文, 稿件, 正文, 摘要`
  (inline strings ≥ 40 chars or file paths); else the largest unclassified text file; a lone PDF is extracted and noted.
- termbase: keys `termbase, glossary, terms, terminology, 术语, 术语表, 词表` or file names containing term/glossary/术语/词表.
  Formats: CSV, TSV, JSON (list or dict), Markdown table, `variant -> preferred` lines, inline list/dict. Columns are matched
  loosely: preferred/standard/推荐/标准/统一, variants/avoid/deprecated/禁用/不推荐/别名, zh/中文, en/英文, abbr/缩写, note/备注.
- style / constraints: keys `style, style_guide, requirements, target_style, venue, journal, audience, genre, 文体, 要求, 受众`
  and style files (printed by init; the agent applies them).
- reference material (PDF/DOCX/text): extracted to `work/materials/*.txt` for look-ups (grep), never edited.
- output contract: `output_contract` (dict or list; also `outputs`, `output_schema`, `required_outputs`, `deliverables`).
  Fields are mapped by name/description to kinds (`polished_text`, `change_log`, `termbase`, `bilingual`, `fact_map`,
  `check_report`, `needs_confirmation`, `uncertainty`, `sources`, `summary`, `status`); unmapped fields stay `null` and
  make the status `partial` until the agent maps them in an edit file (`fields`).

Mode: `translate_zh_en` / `translate_en_zh` when the task or case asks to translate (翻译, 译成, translate, bilingual ...),
else `polish`. Genre: response, grant, thesis, journal, abstract (keywords in task/case; default journal). Section filter:
"only polish the Methods section" / "仅润色引言部分" keeps other sentences unchanged (reported).

## Segment ids

`p<paragraph>.s<sentence>` for prose, `h<n>` for headings (Markdown `#`, LaTeX `\section{}`, numbered headings in text);
with several manuscripts `d2:p3.s1`. Offsets into the original text are kept, so polishing replaces exactly the sentence
span and leaves everything else (LaTeX preamble, equations, figure/table environments, comments, code blocks, Markdown
tables, line breaks) byte-identical. Sentence boundaries are never placed inside math, citations or cross-references;
abbreviations (e.g., et al., Fig., Eq., i.e., No.) do not end sentences.

## Outputs (field dictionary)

| file / key | content |
|---|---|
| `result.json.case_id`, contract fields | as in case.json; values by kind (see above) |
| `status`, `status_reason` | `success` / `partial` / `failed` and why (unreviewed sentences, unresolved fails, unmapped fields) |
| `change_summary` | edited units, segments in scope, counts per change type, verdicts |
| `checks` | segments, reviewed, not reviewed, severity counts, fails, accepted overrides, counts per code |
| `sources` | manuscript(s), materials, termbase files with SHA-256 and read info (encoding, repairs) |
| `needs_confirmation` | agent questions, `confirm` notes, accepted flags (with the original flag), termbase conflicts, undefined abbreviations |
| `uncertainty` | encoding repairs, classification guesses, ignored edits, unreviewed sentences, out-of-scope sentences, agent notes |
| `polished.<ext>` / `polished.md` / `polished.docx` | full polished text in the input format |
| `change_log.json` | per edited unit: sid(s), original, revised, records (from, to, type, reason), verdict, findings, confirm |
| `change_log.md` / `.csv` | the same for reading / spreadsheets (one CSV row per record) |
| `diff.md`, `diff.html` | every in-scope sentence: inline diff (~~del~~ **ins**), unchanged/not-reviewed markers; HTML = rendered preview with flags |
| `bilingual.md` / `.csv` | sentence-aligned original / revised (translation, or when a contract field asks for bilingual output) |
| `termbase.csv` | preferred, abbr, variants, zh, en, source (file / agent / text), count in revised text, variant counts, enforced, conflict |
| `fact_map.json` | per sentence: offsets, numbers, citations, references, math, hedges, boosters, negation, quantifiers, causal words, conditions in original and revised; `preserved` and meaning flags |
| `check_report.json` | all findings per unit and for the document, termbase conflicts, summary |
| `review.md` | one-page summary: status, unresolved fails, items to confirm, document checks, limits |

Finding severities: `fail` (blocks success), `warn` (decide), `info`, `accepted` (an agent `accept` with its reason; the
original severity is kept in `severity_original` and the item is listed in needs_confirmation).

## Method

1. **Edit at sentence level, record at span level.** Each record must be locatable in the original (`from`) and the revised
   sentence (`to`); a token diff (word-level for Latin script, character-level for CJK) must be fully covered by records.
   This makes every change reviewable on its own and stops silent rewrites.
2. **Meaning invariants.** For each edited unit the original and revised sentences are reduced to profiles: numbers with
   units (digits and number words, thousands separators and dash styles normalised), citation markers (`[3]`, `[1-3]`,
   author–year, `\cite{}`), cross-references (Fig./Table/Eq./Section, 图/表/式, `\ref{}`), math and LaTeX commands, and
   counts of lexicon classes. Hedges are compared by strength (weak: may, 可能, 有望, 以期; moderate: suggest, 表明, 拟,
   aim to): losing a hedge without an equal or weaker replacement is a strengthened claim. An association replaced by an
   effect verb (associated with -> increased the risk of) counts as a causal claim. Antonym swaps show up as one polarity
   losing words while the other gains.
3. **Termbase sweep** over the whole revised text, tolerant to case, hyphen/space variation and plurals; termbase terms are
   masked before the meaning checks (so 首次库伦效率 is not a novelty claim). Internal termbase conflicts are reported and not
   enforced. Abbreviations: definitions "long form (ABBR)" / "中文（ABBR）", first use vs definition, redefinition, different
   expansions, termbase abbreviations never defined.
4. **Translation mode** compares the same profiles across languages with tolerance (hedge level ±1 warn; negation,
   universal quantifiers, conditions and direction words warn) and checks that source terms appear with their target term.
5. **Honest status.** Unreviewed chunks stay original and are listed; fails block `success`; accepted overrides are
   visible to the author.

## Self-evaluation (author-written cases; not the platform's fixed cases)

Six cases written by the author: English abstract + introduction (Markdown, termbase), Chinese thesis section (txt,
Chinese termbase), LaTeX methods section, Chinese grant paragraph -> English (inline JSON glossary) [dev set, rules tuned on
it]; clinical English abstract (British English, TSV glossary) and Chinese grant paragraph [held-out, written after a code
freeze; `tests/FREEZE_holdout.sha256`]. Gold edits by the author; defects are bad edits disguised with plausible records.

| set | planted defects caught (fail) | caught incl. warn | benign edits passed | clean gold edits failing | baseline: numbers+citations only | baseline: record coverage only |
|---|---:|---:|---:|---:|---:|---:|
| dev (tuned) | 42/42 | 42/42 | — | 0/27 | 10/42 | 3/42 |
| held-out, at freeze | 13/18 | 15/18 | 3/4 | 0/10 | 5/18 | 1/18 |
| held-out, after post-freeze lexicon fix | 17/18 | 18/18 | 4/4 | 0/10 | 5/18 | 1/18 |

Held-out misses at freeze: association -> "increased the risk of" (causal), "after adjusting for ..." dropped, "在高电流密度下"
dropped (caught as a number change, not as a condition), 以期 dropped (hedge not in the lexicon); benign false positive:
不理想 -> 有待提高 (negation count). Remaining miss after the fix: a promotional phrase the polish failed to remove gets a
warning (R04), not a fail - by design. 8 of 37 clean gold edits needed an explicit `accept` (judgement calls such as removing
"完全"/"huge"). Candidate finder recall on planted language errors: dev 30/32, held-out 4/13 at freeze, 10/13 after the fix.
Robustness (13 checks) all pass: missing case.json, empty manuscript, mojibake repair, GB18030, termbase conflict, 600-sentence
input (20 chunks; one chunk edited -> partial, 570 unreviewed sentences listed), broken edit JSON, unknown sid, Japanese sentence, DOCX in/out, PDF-only
input, deterministic rebuild, standalone audit of a full-paragraph rewrite.

Fresh-directory check (only `submission/` copied to `skills/weekly-skill`, new reviewer-response case written after the
evaluation, `execution/results/fresh_response/`): init + build in < 1 s, status success, all three contract fields filled,
Markdown bold labels kept. That run exposed one bug, fixed afterwards: `Table S2` and `Table 2` normalised to the same
reference key, so a supplementary -> main reference swap was not flagged; supplementary prefixes are now kept
(`table:s2` vs `table:2`, `附图2` -> `suppfig:2`). The evaluation numbers above are unchanged after that fix.

## Limits

- The checks are lexical. They see that a hedge, number or condition disappeared, not whether a paraphrase kept the
  meaning; legitimate paraphrases can be flagged (accept them with a reason) and novel phrasings can slip through
  (e.g. a condition expressed without a listed cue word, causal claims without causal vocabulary).
- Lexicons cover English and Chinese academic prose; other languages get only number/citation/reference/math checks.
- Grammar is the agent's job; the candidate finder is a set of regex hints with modest recall on unseen text.
- Merged sentences are checked as one unit; moving a clause to another sentence shows as a loss in one and a gain in the other.
- DOCX output keeps paragraph text only (no run formatting, tables, comments or tracked changes); PDF input loses layout.
- Termbase matching is surface-based (case, hyphen, plural); inflected Chinese compounds or synonyms outside the list are not found.
- The self-evaluation uses the author's own cases, gold edits and defects; it measures the checker, not a model's polishing quality.

## Maintenance

- Add discipline vocabulary in `rules/lexicon.json` (keep class names; add `exclude_*` entries for false hits) and style rules
  in `rules/style_rules.json` (`residual: true` re-checks them on the revised text). Re-run `python tests/run_eval.py` in the
  bundle to see the effect on detection and false positives.
- Version: 0.2.0 (2026-11-25). Added native `.xlsx` termbase/table reader, JSON Schema `output_contract` parsing, `避免翻译腔` mode guard, multi-section filter, factored-unit / `是否` false-fail fixes, punctuation-remainder `R02` warning downgrade, and `polished_preview.pdf`/`.png` visual rendering. Scripts and rules are deterministic: same inputs and edits -> same outputs (timestamps aside).
