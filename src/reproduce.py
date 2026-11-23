#!/usr/bin/env python3
"""Reproduce the self-evaluation of the academic-polish-ledger Skill.

Run from the bundle root:   python src/reproduce.py

1. tests/run_eval.py --set all: clean gold runs, planted defects (dev + held-out), benign edits, baselines,
   candidate-finder recall, 13 robustness checks -> execution/results/metrics.json, eval_rows.json, commands.json;
2. keeps the held-out result recorded at the code freeze (execution/results/metrics_holdout_at_freeze.json);
3. writes execution/run.log, trace/trace.jsonl, characterization.json, arm_manifest.json.

The cases, gold edits and defects are written by the author; they are not the platform's fixed cases,
and no language model is called here.
"""
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "execution", "results")
TRACE = []


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def step(kind, **kw):
    TRACE.append(dict(step_type=kind, timestamp=now(), step_order=len(TRACE) + 1, **kw))


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    t0 = time.time()
    os.makedirs(os.path.join(ROOT, "trace"), exist_ok=True)
    step("thought", title="Plan", body="Run the planted-defect evaluation of the polishing checks (dev set + held-out set written after a code freeze), "
                                       "benign-edit false-positive probes, baselines and robustness checks; then record metrics, manifest and trace.")
    freeze = []
    with open(os.path.join(ROOT, "tests", "FREEZE_holdout.sha256"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                h, f = line.split(None, 1)
                f = f.strip().lstrip("*")
                freeze.append(f"{f}: {'unchanged since freeze' if sha(os.path.join(ROOT, 'submission', f)) == h else 'CHANGED after freeze (post-freeze fix)'}")
    cmd = [sys.executable, os.path.join(ROOT, "tests", "run_eval.py"), "--set", "all"]
    step("tool_call", tool_name="python", tool_call_id="c2", tool_args={"argv": ["tests/run_eval.py", "--set", "all"]})
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=ROOT, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    step("tool_result", tool_call_id="c2", exit_code=r.returncode, stdout_tail=r.stdout[-600:])
    with open(os.path.join(ROOT, "execution", "run.log"), "w", encoding="utf-8") as log:
        log.write(f"# reproduce.py run at {now()}\n$ python tests/run_eval.py --set all\n{r.stdout}\n{r.stderr}\n[exit {r.returncode}]\n\n")
        log.write("# frozen files vs tests/FREEZE_holdout.sha256\n" + "\n".join(freeze) + "\n\n")
        cmds = load(os.path.join(RES, "commands.json"))
        for k, c in enumerate(cmds):
            step("tool_call", tool_name="python", tool_call_id=f"s{k}", tool_args={"argv": c["argv"]})
            step("tool_result", tool_call_id=f"s{k}", exit_code=c["exit"], stdout_tail=c["stdout_tail"][-300:])
        log.write(f"# {len(cmds)} script invocations (argv, exit, seconds, stdout tail) are in execution/results/commands.json\n")
        for c in cmds[:12]:
            log.write(f"$ python {' '.join(c['argv'])}\n{c['stdout_tail'][-600:]}\n[exit {c['exit']}, {c['seconds']} s]\n\n")
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit(r.returncode)
    m = load(os.path.join(RES, "metrics.json"))
    hf = load(os.path.join(RES, "metrics_holdout_at_freeze.json"))["sets"]["holdout"]
    m["holdout_at_freeze (before post-freeze lexicon fix)"] = {k: v for k, v in hf.items() if k != "clean"}
    with open(os.path.join(RES, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1)
    dev, ho = m["sets"]["dev"], m["sets"]["holdout"]
    rob = m["robustness"]
    step("observation", title="Result", body=json.dumps({"dev_detected": dev["detected_fail"], "holdout_detected_at_freeze": hf["detected_fail"],
                                                         "holdout_detected_after_fix": ho["detected_fail"], "benign_passed_after_fix": f"{ho['benign_passed']}/{ho['benign_edits']}",
                                                         "robustness_ok": f"{sum(rob.values())}/{len(rob)}"}))
    wall = round(time.time() - t0, 2)
    clean_units = dev["clean_units"] + ho["clean_units"]
    clean_fail = dev["clean_units_fail_after_review"] + ho["clean_units_fail_after_review"]
    rows = [
        ("planted defects caught at fail level (dev set, rules tuned on it)", dev["detected_fail"], 1.0, 0.1,
         f"{dev['defects']} bad edits with plausible change records in 4 cases (EN Markdown, ZH thesis, LaTeX, ZH->EN grant); baselines: numbers+citations only {dev['baseline_numbers_citations_only']:.3f}, record coverage only {dev['baseline_record_coverage_only']:.3f}, no checks 0"),
        ("planted defects caught at fail level (held-out, at code freeze)", hf["detected_fail"], 1.0, 0.3,
         f"{hf['defects']} defects in 2 cases written after the freeze; misses: " + "; ".join(hf["missed"])),
        ("planted defects caught at fail level (held-out, after post-freeze lexicon fix)", ho["detected_fail"], 1.0, 0.1,
         "same cases after the fix, no longer a clean held-out measure; remaining: " + "; ".join(ho["missed"])),
        ("planted defects caught incl. warnings (held-out, at freeze)", hf["detected_fail_or_warn"], 1.0, 0.2, "warn = shown to the agent but not blocking"),
        ("benign edits not failed (held-out, at freeze)", hf["benign_passed"] / hf["benign_edits"], 1.0, 0.25, "; ".join(hf["benign_failed"]) or "none failed"),
        ("benign edits not failed (held-out, after fix)", ho["benign_passed"] / ho["benign_edits"], 1.0, 0.0, f"{ho['benign_edits']} benign edits (number format, equivalent modal, promo removed, negation paraphrase)"),
        ("clean gold edits without unresolved fail (all cases)", 1 - clean_fail / clean_units, 1.0, 0.0,
         f"{clean_units} gold edits; {dev['clean_flags_needing_accept'] + ho['clean_flags_needing_accept']} flags needed an explicit accept with reason"),
        ("candidate finder recall on planted language errors (dev)", dev["candidate_finder_recall"], 1.0, 0.2, f"{dev['planted_language_errors']} planted errors"),
        ("candidate finder recall on planted language errors (held-out, after fix)", ho["candidate_finder_recall"], 1.0, 0.3,
         f"{ho['planted_language_errors']} planted errors; at freeze {hf['candidate_finder_recall']:.3f}"),
        ("robustness checks passed", sum(rob.values()) / len(rob), 1.0, 0.0, ", ".join(rob)),
    ]
    char = {"deviations_from_paper": [{"target": t, "metric": "absolute_error", "actual_value": round(a, 4), "reference_value": ref,
                                       "score": round(max(0.0, 1 - abs(a - ref) / tol), 4) if tol else (1.0 if abs(a - ref) < 1e-9 else 0.0),
                                       "explanation": ex, "evidence_artifact": "metrics", "tolerance": tol} for t, a, ref, tol, ex in rows],
            "notes": "Self-evaluation on author-written cases with author gold edits and planted defects; the platform's three fixed cases and any model run are not part of it. "
                     "Scores use the protocol's absolute_error formula max(0, 1 - deviation/tolerance) against the ideal value 1.0."}
    with open(os.path.join(ROOT, "characterization.json"), "w", encoding="utf-8") as fh:
        json.dump(char, fh, ensure_ascii=False, indent=1)
    arts = [("metrics", "execution/results/metrics.json", "metric", "json"),
            ("eval_rows", "execution/results/eval_rows.json", "data", "json"),
            ("metrics_holdout_at_freeze", "execution/results/metrics_holdout_at_freeze.json", "metric", "json"),
            ("eval_rows_holdout_at_freeze", "execution/results/eval_rows_holdout_at_freeze.json", "data", "json"),
            ("commands", "execution/results/commands.json", "log", "json")]
    for c in ("dev_en", "dev_zh", "dev_tex", "dev_grant", "ho_bio", "ho_grant_zh"):
        o = f"execution/results/cases/{c}/output"
        pol = [f for f in sorted(os.listdir(os.path.join(ROOT, o))) if f.startswith("polished.")][0]
        arts += [(f"{c}_result", f"{o}/result.json", "data", "json"), (f"{c}_polished", f"{o}/{pol}", "data", pol.rsplit(".", 1)[1]),
                 (f"{c}_change_log", f"{o}/change_log.md", "data", "markdown"), (f"{c}_diff_preview", f"{o}/diff.html", "figure", "html")]
    manifest = {
        "arm_version": "1.1",
        "paper": {"title": "写作02｜学术语言润色 — academic-polish-ledger Skill", "challenge_id": "product-arena-02-7051d92d"},
        "entrypoint": "src/reproduce.py",
        "environment": {"dependencies": "requirements.txt", "python_version": ">=3.8", "gpu_required": False,
                        "extra_packages": ["PyMuPDF>=1.23 (optional, PDF manuscripts only)"]},
        "execution": {"log_path": "execution/run.log", "exit_code": 0, "ran_at": now(), "wall_time_s": wall, "ran_by": "agent",
                      "artifacts": [{"id": i, "path": p, "type": t, "format": f, "checksum_sha256": sha(os.path.join(ROOT, p))} for i, p, t, f in arts]},
        "expected_outputs": [{"name": r_[0], "type": "metric", "produced_by": ["metrics"], "comparison_method": "numeric_tolerance"} for r_ in rows],
        "handoff": {"status": "partial",
                    "next_suggestion": "Run on the platform's three fixed cases with the DeepSeek harness (base vs Skill); extend lexicons for conditions/causal phrasing found there; add more discipline termbases.",
                    "hypothesis": "Sentence-level minimal edits with span-level change records, checked by deterministic meaning invariants (numbers, citations, references, hedge strength, negation, quantifiers, causality, conditions) and a termbase sweep, catch most claim-changing polish errors that a fluent rewrite hides, while keeping the output directly usable."},
    }
    with open(os.path.join(ROOT, "arm_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "trace", "trace.jsonl"), "w", encoding="utf-8") as fh:
        for t in TRACE:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(json.dumps({"wall_s": wall, "rows": [(t, round(a, 3)) for t, a, *_ in rows]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
