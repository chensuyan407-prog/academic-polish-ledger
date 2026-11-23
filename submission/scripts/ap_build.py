#!/usr/bin/env python3
"""Step 3 of academic-polish-ledger: apply the sentence edits, check them, write the deliverables.

  python ap_build.py --work /app/work --out /app/output

Reads WORK/state.json (from ap_init.py) and every WORK/edits/*.json (+ WORK/edits.json if present).
Edit file format:
  {"chunk": 1, "status": "done",                       # "done" = every sentence of the chunk was reviewed
   "edits": [{"sid": "p2.s3", "revised": "...", "changes": [{"from": "..", "to": "..", "type": "grammar", "reason": ".."}],
              "accept": {"I05": "why this flagged change is intended"}, "confirm": "question for the author"},
             {"sid": ["p3.s1", "p3.s2"], "revised": "merged sentence", "changes": [...]}],
   "terms": [{"preferred": "density functional theory", "variants": ["density-functional theory"], "abbr": "DFT", "zh": "密度泛函理论"}],
   "needs_confirmation": [{"sid": "p4.s2", "issue": "..."}], "notes": ["..."],
   "fields": {"<contract field>": {"kind": "polished_text|change_log|termbase|bilingual|fact_map|check_report|needs_confirmation|uncertainty|sources|summary"} | {"value": ...}},
   "accept_doc": {"D04": "reason"}, "mode": "polish|translate_zh_en|translate_en_zh"}
Writes OUT/: polished.<ext> (+ polished.md), change_log.{json,md,csv}, diff.md, diff.html (rendered preview),
bilingual.{md,csv} (translation or when asked), termbase.csv, fact_map.json, check_report.json, review.md, result.json.
Exit code 0 = no unresolved fail; 1 = fails remain (fix and re-run); 2 = nothing to build.
"""
import argparse
import csv
import datetime as dt
import glob
import html
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ap_common import CJK, dump_json, lexical_hits, load_json, numbers, protected_tokens, term_regex, termbase_conflicts, write_text  # noqa: E402
from ap_check import FAIL, INFO, WARN, check_pair, doc_checks, hunks, verdict  # noqa: E402
from ap_lint import lint  # noqa: E402

VERSION = "0.1.0"
KIND_PATTERNS = [
    ("bilingual", r"bilingual|parallel|对照|双语|中英"),
    ("termbase", r"term|glossar|术语|词表|vocab"),
    ("fact_map", r"fact|source_map|provenance|evidence|来源|映射|溯源|事实"),
    ("check_report", r"check|invariant|qa\b|quality|校验|检查|一致性|verification|verify"),
    ("needs_confirmation", r"confirm|人工|待确认|review_items|flag|issue|question|query|疑问"),
    ("uncertainty", r"uncertain|limitation|gap|不确定|缺口|局限|风险|risk"),
    ("change_log", r"change|edit|revision|修改|说明|log|record|diff|清单|记录|track|modif"),
    ("sources", r"^sources?$|input|材料|输入"),
    ("summary", r"summary|overview|摘要说明|总结|概述|review"),
    ("status", r"^status$|状态"),
    ("polished_text", r"polish|revised|润色|text|manuscript|稿|translat|译文|abstract|output|全文|正文|result|final|article|section|paragraph|段|draft|英文|中文|content"),
]


def field_kind(name, desc=""):
    s = f"{name} {desc if isinstance(desc, str) else json.dumps(desc, ensure_ascii=False)}".lower()
    n = name.lower()
    for kind, pat in KIND_PATTERNS:
        if re.search(pat, n):
            return kind
    for kind, pat in KIND_PATTERNS:
        if re.search(pat, s):
            return kind
    return None


