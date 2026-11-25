#!/usr/bin/env python3
"""Step 1 of academic-polish-ledger: read the case, find manuscript / termbase / style guide / reference material,
segment the manuscript into sentences with stable ids, run the candidate finder and write the work plan.

  python ap_init.py --case /input/case.json --out /app/output --work /app/work [--manuscript FILE] [--termbase FILE]
                    [--mode polish|translate] [--genre journal|thesis|grant|response|abstract] [--chunk 40]

Writes
  WORK/state.json                 everything ap_build.py needs (case_id, contract, documents, segments, mode, genre)
  WORK/chunks/chunk_NN.md         sentences to edit (id, text, lint hints, tokens that must survive)
  WORK/edits/chunk_NN.json        edit templates: fill "edits", set "status": "done"
  WORK/termbase.json              termbase entries (given + abbreviations defined in the text) and internal conflicts
  WORK/materials/*.txt            text of reference materials (PDF/DOCX) for fact look-ups (grep them)
  OUT/result.json                 valid partial result (status partial, nothing polished yet)
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ap_common import (TEXT_EXT, abbreviation_definitions, dump_json, lang_of, load_termbase, numbers, protected_tokens,  # noqa: E402
                       read_any, segment, term_regex, termbase_conflicts, write_text, lexical_hits)
from ap_lint import lint  # noqa: E402

VERSION = "0.2.0"
CONTRACT_KEYS = ("output_contract", "outputs_contract", "output_schema", "required_outputs", "output_fields", "outputs", "deliverables")
MS_KEYS = ("manuscript", "draft", "text", "input_text", "source_text", "original", "original_text", "content", "document", "paper_text",
           "abstract", "paragraph", "paragraphs", "section", "sections", "passage", "body", "原文", "稿件", "待润色", "正文", "摘要", "段落", "input")
TB_KEYS = ("termbase", "glossary", "terms", "terminology", "term_table", "术语", "术语表", "词表")
STYLE_KEYS = ("style", "style_guide", "style_rules", "rules", "requirements", "constraints", "target_style", "venue", "journal", "audience",
              "genre", "register", "风格", "文体", "要求", "受众", "目标期刊")
REF_KEYS = ("reference", "references", "materials", "material", "sources", "source", "paper", "pdf", "facts", "fact_sheet", "参考", "材料", "事实")


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def key_has(path, keys):
    last = re.split(r"[.\[]", path.lower())
    return any(k in seg for seg in last for k in keys)


def resolve(val, bases):
    if not isinstance(val, str) or len(val) > 400 or "\n" in val:
        return None
    for b in bases:
        p = val if os.path.isabs(val) else os.path.join(b, val)
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None


def classify_file(p, keypath=""):
    n = os.path.basename(p).lower()
    if re.search(r"term|glossar|术语|词表|vocab", n) or key_has(keypath, TB_KEYS):
        return "termbase"
    if re.search(r"style|guide|规范|要求|instruction|rubric|template", n) or key_has(keypath, ("style", "guide", "rules", "风格", "规范")):
        return "style"
    if key_has(keypath, MS_KEYS) or re.search(r"manuscript|draft|原文|稿|abstract|摘要|input|polish|润色|section|chapter|grant|申请|proposal|response|rebuttal", n):
        return "manuscript"
    if key_has(keypath, REF_KEYS) or n.endswith(".pdf") or re.search(r"ref|paper|source|material|fact|论文|材料", n):
        return "reference"
    return "unknown"


def detect_mode(task, case):
    m = case.get("mode") if isinstance(case, dict) else None
    if isinstance(m, str) and m:
        return m
    clean_case = {k: v for k, v in case.items() if k not in CONTRACT_KEYS} if isinstance(case, dict) else case
    t = (task + " " + json.dumps(clean_case, ensure_ascii=False)).lower()
    t = re.sub(r"避免翻译腔|去翻译腔|翻译腔|直译腔|translationese", " ", t)
    if re.search(r"翻译|译成|译为|译文|中译英|英译中|translat|into english|into chinese|英文版|英文摘要.*中文|双语对照|bilingual", t):
        if re.search(r"英译中|into chinese|译成中文|译为中文", t):
            return "translate_en_zh"
        return "translate_zh_en"
    contract_str = json.dumps(next((case[k] for k in CONTRACT_KEYS if isinstance(case, dict) and k in case), {}), ensure_ascii=False).lower()
    if "bilingual" in contract_str and not re.search(r"polish|润色", t):
        return "translate_zh_en"
    return "polish"


def detect_genre(task, case):
    t = (task + " " + json.dumps(case, ensure_ascii=False)).lower()
    for g, pat in (("response", r"审稿|回复|rebuttal|response to (?:the )?reviewer|point-by-point"), ("grant", r"基金|申请书|grant|proposal|nsfc|立项"),
                   ("thesis", r"学位论文|毕业论文|thesis|dissertation"), ("journal", r"期刊|journal|manuscript|submission|投稿"), ("abstract", r"摘要|abstract"), ("journal", r"论文|paper")):
        if re.search(pat, t):
            return g
    return "journal"


def section_filter(task):
    """Sections the task restricts the work to, e.g. 'only polish the Methods section' / '仅润色引言和讨论部分'."""
    out = []
    for raw in re.findall(r"(?:only|仅|只)\s*(?:polish|edit|revise|润色|修改|处理)?\s*(?:the\s+)?([A-Za-z0-9\u4e00-\u9fff &、,，和与.]{2,48}?)\s*(?:sections?|部分|章节|一节|节)", task, flags=re.I):
        for part in re.split(r"\s*(?:and|&|,|，|、|和|与)\s*", raw.strip()):
            p = part.strip()
            if p:
                out.append(p)
    for m in re.findall(r"(?:only|仅|只)\s*(?:polish|edit|revise|润色|修改|处理)\s+(?:Section|Sec\.?|第)\s*(\d+(?:\.\d+)*)\s*[章节]?", task, flags=re.I):
        if m not in out:
            out.append(m)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", default="/input/case.json")
    ap.add_argument("--task")
    ap.add_argument("--out", default="/app/output")
    ap.add_argument("--work", default="/app/work")
    ap.add_argument("--manuscript", action="append", help="override: manuscript file(s)")
    ap.add_argument("--termbase", action="append", help="override/add: termbase file(s)")
    ap.add_argument("--mode")
    ap.add_argument("--genre")
    ap.add_argument("--chunk", type=int, default=30, help="sentences per chunk file")
    a = ap.parse_args()
    t0 = dt.datetime.now(dt.timezone.utc)
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(a.work, exist_ok=True)
    problems = []

    case = {}
    case_dir = os.path.dirname(os.path.abspath(a.case)) if a.case else os.getcwd()
    if a.case and os.path.exists(a.case):
        try:
            raw = open(a.case, "rb").read()
            from ap_common import decode_bytes
            case = json.loads(decode_bytes(raw)[0])
        except Exception as e:  # noqa: BLE001
            problems.append(f"case.json unreadable: {e}")
    else:
        problems.append(f"case.json not found at {a.case}")
    if not isinstance(case, dict):
        case = {"_raw": case}
    task_path = a.task or next((p for p in (os.path.join(case_dir, "task.md"), "/input/task.md", "task.md") if os.path.exists(p)), None)
    task = read_any(task_path)[0] if task_path else ""
    case_id = case.get("case_id") or case.get("id") or os.environ.get("CASE_ID") or "unknown"
    contract = next((case[k] for k in CONTRACT_KEYS if k in case), None)
    if contract is None:
        problems.append("no output_contract in case.json; default fields used")
        contract = {"polished_text": "polished full text", "change_log": "sentence-level change records"}
    contract_props = {}
    if isinstance(contract, dict) and isinstance(contract.get("properties"), dict):
        contract_props = contract["properties"]
        fields = list(contract_props.keys())
    elif isinstance(contract, dict):
        fields = list(contract.keys())
    else:
        fields = [c if isinstance(c, str) else c.get("name", str(c)) for c in contract]

    bases = [case_dir, "/input", os.getcwd()]
    files = {}  # path -> role
    inline_ms, inline_tb, style_notes = [], [], []
    for k in MS_KEYS:
        if isinstance(case.get(k), list) and case[k] and all(isinstance(x, str) for x in case[k]):
            inline_ms.append((k, "\n\n".join(case[k])))
    joined_ms_keys = {k for k, _ in inline_ms}
    for path, val in walk(case):
        if path.split("[")[0] in joined_ms_keys:
            continue
        p = resolve(val, bases)
        if p:
            files.setdefault(p, classify_file(p, path))
            continue
        if isinstance(val, str):
            if key_has(path, CONTRACT_KEYS):
                continue
            if key_has(path, MS_KEYS) and len(val.strip()) >= 15:
                inline_ms.append((path, val))
            elif key_has(path, TB_KEYS):
                inline_tb.append((path, val))
            elif key_has(path, STYLE_KEYS) or key_has(path, ("task", "instruction", "requirement", "说明", "目标")):
                style_notes.append(f"{path}: {val}")
    for k in TB_KEYS:
        if isinstance(case.get(k), (list, dict)):
            inline_tb.append((k, case[k]))
    for d in {case_dir, "/input"}:
        if os.path.isdir(d):
            for r, _, fs in os.walk(d):
                for fn in fs:
                    p = os.path.abspath(os.path.join(r, fn))
                    if fn in ("case.json", "task.md") or p in files:
                        continue
                    if os.path.splitext(fn)[1].lower() in TEXT_EXT + (".docx", ".pdf", ".csv", ".tsv", ".xlsx", ".json"):
                        files[p] = classify_file(p)
    if a.manuscript:
        for p in files:
            if files[p] == "manuscript":
                files[p] = "reference"
        for m in a.manuscript:
            files[os.path.abspath(m)] = "manuscript"
    for t in a.termbase or []:
        files[os.path.abspath(t)] = "termbase"
    # json files that are not termbases are case data, csv/tsv default to termbase
    for p, role in list(files.items()):
        ext = os.path.splitext(p)[1].lower()
        if role == "unknown" and ext in (".csv", ".tsv"):
            files[p] = "termbase"
        elif role == "unknown" and ext == ".xlsx":
            files[p] = "termbase" if re.search(r"term|glossar|术语|词表|vocab", os.path.basename(p).lower()) else "reference"
        elif role == "unknown" and ext == ".json":
            files[p] = "reference"
    if not inline_ms and not any(r == "manuscript" for r in files.values()):
        cand = sorted([p for p, r in files.items() if r == "unknown" and os.path.splitext(p)[1].lower() in TEXT_EXT + (".docx",)],
                      key=lambda p: -os.path.getsize(p))
        if cand:
            files[cand[0]] = "manuscript"
            problems.append(f"manuscript chosen by size: {os.path.basename(cand[0])} (override with --manuscript)")
        else:
            pdfs = [p for p, r in files.items() if p.lower().endswith(".pdf")]
            if pdfs:
                files[pdfs[0]] = "manuscript"
                problems.append(f"only a PDF was found; polishing its extracted text: {os.path.basename(pdfs[0])}")
    for p, r in files.items():
        if r == "unknown":
            files[p] = "reference"

    mode = a.mode or detect_mode(task, case)
    genre = a.genre or detect_genre(task, case)
    sections = section_filter(task)

    docs, segs_all = [], []
    ms_items = [("inline:" + k, v, None) for k, v in inline_ms] + [(p, None, p) for p, r in files.items() if r == "manuscript"]
    for i, (name, inline, path) in enumerate(ms_items, 1):
        prefix = "" if len(ms_items) == 1 else f"d{i}:"
        try:
            if inline is not None:
                from ap_common import decode_bytes
                text, info = inline.replace("\r\n", "\n"), {"encoding": "json-string", "repairs": []}
                fmt = "tex" if re.search(r"\\(?:section|begin|cite)\b", text) else "md" if re.search(r"(?m)^#{1,6} ", text) else "txt"
            else:
                text, fmt, info = read_any(path)
        except Exception as e:  # noqa: BLE001
            problems.append(f"cannot read manuscript {name}: {e}")
            continue
        segs = segment(text, fmt, prefix)
        doc = {"doc_id": f"d{i}", "name": os.path.basename(path) if path else name, "path": path, "fmt": fmt, "text": text,
               "sha256": sha(path) if path else hashlib.sha256(text.encode("utf-8")).hexdigest(), "read_info": info,
               "lang": lang_of(text), "n_sentences": sum(1 for s in segs if s["kind"] == "sentence"), "n_headings": sum(1 for s in segs if s["kind"] == "heading")}
        if info.get("repairs"):
            problems += [f"{doc['name']}: {r}" for r in info["repairs"]]
        if info.get("replacement_chars") or info.get("mojibake_left"):
            problems.append(f"{doc['name']}: {info.get('replacement_chars', 0)} replacement characters / {info.get('mojibake_left', 0)} mojibake sequences remain - do not guess those words; list them in needs_confirmation")
        langs = {s["lang"] for s in segs}
        if langs & {"ja", "ko"}:
            problems.append(f"{doc['name']}: Japanese/Korean sentences present - lexicon checks cover zh/en only; only numbers, citations, references and math are checked there")
        for s in segs:
            s["doc"] = doc["doc_id"]
        docs.append(doc)
        segs_all += segs

    # section filter: mark sentences outside the requested sections
    if sections and segs_all:
        current, inside = None, False
        for s in segs_all:
            if s["kind"] == "heading":
                current = s["text"]
                inside = any(x.lower() in current.lower() for x in sections)
            s["in_scope"] = inside
        if not any(s.get("in_scope") for s in segs_all):
            for s in segs_all:
                s["in_scope"] = True
            problems.append(f"requested section(s) {sections} not found among headings; all text kept in scope - confirm")
    else:
        for s in segs_all:
            s["in_scope"] = True

    # termbase
    terms, tb_sources = [], []
    for p, r in files.items():
        if r == "termbase":
            try:
                e = load_termbase(p)
                terms += e
                tb_sources.append({"path": p, "entries": len(e), "sha256": sha(p)})
            except Exception as ex:  # noqa: BLE001
                problems.append(f"termbase {os.path.basename(p)} unreadable: {ex}")
    for k, v in inline_tb:
        try:
            obj = json.loads(v) if isinstance(v, str) and v.strip()[:1] in "[{" else v
            e = load_termbase(obj) if not isinstance(obj, str) else []
            if isinstance(obj, str):
                for line in obj.splitlines():
                    m = re.match(r"\s*[-*]?\s*(.+?)\s*(?:=>|->|→|:|：|=)\s*(.+)$", line)
                    if m:
                        e.append({"preferred": m.group(2).strip(), "variants": [m.group(1).strip()], "zh": "", "en": "", "abbr": "", "note": "", "source": "inline"})
            terms += e
            tb_sources.append({"path": f"case.json:{k}", "entries": len(e)})
        except Exception as ex:  # noqa: BLE001
            problems.append(f"inline termbase {k} unreadable: {ex}")
    conflicts = termbase_conflicts(terms)
    auto_abbr = []
    for d in docs:
        for ab, lf, pos in abbreviation_definitions(d["text"]):
            auto_abbr.append({"abbr": ab, "long": lf, "doc": d["doc_id"], "offset": pos})
    dump_json({"entries": terms, "sources": tb_sources, "conflicts": conflicts, "abbreviations_in_text": auto_abbr}, os.path.join(a.work, "termbase.json"))

    # reference materials -> text for look-ups
    mats = []
    for p, r in files.items():
        if r in ("reference", "style"):
            try:
                text, fmt, info = read_any(p)
                outp = os.path.join(a.work, "materials", os.path.splitext(os.path.basename(p))[0] + ".txt")
                write_text(outp, text)
                mats.append({"path": p, "role": r, "text_path": outp, "sha256": sha(p), "chars": len(text), "fmt": fmt})
                if r == "style":
                    style_notes.append(f"style file {os.path.basename(p)} -> {outp}")
            except Exception as ex:  # noqa: BLE001
                mats.append({"path": p, "role": r, "error": str(ex)})
                problems.append(f"material {os.path.basename(p)} unreadable: {ex}")

    # chunks
    sents = [s for s in segs_all if s["in_scope"]]
    mask0 = sorted({x for t in terms for x in [t.get("preferred"), t.get("zh"), t.get("en")] + list(t.get("variants") or []) if isinstance(x, str) and len(x) > 1}, key=len, reverse=True)
    chunk_dir, edit_dir = os.path.join(a.work, "chunks"), os.path.join(a.work, "edits")
    os.makedirs(chunk_dir, exist_ok=True)
    os.makedirs(edit_dir, exist_ok=True)
    chunks = []
    lint_total = 0
    for ci in range(0, len(sents), a.chunk):
        part = sents[ci:ci + a.chunk]
        n = ci // a.chunk + 1
        lines = [f"# chunk {n:02d} ({len(part)} segments) - mode {mode}, genre {genre}", "",
                 "Keep: numbers/units, citation markers, Fig./Table/Eq. references, math, hedges, negation, quantifiers, conditions.", ""]
        for s in part:
            hints = lint(s["text"], s["lang"], genre)
            lint_total += len(hints)
            keep = []
            nums = [r for _, _, r in numbers(s["text"])]
            if nums:
                keep.append("nums " + " ".join(nums[:10]))
            pt = protected_tokens(s["text"])
            if pt.get("latex_cmd"):
                pt["citation"] = pt.get("citation", []) + [x for x in pt["latex_cmd"] if x.startswith(r"\cite")]
                pt["xref"] = pt.get("xref", []) + [x for x in pt["latex_cmd"] if not x.startswith(r"\cite")]
            for k in ("citation", "xref", "math"):
                if pt.get(k):
                    keep.append(k + " " + " ".join(pt[k][:6]))
            lh = lexical_hits(s["text"], mask0)
            sem = [f"{c.replace('quantifier_', 'q:').replace('hedge_', 'hedge:')}={'/'.join(sorted(set(v)))}" for c, v in lh.items() if not c.startswith("direction")]
            lines.append(f"[{s['sid']}]{' (heading)' if s['kind'] == 'heading' else ''} {s['text']}")
            if keep or sem:
                lines.append("    keep: " + "; ".join(keep + sem))
            for h in hints:
                lines.append(f"    hint {h['rule']} ({h['category']}): \"{h['match']}\" - {h['message']}; {h['hint']}")
            for t in terms:
                for v in t.get("variants") or []:
                    rx = term_regex(v)
                    if rx and rx.search(s["text"]):
                        lines.append(f"    hint TERM (terminology): \"{rx.search(s['text']).group(0)}\" is a termbase variant; use \"{t['preferred']}\"" + (f" (abbr {t['abbr']})" if t.get("abbr") else ""))
                        lint_total += 1
            lines.append("")
        write_text(os.path.join(chunk_dir, f"chunk_{n:02d}.md"), "\n".join(lines))
        ep = os.path.join(edit_dir, f"chunk_{n:02d}.json")
        if not os.path.exists(ep):
            dump_json({"chunk": n, "status": "todo", "sids": [s["sid"] for s in part], "edits": []}, ep)
        chunks.append({"chunk": n, "sids": [s["sid"] for s in part], "md": os.path.join(chunk_dir, f"chunk_{n:02d}.md"), "edits": ep})

    state = {"version": VERSION, "case_id": case_id, "case_path": a.case, "task_path": task_path, "contract": contract, "contract_props": contract_props, "fields": fields,
             "mode": mode, "genre": genre, "sections": sections, "docs": docs, "segments": segs_all, "chunks": chunks,
             "files": [{"path": p, "role": r} for p, r in files.items()], "materials": mats, "style_notes": style_notes,
             "problems": problems, "termbase_path": os.path.join(a.work, "termbase.json"), "out": os.path.abspath(a.out),
             "work": os.path.abspath(a.work), "init_at": t0.isoformat()}
    dump_json(state, os.path.join(a.work, "state.json"))

    status = "failed" if not docs else "partial"
    result = {"case_id": case_id, "status": status,
              "status_reason": "no manuscript text could be read" if not docs else "initialised; no edits applied yet",
              **{f: None for f in fields}, "mode": mode, "genre": genre,
              "sources": [{"name": d["name"], "sha256": d["sha256"], "fmt": d["fmt"], "read_info": d["read_info"]} for d in docs] + [{"name": os.path.basename(m["path"]), "role": m["role"], "sha256": m.get("sha256")} for m in mats],
              "uncertainty": problems, "needs_confirmation": [], "skill": {"name": "academic-polish-ledger", "version": VERSION}}
    dump_json(result, os.path.join(a.out, "result.json"))

    print(f"case_id: {case_id}   mode: {mode}   genre: {genre}   contract fields: {fields}")
    for d in docs:
        print(f"manuscript {d['doc_id']}: {d['name']} fmt={d['fmt']} lang={d['lang']} sentences={d['n_sentences']} headings={d['n_headings']} encoding={d['read_info'].get('encoding')}")
    for p, r in files.items():
        if r != "manuscript":
            print(f"{r}: {p}")
    if sections:
        print(f"section filter from task: {sections} -> {len(sents)} of {len(segs_all)} segments in scope")
    print(f"termbase entries: {len(terms)}  conflicts: {len(conflicts)}  abbreviations defined in text: {len(auto_abbr)}")
    for c in conflicts:
        print(f"  TERMBASE CONFLICT {c['type']}: {c['term']} -> {c['entries']}  (do not enforce; list in needs_confirmation)")
    for s in style_notes[:12]:
        print(f"style/constraint: {s[:300]}")
    print(f"lint hints: {lint_total}   chunks: {len(chunks)} x <= {a.chunk} segments -> {chunk_dir}")
    for p in problems:
        print(f"NOTE: {p}")
    print(f"next: read {chunks[0]['md'] if chunks else '(no chunks)'}, write edits into {edit_dir}/chunk_NN.json, then run ap_build.py --work {a.work} --out {a.out}")
    return 0 if docs else 2


if __name__ == "__main__":
    sys.exit(main())
