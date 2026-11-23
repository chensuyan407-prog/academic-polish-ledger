#!/usr/bin/env python3
"""Self-evaluation of academic-polish-ledger on author-written cases (not the platform's fixed cases).

  python tests/run_eval.py [--set dev|holdout|all] [--json execution/results/metrics.json]

1. clean runs: each case's gold edits (tests/eval/gold/<case>.json) -> init + build; counts fails / warns / accepted overrides;
2. planted defects (tests/eval/mutations_<set>.json): one bad edit per run, disguised with a plausible change record;
   detected = the expected check code fires at fail level; baselines are computed from the same runs:
   B0 no checks, B1 numbers + citation markers only (I01/I02), B2 record coverage only (R01/R02);
3. candidate finder recall on the planted language errors (tests/eval/planted_errors_<set>.json) and whether the gold fixed them;
4. robustness: missing case, empty manuscript, mojibake, GB18030, termbase conflict, long input, broken edits JSON,
   unknown sid, Japanese sentence, DOCX in/out, PDF-only input, deterministic rebuild, standalone audit of a full rewrite.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "submission", "scripts")
CASES = os.path.join(ROOT, "tests", "cases")
EVAL = os.path.join(ROOT, "tests", "eval")
RES = os.path.join(ROOT, "execution", "results")
sys.path.insert(0, SCRIPTS)
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
LOG = []


def run(args, quiet=False):
    t = time.time()
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8", env=ENV, cwd=ROOT)
    LOG.append({"argv": [os.path.relpath(a, ROOT) if os.path.exists(a) else a for a in args], "exit": r.returncode,
                "seconds": round(time.time() - t, 3), "stdout_tail": r.stdout[-1500:], "stderr_tail": r.stderr[-800:]})
    if r.returncode not in (0, 1, 2) or (r.stderr and "Traceback" in r.stderr):
        print(r.stdout[-2000:], r.stderr[-3000:])
    return r


def load(p, default=None):
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def dump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(o, fh, ensure_ascii=False, indent=1)


def sha_file(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def init_build(case_json, work, out, gold=None, extra=None):
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)
    args = [os.path.join(SCRIPTS, "ap_init.py"), "--case", case_json, "--out", out, "--work", work] + (extra or [])
    r1 = run(args)
    if gold is not None:
        dump(gold, os.path.join(work, "edits", "chunk_01.json"))
    r2 = run([os.path.join(SCRIPTS, "ap_build.py"), "--work", work, "--out", out]) if os.path.exists(os.path.join(work, "state.json")) else None
    return r1, r2


def findings_all(rep):
    fs = []
    for u in rep.get("units", []):
        for f in u["findings"]:
            fs.append(dict(f, sids=u["sids"]))
    for f in rep.get("document", []):
        fs.append(dict(f))
    return fs


def clean_runs(cases):
    rows = {}
    for c in cases:
        gold = load(os.path.join(EVAL, "gold", f"{c}.json"))
        base = os.path.join(RES, "cases", c)
        t = time.time()
        r1, r2 = init_build(os.path.join(CASES, c, "input", "case.json"), os.path.join(base, "work"), os.path.join(base, "output"), gold)
        rep = load(os.path.join(base, "output", "check_report.json"), {})
        res = load(os.path.join(base, "output", "result.json"), {})
        fs = findings_all(rep)
        acc = [f for f in fs if f["severity"] == "accepted"]
        rows[c] = {"status": res.get("status"), "status_reason": res.get("status_reason"), "build_exit": r2.returncode if r2 else None,
                   "segments": rep.get("summary", {}).get("segments_in_scope"), "edited_units": rep.get("summary", {}).get("edited_units"),
                   "fail": sum(f["severity"] == "fail" for f in fs), "warn": sum(f["severity"] == "warn" for f in fs),
                   "accepted_fail": sum(f.get("severity_original") == "fail" for f in acc), "accepted_warn": sum(f.get("severity_original") == "warn" for f in acc),
                   "accepted_codes": [f["code"] for f in acc], "warn_codes": [f["code"] for f in fs if f["severity"] == "warn"],
                   "unit_verdicts": {"+".join(u["sids"]): u["verdict"] for u in rep.get("units", [])}, "seconds": round(time.time() - t, 2),
                   "contract_fields_filled": [k for k in (res.keys()) if k in load(os.path.join(base, "work", "state.json"), {}).get("fields", []) and res[k] is not None]}
    return rows


def mutation_runs(items, golds):
    rows = []
    tmp = os.path.join(RES, "_mut_tmp")
    for it in items:
        c = it["case"]
        base = os.path.join(RES, "cases", c)
        w, o = os.path.join(tmp, "work"), os.path.join(tmp, "output")
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(os.path.join(base, "work"), w)
        os.makedirs(o)
        shutil.copy(os.path.join(base, "output", "result.json"), os.path.join(o, "result.json"))
        g = json.loads(json.dumps(golds[c]))
        eds = []
        for e in g["edits"]:
            if e["sid"] != it["sid"]:
                eds.append(e)
                continue
            if it.get("drop"):
                continue
            e = dict(e)
            e["revised"] = it["revised"]
            ch = it["changes"] if "changes" in it else list(e.get("changes", [])) + ([it["record"]] if it.get("record") else [])
            if "changes" not in it and not it.get("record") and g.get("mode", "").startswith("translate"):
                ch = e.get("changes", [])
            e["changes"] = ch
            e["accept"] = it.get("accept", {})
            e.pop("confirm", None)
            eds.append(e)
        if not it.get("drop") and not any(e["sid"] == it["sid"] for e in eds):
            eds.append({"sid": it["sid"], "revised": it["revised"], "changes": it.get("changes", [it["record"]] if it.get("record") else []), "accept": it.get("accept", {})})
        g["edits"] = eds
        dump(g, os.path.join(w, "edits", "chunk_01.json"))
        r = run([os.path.join(SCRIPTS, "ap_build.py"), "--work", w, "--out", o, "--quiet"])
        rep = load(os.path.join(o, "check_report.json"), {})
        fs = findings_all(rep)
        code = lambda f: "I11" if f["code"] == "I11u" else f["code"]  # noqa: E731
        if it["expect"] is None:  # benign edit: must not fail
            strict = loose = not any(f["severity"] == "fail" for f in fs)
        else:
            strict = any(code(f) == it["expect"] and f["severity"] == "fail" for f in fs)
            loose = any(code(f) == it["expect"] and f["severity"] in ("fail", "warn") for f in fs)
        unit_fail = any(f["severity"] == "fail" and it["sid"] in f.get("sids", []) for f in fs) or any(f["severity"] == "fail" and it["sid"] in (f.get("sids") or []) for f in rep.get("document", []))
        rows.append({"id": it["id"], "case": c, "sid": it["sid"], "kind": it["kind"], "expect": it["expect"], "detected": strict, "detected_or_warned": loose,
                     "sentence_or_doc_failed": unit_fail or strict, "codes_fired": sorted({f"{f['code']}:{f['severity']}" for f in fs if f["severity"] in ("fail", "warn")}),
                     "baseline_numcite": any(f["code"] in ("I01", "I02") and f["severity"] == "fail" and it["sid"] in f.get("sids", []) for f in fs),
                     "baseline_record_only": any(f["code"] in ("R01", "R02") and f["severity"] == "fail" and it["sid"] in f.get("sids", []) for f in fs),
                     "build_exit": r.returncode})
    shutil.rmtree(tmp, ignore_errors=True)
    return rows


def lint_recall(planted, golds):
    from ap_lint import lint
    from ap_common import load_json, term_regex
    rows = []
    for c, errs in planted.items():
        if c.startswith("_"):
            continue
        st = load_json(os.path.join(RES, "cases", c, "work", "state.json"))
        tb = load_json(os.path.join(RES, "cases", c, "work", "termbase.json"), {})
        segs = {s["sid"]: s for s in st["segments"]}
        gold_rev = {e["sid"]: e["revised"] for e in golds[c]["edits"] if isinstance(e["sid"], str)}
        for er in errs:
            s = segs[er["sid"]]
            hints = [h["match"] for h in lint(s["text"], s["lang"], st["genre"])]
            for t in tb.get("entries", []):
                for v in t.get("variants", []):
                    rx = term_regex(v)
                    m = rx.search(s["text"]) if rx else None
                    if m:
                        hints.append(m.group(0))
            hit = any(er["match"].lower() in h.lower() or h.lower() in er["match"].lower() for h in hints if h)
            rev = gold_rev.get(er["sid"], s["text"])
            still = re.search(re.escape(er["match"]) + (r"(?![A-Za-z.])" if re.search(r"[A-Za-z.]$", er["match"]) else ""), rev)
            rows.append({"case": c, "sid": er["sid"], "match": er["match"], "type": er["type"], "hinted": hit, "gold_fixed": not still})
    return rows


def robustness():
    from ap_build import write_docx
    base = os.path.join(RES, "robustness")
    shutil.rmtree(base, ignore_errors=True)
    out = {}

    def mk(name, files, case=None):
        d = os.path.join(base, name, "input")
        os.makedirs(d)
        for fn, content in files.items():
            p = os.path.join(d, fn)
            if isinstance(content, bytes):
                open(p, "wb").write(content)
            else:
                open(p, "w", encoding="utf-8").write(content)
        if case is not None:
            dump(case, os.path.join(d, "case.json"))
        return d

    def res(name):
        return load(os.path.join(base, name, "output", "result.json"), {})

    def W(name):
        return os.path.join(base, name, "work"), os.path.join(base, name, "output")

    # 1 missing case.json
    os.makedirs(os.path.join(base, "missing_case", "input"))
    w, o = W("missing_case")
    r = run([os.path.join(SCRIPTS, "ap_init.py"), "--case", os.path.join(base, "missing_case", "input", "case.json"), "--out", o, "--work", w])
    out["missing_case_json"] = {"init_exit": r.returncode, "status": res("missing_case").get("status"), "ok": res("missing_case").get("status") == "failed" and r.returncode == 2}
    # 2 empty manuscript
    d = mk("empty_manuscript", {"manuscript.txt": ""}, {"case_id": "empty", "manuscript": "manuscript.txt", "output_contract": ["polished_text"]})
    w, o = W("empty_manuscript")
    init_build(os.path.join(d, "case.json"), w, o, {"chunk": 1, "status": "done", "edits": []})
    rr = res("empty_manuscript")
    out["empty_manuscript"] = {"status": rr.get("status"), "reason": rr.get("status_reason"), "ok": rr.get("status") in ("partial", "failed") and "success" != rr.get("status")}
    # 3 mojibake (UTF-8 read as cp1252, saved again as UTF-8)
    txt = "The sample’s band gap is about 2.3 eV at 300 °C — see Fig. 2.\n"
    moj = txt.encode("utf-8").decode("cp1252", errors="replace").encode("utf-8")
    d = mk("mojibake", {"manuscript.txt": moj}, {"case_id": "moj", "manuscript": "manuscript.txt", "output_contract": ["polished_text"]})
    w, o = W("mojibake")
    init_build(os.path.join(d, "case.json"), w, o, {"chunk": 1, "status": "done", "edits": []})
    st = load(os.path.join(w, "state.json"), {})
    ri = st.get("docs", [{}])[0].get("read_info", {}) if st.get("docs") else {}
    out["mojibake_repair"] = {"repairs": ri.get("repairs"), "text_ok": bool(st.get("docs")) and "’" in st["docs"][0]["text"] and "°C" in st["docs"][0]["text"],
                              "reported_in_uncertainty": any("reversed" in u for u in res("mojibake").get("uncertainty", []))}
    out["mojibake_repair"]["ok"] = out["mojibake_repair"]["text_ok"] and out["mojibake_repair"]["reported_in_uncertainty"]
    # 4 GB18030 file
    d = mk("gb18030", {"稿件.txt": "本文研究了氧空位对电导率的影响。结果表明，电导率提高了约25%。".encode("gb18030")},
           {"case_id": "gbk", "manuscript": "稿件.txt", "output_contract": ["润色全文"]})
    w, o = W("gb18030")
    init_build(os.path.join(d, "case.json"), w, o, {"chunk": 1, "status": "done", "edits": []})
    st = load(os.path.join(w, "state.json"), {})
    out["gb18030_input"] = {"encoding": st["docs"][0]["read_info"]["encoding"] if st.get("docs") else None,
                            "ok": bool(st.get("docs")) and "氧空位" in st["docs"][0]["text"]}
    # 5 termbase conflict
    d = mk("termbase_conflict", {"manuscript.md": "We used density-functional theory for all calculations. The DFT results agree with experiment.\n",
                                 "terms.csv": "preferred,variants\ndensity functional theory,density-functional theory\nDFT method,density-functional theory\n"},
           {"case_id": "tbc", "manuscript": "manuscript.md", "termbase": "terms.csv", "output_contract": {"polished_text": "", "needs_confirmation": ""}})
    w, o = W("termbase_conflict")
    init_build(os.path.join(d, "case.json"), w, o, {"chunk": 1, "status": "done", "edits": []})
    rr = res("termbase_conflict")
    rep = load(os.path.join(o, "check_report.json"), {})
    out["termbase_conflict"] = {"conflicts": rr.get("termbase_conflicts"), "flagged_for_confirmation": any("termbase conflict" in c.get("issue", "") for c in rr.get("needs_confirmation", [])),
                                "not_enforced": not any(f["code"] == "D01" for f in rep.get("document", []))}
    out["termbase_conflict"]["ok"] = bool(rr.get("termbase_conflicts")) and out["termbase_conflict"]["flagged_for_confirmation"] and out["termbase_conflict"]["not_enforced"]
    # 6 long input, only first chunk edited
    para = " ".join(f"Sample {i} was annealed at {300 + i} K for {i % 7 + 1} h, and its resistance decreased by about {i % 20 + 1}% [{i % 9 + 1}]." for i in range(1, 41))
    long_text = "\n\n".join(para for _ in range(15))
    d = mk("long_input", {"manuscript.txt": long_text}, {"case_id": "long", "manuscript": "manuscript.txt", "output_contract": ["polished_text", "change_log"]})
    w, o = W("long_input")
    t = time.time()
    r1 = run([os.path.join(SCRIPTS, "ap_init.py"), "--case", os.path.join(d, "case.json"), "--out", o, "--work", w])
    st = load(os.path.join(w, "state.json"), {})
    e = {"chunk": 1, "status": "done", "edits": [{"sid": "p1.s1", "revised": "Sample 1 was annealed at 301 K for 2 h, and its resistance decreased by approximately 2% [2].",
                                                  "changes": [{"from": "about", "to": "approximately", "type": "word-choice", "reason": "formal"}]}]}
    dump(e, os.path.join(w, "edits", "chunk_01.json"))
    r2 = run([os.path.join(SCRIPTS, "ap_build.py"), "--work", w, "--out", o])
    rr = res("long_input")
    out["long_input"] = {"sentences": len(st.get("segments", [])), "chunks": len(st.get("chunks", [])), "seconds_init_build": round(time.time() - t, 2),
                         "status": rr.get("status"), "not_reviewed": rr.get("checks", {}).get("not_reviewed"),
                         "ok": rr.get("status") == "partial" and rr.get("checks", {}).get("not_reviewed", 0) > 500}
    # 7 broken edits JSON + 8 unknown sid
    d = mk("bad_edits", {"manuscript.txt": "The results is clear. We measured 5 samples."}, {"case_id": "bad", "manuscript": "manuscript.txt", "output_contract": ["polished_text"]})
    w, o = W("bad_edits")
    run([os.path.join(SCRIPTS, "ap_init.py"), "--case", os.path.join(d, "case.json"), "--out", o, "--work", w])
    open(os.path.join(w, "edits", "chunk_01.json"), "w", encoding="utf-8").write('{"chunk": 1, "status": "done", "edits": [ {"sid": "p1.s1", ')
    dump({"edits": [{"sid": "p9.s9", "revised": "x", "changes": []}], "status": "partial"}, os.path.join(w, "edits", "extra.json"))
    run([os.path.join(SCRIPTS, "ap_build.py"), "--work", w, "--out", o])
    rr = res("bad_edits")
    out["broken_edits_json"] = {"status": rr.get("status"), "noted": any("invalid JSON" in u for u in rr.get("uncertainty", [])), "ok": rr.get("status") == "partial" and any("invalid JSON" in u for u in rr.get("uncertainty", []))}
    out["unknown_sid"] = {"noted": any("unknown sid" in u for u in rr.get("uncertainty", [])), "ok": any("unknown sid" in u for u in rr.get("uncertainty", []))}
    # 9 Japanese sentence in an English manuscript
    d = mk("mixed_ja", {"manuscript.txt": "The film thickness was 20 nm. この結果は再現性が高いことを示している。 The device was stable."},
           {"case_id": "ja", "manuscript": "manuscript.txt", "output_contract": ["polished_text"]})
    w, o = W("mixed_ja")
    init_build(os.path.join(d, "case.json"), w, o, {"chunk": 1, "status": "done", "edits": []})
    out["mixed_japanese"] = {"noted": any("Japanese" in u for u in res("mixed_ja").get("uncertainty", []))}
    out["mixed_japanese"]["ok"] = out["mixed_japanese"]["noted"]
    # 10 DOCX in/out
    d = os.path.join(base, "docx_io", "input")
    os.makedirs(d)
    write_docx(os.path.join(d, "draft.docx"), ["Introduction", "The method have been used widely. It's simple."])
    dump({"case_id": "docx", "manuscript": "draft.docx", "output_contract": ["polished_text", "change_log"]}, os.path.join(d, "case.json"))
    w, o = W("docx_io")
    init_build(os.path.join(d, "case.json"), w, o, {"chunk": 1, "status": "done", "edits": [
        {"sid": "p1.s1", "revised": "The method has been used widely.", "changes": [{"from": "have", "to": "has", "type": "agreement", "reason": "singular subject"}]},
        {"sid": "p1.s2", "revised": "It is simple.", "changes": [{"from": "It's", "to": "It is", "type": "register", "reason": "no contractions"}]}]})
    from ap_common import read_docx
    pd = os.path.join(o, "polished.docx")
    out["docx_io"] = {"polished_docx": os.path.exists(pd), "roundtrip_text": read_docx(pd) if os.path.exists(pd) else None, "status": res("docx_io").get("status")}
    out["docx_io"]["ok"] = bool(out["docx_io"]["roundtrip_text"]) and "has been used" in out["docx_io"]["roundtrip_text"]
    # 11 PDF-only input
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    d = os.path.join(base, "pdf_only", "input")
    os.makedirs(d)
    doc = fitz.open()
    pg = doc.new_page()
    pg.insert_text((72, 90), "The samples was heated to 500 K for 2 h.", fontsize=11)
    doc.save(os.path.join(d, "draft.pdf"))
    dump({"case_id": "pdf", "files": ["draft.pdf"], "output_contract": ["polished_text"]}, os.path.join(d, "case.json"))
    w, o = W("pdf_only")
    init_build(os.path.join(d, "case.json"), w, o, {"chunk": 1, "status": "done", "edits": []})
    rr = res("pdf_only")
    out["pdf_only_input"] = {"noted": any("PDF" in u for u in rr.get("uncertainty", [])), "polished": bool(rr.get("polished_text"))}
    out["pdf_only_input"]["ok"] = out["pdf_only_input"]["noted"] and out["pdf_only_input"]["polished"]
    # 12 deterministic rebuild (dev_en)
    w = os.path.join(RES, "cases", "dev_en", "work")
    o1, o2 = os.path.join(base, "det_1"), os.path.join(base, "det_2")
    for oo in (o1, o2):
        os.makedirs(oo)
        shutil.copy(os.path.join(RES, "cases", "dev_en", "output", "result.json"), oo)
        run([os.path.join(SCRIPTS, "ap_build.py"), "--work", w, "--out", oo, "--quiet"])
    same = all(sha_file(os.path.join(o1, f)) == sha_file(os.path.join(o2, f)) for f in ("polished.md", "change_log.json", "check_report.json", "fact_map.json", "diff.html"))
    out["deterministic_rebuild"] = {"ok": same, "files": ["polished.md", "change_log.json", "check_report.json", "fact_map.json", "diff.html"]}
    # 13 standalone audit of a whole-paragraph rewrite (the typical base-agent failure, written by the author)
    d = os.path.join(base, "audit_rewrite")
    os.makedirs(d)
    shutil.copy(os.path.join(CASES, "dev_en", "input", "manuscript.md"), os.path.join(d, "original.md"))
    open(os.path.join(d, "rewrite.md"), "w", encoding="utf-8").write(
        "# Abstract\n\nPerovskite solar cells (PSCs) are a leading renewable energy technology, yet their long-term stability is limited by moisture and heat. "
        "We report a fluorinated hole transport layer that suppresses ion migration at the interface. The champion device reaches a power conversion efficiency (PCE) of 23.4% "
        "and retains 90% of its initial efficiency after 1000 h at 85 °C. These results demonstrate that interfacial fluorination is an effective strategy for stable devices [4, 7].\n\n"
        "# Introduction\n\nPerovskite solar cells have made remarkable progress over the past decade [1-3], with efficiencies rising from 3.8% to 26% [2]. "
        "However, degradation under operating conditions still prevents commercialization. Many studies attribute this degradation to iodide ion migration, which accelerates above 60 °C [5]. "
        "An HTL with low ion permeability will therefore extend device lifetime. Here, we design a fluorinated polymer and investigate its effect on the stability of PSCs (Table 1).\n")
    r = run([os.path.join(SCRIPTS, "ap_check.py"), "--orig", os.path.join(d, "original.md"), "--rev", os.path.join(d, "rewrite.md"),
             "--termbase", os.path.join(CASES, "dev_en", "input", "termbase.csv"), "--json", os.path.join(d, "audit.json")])
    au = load(os.path.join(d, "audit.json"), {})
    planted = ["hedge removed (may suppress -> suppresses)", "approximator removed (about 90%)", "figure reference dropped (Fig. 3b)", "hedge strengthened (suggest -> demonstrate)",
               "promotional (remarkable)", "bound removed (above 26%)", "quantifier (several -> many)", "hedge removed (could -> will)", "condition dropped (if ...)"]
    codes = au.get("summary", {}).get("codes", {})
    out["audit_full_rewrite"] = {"planted_meaning_changes": len(planted), "planted": planted, "flag_codes": codes, "pairs_flagged": sum(1 for p in au.get("pairs", []) if any(f["severity"] == "fail" for f in p["findings"])),
                                 "ok": all(codes.get(k, 0) > 0 for k in ("I05", "I07", "I03", "I11", "I13"))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="all")
    ap.add_argument("--json", default=os.path.join(RES, "metrics.json"))
    ap.add_argument("--no-robustness", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    sets = ["dev", "holdout"] if a.set == "all" else [a.set]
    metrics = {"sets": {}, "notes": "author-written cases; not the platform's fixed cases; no model was run - the edits are the author's gold edits and hand-made defects"}
    all_rows = {}
    for s in sets:
        mp = os.path.join(EVAL, f"mutations_{s}.json")
        if not os.path.exists(mp):
            continue
        items = load(mp)["items"]
        cases = sorted({i["case"] for i in items} | set(k for k in load(os.path.join(EVAL, f"planted_errors_{s}.json"), {}) if not k.startswith("_")))
        golds = {c: load(os.path.join(EVAL, "gold", f"{c}.json")) for c in cases}
        clean = clean_runs(cases)
        rows = mutation_runs(items, golds)
        lr = lint_recall(load(os.path.join(EVAL, f"planted_errors_{s}.json"), {}), golds)
        benign = [r for r in rows if r["expect"] is None]
        rows_b = rows
        rows = [r for r in rows if r["expect"] is not None]
        n = len(rows)
        by_kind = {}
        for r in rows:
            k = by_kind.setdefault(r["kind"], [0, 0])
            k[0] += r["detected"]
            k[1] += 1
        m = {"cases": cases, "clean": clean, "defects": n, "benign_edits": len(benign), "benign_passed": sum(r["detected"] for r in benign),
             "benign_failed": [r["id"] + " " + r["kind"] + " fired=" + ",".join(r["codes_fired"]) for r in benign if not r["detected"]],
             "detected_fail": sum(r["detected"] for r in rows) / n if n else None,
             "detected_fail_or_warn": sum(r["detected_or_warned"] for r in rows) / n if n else None,
             "sentence_or_doc_failed": sum(r["sentence_or_doc_failed"] for r in rows) / n if n else None,
             "baseline_no_checks": 0.0 if n else None,
             "baseline_numbers_citations_only": sum(r["baseline_numcite"] for r in rows) / n if n else None,
             "baseline_record_coverage_only": sum(r["baseline_record_only"] for r in rows) / n if n else None,
             "by_kind": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_kind.items())},
             "missed": [r["id"] + " " + r["kind"] + " fired=" + ",".join(r["codes_fired"]) for r in rows if not r["detected"]],
             "clean_units": sum(v["edited_units"] or 0 for v in clean.values()),
             "clean_units_fail_after_review": sum(v["fail"] for v in clean.values()),
             "clean_flags_needing_accept": sum(v["accepted_fail"] + v["accepted_warn"] for v in clean.values()),
             "clean_warn": sum(v["warn"] for v in clean.values()),
             "planted_language_errors": len(lr), "candidate_finder_recall": sum(r["hinted"] for r in lr) / len(lr) if lr else None,
             "gold_fixed_planted_errors": sum(r["gold_fixed"] for r in lr) / len(lr) if lr else None}
        metrics["sets"][s] = m
        all_rows[s] = {"mutations": rows_b, "lint": lr}
    if not a.no_robustness:
        rb = robustness()
        metrics["robustness"] = {k: v.get("ok") for k, v in rb.items()}
        metrics["robustness_detail"] = rb
    metrics["wall_seconds"] = round(time.time() - t0, 2)
    dump(metrics, a.json)
    dump(all_rows, os.path.join(os.path.dirname(a.json), "eval_rows.json"))
    dump(LOG, os.path.join(os.path.dirname(a.json), "commands.json"))
    print(json.dumps({s: {k: v for k, v in m.items() if k not in ("clean",)} for s, m in metrics["sets"].items()}, ensure_ascii=False, indent=1))
    if "robustness" in metrics:
        print(json.dumps(metrics["robustness"], indent=1))
    print("wall", metrics["wall_seconds"])


if __name__ == "__main__":
    main()