def load_edits(work, chunks=None):
    chunk_sids = {c["chunk"]: c["sids"] for c in (chunks or [])}
    files = sorted(glob.glob(os.path.join(work, "edits", "*.json")))
    if os.path.exists(os.path.join(work, "edits.json")):
        files.append(os.path.join(work, "edits.json"))
    bundle = {"edits": [], "terms": [], "needs_confirmation": [], "notes": [], "fields": {}, "accept_doc": {}, "reviewed": set(), "mode": None,
              "errors": [], "files": []}
    for p in files:
        try:
            d = load_json(p)
        except Exception as e:  # noqa: BLE001
            bundle["errors"].append(f"{os.path.basename(p)}: invalid JSON ({e}) - file ignored")
            continue
        if isinstance(d, list):
            d = {"edits": d, "status": "done"}
        bundle["files"].append(os.path.basename(p))
        for e in d.get("edits", []) or []:
            e = dict(e)
            e["_file"] = os.path.basename(p)
            bundle["edits"].append(e)
        bundle["terms"] += d.get("terms", []) or []
        bundle["needs_confirmation"] += d.get("needs_confirmation", []) or []
        bundle["notes"] += d.get("notes", []) or []
        bundle["fields"].update(d.get("fields", {}) or {})
        bundle["accept_doc"].update(d.get("accept_doc", {}) or {})
        if d.get("mode"):
            bundle["mode"] = d["mode"]
        if str(d.get("status", "")).lower() in ("done", "reviewed", "complete", "completed"):
            bundle["reviewed"].update(d.get("sids") or chunk_sids.get(d.get("chunk"), []))
        bundle["reviewed"].update(d.get("reviewed") or [])
        for e in d.get("edits", []) or []:
            sid = e.get("sid")
            bundle["reviewed"].update(sid if isinstance(sid, list) else [sid])
    return bundle


def write_docx(path, paragraphs):
    def esc(t):
        return html.escape(t, quote=False)
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{esc(p)}</w:t></w:r></w:p>' for p in paragraphs)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{body}<w:sectPr/></w:body></w:document>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", doc)


def inline_diff(a, b):
    hs, _, _ = hunks(a, b)
    out, pos = [], 0
    for a0, a1, b0, b1, ta, tb in hs:
        out.append(a[pos:a0])
        if ta.strip():
            out.append(f"~~{ta}~~")
        if tb.strip():
            out.append(f"**{tb}**")
        pos = a1
    out.append(a[pos:])
    return "".join(out)


def html_diff(a, b):
    hs, _, _ = hunks(a, b)
    out, pos = [], 0
    for a0, a1, b0, b1, ta, tb in hs:
        out.append(html.escape(a[pos:a0]))
        if ta:
            out.append(f"<del>{html.escape(ta)}</del>")
        if tb:
            out.append(f"<ins>{html.escape(tb)}</ins>")
        pos = a1
    out.append(html.escape(a[pos:]))
    return "".join(out)


