#!/usr/bin/env python3
"""Candidate finder: run rules/style_rules.json over sentences. Heuristic hints for the agent, not verdicts.

CLI:  python ap_lint.py FILE [--genre journal] [--json]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ap_common import RULES_DIR, load_json, protected_spans, read_any, segment  # noqa: E402

_RULES = None


def rules():
    global _RULES
    if _RULES is None:
        _RULES = []
        for r in load_json(os.path.join(RULES_DIR, "style_rules.json"))["rules"]:
            r = dict(r)
            r["rx"] = re.compile(r["pattern"], 0 if r.get("case") else re.I)
            _RULES.append(r)
    return _RULES


def lint(text, lang, genre=None, residual_only=False):
    """List of {rule, category, match, message, hint} for one sentence. Matches inside protected spans
    (math, citations, cross-references, LaTeX commands) are ignored."""
    prot = protected_spans(text)
    hits = []
    for r in rules():
        if residual_only and not r.get("residual"):
            continue
        if r["lang"] != "any" and r["lang"] != lang and not (r["lang"] == "en" and lang == "other"):
            continue
        if r.get("genres") and genre and genre not in r["genres"]:
            continue
        for m in r["rx"].finditer(text):
            if any(a <= m.start() < b for a, b, _, _ in prot):
                continue
            if r["id"] == "EN07" and m.group(1).lower() in ("that", "had", "is"):
                continue
            hits.append({"rule": r["id"], "category": r["category"], "match": m.group(0).strip(), "message": r["message"], "hint": r["hint"]})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--genre")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    text, fmt, _ = read_any(a.file)
    out = []
    for s in segment(text, fmt):
        for h in lint(s["text"], s["lang"], a.genre):
            out.append(dict(sid=s["sid"], **h))
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for h in out:
            print(f'{h["sid"]:<9} {h["rule"]:<5} {h["category"]:<16} "{h["match"]}"  {h["message"]} -> {h["hint"]}')


if __name__ == "__main__":
    main()