def fact_profile(t):
    lh = lexical_hits(t)
    pt = protected_tokens(t)
    return {"numbers": [f"{r}{(' ' + u) if u else ''}" for _, u, r in numbers(t)], "citations": pt.get("citation", []), "references": pt.get("xref", []),
            "math": pt.get("math", []), "hedges": lh.get("hedge_weak", []) + lh.get("hedge_moderate", []), "boosters": lh.get("booster", []),
            "negation": lh.get("negation", []), "quantifiers": sum((lh.get(k, []) for k in lh if k.startswith("quantifier")), []),
            "causal": lh.get("causal", []), "conditions": lh.get("conditional", [])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default="/app/work")
    ap.add_argument("--out", default="/app/output")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    st = load_json(os.path.join(a.work, "state.json"))
    if not st:
        print("state.json missing: run ap_init.py first")
        return 2
    os.makedirs(a.out, exist_ok=True)
    E = load_edits(a.work, st.get("chunks"))
    mode = E["mode"] or st["mode"]
    translate = mode.startswith("translate")
    genre = st["genre"]
    segs = st["segments"]
    by_sid = {s["sid"]: s for s in segs}
    order = {s["sid"]: i for i, s in enumerate(segs)}
    problems = list(st.get("problems", [])) + E["errors"]

    # ---- units: one edit -> one or more consecutive sids
    units, seen = [], {}
    for e in E["edits"]:
        sids = e.get("sid")
        sids = sids if isinstance(sids, list) else [sids]
        bad = [s for s in sids if s not in by_sid]
        if bad:
            problems.append(f"edit in {e['_file']} refers to unknown sid {bad} - ignored")
            continue
        sids = sorted(sids, key=order.get)
        if any(order[sids[i + 1]] != order[sids[i]] + 1 for i in range(len(sids) - 1)):
            problems.append(f"edit {sids} merges non-consecutive sentences - ignored")
            continue
        dup = [s for s in sids if s in seen]
        if dup:
            problems.append(f"sid {dup} edited twice ({seen[dup[0]]} and {e['_file']}); the later edit wins")
            units = [u for u in units if not set(u["sids"]) & set(dup)]
        for s in sids:
            seen[s] = e["_file"]
        rev = e.get("revised")
        if rev is None:
            problems.append(f"edit {sids} has no 'revised' text - ignored")
            continue
        orig = " ".join(by_sid[s]["text"] for s in sids) if not re.search(f"[{CJK}]", by_sid[sids[0]]["text"]) else "".join(by_sid[s]["text"] for s in sids)
        units.append({"sids": sids, "orig": orig, "rev": str(rev).strip(), "changes": e.get("changes") or [], "accept": e.get("accept") or {},
                      "confirm": e.get("confirm"), "file": e["_file"]})
    unit_of = {s: u for u in units for s in u["sids"]}

    # ---- per-unit checks (termbase terms are masked for the meaning-class checks)
    tb0 = load_json(st["termbase_path"], {}) or {}
    mask = sorted({x for t in tb0.get("entries", []) + [t for t in E["terms"] if isinstance(t, dict)]
                   for x in [t.get("preferred"), t.get("zh"), t.get("en")] + list(t.get("variants") or []) if isinstance(x, str) and len(x) > 1}, key=len, reverse=True)
    report_units = []
    for u in units:
        lang = by_sid[u["sids"][0]]["lang"]
        tgt_lang = "en" if mode == "translate_zh_en" else "zh" if mode == "translate_en_zh" else lang
        fd = check_pair(u["orig"], u["rev"], mode, u["changes"], u["accept"], genre, tgt_lang, mask)
        u["findings"] = fd
        u["verdict"] = verdict(fd)
        report_units.append(u)
    # reviewed but unchanged sentences: residual style issues; translation mode: untranslated = fail
    untouched = []
    for s in segs:
        if not s["in_scope"] or s["sid"] in unit_of:
            continue
        if translate and s["sid"] in E["reviewed"] and s["lang"] in ("zh", "en") and \
                ((mode == "translate_zh_en" and s["lang"] == "zh") or (mode == "translate_en_zh" and s["lang"] == "en")):
            untouched.append({"sids": [s["sid"]], "orig": s["text"], "rev": s["text"], "changes": [], "accept": {},
                              "findings": [{"code": "S02", "severity": FAIL, "detail": "sentence left untranslated"}], "verdict": FAIL, "file": None})
            continue
        if s["sid"] in E["reviewed"]:
            res = lint(s["text"], s["lang"], genre, residual_only=True)
            if res:
                untouched.append({"sids": [s["sid"]], "orig": s["text"], "rev": s["text"], "changes": [], "accept": {}, "file": None,
                                  "findings": [{"code": "R04", "severity": WARN, "detail": f"kept unchanged although {h['rule']} ({h['message']}) matches \"{h['match']}\""} for h in res],
                                  "verdict": WARN})
    not_reviewed = [s["sid"] for s in segs if s["in_scope"] and s["sid"] not in E["reviewed"]]
    out_of_scope = [s["sid"] for s in segs if not s["in_scope"]]

    # ---- assemble polished documents
    polished_docs = []
    for d in st["docs"]:
        text = d["text"]
        dsegs = [s for s in segs if s["doc"] == d["doc_id"]]
        reps = []
        done = set()
        for s in dsegs:
            u = unit_of.get(s["sid"])
            if not u or s["sid"] in done:
                continue
            first, last = by_sid[u["sids"][0]], by_sid[u["sids"][-1]]
            reps.append((first["start"], last["end"], u["rev"]))
            done.update(u["sids"])
        reps.sort()
        out, pos = [], 0
        for k, (s0, e0, r) in enumerate(reps):
            gap = text[pos:s0]
            if out and gap == "" and re.search(r"[A-Za-z0-9.;:!?)\]]$", out[-1]) and re.match(r"[A-Za-z0-9(\[$\\]", r):
                gap = " "
            out.append(gap)
            out.append(r)
            pos = e0
        tail = text[pos:]
        if out and tail and re.match(r"[A-Za-z(\[]", tail) and re.search(r"[.;:!?]$", out[-1]):
            tail = " " + tail
        out.append(tail)
        ptext = "".join(out)
        polished_docs.append({"doc": d, "text": ptext})
    revised_by_sid = {}
    for s in segs:
        u = unit_of.get(s["sid"])
        if u:
            revised_by_sid[s["sid"]] = u["rev"] if s["sid"] == u["sids"][0] else ""
        else:
            revised_by_sid[s["sid"]] = s["text"]

    # ---- terms + document checks
    tb = load_json(st["termbase_path"], {}) or {}
    terms = list(tb.get("entries", []))
    agent_terms = []
    for t in E["terms"]:
        if isinstance(t, dict) and t.get("preferred"):
            agent_terms.append({"preferred": t["preferred"], "variants": t.get("variants", []) or [], "zh": t.get("zh", ""), "en": t.get("en", ""),
                                "abbr": t.get("abbr", ""), "note": t.get("note", ""), "source": "agent"})
    conflicts = termbase_conflicts(terms + agent_terms)
    conflict_terms = {c["term"] for c in conflicts} | {x for c in conflicts for x in c["entries"]}
    enforce = [t for t in terms + agent_terms if t["preferred"] not in conflict_terms and not any(v in conflict_terms for v in t["variants"])]
    full_rev = "\n\n".join(p["text"] for p in polished_docs)
    seg_view = [{"sid": s["sid"], "text": s["text"], "revised": revised_by_sid[s["sid"]]} for s in segs]
    pairs = [(s["sid"], s["text"], revised_by_sid[s["sid"]]) for s in segs]
    dfind = doc_checks(full_rev, enforce, mode, pairs, seg_view)
    for f in dfind:
        r = E["accept_doc"].get(f["code"])
        if r and f["severity"] in (FAIL, WARN):
            f["accepted"], f["severity_original"], f["severity"] = r, f["severity"], "accepted"

    # ---- tallies
    all_units = report_units + untouched
    sev = Counter(x["severity"] for u in all_units for x in u["findings"]) + Counter(x["severity"] for x in dfind)
    fails = [(u["sids"], x) for u in all_units for x in u["findings"] if x["severity"] == FAIL] + [(f.get("sids", ["doc"]), f) for f in dfind if f["severity"] == FAIL]
    accepted = [(u["sids"], x) for u in all_units for x in u["findings"] if x["severity"] == "accepted"] + [(["doc"], f) for f in dfind if f["severity"] == "accepted"]
    types = Counter(t.strip() for u in report_units for c in u["changes"] for t in re.split(r"[,/+ ]+", (c.get("type") or "unlabelled").lower()) if t.strip())
    n_scope = sum(1 for s in segs if s["in_scope"])

    # ---- change log
    log = []
    for u in sorted(report_units, key=lambda u: order[u["sids"][0]]):
        log.append({"sid": u["sids"][0] if len(u["sids"]) == 1 else u["sids"], "original": u["orig"], "revised": u["rev"],
                    "changes": u["changes"], "verdict": u["verdict"], "findings": u["findings"], "confirm": u.get("confirm"),
                    "edit_file": u["file"]})
    dump_json(log, os.path.join(a.out, "change_log.json"))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sid", "original_sentence", "revised_sentence", "from", "to", "type", "reason", "verdict", "flags"])
    for r in log:
        flags = "; ".join(f"{x['code']}:{x['severity']}" for x in r["findings"])
        sid = r["sid"] if isinstance(r["sid"], str) else "+".join(r["sid"])
        if not r["changes"]:
            w.writerow([sid, r["original"], r["revised"], "", "", "", "", r["verdict"], flags])
        for c in r["changes"]:
            w.writerow([sid, r["original"], r["revised"], c.get("from", ""), c.get("to", ""), c.get("type", ""), c.get("reason", ""), r["verdict"], flags])
    write_text(os.path.join(a.out, "change_log.csv"), "﻿" + buf.getvalue())
    md = [f"# Change log - {st['case_id']}", "", f"mode `{mode}` · genre `{genre}` · {len(log)} edited units of {n_scope} segments in scope · "
          f"verdicts {dict(Counter(r['verdict'] for r in log))}", "",
          "Legend: ~~deleted~~ **inserted**. Every change has from → to, type and reason; flags are the invariant checks (I = meaning, R = record, D = document).", ""]
    for r in log:
        sid = r["sid"] if isinstance(r["sid"], str) else " + ".join(r["sid"])
        md.append(f"## [{sid}] {r['verdict']}")
        md.append("")
        md.append(f"- original: {r['original']}")
        md.append(f"- revised: {r['revised']}")
        if not translate:
            md.append(f"- diff: {inline_diff(r['original'], r['revised'])}")
        md.append("")
        if r["changes"]:
            md.append("| # | from | to | type | reason |")
            md.append("|---|---|---|---|---|")
            for k, c in enumerate(r["changes"], 1):
                md.append(f"| {k} | {str(c.get('from', '')).replace('|', '/')} | {str(c.get('to', '')).replace('|', '/')} | {c.get('type', '')} | {str(c.get('reason', '')).replace('|', '/')} |")
            md.append("")
        for x in r["findings"]:
            md.append(f"- {x['code']} **{x['severity']}**: {x['detail']}" + (f" — accepted: {x['accepted']}" if x.get("accepted") else ""))
        if r.get("confirm"):
            md.append(f"- needs author confirmation: {r['confirm']}")
        md.append("")
    write_text(os.path.join(a.out, "change_log.md"), "\n".join(md))

    # ---- polished files + diff views
    artifacts = {}
    for p in polished_docs:
        d = p["doc"]
        stem = "polished" if len(polished_docs) == 1 else f"polished_{d['doc_id']}"
        ext = {"md": ".md", "tex": ".tex", "txt": ".txt", "docx": ".docx", "pdf": ".md", "json": ".txt"}[d["fmt"]]
        if d["fmt"] == "docx":
            write_docx(os.path.join(a.out, stem + ".docx"), [x for x in p["text"].split("\n\n")])
            write_text(os.path.join(a.out, stem + ".md"), p["text"])
            artifacts[d["doc_id"]] = [stem + ".docx", stem + ".md"]
        else:
            write_text(os.path.join(a.out, stem + ext), p["text"])
            artifacts[d["doc_id"]] = [stem + ext]
            if ext != ".md":
                write_text(os.path.join(a.out, stem + ".md"), p["text"])
                artifacts[d["doc_id"]].append(stem + ".md")
    diff_md, diff_html = ["# Sentence diff (original → revised)", ""], []
    for s in segs:
        if not s["in_scope"]:
            continue
        u = unit_of.get(s["sid"])
        if u and s["sid"] != u["sids"][0]:
            continue
        if u:
            diff_md.append(f"[{'+'.join(u['sids'])}] " + (inline_diff(u["orig"], u["rev"]) if not translate else f"{u['orig']}  \n→ {u['rev']}"))
            v = u["verdict"]
            diff_html.append(f'<tr class="{v}"><td>{html.escape("+".join(u["sids"]))}</td><td>{html.escape(u["orig"])}</td><td>{html_diff(u["orig"], u["rev"]) if not translate else html.escape(u["rev"])}</td>'
                             f'<td>{"<br>".join(html.escape(c.get("type", "") + ": " + c.get("reason", "")) for c in u["changes"])}</td>'
                             f'<td>{"<br>".join(html.escape(x["code"] + " " + x["severity"] + ": " + x["detail"]) for x in u["findings"] if x["severity"] != INFO)}</td></tr>')
        else:
            diff_md.append(f"[{s['sid']}] {s['text']}  _(unchanged{'' if s['sid'] in E['reviewed'] else ', NOT REVIEWED'})_")
        diff_md.append("")
    write_text(os.path.join(a.out, "diff.md"), "\n".join(diff_md))
    write_text(os.path.join(a.out, "diff.html"), "<!doctype html><meta charset='utf-8'><title>Polish diff</title><style>body{font:14px/1.5 sans-serif;margin:16px}"
               "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:4px 6px;vertical-align:top}del{background:#fdd}ins{background:#dfd;text-decoration:none}"
               "tr.fail{background:#fff0f0}tr.warn{background:#fffbe6}</style>"
               f"<h1>{html.escape(str(st['case_id']))} — {html.escape(mode)}</h1><table><tr><th>sid</th><th>original</th><th>revised</th><th>change records</th><th>checks</th></tr>"
               + "".join(diff_html) + "</table>")
    bilingual_rows = []
    want_bi = translate or any(field_kind(f, st["contract"].get(f, "") if isinstance(st["contract"], dict) else "") == "bilingual" for f in st["fields"])
    if want_bi:
        bm = ["| sid | original | revised / translation |", "|---|---|---|"]
        for s in segs:
            if not s["in_scope"]:
                continue
            r = revised_by_sid[s["sid"]]
            u = unit_of.get(s["sid"])
            if u and s["sid"] != u["sids"][0]:
                continue
            o = u["orig"] if u else s["text"]
            bilingual_rows.append({"sid": "+".join(u["sids"]) if u else s["sid"], "original": o, "revised": r})
            bm.append(f"| {bilingual_rows[-1]['sid']} | {o.replace('|', '/')} | {r.replace('|', '/')} |")
        write_text(os.path.join(a.out, "bilingual.md"), "\n".join(bm))
        buf = io.StringIO()
        cw = csv.writer(buf)
        cw.writerow(["sid", "original", "revised"])
        for r in bilingual_rows:
            cw.writerow([r["sid"], r["original"], r["revised"]])
        write_text(os.path.join(a.out, "bilingual.csv"), "﻿" + buf.getvalue())

    # ---- termbase output
    term_rows = []
    plain_rev = full_rev
    for t in terms + agent_terms:
        rx = term_regex(t["preferred"])
        cnt = len(rx.findall(plain_rev)) if rx else 0
        var_cnt = {v: len(term_regex(v).findall(plain_rev)) for v in t["variants"] if term_regex(v)}
        term_rows.append({**t, "count_in_revised": cnt, "variant_counts_in_revised": var_cnt,
                          "enforced": t in enforce, "conflict": t["preferred"] in conflict_terms or any(v in conflict_terms for v in t["variants"])})
    for ab in tb.get("abbreviations_in_text", []):
        if not any(r.get("abbr") == ab["abbr"] for r in term_rows):
            term_rows.append({"preferred": ab["long"], "abbr": ab["abbr"], "variants": [], "zh": "", "en": "", "note": "abbreviation defined in the original text",
                              "source": "text", "count_in_revised": len(re.findall(r"(?<![\w-])" + re.escape(ab["abbr"]) + r"(?![\w-])", plain_rev)), "enforced": False, "conflict": False})
    buf = io.StringIO()
    cw = csv.writer(buf)
    cw.writerow(["preferred", "abbr", "variants_to_avoid", "zh", "en", "source", "count_in_revised", "variant_counts_in_revised", "enforced", "conflict", "note"])
    for r in term_rows:
        cw.writerow([r["preferred"], r.get("abbr", ""), ";".join(r["variants"]), r.get("zh", ""), r.get("en", ""), r["source"], r["count_in_revised"],
                     json.dumps(r.get("variant_counts_in_revised", {}), ensure_ascii=False), r["enforced"], r["conflict"], r.get("note", "")])
    write_text(os.path.join(a.out, "termbase.csv"), "﻿" + buf.getvalue())

    # ---- fact map
    fact_map = []
    for s in segs:
        if not s["in_scope"]:
            continue
        u = unit_of.get(s["sid"])
        if u and s["sid"] != u["sids"][0]:
            continue
        o = u["orig"] if u else s["text"]
        r = u["rev"] if u else s["text"]
        po, pr = fact_profile(o), fact_profile(r)
        meaning = [x for x in (u["findings"] if u else []) if x["code"].startswith("I")]
        fact_map.append({"sid": "+".join(u["sids"]) if u else s["sid"], "doc": s["doc"], "offset": [s["start"], by_sid[u["sids"][-1]]["end"] if u else s["end"]],
                         "changed": bool(u), "original": po, "revised": pr if u else "same",
                         "preserved": not any(x["severity"] in (FAIL, WARN) for x in meaning),
                         "meaning_flags": [f"{x['code']}:{x['severity']}" for x in meaning]})
    dump_json(fact_map, os.path.join(a.out, "fact_map.json"))

    # ---- needs confirmation / uncertainty
    confirm = []
    for c in E["needs_confirmation"]:
        confirm.append(c if isinstance(c, dict) else {"issue": str(c)})
    for u in report_units:
        if u.get("confirm"):
            confirm.append({"sid": "+".join(u["sids"]), "issue": u["confirm"]})
    for c in conflicts:
        confirm.append({"issue": f"termbase conflict ({c['type']}): {c['term']} -> {c['entries']}; not enforced", "source": "termbase"})
    for sids, x in accepted:
        confirm.append({"sid": "+".join(sids), "issue": f"flag {x['code']} accepted by the editor: {x['accepted']} (original flag: {x['detail']})"})
    for f in dfind:
        if f["code"] == "D03" and f["severity"] == INFO:
            confirm.append({"issue": f["detail"], "source": "D03"})
    uncertainty = problems + [f"{len(not_reviewed)} in-scope segments were not reviewed: {not_reviewed[:30]}"] * bool(not_reviewed) + E["notes"]
    if out_of_scope:
        uncertainty.append(f"{len(out_of_scope)} segments outside the requested sections were left unchanged")

    # ---- status
    reasons = []
    if not st["docs"]:
        status = "failed"
        reasons.append("no manuscript text")
    else:
        if fails:
            reasons.append(f"{len(fails)} unresolved fail flags")
        if not_reviewed:
            reasons.append(f"{len(not_reviewed)}/{n_scope} segments not reviewed")
        if not report_units and not E["reviewed"]:
            reasons.append("no edits submitted")
        status = "success" if not reasons else "partial"

    check_report = {"summary": {"segments_in_scope": n_scope, "edited_units": len(report_units), "reviewed": n_scope - len(not_reviewed),
                                "not_reviewed": len(not_reviewed), "severity": dict(sev), "fail": len(fails), "accepted_overrides": len(accepted),
                                "change_types": dict(types), "by_code": dict(Counter(x["code"] for u in all_units for x in u["findings"] if x["severity"] in (FAIL, WARN)) +
                                                                          Counter(f["code"] for f in dfind if f["severity"] in (FAIL, WARN)))},
                    "units": [{"sids": u["sids"], "verdict": u["verdict"], "findings": u["findings"]} for u in all_units if u["findings"]],
                    "document": dfind, "termbase_conflicts": conflicts}
    dump_json(check_report, os.path.join(a.out, "check_report.json"))

    kinds = {
        "polished_text": full_rev if len(polished_docs) == 1 else {p["doc"]["doc_id"]: p["text"] for p in polished_docs},
        "change_log": [{"sid": r["sid"], "original": r["original"], "revised": r["revised"], "changes": r["changes"], "verdict": r["verdict"],
                        "flags": [f"{x['code']}:{x['severity']}" for x in r["findings"] if x["severity"] != INFO]} for r in log],
        "termbase": [{k: r.get(k) for k in ("preferred", "abbr", "variants", "zh", "en", "source", "count_in_revised", "enforced", "conflict", "note")} for r in term_rows],
        "bilingual": bilingual_rows or [{"sid": s["sid"], "original": s["text"], "revised": revised_by_sid[s["sid"]]} for s in segs if s["in_scope"] and revised_by_sid[s["sid"]]],
        "fact_map": fact_map, "check_report": check_report["summary"], "needs_confirmation": confirm, "uncertainty": uncertainty,
        "sources": None, "status": status,
        "summary": f"{len(report_units)} of {n_scope} segments edited; change types {dict(types)}; {len(fails)} unresolved fails; {len(accepted)} accepted overrides; status {status}",
    }
    result = load_json(os.path.join(a.out, "result.json"), {}) or {}
    sources = [{"name": d["name"], "role": "manuscript", "sha256": d["sha256"], "fmt": d["fmt"], "read_info": d["read_info"]} for d in st["docs"]] + \
              [{"name": os.path.basename(m["path"]), "role": m["role"], "sha256": m.get("sha256"), "text": m.get("text_path")} for m in st.get("materials", [])] + \
              [{"name": t.get("path"), "role": "termbase", "entries": t.get("entries"), "sha256": t.get("sha256")} for t in tb.get("sources", [])]
    kinds["sources"] = sources
    unfilled = []
    for f in st["fields"]:
        desc = st["contract"].get(f, "") if isinstance(st["contract"], dict) else ""
        spec = E["fields"].get(f)
        if isinstance(spec, dict) and "value" in spec:
            result[f] = spec["value"]
            continue
        kind = (spec or {}).get("kind") if isinstance(spec, dict) else (spec if isinstance(spec, str) else None)
        kind = kind or field_kind(f, desc)
        if kind in kinds:
            result[f] = kinds[kind]
        else:
            result[f] = None
            unfilled.append(f)
    if unfilled:
        status = "partial" if status == "success" else status
        reasons.append(f"contract fields not mapped: {unfilled} (set them in an edits file under 'fields')")
    out_files = sorted(os.path.relpath(p, a.out).replace(os.sep, "/") for p in glob.glob(os.path.join(a.out, "*")) if os.path.isfile(p))
    result.update({"case_id": st["case_id"], "status": status, "status_reason": "; ".join(reasons) or "all segments reviewed, no unresolved fail",
                   "mode": mode, "genre": genre, "polished_files": artifacts, "artifacts": out_files,
                   "change_summary": {"edited_units": len(report_units), "segments_in_scope": n_scope, "change_types": dict(types),
                                      "verdicts": dict(Counter(r["verdict"] for r in log))},
                   "checks": check_report["summary"], "sources": sources, "needs_confirmation": confirm, "uncertainty": uncertainty,
                   "termbase_conflicts": conflicts, "fact_source_map": "fact_map.json",
                   "skill": {"name": "academic-polish-ledger", "version": VERSION},
                   "run": {"built_at": dt.datetime.now(dt.timezone.utc).isoformat(), "edit_files": E["files"]}})
    for f in st["fields"]:
        if f in ("status", "case_id", "sources", "uncertainty", "needs_confirmation"):
            continue
    dump_json(result, os.path.join(a.out, "result.json"))

    rv = [f"# Review - {st['case_id']}", "", f"- status: **{status}** — {result['status_reason']}", f"- mode: {mode}; genre: {genre}",
          f"- segments in scope: {n_scope}; edited: {len(report_units)}; not reviewed: {len(not_reviewed)}", f"- change types: {dict(types)}",
          f"- flags: {dict(sev)}; accepted overrides: {len(accepted)}", "", "## Unresolved fails", ""]
    rv += [f"- [{'+'.join(s) if isinstance(s, list) else s}] {x['code']}: {x['detail']}" for s, x in fails] or ["- none"]
    rv += ["", "## Needs author confirmation", ""] + ([f"- {('[' + c['sid'] + '] ') if c.get('sid') else ''}{c.get('issue')}" for c in confirm] or ["- none"])
    rv += ["", "## Document checks", ""] + ([f"- {f['code']} {f['severity']}: {f['detail']}" for f in dfind] or ["- none"])
    rv += ["", "## Uncertainty / limits", ""] + ([f"- {u}" for u in uncertainty] or ["- none"])
    write_text(os.path.join(a.out, "review.md"), "\n".join(rv))

    if not a.quiet:
        print(f"status: {status} - {result['status_reason']}")
        print(f"units: {len(report_units)} edited / {n_scope} in scope; verdicts {dict(Counter(r['verdict'] for r in log))}; flags {dict(sev)}")
        for sids, x in fails[:40]:
            print(f"FAIL [{'+'.join(sids) if isinstance(sids, list) else sids}] {x['code']}: {x['detail']}")
        warns = [(u["sids"], x) for u in all_units for x in u["findings"] if x["severity"] == WARN] + [(["doc"], f) for f in dfind if f["severity"] == WARN]
        for sids, x in warns[:40]:
            print(f"warn [{'+'.join(sids)}] {x['code']}: {x['detail']}")
        if len(warns) > 40:
            print(f"... {len(warns) - 40} more warnings in check_report.json")
        for p in problems[-8:]:
            print(f"NOTE: {p}")
        print(f"outputs: {a.out} ({len(out_files)} files)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
